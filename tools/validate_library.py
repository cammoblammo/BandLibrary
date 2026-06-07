#!/usr/bin/env python3
"""
validate_library.py — Validate the BandLibrary piece library.

Usage:
    python3 tools/validate_library.py [options] [slug ...]

Validates all pieces by default. Pass one or more slugs to check specific pieces.
Use --ensemble to additionally validate an ensemble definition and check coverage.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required. Install it with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

try:
    from pypdf import PdfReader
except ImportError:
    print("ERROR: pypdf is required. Install it with: pip install pypdf", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Result collection
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warning(self, msg: str) -> None:
        self.warnings.append(msg)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


# ---------------------------------------------------------------------------
# Piece validation
# ---------------------------------------------------------------------------

def validate_piece(slug: str, library: Path, result: ValidationResult) -> dict | None:
    """
    Validate a single piece directory. Returns the parsed YAML data on success,
    or None if validation failed badly enough to prevent further checks.
    """
    piece_dir = library / slug

    if not piece_dir.is_dir():
        result.error(f"{slug}: not a directory")
        return None

    yaml_path = piece_dir / f"{slug}.yaml"
    pdf_path = piece_dir / f"{slug}.pdf"

    # Required files
    if not yaml_path.exists():
        result.error(f"{slug}: missing YAML file ({yaml_path.name})")
    if not pdf_path.exists():
        result.error(f"{slug}: missing PDF file ({pdf_path.name})")

    if not yaml_path.exists() or not pdf_path.exists():
        return None

    # Parse YAML
    try:
        with yaml_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        result.error(f"{slug}: YAML parse error: {e}")
        return None

    if not isinstance(data, dict):
        result.error(f"{slug}: YAML must be a mapping at top level")
        return None

    # piece section
    piece_meta = data.get("piece")
    if not isinstance(piece_meta, dict):
        result.error(f"{slug}: missing or invalid 'piece' section")
        return None

    # source_pdf matches expected filename
    source_pdf = piece_meta.get("source_pdf")
    if not isinstance(source_pdf, str) or not source_pdf.strip():
        result.error(f"{slug}: missing or invalid piece.source_pdf")
    elif source_pdf != pdf_path.name:
        result.error(
            f"{slug}: piece.source_pdf is {source_pdf!r} "
            f"but expected {pdf_path.name!r}"
        )

    # title
    title = piece_meta.get("title")
    if not isinstance(title, str) or not title.strip():
        result.error(f"{slug}: missing or invalid piece.title")

    # id matches slug
    piece_id = piece_meta.get("id")
    if piece_id != slug:
        result.error(f"{slug}: piece.id is {piece_id!r} but expected {slug!r}")

    # parts section
    parts = data.get("parts")
    if not isinstance(parts, list) or not parts:
        result.error(f"{slug}: missing or empty 'parts' list")
        return data

    # Read PDF page count once
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

        # Duplicate ID
        if part_id in seen_ids:
            result.error(f"{slug}: duplicate part id {part_id!r}")
        else:
            seen_ids.add(part_id)

        # Page range
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

    # Assignments
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


# ---------------------------------------------------------------------------
# Ensemble validation
# ---------------------------------------------------------------------------

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

    # Check fallback IDs exist within the ensemble
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

    col_width = max(len(p.get("label", p.get("id", ""))) for p in valid_parts) + 2

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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate BandLibrary piece library."
    )
    parser.add_argument(
        "slugs",
        nargs="*",
        metavar="SLUG",
        help="Piece slugs to validate. Validates all pieces if omitted.",
    )
    parser.add_argument(
        "--library",
        type=Path,
        default=Path("library"),
        help='Library root directory (default: "library")',
    )
    parser.add_argument(
        "--ensemble",
        type=Path,
        default=None,
        metavar="FILE",
        help="Ensemble YAML file to validate and check coverage against.",
    )

    args = parser.parse_args()

    if not args.library.exists():
        print(f"ERROR: library directory not found: {args.library}", file=sys.stderr)
        return 1

    # Determine slugs to validate
    if args.slugs:
        slugs = args.slugs
    else:
        slugs = sorted(
            d.name for d in args.library.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        )

    if not slugs:
        print("Library is empty — nothing to validate.")
        return 0

    result = ValidationResult()
    pieces_data: dict[str, dict] = {}

    print(f"Validating {len(slugs)} piece(s)...\n")

    for slug in slugs:
        data = validate_piece(slug, args.library, result)
        if data is not None:
            pieces_data[slug] = data

    # Print errors and warnings
    if result.errors:
        print(f"Errors ({len(result.errors)}):")
        for e in result.errors:
            print(f"  ERROR: {e}")
        print()

    if result.warnings:
        print(f"Warnings ({len(result.warnings)}):")
        for w in result.warnings:
            print(f"  WARNING: {w}")
        print()

    if result.ok and not result.warnings:
        print(f"All {len(slugs)} piece(s) valid.")
    elif result.ok:
        print(f"All {len(slugs)} piece(s) valid (with warnings).")
    else:
        print(f"{len(result.errors)} error(s) found in {len(slugs)} piece(s).")

    # Ensemble validation
    if args.ensemble:
        print()
        ensemble_result = ValidationResult()
        validate_ensemble(args.ensemble, pieces_data, ensemble_result)

        if ensemble_result.errors:
            print(f"\nEnsemble errors ({len(ensemble_result.errors)}):")
            for e in ensemble_result.errors:
                print(f"  ERROR: {e}")

        if ensemble_result.warnings:
            print(f"\nEnsemble warnings ({len(ensemble_result.warnings)}):")
            for w in ensemble_result.warnings:
                print(f"  WARNING: {w}")

        if not ensemble_result.errors and not ensemble_result.warnings:
            print("Ensemble definition valid.")

        if not ensemble_result.ok:
            return 1

    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
