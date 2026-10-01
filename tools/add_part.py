#!/usr/bin/env python3

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
from pathlib import Path

from lib.aliases import load_aliases
from lib.parts import add_part


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Append an additional part PDF to an existing library piece."
    )
    parser.add_argument("slug")
    parser.add_argument("label")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--library", type=Path, default=Path("library"))
    parser.add_argument("--aliases", type=Path, default=Path("config/aliases.yaml"))

    args = parser.parse_args()

    try:
        aliases = load_aliases(args.aliases)
        add_part(
            slug=args.slug,
            label=args.label,
            source_pdf=args.pdf,
            library=args.library,
            aliases=aliases,
        )
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
