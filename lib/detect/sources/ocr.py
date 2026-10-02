"""
Read scanned pages with Tesseract (local OCR; nothing leaves the computer).

Words come back with their positions, joined into lines the same way as the
text layer, so the same label-finding rules apply. Sizes are converted from
pixels to points so OCR pages and text pages can be compared.
"""

from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path

import pymupdf

from ..pages import BOTTOM_ZONE, TOP_ZONE, RawPage
from .text_layer import _join_spans

DPI = 200
# Pages read at once. Each Tesseract is limited to one thread, which is
# faster overall than one page at a time with Tesseract's own threads.
WORKERS = max(1, min(4, (os.cpu_count() or 2)))
CACHE_VERSION = 2       # bump when the cached reading changes shape
MIN_CONFIDENCE = 50


@lru_cache(maxsize=1)
def available() -> str | None:
    """None if OCR can run, otherwise why not."""
    try:
        import pytesseract
    except ImportError:
        return "the pytesseract Python package is not installed"
    try:
        pytesseract.get_tesseract_version()
    except Exception:
        return "Tesseract is not installed (sudo apt install tesseract-ocr)"
    return None


def _words(page: pymupdf.Page, top: float = 0.0, bottom: float = 1.0) -> list[dict]:
    """OCR the band of the page between top and bottom (fractions of its height)."""
    import pytesseract
    from PIL import Image

    rect = page.rect
    clip = pymupdf.Rect(0, rect.height * top, rect.width, rect.height * bottom)
    pix = page.get_pixmap(dpi=DPI, clip=clip, colorspace=pymupdf.csGRAY)
    image = Image.frombytes("L", (pix.width, pix.height), pix.samples)
    # psm 11: sparse text, so words scattered among staves are still found
    os.environ.setdefault("OMP_THREAD_LIMIT", "1")
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT,
                                     config="--psm 11")
    w, h = pix.width, pix.height / (bottom - top)   # h: whole page, in pixels
    offset = top * h
    words = []
    for i, text in enumerate(data["text"]):
        text = text.strip()
        if not text or float(data["conf"][i]) < MIN_CONFIDENCE:
            continue
        if not any(c.isalnum() for c in text):
            continue
        left, y = data["left"][i], data["top"][i] + offset
        width, height = data["width"][i], data["height"][i]
        words.append({
            "text": text, "size": round(height * 72 / DPI, 1),
            "x0": left / w, "y0": y / h,
            "x1": (left + width) / w, "y1": (y + height) / h,
        })
    return words


def _read(page: pymupdf.Page) -> dict:
    """
    The whole page, plus the top and bottom margins on their own: OCR reads
    a part name in a margin more reliably without the music beside it.
    """
    return {
        "aspect": page.rect.height / page.rect.width,
        "page": _words(page),
        "top": _words(page, 0.0, TOP_ZONE + 0.04),
        "bottom": _words(page, BOTTOM_ZONE - 0.04, 1.0),
    }


def _lines(read: dict):
    for words in (read["page"], read["top"], read["bottom"]):
        for word in words:
            # A word's box is about cap height; a font's em is larger
            word["em"] = 2.0 * (word["y1"] - word["y0"]) * read["aspect"]
    margins = [l for l in _join_spans(read["top"]) if l.y0 < TOP_ZONE] \
        + [l for l in _join_spans(read["bottom"]) if l.y1 > BOTTOM_ZONE]
    # Keep what only the whole-page reading found, even in the margins
    lines = margins + [l for l in _join_spans(read["page"])
                       if not any(_overlap(l, m) for m in margins)]
    return sorted(lines, key=lambda l: (l.y0, l.x0))


def _overlap(a, b) -> bool:
    return a.x0 < b.x1 and b.x0 < a.x1 and a.y0 < b.y1 and b.y0 < a.y1


def pdf_digest(pdf_path: Path) -> str:
    return hashlib.sha1(pdf_path.read_bytes()).hexdigest()[:16]


def read_page(page: pymupdf.Page, number: int, cache: Path | None = None) -> RawPage:
    """
    OCR one page. cache (a JSON file, used by the scoring tool) keeps the
    words so repeated runs over the library don't re-read every scan.
    """
    if cache is not None and cache.exists():
        return RawPage(number, _lines(json.loads(cache.read_text())), "ocr")
    read = _read(page)
    if cache is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(read))
    return RawPage(number, _lines(read), "ocr")
