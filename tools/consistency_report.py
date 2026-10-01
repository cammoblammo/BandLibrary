#!/usr/bin/env python3
"""
Report how each ensemble's chairs resolve against the library, and flag
inconsistencies in fallbacks, part names and assignments.

Usage:
  python3 tools/consistency_report.py [--ensemble FILE ...] [--html report.html]
"""

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
from pathlib import Path

from lib.report import build_report
from lib.report_html import render_html, render_text


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report fallback and assignment consistency across ensembles."
    )
    parser.add_argument("--library", type=Path, default=Path("library"))
    parser.add_argument(
        "--ensemble", type=Path, action="append", default=None, metavar="FILE",
        help="Ensemble file (repeatable). Default: every file in config/ensembles/",
    )
    parser.add_argument("--html", type=Path, default=None, metavar="FILE",
                        help="Also write an HTML report with the full grids")
    parser.add_argument("--fragment", action="store_true",
                        help="Write the HTML without the <html>/<head>/<body> wrapper")
    args = parser.parse_args()

    ensembles = args.ensemble or sorted(Path("config/ensembles").glob("*.yaml"))
    if not ensembles:
        print("ERROR: no ensemble files found", file=sys.stderr)
        return 1

    try:
        report = build_report(args.library, ensembles)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print(render_text(report))

    if args.html:
        args.html.parent.mkdir(parents=True, exist_ok=True)
        args.html.write_text(render_html(report, standalone=not args.fragment), encoding="utf-8")
        print(f"HTML report written to {args.html}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
