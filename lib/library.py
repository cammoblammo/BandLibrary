"""
Ensemble and piece loading for BandLibrary.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from pypdf import PdfReader

from .models import TAKES_ALL, TAKES_ONE, EnsemblePart, Piece, PiecePart
from .reading_groups import default_groups_path, expand_entry, load_reading_groups


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


def _string_list(value, what: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(x, str) and x.strip() for x in value):
        raise LibraryError(f"{what} must be a list of non-empty strings")
    return [x.strip() for x in value]


def load_ensemble(
    path: Path,
    groups_path: Path | None = None,
) -> tuple[str, str, list[EnsemblePart]]:
    """
    Load and validate an ensemble YAML file.
    Returns (ensemble_name, band_name, parts).
    band_name may be an empty string if not specified.

    Each part lists `prefer` and `compromise` substitutes (schema 2), or a
    single `fallback` list (schema 1, treated as `prefer`). Entries such as
    "flex 3" are expanded using the reading groups in config/reading_groups.yaml.
    """
    data = load_yaml_file(path)
    try:
        groups = load_reading_groups(groups_path or default_groups_path(path))
    except ValueError as exc:
        raise LibraryError(str(exc)) from exc

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

        if not isinstance(part_id, str) or not part_id.strip():
            raise LibraryError(f"parts[{i}].id in {path} must be a non-empty string")
        if not isinstance(label, str) or not label.strip():
            raise LibraryError(f"parts[{i}].label in {path} must be a non-empty string")
        if part_id in seen_ids:
            raise LibraryError(f"Duplicate ensemble part id {part_id!r} in {path}")

        where = f"Ensemble part {part_id!r} in {path}"
        if "fallback" in item and ("prefer" in item or "compromise" in item):
            raise LibraryError(f"{where}: use either 'fallback' or 'prefer'/'compromise', not both")
        prefer_spec = _string_list(item.get("prefer", item.get("fallback")), f"{where}: prefer")
        compromise_spec = _string_list(item.get("compromise"), f"{where}: compromise")
        reads = _string_list(item.get("reads"), f"{where}: reads")
        for name in reads:
            if name not in groups:
                raise LibraryError(f"{where}: unknown reading group {name!r}")

        takes = item.get("takes", TAKES_ONE)
        if takes not in (TAKES_ONE, TAKES_ALL):
            raise LibraryError(f"{where}: 'takes' must be '{TAKES_ONE}' or '{TAKES_ALL}'")
        if takes == TAKES_ALL:
            if not reads:
                raise LibraryError(f"{where}: 'takes: all' needs 'reads' (which parts to take)")
            if prefer_spec or compromise_spec:
                raise LibraryError(
                    f"{where}: a 'takes: all' chair gets every part it reads, so it "
                    f"doesn't use 'prefer' or 'compromise'")

        try:
            prefer = _expand(prefer_spec, reads, groups, where)
            compromise = _expand(compromise_spec, reads, groups, where)
        except ValueError as exc:
            raise LibraryError(str(exc)) from exc
        compromise = [x for x in compromise if x not in prefer]

        if part_id in prefer or part_id in compromise:
            raise LibraryError(f"{where} includes itself in its substitutes")

        seen_ids.add(part_id)
        parts.append(EnsemblePart(
            id=part_id,
            label=label,
            prefer=prefer,
            compromise=compromise,
            reads=reads,
            prefer_spec=prefer_spec,
            compromise_spec=compromise_spec,
            takes=takes,
            read_groups=tuple(groups[name] for name in reads),
        ))

    return ensemble_name, band_name, parts


def _expand(specs: list[str], reads: list[str], groups, where: str) -> list[str]:
    ids: list[str] = []
    for spec in specs:
        for part_id in expand_entry(spec, reads, groups, where):
            if part_id not in ids:
                ids.append(part_id)
    return ids


def load_piece(library_dir: Path, slug: str) -> Piece:
    """Load and validate a piece from the library."""
    piece_dir = library_dir / slug
    piece_yaml = piece_dir / f"{slug}.yaml"

    data = load_yaml_file(piece_yaml)

    piece_meta = data.get("piece")
    parts_raw = data.get("parts")
    assignments_raw = data.get("assignments")
    if assignments_raw is None:
        assignments_raw = {}

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

    # A chair gets one part (a string) or, for a "takes: all" chair such as
    # Percussion, a list of parts
    assignments: dict[str, str | tuple[str, ...]] = {}
    for target_id, value in assignments_raw.items():
        if not isinstance(target_id, str) or not target_id.strip():
            raise LibraryError(
                f"Invalid assignment key in {piece_yaml}"
            )
        sources = [value] if isinstance(value, str) else value
        if (not isinstance(sources, list) or not sources
                or not all(isinstance(x, str) and x.strip() for x in sources)):
            raise LibraryError(
                f"Invalid assignment value for {target_id!r} in {piece_yaml}: "
                f"give a part id, or a list of part ids"
            )
        for source_id in sources:
            if source_id not in parts_by_id:
                raise LibraryError(
                    f"Assignment for {target_id!r} in {piece_yaml} "
                    f"refers to unknown part id {source_id!r}"
                )
        assignments[target_id] = value if isinstance(value, str) else tuple(value)

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
