"""
Turn page readings into draft parts.

A new part starts where the part name changes. A page with text but no
part name continues the part before it. Score pages and pages without text
end the current part and are reported, never guessed at.
"""

from __future__ import annotations

from collections import Counter

from .pages import DraftPart, PageNote, PageReading


def page_list(pages: list[int]) -> str:
    """[8] -> "page 8"; [8, 9, 11] -> "pages 8-9, 11"."""
    runs: list[list[int]] = []
    for p in pages:
        if runs and p == runs[-1][-1] + 1:
            runs[-1].append(p)
        else:
            runs.append([p])
    text = ", ".join(str(r[0]) if len(r) == 1 else f"{r[0]}-{r[-1]}" for r in runs)
    return ("page " if len(pages) == 1 else "pages ") + text


def segment(readings: list[PageReading]) -> tuple[list[DraftPart], list[PageNote]]:
    parts: list[DraftPart] = []
    skipped: list[PageNote] = []
    current: DraftPart | None = None
    unnamed: list[int] = []

    def close():
        nonlocal current, unnamed
        if current is not None and unnamed:
            verb = "shows" if len(unnamed) == 1 else "show"
            current.notes.append(f"{page_list(unnamed)} {verb} no part name")
        current, unnamed = None, []

    def skip(page: int, reason: str):
        if skipped and skipped[-1].reason == reason and skipped[-1].end == page - 1:
            skipped[-1].end = page
        else:
            skipped.append(PageNote(page, page, reason))

    for r in readings:
        if not r.has_text:
            close()
            skip(r.page, "no-text")
        elif r.is_score:
            close()
            skip(r.page, "score")
        elif r.label is not None:
            if current is not None and current.label == r.label.label \
                    and current.end == r.page - 1:
                current.end = r.page
            else:
                close()
                current = DraftPart(r.label.label, r.label.part_id, r.page, r.page,
                                    r.label.known, list(r.label.notes))
                parts.append(current)
        elif current is not None and current.end == r.page - 1:
            current.end = r.page
            unnamed.append(r.page)
        else:
            skip(r.page, "no-name")
    close()

    counts = Counter(p.label for p in parts)
    for p in parts:
        if counts[p.label] > 1:
            p.notes.append("this name is used more than once: rename or remove a copy")
        elif f"{p.label} 2" in counts and f"{p.label} 1" not in counts:
            p.notes.append(f'there is also a "{p.label} 2": is this "{p.label} 1"?')
    return parts, skipped
