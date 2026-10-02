"""
Write a draft as manual-file text.

Notes go on their own "# " line above the entry they refer to: the manual
parser skips whole comment lines, but not comments after an entry.
"""

from __future__ import annotations

from .pages import Draft
from .segment import page_list

HEADER = [
    "# Detected by BandBook from the PDF's text. Check every line against",
    "# the PDF before importing; look first at lines marked \"check\".",
]

SKIP_REASONS = {
    "score": "score (skipped)",
    "no-text": "no text found: map these by hand",
    "no-name": "no part name found (cover or notes?)",
}


def _pages(start: int, end: int) -> str:
    return str(start) if start == end else f"{start}-{end}"


def render(draft: Draft) -> str:
    lines: list[str] = []
    if draft.title:
        lines.append("# check: title read from the PDF")
        lines.append(f"Title: {draft.title}")
    lines.extend(HEADER)
    if draft.ocr_pages:
        lines.append(f"# Read from scanned images (OCR): {page_list(draft.ocr_pages)}.")
        lines.append("# OCR makes mistakes: check names and page numbers closely.")
    if draft.ocr_unavailable:
        lines.append(f"# Scanned pages were not read: {draft.ocr_unavailable}.")

    events: list[tuple[int, list[str]]] = []
    for note in draft.skipped:
        label = "page" if note.start == note.end else "pages"
        events.append((note.start, [
            f"# {label} {_pages(note.start, note.end)}: {SKIP_REASONS[note.reason]}"
        ]))
    for part in draft.parts:
        block = [f"# check: {n}" for n in part.notes]
        block.append(f"{part.label}: {_pages(part.start, part.end)}")
        events.append((part.start, block))

    for _, block in sorted(events, key=lambda e: e[0]):
        lines.extend(block)
    return "\n".join(lines) + "\n"


def check_count(draft: Draft) -> int:
    """Lines the reader should look at first."""
    return (sum(1 for p in draft.parts if p.notes)
            + sum(1 for n in draft.skipped if n.reason != "score"))
