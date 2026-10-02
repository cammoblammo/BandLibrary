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
        # Different names that the aliases turn into the same part ID: the
        # import would refuse them, so say so in the draft
        same_id = [q for q in parts
                   if q is not p and q.part_id == p.part_id and q.label != p.label]
        if same_id:
            others = "; ".join(f'"{q.label}" ({page_list(list(range(q.start, q.end + 1)))})'
                               for q in same_id)
            p.notes.append(f'"{p.label}" has the same part ID ({p.part_id}) as {others}: '
                           "rename one, or the import will refuse it")
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


OPENING_SHARE = 0.75    # share of parts that start on a page with the title


def continuation_notes(parts: list[DraftPart], titled: set[int],
                       checkable: set[int]) -> None:
    """
    Flag a part that starts on a page without the title when nearly every
    other part starts on one: it may be a second page with a misprinted
    header (Bad Guy, page 16). A note only; the pages are not merged.

    titled: pages showing the piece's title; checkable: pages whose text
    can be trusted for this (the text layer, not OCR).
    """
    starts = [p.start for p in parts if p.start in checkable]
    if len(starts) < 3 or sum(s in titled for s in starts) < OPENING_SHARE * len(starts):
        return
    for before, part in zip(parts, parts[1:]):
        if part.start in checkable and part.start not in titled \
                and before.end == part.start - 1:
            part.notes.insert(0, f"page {part.start} looks like a second page (no title), "
                                 f'but its header says "{part.label}": is it part of '
                                 f'"{before.label}" above?')
