#!/usr/bin/env python3
"""
add_part.py — Append an additional part PDF to an existing library piece.

Usage:
    python3 tools/add_part.py <piece-slug> <part-label> <part.pdf> [options]

The source PDF is appended to the piece's existing PDF. The page range is
calculated automatically. The piece YAML is updated with the new part.
The source PDF is removed after a successful import.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import unicodedata
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required. Install it with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    print("ERROR: pypdf is required. Install it with: pip install pypdf", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Normalisation (mirrors import_piece.py)
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    return text.strip("-")


def default_normalise_part_id(label: str) -> str:
    return slugify(label).replace("-", "_")


def canonicalise_alias_key(label: str) -> str:
    text = unicodedata.normalize("NFKD", label)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def load_aliases(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {}
    if not path.is_file():
        raise ValueError(f"Alias path is not a file: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Alias file must contain a top-level mapping: {path}")

    aliases = data.get("aliases")
    if aliases is None:
        return {}
    if not isinstance(aliases, dict):
        raise ValueError(f"'aliases' in {path} must be a mapping")

    loaded: dict[str, str] = {}
    for raw_label, target_id in aliases.items():
        if not isinstance(raw_label, str) or not raw_label.strip():
            raise ValueError(f"Alias key must be a non-empty string in {path}")
        if not isinstance(target_id, str) or not target_id.strip():
            raise ValueError(f"Alias target must be a non-empty string in {path}")
        key = canonicalise_alias_key(raw_label)
        if key in loaded and loaded[key] != target_id:
            raise ValueError(f"Conflicting alias entries for {raw_label!r} in {path}")
        loaded[key] = target_id.strip()

    return loaded


def normalise_part_id(label: str, aliases: dict[str, str]) -> str:
    key = canonicalise_alias_key(label)
    if key in aliases:
        return aliases[key]
    return default_normalise_part_id(label)


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def add_part(
    slug: str,
    label: str,
    source_pdf: Path,
    library: Path,
    aliases: dict[str, str],
) -> None:
    # Locate piece
    piece_dir = library / slug
    if not piece_dir.exists():
        raise FileNotFoundError(f"Piece not found in library: {slug}")

    yaml_path = piece_dir / f"{slug}.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"Piece YAML not found: {yaml_path}")

    if not source_pdf.exists():
        raise FileNotFoundError(f"Source PDF not found: {source_pdf}")

    # Load existing YAML
    with yaml_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Malformed YAML in {yaml_path}")

    piece_meta = data.get("piece", {})
    existing_parts = data.get("parts", [])

    if not isinstance(existing_parts, list):
        raise ValueError(f"'parts' in {yaml_path} must be a list")

    # Normalise new part ID
    part_id = normalise_part_id(label, aliases)

    # Check for duplicate
    existing_ids = {p["id"] for p in existing_parts if isinstance(p, dict)}
    existing_labels = {p.get("label", "") for p in existing_parts if isinstance(p, dict)}

    if part_id in existing_ids:
        raise ValueError(
            f"Part id {part_id!r} already exists in {slug}. "
            f"Check the piece YAML — if the part is genuinely different, "
            f"add an alias to give it a distinct canonical ID."
        )
    if label in existing_labels:
        raise ValueError(
            f"Part label {label!r} already exists in {slug}."
        )

    # Find the existing piece PDF
    source_pdf_name = piece_meta.get("source_pdf")
    if not source_pdf_name:
        raise ValueError(f"Missing source_pdf in piece metadata: {yaml_path}")

    piece_pdf_path = piece_dir / source_pdf_name
    if not piece_pdf_path.exists():
        raise FileNotFoundError(f"Piece PDF not found: {piece_pdf_path}")

    # Calculate current page count (new part starts on next page)
    existing_reader = PdfReader(str(piece_pdf_path))
    existing_page_count = len(existing_reader.pages)

    new_reader = PdfReader(str(source_pdf))
    new_page_count = len(new_reader.pages)

    if new_page_count == 0:
        raise ValueError(f"Source PDF has no pages: {source_pdf}")

    start_page = existing_page_count + 1
    end_page = existing_page_count + new_page_count

    # Prepare the new part stanza
    new_part = {
        "id": part_id,
        "label": label,
        "pages": [start_page, end_page],
    }

    # --- Safe write with rollback ---
    backup_pdf = piece_pdf_path.with_suffix(".pdf.backup")
    backup_yaml = yaml_path.with_suffix(".yaml.backup")

    try:
        # Back up both files
        shutil.copy2(piece_pdf_path, backup_pdf)
        shutil.copy2(yaml_path, backup_yaml)

        # Merge PDFs
        writer = PdfWriter()
        for page in existing_reader.pages:
            writer.add_page(page)
        for page in new_reader.pages:
            writer.add_page(page)

        with piece_pdf_path.open("wb") as f:
            writer.write(f)

        # Update YAML
        data["parts"] = existing_parts + [new_part]

        with yaml_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, sort_keys=False)

        # Remove source PDF only after everything succeeded
        source_pdf.unlink()

        # Remove backups
        backup_pdf.unlink()
        backup_yaml.unlink()

        print(f"Added part '{label}' ({part_id}) to {slug}: pages {start_page}-{end_page}")

    except Exception:
        # Rollback: restore originals if backups exist
        if backup_pdf.exists():
            shutil.copy2(backup_pdf, piece_pdf_path)
            backup_pdf.unlink()
        if backup_yaml.exists():
            shutil.copy2(backup_yaml, yaml_path)
            backup_yaml.unlink()
        raise


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Append an additional part PDF to an existing library piece."
    )
    parser.add_argument("slug", help="Piece slug (must exist in the library)")
    parser.add_argument("label", help="Part label (e.g. 'Tenor Horn')")
    parser.add_argument("pdf", type=Path, help="Source PDF to append")
    parser.add_argument(
        "--library",
        type=Path,
        default=Path("library"),
        help='Library root directory (default: "library")',
    )
    parser.add_argument(
        "--aliases",
        type=Path,
        default=Path("config/aliases.yaml"),
        help='Aliases file (default: "config/aliases.yaml")',
    )

    args = parser.parse_args()

    try:
        aliases = load_aliases(args.aliases)
        add_part(
            slug=args.slug,
            label=args.label,
            source_pdf=args.pdf,
            library=args.library,
            aliases=aliases,
        )
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
