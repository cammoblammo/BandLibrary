#!/usr/bin/env python3

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import shutil
import sys
from pathlib import Path

import yaml
from pypdf import PdfReader, PdfWriter

from lib.aliases import load_aliases, normalise_part_id
from lib.utils import slugify


def add_part(
    slug: str,
    label: str,
    source_pdf: Path,
    library: Path,
    aliases: dict[str, str],
) -> None:
    piece_dir = library / slug
    if not piece_dir.exists():
        raise FileNotFoundError(f"Piece not found in library: {slug}")

    yaml_path = piece_dir / f"{slug}.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"Piece YAML not found: {yaml_path}")

    if not source_pdf.exists():
        raise FileNotFoundError(f"Source PDF not found: {source_pdf}")

    with yaml_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Malformed YAML in {yaml_path}")

    piece_meta = data.get("piece", {})
    existing_parts = data.get("parts", [])

    if not isinstance(existing_parts, list):
        raise ValueError(f"'parts' in {yaml_path} must be a list")

    part_id = normalise_part_id(label, aliases)

    existing_ids = {p["id"] for p in existing_parts if isinstance(p, dict)}
    existing_labels = {p.get("label", "") for p in existing_parts if isinstance(p, dict)}

    if part_id in existing_ids:
        raise ValueError(
            f"Part id {part_id!r} already exists in {slug}. "
            f"Check the piece YAML — if the part is genuinely different, "
            f"add an alias to give it a distinct canonical ID."
        )
    if label in existing_labels:
        raise ValueError(f"Part label {label!r} already exists in {slug}.")

    source_pdf_name = piece_meta.get("source_pdf")
    if not source_pdf_name:
        raise ValueError(f"Missing source_pdf in piece metadata: {yaml_path}")

    piece_pdf_path = piece_dir / source_pdf_name
    if not piece_pdf_path.exists():
        raise FileNotFoundError(f"Piece PDF not found: {piece_pdf_path}")

    existing_reader = PdfReader(str(piece_pdf_path))
    existing_page_count = len(existing_reader.pages)

    new_reader = PdfReader(str(source_pdf))
    new_page_count = len(new_reader.pages)

    if new_page_count == 0:
        raise ValueError(f"Source PDF has no pages: {source_pdf}")

    start_page = existing_page_count + 1
    end_page = existing_page_count + new_page_count

    new_part = {
        "id": part_id,
        "label": label,
        "pages": [start_page, end_page],
    }

    if start_page == end_page:
        page_spec = str(start_page)
    else:
        page_spec = f"{start_page}-{end_page}"
    manual_line = f"{label}: {page_spec}\n"

    manual_path = piece_dir / f"{slug}.manual.txt"

    backup_pdf = piece_pdf_path.with_suffix(".pdf.backup")
    backup_yaml = yaml_path.with_suffix(".yaml.backup")
    backup_manual = manual_path.with_suffix(".manual.txt.backup") if manual_path.exists() else None

    try:
        shutil.copy2(piece_pdf_path, backup_pdf)
        shutil.copy2(yaml_path, backup_yaml)
        if manual_path.exists():
            shutil.copy2(manual_path, backup_manual)

        writer = PdfWriter()
        for page in existing_reader.pages:
            writer.add_page(page)
        for page in new_reader.pages:
            writer.add_page(page)

        with piece_pdf_path.open("wb") as f:
            writer.write(f)

        data["parts"] = existing_parts + [new_part]
        with yaml_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, sort_keys=False)

        if not manual_path.exists():
            print(
                f"WARNING: no manual file found for {slug} — "
                f"creating {manual_path.name} (will contain the added part only)"
            )
        with manual_path.open("a", encoding="utf-8") as f:
            f.write(manual_line)

        source_pdf.unlink()

        backup_pdf.unlink()
        backup_yaml.unlink()
        if backup_manual and backup_manual.exists():
            backup_manual.unlink()

        print(f"Added part '{label}' ({part_id}) to {slug}: pages {start_page}-{end_page}")

    except Exception:
        if backup_pdf.exists():
            shutil.copy2(backup_pdf, piece_pdf_path)
            backup_pdf.unlink()
        if backup_yaml.exists():
            shutil.copy2(backup_yaml, yaml_path)
            backup_yaml.unlink()
        if backup_manual and backup_manual.exists():
            shutil.copy2(backup_manual, manual_path)
            backup_manual.unlink()
        raise


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Append an additional part PDF to an existing library piece."
    )
    parser.add_argument("slug")
    parser.add_argument("label")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--library", type=Path, default=Path("library"))
    parser.add_argument("--aliases", type=Path, default=Path("config/aliases.yaml"))

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
