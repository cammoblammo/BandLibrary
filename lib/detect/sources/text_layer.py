"""
Read the text layer of a PDF with PyMuPDF.

Spans that sit side by side on one baseline are joined into a line, so a
flat drawn in a music font ("Part 1 in B" + "b") comes back as one piece of
text. Lines that hold no letters or digits are kept (music glyphs show the
page has a text layer) but are not candidates for anything.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Callable

import pymupdf

from ..pages import RawPage, TextLine


def _decode(c: str) -> str:
    # Symbol-encoded fonts (common in older Finale PDFs) store "A" as
    # U+F041: shift U+F020–U+F07E back to plain ASCII.
    if "" <= c <= "":
        return chr(ord(c) - 0xF000)
    return c


def _clean(text: str) -> str:
    # Music fonts put control characters in the text layer
    return "".join(_decode(c) for c in text if unicodedata.category(c) != "Cc")


def _join_spans(spans: list[dict]) -> list[TextLine]:
    """
    Join spans on the same baseline that touch horizontally. Spans are taken
    left to right, so a taller first word ("B♭" before "CLARINET") still
    starts the line.
    """
    lines: list[TextLine] = []
    for sp in sorted(spans, key=lambda s: s["x0"]):
        best, best_gap = None, None
        for line in lines:
            same_row = abs((line.y0 + line.y1) / 2 - (sp["y0"] + sp["y1"]) / 2) \
                < 0.5 * max(line.y1 - line.y0, sp["y1"] - sp["y0"])
            gap = sp["x0"] - line.x1
            if same_row and -0.002 <= gap < sp["em"] * 0.6 \
                    and (best_gap is None or gap < best_gap):
                best, best_gap = line, gap
        if best is None:
            lines.append(TextLine(sp["text"], sp["x0"], sp["y0"], sp["x1"],
                                  sp["y1"], sp["size"]))
            continue
        sep = " " if best_gap > sp["em"] * 0.15 and not best.text.endswith(" ") else ""
        best.text += sep + sp["text"]
        best.x1 = sp["x1"]
        best.y0 = min(best.y0, sp["y0"])
        best.y1 = max(best.y1, sp["y1"])
        best.size = max(best.size, sp["size"])
    for line in lines:
        line.text = " ".join(line.text.split())
    lines = [l for l in lines if l.text]
    return sorted(lines, key=lambda l: (l.y0, l.x0))


def read_page(page: pymupdf.Page, number: int) -> RawPage:
    w, h = page.rect.width, page.rect.height
    spans = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for sp in line["spans"]:
                text = _clean(sp["text"])
                if not text.strip():
                    continue
                x0, y0, x1, y1 = sp["bbox"]
                spans.append({
                    "text": text, "size": round(sp["size"], 1),
                    "x0": x0 / w, "y0": y0 / h, "x1": x1 / w, "y1": y1 / h,
                    "em": sp["size"] / w,
                })
    return RawPage(page=number, lines=_join_spans(spans), source="text")


def read_pdf(path: Path,
             progress: Callable[[int, int], None] | None = None) -> list[RawPage]:
    pages = []
    with pymupdf.open(path) as doc:
        total = doc.page_count
        for i, page in enumerate(doc, start=1):
            pages.append(read_page(page, i))
            if progress:
                progress(i, total)
    return pages
