"""
What detection knows about each page of a PDF.

A source (text layer now; OCR or AI later) only reads pages and returns
RawPages. Everything after that — which text is the part name, where parts
start and end — is decided locally, so results are repeatable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Page margins, as fractions of the page height: part names are usually here
TOP_ZONE = 0.2
BOTTOM_ZONE = 0.8


@dataclass
class TextLine:
    """One line of text on a page. Positions are fractions of the page size."""
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    size: float


@dataclass
class RawPage:
    """A page as a source read it."""
    page: int                       # 1-based
    lines: list[TextLine]
    source: str = "text"            # "text", "ocr" or "ai"
    clef: str | None = None         # first staff's clef, "treble" or "bass", if read


@dataclass
class NameMatch:
    """A piece of page text read as a part name."""
    label: str                      # as it should appear in the manual file
    part_id: str
    known: bool                     # resolved by an alias or the "Part N in X" pattern
    notes: list[str] = field(default_factory=list)


@dataclass
class PageReading:
    """A page after label finding: what segmentation works from."""
    page: int
    has_text: bool
    is_score: bool = False
    label: NameMatch | None = None
    source: str = "text"
    clef: str | None = None


@dataclass
class DraftPart:
    label: str
    part_id: str
    start: int
    end: int
    known: bool = True
    notes: list[str] = field(default_factory=list)


@dataclass
class PageNote:
    """A run of pages that is not part of any detected part."""
    start: int
    end: int
    reason: str                     # "score", "no-text", "no-name"


@dataclass
class Draft:
    title: str | None
    parts: list[DraftPart]
    skipped: list[PageNote]
    page_count: int
    text_pages: int                 # pages with real text (not just a watermark)
    ocr_pages: list[int] = field(default_factory=list)
    ocr_unavailable: str | None = None  # why scans weren't read, if they weren't
