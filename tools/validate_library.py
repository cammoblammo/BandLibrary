#!/usr/bin/env python3

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import sys
from pathlib import Path

from lib.validator import check_library


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate BandLibrary piece library.")
    parser.add_argument("slugs", nargs="*", metavar="SLUG")
    parser.add_argument("--library", type=Path, default=Path("library"))
    parser.add_argument(
        "--ensemble", type=Path, action="append", default=None, metavar="FILE",
        help="Ensemble to validate and check coverage against (repeatable)",
    )

    args = parser.parse_args()

    ok, text = check_library(args.library, args.ensemble, args.slugs)
    print(text)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
