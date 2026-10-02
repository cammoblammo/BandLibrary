"""
Manual mapping file parsing for BandLibrary.
"""

from __future__ import annotations

import re
from pathlib import Path

from .aliases import normalise_part_id
from .utils import canonicalise_alias_key


# "Part 3 in Eb", "Part 4 in C BC": the flexible-arrangement naming
# convention (see docs/manual-editor.md, "Naming parts")
FLEX_ID_RE = re.compile(r"part_\d+[a-z]?_in_[a-g]b?(?:_tc|_bc)?")


def parse_page_spec(text: str, line_number: int) -> tuple[int, int]:
    text = text.strip()

    if re.fullmatch(r"\d+", text):
        page = int(text)
        if page <= 0:
            raise ValueError(f"Line {line_number}: page must be positive")
        return page, page

    match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", text)
    if match:
        start, end = int(match.group(1)), int(match.group(2))
        if start <= 0 or end <= 0:
            raise ValueError(f"Line {line_number}: page must be positive")
        if start > end:
            raise ValueError(f"Line {line_number}: invalid range {text}")
        return start, end

    raise ValueError(
        f"Line {line_number}: invalid page spec '{text}' "
        "(expected '12' or '13-14')"
    )


def parse_manual_file(
    path: Path,
    aliases: dict[str, str],
) -> tuple[str | None, list[dict], list[tuple[str, str]]]:
    """
    Parse a .manual.txt file.

    Returns (title, parts, unaliased) where:
    - title may be None if not specified
    - parts is a list of dicts with keys: label, id, pages
    - unaliased is a list of (label, id) tuples for labels resolved
      by slugification rather than an explicit alias (flexible-arrangement
      names like "Part 3 in Eb" are left out: they need no alias)
    """
    title = None
    parts = []
    unaliased: list[tuple[str, str]] = []

    with path.open("r", encoding="utf-8") as f:
        for i, raw in enumerate(f, start=1):
            line = raw.strip()

            if not line or line.startswith("#"):
                continue

            if ":" not in line:
                raise ValueError(f"Line {i}: expected 'Label: pages'")

            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()

            if key.lower() == "title":
                title = value
                continue

            if not key:
                raise ValueError(
                    f"Line {i}: missing part label before ':' "
                    "(remove the line or add a label)"
                )

            start, end = parse_page_spec(value, i)

            part_id = normalise_part_id(key, aliases)
            # Track labels that fell through to slugification, apart from
            # flexible-arrangement names, which need no alias
            alias_key = canonicalise_alias_key(key)
            if alias_key not in aliases and not FLEX_ID_RE.fullmatch(part_id):
                unaliased.append((key, part_id))

            parts.append({
                "label": key,
                "id": part_id,
                "pages": [start, end],
            })

    if not parts:
        raise ValueError(f"Manual file contains no parts: {path}")

    return title, parts, unaliased
