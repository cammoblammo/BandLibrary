#!/usr/bin/env python3

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import sys
from pathlib import Path

from lib.builder import create_zip_archive, generate_booklets
from lib.library import load_ensemble, load_piece, load_piece_list
from lib.matcher import build_match_plan, build_report
from lib.utils import slugify_edition


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build booklet PDFs for an ensemble from imported library pieces."
    )
    parser.add_argument("--ensemble", type=Path, required=True)
    parser.add_argument("--library", type=Path, default=Path("library"))
    parser.add_argument("--output", type=Path, default=Path("output"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--edition", type=str, default=None, metavar="LABEL")
    parser.add_argument("--piece-list", type=Path, default=None, metavar="FILE")
    parser.add_argument(
        "--test",
        action="store_true",
        help='Write output to "test-output/" instead of the output directory',
    )
    parser.add_argument("pieces", nargs="*", metavar="PIECE")

    args = parser.parse_args()

    try:
        if args.test:
            args.output = Path("test-output")
            print("Test mode — output will be written to test-output/")

        slugs: list[str] = []
        if args.piece_list is not None:
            slugs.extend(load_piece_list(args.piece_list))
        slugs.extend(args.pieces)

        if not slugs:
            print(
                "ERROR: no pieces specified. "
                "Provide piece slugs on the command line or via --piece-list.",
                file=sys.stderr,
            )
            return 1

        ensemble_name, ensemble_parts = load_ensemble(args.ensemble)
        pieces = [load_piece(args.library, slug) for slug in slugs]
        pieces_by_slug = {piece.slug: piece for piece in pieces}

        grouped_matches = build_match_plan(ensemble_parts, pieces)
        report_lines, warning_lines = build_report(
            ensemble_name, ensemble_parts, pieces, grouped_matches
        )

        print("\n".join(report_lines))

        if warning_lines:
            for line in warning_lines:
                print(line, file=sys.stderr)

        if args.dry_run:
            print("Dry run — no files generated.")
            return 0

        generated_files = generate_booklets(
            output_dir=args.output,
            ensemble_parts=ensemble_parts,
            pieces_by_slug=pieces_by_slug,
            grouped_matches=grouped_matches,
        )

        archive_stem = args.ensemble.stem
        if args.edition:
            archive_stem = f"{archive_stem}-{slugify_edition(args.edition)}"

        zip_path = create_zip_archive(args.output, generated_files, archive_stem)

        print(f"\nGenerated {len(generated_files)} booklet PDF(s) in {args.output}")
        print(f"Created archive: {zip_path}")

        print("\nSummary:")
        for ep in ensemble_parts:
            matches = grouped_matches[ep.id]
            covered = sum(1 for m in matches if m.matched_id is not None)
            print(f"  {ep.label}: {covered}/{len(matches)} pieces covered")

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
