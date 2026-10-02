"""
Find each page's part name among its text.

Part names are not always at the top of the page, so the name is found by
how it behaves across the whole PDF rather than where it sits:

1. Text repeated on most pages (title, composer, web address, watermark)
   is page furniture. A page with nothing but furniture has no real text.
2. Pages with several staff names are score pages.
3. Of the text that reads as a part name, the "slot" (top / body / bottom
   of the page, and type size) used on the most pages is where this PDF
   prints its part names. Cue names in the music ("T. Sax", "Triangle")
   sit elsewhere and are ignored.
"""

from __future__ import annotations

from collections import Counter

from ..utils import canonicalise_alias_key
from .names import is_score_marker, looks_instrumental, parse_name
from .pages import BOTTOM_ZONE, TOP_ZONE, NameMatch, PageReading, RawPage, TextLine

FURNITURE_SHARE = 0.5      # on at least half of the pages with text…
FURNITURE_MIN_PAGES = 3    # …and at least this many
SCORE_MIN_NAMES = 4        # distinct staff names that make a score page
SCORE_MARGIN = 0.25        # …in the left quarter of the page
SCORE_SPREAD = 0.25        # …spread over at least this much of its height


def _zone(line: TextLine) -> str:
    if line.y0 < TOP_ZONE:
        return "top"
    if line.y1 > BOTTOM_ZONE:
        return "bottom"
    return "body"


def _slot(line: TextLine, source: str) -> tuple[str, int]:
    # OCR word heights vary with the letters in them (caps, descenders,
    # a tall "B♭"), so on scanned pages only the zone counts.
    return (_zone(line), round(line.size) if source == "text" else 0)


def find_furniture(pages: list[RawPage]) -> set[str]:
    """Canonical text of lines repeated across most pages."""
    counts: Counter[str] = Counter()
    pages_with_text = 0
    for page in pages:
        keys = {canonicalise_alias_key(l.text) for l in page.lines}
        keys.discard("")
        if page.lines:
            pages_with_text += 1
        counts.update(keys)
    threshold = max(FURNITURE_MIN_PAGES, FURNITURE_SHARE * pages_with_text)
    return {k for k, n in counts.items() if n >= threshold}


def _is_score(lines: list[TextLine]) -> bool:
    if any(is_score_marker(l.text) for l in lines):
        return True
    # Staff names run down the left margin of a score, over much of the page
    staves = [l for l in lines
              if l.x0 < SCORE_MARGIN and looks_instrumental(l.text)]
    names = {canonicalise_alias_key(l.text) for l in staves}
    return (len(names) >= SCORE_MIN_NAMES
            and max(l.y0 for l in staves) - min(l.y0 for l in staves) >= SCORE_SPREAD)


def real_lines(page: RawPage, furniture: set[str]) -> list[TextLine]:
    """Lines that aren't page furniture. Music glyphs count: they are text."""
    return [l for l in page.lines
            if canonicalise_alias_key(l.text) not in furniture]


def read_labels(pages: list[RawPage],
                aliases: dict[str, str]) -> list[PageReading]:
    furniture = find_furniture(pages)

    readings: list[PageReading] = []
    candidates: dict[int, list[tuple[TextLine, NameMatch]]] = {}

    for page in pages:
        real = real_lines(page, furniture)
        reading = PageReading(page=page.page, has_text=bool(real),
                              source=page.source)
        readings.append(reading)
        if not real:
            continue
        reading.is_score = _is_score(real)
        if reading.is_score:
            continue
        found = []
        for line in page.lines:
            match = parse_name(line.text, aliases)
            if match:
                found.append((line, match))
        candidates[page.page] = found

    # Text-layer pages and scanned pages are found separately: a mixed PDF
    # prints names in one style, but OCR measures them differently.
    slots = {source: _best_slot({r.page: candidates[r.page] for r in readings
                                 if r.source == source and r.page in candidates},
                                source)
             for source in {r.source for r in readings}}

    for reading in readings:
        slot = slots[reading.source]
        if slot is None:
            continue
        in_slot = [(l, m) for l, m in candidates.get(reading.page, [])
                   if _slot(l, reading.source) == slot]
        if in_slot:
            # Nearest the page edge wins if a page has more than one
            line, match = min(in_slot, key=lambda lm: min(lm[0].y0, 1 - lm[0].y1))
            reading.label = match

    _fill_off_slot(readings, candidates)
    return readings


def _fill_off_slot(readings: list[PageReading],
                   candidates: dict[int, list[tuple[TextLine, NameMatch]]]) -> None:
    """
    A part bound in from another source prints its name in another style.
    Accept a known part name in a page margin, unless the page sits inside
    a part whose name appears on both sides of it (an extra title page).
    """
    slot_labels = [r.label.label if r.label else None for r in readings]
    for i, reading in enumerate(readings):
        if reading.label or not reading.has_text or reading.is_score:
            continue
        margin = [(l, m) for l, m in candidates.get(reading.page, [])
                  if m.known and _zone(l) != "body"]
        if not margin:
            continue
        before = next((s for s in reversed(slot_labels[:i]) if s), None)
        after = next((s for s in slot_labels[i + 1:] if s), None)
        if before is not None and before == after:
            continue
        reading.label = max(margin, key=lambda lm: lm[0].size)[1]


def _best_slot(candidates: dict[int, list[tuple[TextLine, NameMatch]]],
               source: str):
    pages_in: Counter = Counter()
    labels_in: dict[tuple, set[str]] = {}
    for found in candidates.values():
        for slot in {_slot(l, source) for l, _ in found}:
            pages_in[slot] += 1
        for line, match in found:
            labels_in.setdefault(_slot(line, source), set()).add(match.label)
    if not pages_in:
        return None

    def rank(slot):
        zone, size = slot
        return (pages_in[slot], len(labels_in[slot]), zone != "body", size)

    return max(pages_in, key=rank)


def find_title(pages: list[RawPage], aliases: dict[str, str]) -> str | None:
    """
    The largest repeated text that isn't a part name or a credit line;
    failing that, the largest text on the first page with text.
    """
    furniture = find_furniture(pages)

    def usable(line: TextLine) -> bool:
        low = line.text.lower()
        return (sum(c.isalpha() for c in line.text) >= 3
                and line.text[:1].isalpha() and not parse_name(line.text, aliases)
                and "www" not in low and "©" not in line.text
                and "rights reserved" not in low and "copy purchased" not in low
                and not low.startswith(("arr", "composed", "words", "music by")))

    repeated: dict[str, TextLine] = {}
    for page in pages:
        for line in page.lines:
            key = canonicalise_alias_key(line.text)
            if key in furniture and usable(line):
                best = repeated.get(key)
                if best is None or line.size > best.size:
                    repeated[key] = line
    if repeated:
        return max(repeated.values(), key=lambda l: l.size).text

    for page in pages:
        lines = [l for l in page.lines if usable(l)]
        if lines:
            return max(lines, key=lambda l: l.size).text
    return None
