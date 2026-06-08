"""
Piece import logic for BandBook.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from .manual import parse_manual_file
from .utils import infer_title_from_filename, slugify


def import_piece(
    pdf_path: Path,
    manual_path: Path,
    library: Path,
    force: bool,
    aliases: dict[str, str],
) -> list[tuple[str, str]]:
    """
    Import a PDF and manual mapping file into the library.

    Creates library/<slug>/ containing the PDF, manual file, and YAML metadata.
    Raises FileNotFoundError or ValueError on bad input.
    On failure, rolls back any partial changes.
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if not manual_path.exists():
        raise FileNotFoundError(f"Manual file not found: {manual_path}")

    slug = slugify(pdf_path.stem)
    piece_dir = library / slug

    pdf_dest = piece_dir / f"{slug}.pdf"
    manual_dest = piece_dir / f"{slug}.manual.txt"
    yaml_dest = piece_dir / f"{slug}.yaml"

    if piece_dir.exists() and not force:
        print(f"WARNING: {slug} already exists — skipping (use --force to overwrite)")
        return

    # Parse manual file first — fail early before touching the library
    title, parts, unaliased = parse_manual_file(manual_path, aliases)
    if not title:
        title = infer_title_from_filename(pdf_path.stem)

    # Validate duplicate IDs
    seen: set[str] = set()
    for p in parts:
        if p["id"] in seen:
            raise ValueError(f"Duplicate part id: {p['id']}")
        seen.add(p["id"])

    yaml_data = {
        "schema_version": 1,
        "piece": {
            "id": slug,
            "title": title,
            "source_pdf": pdf_dest.name,
            "status": "manual",
        },
        "parts": parts,
    }

    # Handle overwrite safely
    backup_dir = None
    if piece_dir.exists() and force:
        backup_dir = piece_dir.with_name(f".{slug}.backup")
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        piece_dir.rename(backup_dir)

    try:
        piece_dir.mkdir(parents=True, exist_ok=True)

        shutil.copy2(pdf_path, pdf_dest)
        shutil.copy2(manual_path, manual_dest)

        with yaml_dest.open("w", encoding="utf-8") as f:
            yaml.safe_dump(yaml_data, f, sort_keys=False)

        if backup_dir and backup_dir.exists():
            shutil.rmtree(backup_dir)

        print(f"Imported: {piece_dir}")
        return unaliased

    except Exception:
        # Rollback
        if piece_dir.exists():
            shutil.rmtree(piece_dir)
        if backup_dir and backup_dir.exists():
            backup_dir.rename(piece_dir)
        raise

    return []
