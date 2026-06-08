"""
Booklet PDF generation and ZIP archive creation for BandLibrary.
"""

from __future__ import annotations

import zipfile
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from .models import EnsemblePart, MatchResult, Piece


class BuildError(Exception):
    """Raised when booklet generation fails."""


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


def generate_booklets(
    output_dir: Path,
    ensemble_parts: list[EnsemblePart],
    pieces_by_slug: dict[str, Piece],
    grouped_matches: dict[str, list[MatchResult]],
) -> list[Path]:
    """
    Generate one PDF per ensemble part.
    Returns list of paths to generated files.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_files: list[Path] = []

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
            output_path = output_dir / f"{ep.id}.pdf"
            with output_path.open("wb") as f:
                writer.write(f)
            generated_files.append(output_path)
            print(f"Written: {output_path}")

    return generated_files


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
