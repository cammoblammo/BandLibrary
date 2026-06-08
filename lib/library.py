"""
Ensemble and piece loading for BandLibrary.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from pypdf import PdfReader

from .models import EnsemblePart, Piece, PiecePart


class LibraryError(Exception):
    """Raised when a library or ensemble file cannot be loaded."""


def load_yaml_file(path: Path) -> dict:
    if not path.exists():
        raise LibraryError(f"File not found: {path}")
    if not path.is_file():
        raise LibraryError(f"Path is not a file: {path}")
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise LibraryError(f"Failed to parse YAML file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise LibraryError(f"Expected a YAML mapping at top level in {path}")
    return data


def load_ensemble(path: Path) -> tuple[str, str, list[EnsemblePart]]:
    """
    Load and validate an ensemble YAML file.
    Returns (ensemble_name, band_name, parts).
    band_name may be an empty string if not specified.
    """
    data = load_yaml_file(path)

    ensemble_meta = data.get("ensemble")
    parts_raw = data.get("parts")

    if not isinstance(ensemble_meta, dict):
        raise LibraryError(f"Missing or invalid 'ensemble' section in {path}")
    if not isinstance(parts_raw, list) or not parts_raw:
        raise LibraryError(f"Missing or empty 'parts' list in {path}")

    ensemble_name = ensemble_meta.get("name")
    if not isinstance(ensemble_name, str) or not ensemble_name.strip():
        raise LibraryError(f"Missing or invalid ensemble.name in {path}")

    band_name = ensemble_meta.get("band", "")
    if not isinstance(band_name, str):
        band_name = ""
    band_name = band_name.strip()

    parts: list[EnsemblePart] = []
    seen_ids: set[str] = set()

    for i, item in enumerate(parts_raw):
        if not isinstance(item, dict):
            raise LibraryError(f"parts[{i}] in {path} must be a mapping")

        part_id = item.get("id")
        label = item.get("label")
        fallback = item.get("fallback", [])

        if not isinstance(part_id, str) or not part_id.strip():
            raise LibraryError(f"parts[{i}].id in {path} must be a non-empty string")
        if not isinstance(label, str) or not label.strip():
            raise LibraryError(f"parts[{i}].label in {path} must be a non-empty string")
        if not isinstance(fallback, list) or not all(isinstance(x, str) for x in fallback):
            raise LibraryError(f"parts[{i}].fallback in {path} must be a list of strings")
        if part_id in seen_ids:
            raise LibraryError(f"Duplicate ensemble part id {part_id!r} in {path}")
        if part_id in fallback:
            raise LibraryError(
                f"Ensemble part {part_id!r} in {path} includes itself in fallback"
            )

        seen_ids.add(part_id)
        parts.append(EnsemblePart(id=part_id, label=label, fallback=fallback))

    return ensemble_name, band_name, parts


def load_piece(library_dir: Path, slug: str) -> Piece:
    """Load and validate a piece from the library."""
    piece_dir = library_dir / slug
    piece_yaml = piece_dir / f"{slug}.yaml"

    data = load_yaml_file(piece_yaml)

    piece_meta = data.get("piece")
    parts_raw = data.get("parts")
    assignments_raw = data.get("assignments", {})

    if not isinstance(piece_meta, dict):
        raise LibraryError(f"Missing or invalid 'piece' section in {piece_yaml}")
    if not isinstance(parts_raw, list):
        raise LibraryError(f"Missing or invalid 'parts' list in {piece_yaml}")
    if not isinstance(assignments_raw, dict):
        raise LibraryError(f"Invalid 'assignments' in {piece_yaml}: must be a mapping")

    title = piece_meta.get("title")
    source_pdf = piece_meta.get("source_pdf")

    if not isinstance(title, str) or not title.strip():
        raise LibraryError(f"Missing or invalid piece.title in {piece_yaml}")
    if not isinstance(source_pdf, str) or not source_pdf.strip():
        raise LibraryError(f"Missing or invalid piece.source_pdf in {piece_yaml}")

    pdf_path = piece_dir / source_pdf
    if not pdf_path.exists():
        raise LibraryError(f"Source PDF not found for piece {slug}: {pdf_path}")

    reader = PdfReader(str(pdf_path))
    total_pages = len(reader.pages)

    parts_by_id: dict[str, PiecePart] = {}

    for i, item in enumerate(parts_raw):
        if not isinstance(item, dict):
            raise LibraryError(f"parts[{i}] in {piece_yaml} must be a mapping")

        part_id = item.get("id")
        label = item.get("label")
        pages = item.get("pages")

        if not isinstance(part_id, str) or not part_id.strip():
            raise LibraryError(f"parts[{i}].id in {piece_yaml} must be a non-empty string")
        if not isinstance(label, str) or not label.strip():
            raise LibraryError(f"parts[{i}].label in {piece_yaml} must be a non-empty string")
        if (
            not isinstance(pages, list)
            or len(pages) != 2
            or not all(isinstance(x, int) for x in pages)
        ):
            raise LibraryError(
                f"parts[{i}].pages in {piece_yaml} must be a two-element integer list"
            )

        start_page, end_page = pages

        if start_page <= 0 or end_page <= 0 or start_page > end_page:
            raise LibraryError(
                f"Invalid page range for part {part_id!r} in {piece_yaml}: {pages}"
            )
        if end_page > total_pages:
            raise LibraryError(
                f"Part {part_id!r} in piece {slug} references page {end_page}, "
                f"but PDF only has {total_pages} pages"
            )
        if part_id in parts_by_id:
            raise LibraryError(f"Duplicate piece part id {part_id!r} in {piece_yaml}")

        parts_by_id[part_id] = PiecePart(
            id=part_id,
            label=label,
            start_page=start_page,
            end_page=end_page,
        )

    assignments: dict[str, str] = {}
    for target_id, source_id in assignments_raw.items():
        if not isinstance(target_id, str) or not target_id.strip():
            raise LibraryError(
                f"Invalid assignment key in {piece_yaml}"
            )
        if not isinstance(source_id, str) or not source_id.strip():
            raise LibraryError(
                f"Invalid assignment value for {target_id!r} in {piece_yaml}"
            )
        if source_id not in parts_by_id:
            raise LibraryError(
                f"Assignment for {target_id!r} in {piece_yaml} "
                f"refers to unknown part id {source_id!r}"
            )
        assignments[target_id] = source_id

    return Piece(
        slug=slug,
        title=title,
        pdf_path=pdf_path,
        parts_by_id=parts_by_id,
        assignments=assignments,
    )


def list_pieces(library_dir: Path) -> list[str]:
    """Return sorted list of piece slugs in the library."""
    if not library_dir.exists():
        return []
    return sorted(
        d.name for d in library_dir.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )


def load_piece_list(path: Path) -> list[str]:
    """
    Load piece slugs from a plain text file.
    Blank lines and lines beginning with # are ignored.
    """
    if not path.exists():
        raise LibraryError(f"Piece list file not found: {path}")
    if not path.is_file():
        raise LibraryError(f"Piece list path is not a file: {path}")

    slugs: list[str] = []

    with path.open("r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if re.search(r"[\s/\\]", line):
                raise LibraryError(
                    f"Piece list {path}, line {lineno}: "
                    f"invalid slug {line!r}"
                )
            slugs.append(line)

    if not slugs:
        raise LibraryError(f"Piece list file contains no pieces: {path}")

    return slugs
