"""
Booklet PDF generation and ZIP archive creation for BandBook.
"""

from __future__ import annotations

import io
import zipfile
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib import colors

from .models import EnsemblePart, MatchResult, Piece


class BuildError(Exception):
    """Raised when booklet generation fails."""


# ---------------------------------------------------------------------------
# Cover sheet
# ---------------------------------------------------------------------------

def generate_cover_page(
    band_name: str,
    part_label: str,
    edition: str,
    piece_titles: list[str],
) -> PdfWriter:
    """
    Generate a single A4 cover page as a PdfWriter.

    Layout (top to bottom):
      - Band name (large)
      - Part/instrument name (very large, prominent)
      - Edition name
      - Contents list (piece titles in order)
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

    if piece_titles:
        story.append(Paragraph("Contents", style_contents_header))
        for i, title in enumerate(piece_titles, start=1):
            story.append(Paragraph(f"{i}.&nbsp;&nbsp;{title}", style_contents_item))

    doc.build(story)

    buffer.seek(0)
    reader = PdfReader(buffer)
    writer = PdfWriter()
    writer.add_page(reader.pages[0])
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

    # Collect piece titles in build order (deduplicated, order preserved)
    seen_slugs: set[str] = set()
    ordered_slugs: list[str] = []
    for ep in ensemble_parts:
        for result in grouped_matches[ep.id]:
            if result.piece_slug not in seen_slugs:
                seen_slugs.add(result.piece_slug)
                ordered_slugs.append(result.piece_slug)

    piece_titles = [
        pieces_by_slug[slug].title.title()
        for slug in ordered_slugs
        if slug in pieces_by_slug
    ]

    for ep in ensemble_parts:
        writer = PdfWriter()
        matched_any = False

        for result in grouped_matches[ep.id]:
            if result.matched_id is None:
                continue
            piece = pieces_by_slug[result.piece_slug]
            append_part_pages(writer, piece, result.matched_id)
            matched_any = True

        if matched_any:
            # Prepend cover sheet
            cover_writer = generate_cover_page(
                band_name=band_name,
                part_label=ep.label,
                edition=edition,
                piece_titles=piece_titles,
            )
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
