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
            current.printed_for = current.printed_for or r.label.printed_for
            current.clef = current.clef or r.clef
        elif current is not None and current.end == r.page - 1:
            current.end = r.page
            current.clef = current.clef or r.clef
            unnamed.append(r.page)
        else:
            skip(r.page, "no-name")
    close()
    return parts, skipped


def name_notes(parts: list[DraftPart]) -> None:
    """Notes about names across the piece: duplicates, "Trumpet" beside "Trumpet 2"."""
    counts = Counter(p.label for p in parts)
    for p in parts:
        if counts[p.label] > 1:
            p.notes.append(_duplicate_note(p, [q for q in parts
                                               if q.label == p.label and q is not p]))
        elif f"{p.label} 2" in counts and f"{p.label} 1" not in counts:
            p.notes.append(f'there is also a "{p.label} 2": is this "{p.label} 1"?')


def _duplicate_note(part: DraftPart, others: list[DraftPart]) -> str:
    """Say what tells parts with the same printed name apart, if anything does."""
    where = "; ".join(
        f"{page_list(list(range(o.start, o.end + 1)))}"
        + (f", for {o.printed_for}" if o.printed_for else "")
        + (f", {o.clef} clef" if o.clef and o.clef != part.clef else "")
        for o in others)
    clefs = [q.clef for q in [part, *others]]
    if None not in clefs and len(set(clefs)) == len(clefs):
        advice = "adding TC or BC will tell them apart"
    else:
        advice = "rename one so each name is used once, or remove one you don't need"
    this = f" (this one for {part.printed_for})" if part.printed_for else ""
    return f'"{part.label}" is printed more than once{this}; also {where}: {advice}'
