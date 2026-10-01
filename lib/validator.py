"""
Library and ensemble validation for BandLibrary.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pypdf import PdfReader

from .library import LibraryError, load_ensemble
from .matcher import match_part
from .models import EnsemblePart, Piece, PiecePart, ValidationResult
from .reading_groups import (
    ReadingGroup, can_read, default_groups_path, is_flex, load_reading_groups,
)


def validate_piece(
    slug: str,
    library: Path,
    result: ValidationResult,
) -> dict | None:
    """
    Validate a single piece directory.
    Returns parsed YAML data on success, or None if validation failed
    badly enough to prevent further checks.
    """
    piece_dir = library / slug

    if not piece_dir.is_dir():
        result.error(f"{slug}: not a directory")
        return None

    yaml_path = piece_dir / f"{slug}.yaml"
    pdf_path = piece_dir / f"{slug}.pdf"

    if not yaml_path.exists():
        result.error(f"{slug}: missing YAML file ({yaml_path.name})")
    if not pdf_path.exists():
        result.error(f"{slug}: missing PDF file ({pdf_path.name})")

    if not yaml_path.exists() or not pdf_path.exists():
        return None

    try:
        with yaml_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        result.error(f"{slug}: YAML parse error: {e}")
        return None

    if not isinstance(data, dict):
        result.error(f"{slug}: YAML must be a mapping at top level")
        return None

    piece_meta = data.get("piece")
    if not isinstance(piece_meta, dict):
        result.error(f"{slug}: missing or invalid 'piece' section")
        return None

    source_pdf = piece_meta.get("source_pdf")
    if not isinstance(source_pdf, str) or not source_pdf.strip():
        result.error(f"{slug}: missing or invalid piece.source_pdf")
    elif source_pdf != pdf_path.name:
        result.error(
            f"{slug}: piece.source_pdf is {source_pdf!r} "
            f"but expected {pdf_path.name!r}"
        )

    title = piece_meta.get("title")
    if not isinstance(title, str) or not title.strip():
        result.error(f"{slug}: missing or invalid piece.title")

    piece_id = piece_meta.get("id")
    if piece_id != slug:
        result.error(f"{slug}: piece.id is {piece_id!r} but expected {slug!r}")

    parts = data.get("parts")
    if not isinstance(parts, list) or not parts:
        result.error(f"{slug}: missing or empty 'parts' list")
        return data

    try:
        reader = PdfReader(str(pdf_path))
        total_pages = len(reader.pages)
    except Exception as e:
        result.error(f"{slug}: could not read PDF: {e}")
        return data

    seen_ids: set[str] = set()

    for i, part in enumerate(parts):
        if not isinstance(part, dict):
            result.error(f"{slug}: parts[{i}] must be a mapping")
            continue

        part_id = part.get("id")
        label = part.get("label")
        pages = part.get("pages")

        if not isinstance(part_id, str) or not part_id.strip():
            result.error(f"{slug}: parts[{i}].id must be a non-empty string")
            continue

        if not isinstance(label, str) or not label.strip():
            result.error(f"{slug}: part {part_id!r}: label must be a non-empty string")

        if part_id in seen_ids:
            result.error(f"{slug}: duplicate part id {part_id!r}")
        else:
            seen_ids.add(part_id)

        if (
            not isinstance(pages, list)
            or len(pages) != 2
            or not all(isinstance(x, int) for x in pages)
        ):
            result.error(f"{slug}: part {part_id!r}: pages must be a two-element integer list")
            continue

        start, end = pages

        if start <= 0 or end <= 0:
            result.error(f"{slug}: part {part_id!r}: page numbers must be positive")
        elif start > end:
            result.error(f"{slug}: part {part_id!r}: start page {start} > end page {end}")
        elif end > total_pages:
            result.error(
                f"{slug}: part {part_id!r}: page range {start}-{end} exceeds "
                f"PDF page count ({total_pages})"
            )

    assignments = data.get("assignments")
    if assignments is not None:
        if not isinstance(assignments, dict):
            result.error(f"{slug}: 'assignments' must be a mapping")
        else:
            for target_id, source_id in assignments.items():
                if not isinstance(source_id, str) or not source_id.strip():
                    result.error(
                        f"{slug}: assignment for {target_id!r} must be a non-empty string"
                    )
                elif source_id not in seen_ids:
                    result.error(
                        f"{slug}: assignment for {target_id!r} references "
                        f"unknown part id {source_id!r}"
                    )

    return data


def check_readability(
    ensemble_parts: list[EnsemblePart],
    groups: dict[str, ReadingGroup],
) -> list[str]:
    """
    Return problems where a chair lists a part outside the groups it reads.
    Chairs with no `reads` are not checked.
    """
    problems: list[str] = []
    for ep in ensemble_parts:
        if not ep.reads:
            continue
        if not can_read(ep.id, ep.reads, groups):
            problems.append(
                f"{ep.label}: its own part {ep.id!r} is not in the groups it reads "
                f"({', '.join(ep.reads)})"
            )
        for kind, specs in (("prefer", ep.prefer_spec), ("compromise", ep.compromise_spec)):
            for spec in specs:
                if is_flex(spec):
                    continue
                if not can_read(spec, ep.reads, groups):
                    problems.append(
                        f"{ep.label}: {kind} entry {spec!r} is not in the groups it "
                        f"reads ({', '.join(ep.reads)})"
                    )
    return problems


def _piece_from_data(slug: str, data: dict) -> Piece:
    """Build a Piece from already-validated YAML data (no PDF access needed)."""
    parts_by_id = {}
    for p in data.get("parts") or []:
        if isinstance(p, dict) and isinstance(p.get("id"), str):
            pages = p.get("pages") or [0, 0]
            parts_by_id[p["id"]] = PiecePart(
                id=p["id"], label=str(p.get("label", p["id"])),
                start_page=pages[0], end_page=pages[-1],
            )
    assignments = data.get("assignments")
    if not isinstance(assignments, dict):
        assignments = {}
    return Piece(
        slug=slug,
        title=str((data.get("piece") or {}).get("title", slug)),
        pdf_path=Path(),
        parts_by_id=parts_by_id,
        assignments={k: v for k, v in assignments.items() if isinstance(v, str)},
    )


def validate_ensemble(
    ensemble_path: Path,
    pieces_data: dict[str, dict],
    result: ValidationResult,
) -> None:
    """Validate ensemble YAML and report coverage against loaded pieces."""
    try:
        ensemble_name, _, ensemble_parts = load_ensemble(ensemble_path)
        groups = load_reading_groups(default_groups_path(ensemble_path))
    except (LibraryError, ValueError) as e:
        result.error(str(e))
        return

    for problem in check_readability(ensemble_parts, groups):
        result.error(f"Ensemble part {problem}")

    if not pieces_data:
        return

    pieces = [_piece_from_data(slug, data) for slug, data in pieces_data.items()]

    # Coverage report
    print(f"\nCoverage report: {ensemble_name} vs {len(pieces)} piece(s)\n")

    col_width = max(len(ep.label) for ep in ensemble_parts) + 2
    total = len(pieces)

    for ep in ensemble_parts:
        results = [match_part(piece, ep) for piece in pieces]
        matched = sum(1 for r in results if r.matched_id is not None)
        compromises = sum(1 for r in results if r.match_reason == "compromise")
        missing = [r.piece_slug for r in results if r.matched_id is None]

        status = f"{matched}/{total}"
        if compromises:
            status += f" ({compromises} compromise)"
        label_col = f"{ep.label}:".ljust(col_width)

        if matched == total:
            print(f"  {label_col} {status}")
        elif matched == 0:
            print(f"  {label_col} {status}  [no matches]")
        else:
            print(f"  {label_col} {status}  [missing: {', '.join(missing)}]")
