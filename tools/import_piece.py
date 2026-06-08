#!/usr/bin/env python3

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import sys
from pathlib import Path

from lib.aliases import load_aliases
from lib.importer import import_piece


def main() -> int:
    parser = argparse.ArgumentParser(description="Import a piece into the library")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--manual", type=Path, required=True)
    parser.add_argument("--library", type=Path, default=Path("library"))
    parser.add_argument("--aliases", type=Path, default=Path("config/aliases.yaml"))
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--test",
        action="store_true",
        help='Write output to "test/" instead of the library directory',
    )

    args = parser.parse_args()

    try:
        if args.test:
            args.library = Path("test")
            print("Test mode — output will be written to test/")

        aliases = load_aliases(args.aliases)
        unaliased = import_piece(args.pdf, args.manual, args.library, args.force, aliases)
        if unaliased:
            print("\nUnaliased labels (consider adding to config/aliases.yaml):")
            for label, part_id in unaliased:
                print(f'  {label!r:30s} ->  {part_id}')

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
