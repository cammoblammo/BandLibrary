"""
Library and ensemble validation for BandLibrary.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pypdf import PdfReader

from .models import ValidationResult


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


def validate_ensemble(
    ensemble_path: Path,
    pieces_data: dict[str, dict],
    result: ValidationResult,
) -> None:
    """Validate ensemble YAML and report coverage against loaded pieces."""
    if not ensemble_path.exists():
        result.error(f"Ensemble file not found: {ensemble_path}")
        return

    try:
        with ensemble_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        result.error(f"Ensemble YAML parse error: {e}")
        return

    if not isinstance(data, dict):
        result.error("Ensemble YAML must be a mapping at top level")
        return

    ensemble_meta = data.get("ensemble")
    parts = data.get("parts")

    if not isinstance(ensemble_meta, dict):
        result.error("Ensemble YAML: missing or invalid 'ensemble' section")
        return
    if not isinstance(parts, list) or not parts:
        result.error("Ensemble YAML: missing or empty 'parts' list")
        return

    ensemble_name = ensemble_meta.get("name", "(unnamed)")
    ensemble_part_ids: set[str] = set()
    valid_parts: list[dict] = []
    seen_ids: set[str] = set()

    for i, part in enumerate(parts):
        if not isinstance(part, dict):
            result.error(f"Ensemble parts[{i}] must be a mapping")
            continue

        part_id = part.get("id")
        label = part.get("label")
        fallback = part.get("fallback", [])

        if not isinstance(part_id, str) or not part_id.strip():
            result.error(f"Ensemble parts[{i}].id must be a non-empty string")
            continue
        if not isinstance(label, str) or not label.strip():
            result.error(f"Ensemble part {part_id!r}: label must be a non-empty string")
        if not isinstance(fallback, list) or not all(isinstance(x, str) for x in fallback):
            result.error(f"Ensemble part {part_id!r}: fallback must be a list of strings")
            fallback = []
        if part_id in seen_ids:
            result.error(f"Ensemble: duplicate part id {part_id!r}")
        else:
            seen_ids.add(part_id)
            ensemble_part_ids.add(part_id)
            valid_parts.append(part)

        if part_id in fallback:
            result.error(f"Ensemble part {part_id!r}: includes itself in fallback")

    for part in valid_parts:
        for fb_id in part.get("fallback", []):
            if fb_id not in ensemble_part_ids:
                result.warning(
                    f"Ensemble part {part['id']!r}: fallback {fb_id!r} "
                    f"is not a known ensemble part ID"
                )

    if not pieces_data:
        return

    # Coverage report
    print(f"\nCoverage report: {ensemble_name} vs {len(pieces_data)} piece(s)\n")

    col_width = max(
        len(p.get("label", p.get("id", ""))) for p in valid_parts
    ) + 2

    for part in valid_parts:
        part_id = part["id"]
        label = part.get("label", part_id)
        fallback_ids = set(part.get("fallback", []))

        matched = 0
        missing = []

        for slug, piece_data in pieces_data.items():
            piece_parts = {
                p["id"] for p in piece_data.get("parts", [])
                if isinstance(p, dict) and "id" in p
            }
            assignments = piece_data.get("assignments", {})
            if not isinstance(assignments, dict):
                assignments = {}

            if (
                part_id in assignments
                or part_id in piece_parts
                or fallback_ids & piece_parts
            ):
                matched += 1
            else:
                missing.append(slug)

        total = len(pieces_data)
        status = f"{matched}/{total}"
        label_col = f"{label}:".ljust(col_width)

        if matched == total:
            print(f"  {label_col} {status}")
        elif matched == 0:
            print(f"  {label_col} {status}  [no matches]")
            for slug in missing:
                print(f"               missing: {slug}")
        else:
            print(f"  {label_col} {status}  [missing: {', '.join(missing)}]")
