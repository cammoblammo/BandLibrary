#!/usr/bin/env python3
"""
Draft a manual file from a full-set PDF (the app's Detect Parts button).

  python3 tools/detect_parts.py PIECE.pdf            # print the draft
  python3 tools/detect_parts.py --score              # score against library
  python3 tools/detect_parts.py --score -v SLUG ...  # with differences
"""

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
from pathlib import Path

from lib.aliases import load_aliases
from lib.detect import detect_parts, render
from lib.detect.score import score_draft
from lib.reading_groups import load_reading_groups


def run_score(library: Path, slugs: list[str], aliases: dict[str, str],
              groups, verbose: bool, **detect_options) -> int:
    dirs = [library / s for s in slugs] if slugs else sorted(
        d for d in library.iterdir() if d.is_dir())
    rows = []
    for d in dirs:
        slug = d.name
        pdf, manual = d / f"{slug}.pdf", d / f"{slug}.manual.txt"
        if not pdf.exists() or not manual.exists():
            print(f"{slug}: no PDF or manual file, skipped", file=sys.stderr)
            continue
        rows.append(score_draft(slug, detect_parts(pdf, aliases, groups, **detect_options),
                               manual, aliases))

    print(f"{'piece':36} {'text':>9} {'parts':>5} {'ranges':>6} {'names':>5} {'extra':>5}")
    for s in rows:
        text = f"{s.text_pages}/{s.page_count}"
        print(f"{s.slug:36} {text:>9} {s.expected:5} {s.ranges_right:6} "
              f"{s.names_right:5} {s.extra:5}")
        if verbose:
            for line in s.differences:
                print(f"    {line}")
    with_text = [s for s in rows if s.text_pages]
    for heading, group in (("all pieces", rows), ("pieces with text", with_text)):
        expected = sum(s.expected for s in group)
        if expected:
            print(f"{heading}: ranges {sum(s.ranges_right for s in group)}/{expected}, "
                  f"names {sum(s.names_right for s in group)}/{expected}, "
                  f"extra {sum(s.extra for s in group)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("targets", nargs="*",
                        help="PDF to read, or library slugs with --score")
    parser.add_argument("--aliases", type=Path, default=Path("config/aliases.yaml"))
    parser.add_argument("--groups", type=Path, default=Path("config/reading_groups.yaml"))
    parser.add_argument("--library", type=Path, default=Path("library"))
    parser.add_argument("--score", action="store_true",
                        help="Compare detection with the library's manual files")
    parser.add_argument("--no-ocr", action="store_true",
                        help="Read only the text layer; leave scans unread")
    parser.add_argument("--ocr-cache", type=Path, metavar="DIR",
                        help="Keep OCR results here to speed up repeated runs")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="With --score, list every difference")
    args = parser.parse_args()

    aliases = load_aliases(args.aliases)
    groups = load_reading_groups(args.groups)
    options = {"use_ocr": not args.no_ocr, "ocr_cache": args.ocr_cache}
    if args.score:
        return run_score(args.library, args.targets, aliases, groups, args.verbose,
                         **options)
    if len(args.targets) != 1:
        parser.error("give one PDF, or use --score")
    print(render(detect_parts(Path(args.targets[0]), aliases, groups, **options)), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
