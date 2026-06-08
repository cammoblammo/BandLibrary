#!/usr/bin/env python3

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import sys
from pathlib import Path

from lib.models import ValidationResult
from lib.validator import validate_ensemble, validate_piece


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate BandLibrary piece library.")
    parser.add_argument("slugs", nargs="*", metavar="SLUG")
    parser.add_argument("--library", type=Path, default=Path("library"))
    parser.add_argument("--ensemble", type=Path, default=None, metavar="FILE")

    args = parser.parse_args()

    if not args.library.exists():
        print(f"ERROR: library directory not found: {args.library}", file=sys.stderr)
        return 1

    slugs = args.slugs or sorted(
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
