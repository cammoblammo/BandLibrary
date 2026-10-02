"""
Booklet PDF generation and ZIP archive creation for BandBook.
"""

from __future__ import annotations

import io
from xml.sax.saxutils import escape
import zipfile
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib import colors

from .models import EnsemblePart, MatchResult, Piece
from .utils import display_title


class BuildError(Exception):
    """Raised when booklet generation fails."""


# ---------------------------------------------------------------------------
# Cover sheet
# ---------------------------------------------------------------------------

def generate_cover_page(
    band_name: str,
    part_label: str,
    edition: str,
    piece_titles: list[tuple[str, int | None]],
) -> PdfWriter:
    """
    Generate the A4 cover as a PdfWriter: one page, or more if the contents
    list is long.

    Layout (top to bottom):
      - Band name (large)
      - Part/instrument name (very large, prominent)
      - Edition name
      - Contents list: piece titles in order, each with the booklet page it
        starts on (counting the cover as page 1); pieces this part has no
        music for (page None) are shown in brackets, greyed
    """
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=25 * mm,
        rightMargin=25 * mm,
        topMargin=30 * mm,
        bottomMargin=25 * mm,
    )

    W, H = A4

    style_band = ParagraphStyle(
        "band",
        fontSize=22,
        leading=28,
        alignment=TA_CENTER,
        textColor=colors.black,
        fontName="Helvetica",
        spaceAfter=8 * mm,
    )

    style_part = ParagraphStyle(
        "part",
        fontSize=52,
        leading=60,
        alignment=TA_CENTER,
        textColor=colors.black,
        fontName="Helvetica-Bold",
        spaceAfter=8 * mm,
    )

    style_edition = ParagraphStyle(
        "edition",
        fontSize=18,
        leading=24,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#444444"),
        fontName="Helvetica-Oblique",
        spaceAfter=16 * mm,
    )

    style_contents_header = ParagraphStyle(
        "contents_header",
        fontSize=13,
        leading=18,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#444444"),
        fontName="Helvetica-Bold",
        spaceAfter=4 * mm,
    )

    style_contents_item = ParagraphStyle(
        "contents_item",
        fontSize=13,
        leading=20,
        alignment=TA_LEFT,
        textColor=colors.black,
        fontName="Helvetica",
        leftIndent=8 * mm,
    )

    story = []

    # Spacer to push content towards vertical centre
    story.append(Spacer(1, 30 * mm))

    if band_name:
        story.append(Paragraph(band_name, style_band))

    story.append(Paragraph(part_label, style_part))

    if edition:
        story.append(Paragraph(edition, style_edition))

    story.append(Spacer(1, 10 * mm))

    # Divider line (drawn as a narrow black rectangle)
    from reportlab.platypus import HRFlowable
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cccccc")))
    story.append(Spacer(1, 6 * mm))

    style_contents_missing = ParagraphStyle(
        "contents_missing", parent=style_contents_item, textColor=colors.HexColor("#888888"),
    )
    style_contents_note = ParagraphStyle(
        "contents_note", parent=style_contents_item, fontSize=10, leading=14,
        textColor=colors.HexColor("#666666"), fontName="Helvetica-Oblique",
        spaceBefore=4 * mm,
    )

    style_contents_page = ParagraphStyle(
        "contents_page", parent=style_contents_item, alignment=TA_RIGHT, leftIndent=0,
    )

    if piece_titles:
        story.append(Paragraph("Contents", style_contents_header))
        rows = []
        for i, (title, page) in enumerate(piece_titles, start=1):
            if page is not None:
                rows.append([Paragraph(f"{i}.&nbsp;&nbsp;{escape(title)}", style_contents_item),
                             Paragraph(f"p.&nbsp;{page}", style_contents_page)])
            else:
                rows.append([Paragraph(f"{i}.&nbsp;&nbsp;({escape(title)})",
                                       style_contents_missing), ""])
        table = Table(rows, colWidths=[None, 22 * mm])
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(table)
        if any(page is None for _, page in piece_titles):
            story.append(Paragraph(
                "Pieces in brackets have no part for this instrument.", style_contents_note
            ))
        story.append(Paragraph(
            "Page numbers count this cover as page 1.", style_contents_note
        ))

    doc.build(story)

    buffer.seek(0)
    reader = PdfReader(buffer)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    return writer


# ---------------------------------------------------------------------------
# Page extraction
# ---------------------------------------------------------------------------

def append_part_pages(writer: PdfWriter, piece: Piece, part_id: str) -> None:
    """Append pages for a specific part to an existing PdfWriter."""
    part = piece.parts_by_id[part_id]
    reader = PdfReader(str(piece.pdf_path))
    total_pages = len(reader.pages)

    if part.end_page > total_pages:
        raise BuildError(
            f"Part {part_id!r} in piece {piece.slug} references page {part.end_page}, "
            f"but PDF only has {total_pages} pages"
        )

    for page_number in range(part.start_page, part.end_page + 1):
        writer.add_page(reader.pages[page_number - 1])


# ---------------------------------------------------------------------------
# Booklet generation
# ---------------------------------------------------------------------------

def generate_booklets(
    output_dir: Path,
    ensemble_parts: list[EnsemblePart],
    pieces_by_slug: dict[str, Piece],
    grouped_matches: dict[str, list[MatchResult]],
    band_name: str = "",
    edition: str = "",
) -> list[Path]:
    """
    Generate one PDF per ensemble part, each with a cover sheet prepended.
    Returns list of paths to generated files.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_files: list[Path] = []

    for ep in ensemble_parts:
        writer = PdfWriter()
        # Every piece in build order, so numbering matches across booklets,
        # with where it starts among the music pages (None: no part)
        pieces_in_booklet: list[tuple[str, int | None]] = []

        for result in grouped_matches[ep.id]:
            piece = pieces_by_slug[result.piece_slug]
            title = display_title(piece.title)
            if not result.matched_ids:
                pieces_in_booklet.append((title, None))
                continue
            start = len(writer.pages)
            # Several parts for a "takes: all" chair (e.g. Percussion)
            for part_id in result.matched_ids:
                append_part_pages(writer, piece, part_id)
            pieces_in_booklet.append((title, start))

        if any(start is not None for _, start in pieces_in_booklet):
            # Prepend the cover. Page numbers depend on how many pages the
            # cover itself takes, so build it again if the contents spill over.
            cover_pages = 1
            for _ in range(3):      # settles at once in practice
                piece_titles = [
                    (title, None if start is None else cover_pages + start + 1)
                    for title, start in pieces_in_booklet
                ]
                cover_writer = generate_cover_page(
                    band_name=band_name,
                    part_label=ep.label,
                    edition=edition,
                    piece_titles=piece_titles,
                )
                if len(cover_writer.pages) == cover_pages:
                    break
                cover_pages = len(cover_writer.pages)
            final_writer = PdfWriter()
            for page in cover_writer.pages:
                final_writer.add_page(page)
            for page in writer.pages:
                final_writer.add_page(page)

            output_path = output_dir / f"{ep.id}.pdf"
            with output_path.open("wb") as f:
                final_writer.write(f)
            generated_files.append(output_path)
            print(f"Written: {output_path}")

    return generated_files


# ---------------------------------------------------------------------------
# ZIP archive
# ---------------------------------------------------------------------------

def create_zip_archive(
    output_dir: Path,
    files: list[Path],
    archive_stem: str,
) -> Path:
    """Bundle generated files into a timestamped ZIP archive."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    zip_path = output_dir / f"{archive_stem}-{timestamp}.zip"

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in files:
            zf.write(file_path, arcname=file_path.name)

    return zip_path
