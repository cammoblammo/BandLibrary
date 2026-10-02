"""
Automatic part detection: read a full-set PDF and draft its manual file.

See docs/design/part-detection.md. No Qt here, so the GUI and
tools/detect_parts.py give the same results.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

import pymupdf

from ..aliases import normalise_part_id
from ..reading_groups import ReadingGroup, can_read
from ..utils import canonicalise_alias_key
from .labels import find_furniture, find_title, read_labels, real_lines
from .pages import Draft, DraftPart, PageNote, PageReading, RawPage
from .render import check_count, render
from .segment import continuation_notes, name_notes, segment
from .sources import ocr
from .sources.text_layer import read_pdf

# progress(page, of pages, stage): stage is "text" or "ocr"
Progress = Callable[[int, int, str], None]


UNKNOWN_NOTE = "not a known part name: check it, or add an alias"


def detect_pages(pages: list[RawPage], aliases: dict[str, str],
                 groups: dict[str, ReadingGroup] | None = None) -> Draft:
    """
    groups: reading groups; a name the aliases don't know is still fine if
    a reading group already covers its part ID (e.g. "Flute 1").
    """
    readings = read_labels(pages, aliases)
    parts, skipped = segment(readings)
    names = list(groups or {})
    for part in parts:
        _clef_hint(part, aliases, groups or {})
        if not part.known and not can_read(part.part_id, names, groups or {}):
            part.notes.insert(0, UNKNOWN_NOTE)
    # After clefs are added: "Part 3 in C" twice may now be BC and TC
    name_notes(parts)
    title = find_title(pages, aliases)
    if title:
        key = canonicalise_alias_key(title)
        titled = {p.page for p in pages
                  if any(canonicalise_alias_key(l.text) == key for l in p.lines)}
        continuation_notes(parts, titled, {p.page for p in pages if p.source == "text"})
    return Draft(
        title=title,
        parts=parts,
        skipped=skipped,
        page_count=len(pages),
        text_pages=sum(1 for r in readings if r.has_text),
        ocr_pages=[p.page for p in pages if p.source == "ocr"],
    )


def read_pages(pdf_path: Path, use_ocr: bool = True,
               progress: Progress | None = None,
               ocr_cache: Path | None = None) -> tuple[list[RawPage], str | None]:
    """
    Read every page: the text layer first, then OCR for pages that have no
    real text (scans, or scans carrying only a shop's watermark).
    Returns the pages and, if scans were left unread, why.
    """
    pages = read_pdf(pdf_path, (lambda i, n: progress(i, n, "text")) if progress else None)
    if not use_ocr:
        return pages, None
    furniture = find_furniture(pages)
    scans = [p.page for p in pages if not real_lines(p, furniture)]
    if not scans:
        return pages, None
    why = ocr.available()
    if why:
        return pages, why

    cache_dir = ocr_cache / ocr.pdf_digest(pdf_path) if ocr_cache else None

    def read_scan(number: int) -> RawPage:
        cache = (cache_dir / f"p{number}-{ocr.DPI}-v{ocr.CACHE_VERSION}.json"
                 if cache_dir else None)
        # One document per call: PyMuPDF documents aren't shared between threads
        with pymupdf.open(pdf_path) as doc:
            return ocr.read_page(doc[number - 1], number, cache)

    # Tesseract runs as a separate process, so pages can be read side by side
    with ThreadPoolExecutor(max_workers=ocr.WORKERS) as pool:
        futures = [pool.submit(read_scan, n) for n in scans]
        for i, future in enumerate(as_completed(futures), start=1):
            page = future.result()
            pages[page.page - 1] = page
            if progress:
                progress(i, len(scans), "ocr")
    return pages, None


CLEF_NOT_PRINTED = "clef not printed: add TC or BC"


def _group_clef(group: ReadingGroup) -> str | None:
    label = group.label.lower()
    return "treble" if "treble clef" in label else "bass" if "bass clef" in label else None


def _clef_hint(part: DraftPart, aliases: dict[str, str],
               groups: dict[str, ReadingGroup]) -> None:
    """
    Use the clef of the part's first staff, where the PDF shows it:
    - a C part with no clef in its name gets it added ("Part 3 in C BC");
    - a name the reading groups read in the other clef ("Euphonium"
      printed in treble clef) gets a note, but is not renamed.
    """
    clef = part.clef
    if clef is None:
        return
    if CLEF_NOT_PRINTED in part.notes:
        part.label = f"{part.label} {'TC' if clef == 'treble' else 'BC'}"
        part.part_id = normalise_part_id(part.label, aliases)
        part.notes[part.notes.index(CLEF_NOT_PRINTED)] = \
            f"clef added from the first staff ({clef} clef)"
        return
    clefs = {_group_clef(g) for name, g in groups.items()
             if can_read(part.part_id, [name], groups)} - {None}
    if clefs and clef not in clefs:
        other = " or ".join(sorted(clefs))
        part.notes.append(f'the first staff is in {clef} clef, but "{part.label}" '
                          f"is read as a {other}-clef part")


def detect_parts(pdf_path: Path, aliases: dict[str, str],
                 groups: dict[str, ReadingGroup] | None = None,
                 progress: Progress | None = None,
                 use_ocr: bool = True,
                 ocr_cache: Path | None = None) -> Draft:
    pages, ocr_unavailable = read_pages(pdf_path, use_ocr, progress, ocr_cache)
    draft = detect_pages(pages, aliases, groups)
    draft.ocr_unavailable = ocr_unavailable
    return draft


__all__ = [
    "Draft", "DraftPart", "PageNote", "PageReading", "RawPage",
    "check_count", "detect_pages", "detect_parts", "read_pages", "render",
]
