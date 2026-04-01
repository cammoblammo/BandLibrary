#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path
import unicodedata

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required. Install it with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


# -------------------------
# Utilities
# -------------------------

def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    return text.strip("-")


def infer_title_from_filename(path: Path) -> str:
    return re.sub(r"[_\-]+", " ", path.stem).strip()


def default_normalise_part_id(label: str) -> str:
    return slugify(label).replace("-", "_")


def canonicalise_alias_key(label: str) -> str:
    """
    Canonicalise labels for alias lookup so that small differences in spacing,
    punctuation, and case do not matter too much.
    """
    text = unicodedata.normalize("NFKD", label)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# -------------------------
# Alias loading
# -------------------------

def load_aliases(path: Path | None) -> dict[str, str]:
    """
    Load alias mappings from YAML.

    Expected format:

    schema_version: 1
    aliases:
      "Electric guitar": guitar
      "Alto sax 1": alto_sax_1
    """
    if path is None:
        return {}

    if not path.exists():
        raise FileNotFoundError(f"Alias file not found: {path}")
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
            raise ValueError(
                f"Conflicting alias entries for {raw_label!r} in {path}"
            )

        loaded[key] = target_id.strip()

    return loaded


def normalise_part_id(label: str, aliases: dict[str, str]) -> str:
    alias_key = canonicalise_alias_key(label)
    if alias_key in aliases:
        return aliases[alias_key]
    return default_normalise_part_id(label)


# -------------------------
# Manual file parsing
# -------------------------

def parse_page_spec(text: str, line_number: int):
    text = text.strip()

    if re.fullmatch(r"\d+", text):
        page = int(text)
        if page <= 0:
            raise ValueError(f"Line {line_number}: page must be positive")
        return page, page

    match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", text)
    if match:
        start, end = int(match.group(1)), int(match.group(2))
        if start <= 0 or end <= 0:
            raise ValueError(f"Line {line_number}: page must be positive")
        if start > end:
            raise ValueError(f"Line {line_number}: invalid range {text}")
        return start, end

    raise ValueError(
        f"Line {line_number}: invalid page spec '{text}' "
        "(expected '12' or '13-14')"
    )


def parse_manual_file(path: Path, aliases: dict[str, str]):
    title = None
    parts = []

    with path.open("r", encoding="utf-8") as f:
        for i, raw in enumerate(f, start=1):
            line = raw.strip()

            if not line or line.startswith("#"):
                continue

            if ":" not in line:
                raise ValueError(f"Line {i}: expected 'Label: pages'")

            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()

            if key.lower() == "title":
                title = value
                continue

            start, end = parse_page_spec(value, i)

            parts.append({
                "label": key,
                "id": normalise_part_id(key, aliases),
                "pages": [start, end]
            })

    if not parts:
        raise ValueError("Manual file contains no parts")

    return title, parts


# -------------------------
# Main import logic
# -------------------------

def import_piece(
    pdf_path: Path,
    manual_path: Path,
    library: Path,
    force: bool,
    aliases: dict[str, str],
):
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
        print(f"WARNING: {slug} already exists — skipping")
        return

    # Parse manual file first (fail early)
    title, parts = parse_manual_file(manual_path, aliases)
    if not title:
        title = infer_title_from_filename(pdf_path)

    # Validate duplicate IDs
    seen = set()
    for p in parts:
        if p["id"] in seen:
            raise ValueError(f"Duplicate part id: {p['id']}")
        seen.add(p["id"])

    # Prepare YAML structure
    yaml_data = {
        "schema_version": 1,
        "piece": {
            "id": slug,
            "title": title,
            "source_pdf": pdf_dest.name,
            "status": "manual"
        },
        "parts": parts
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

        # Remove originals only after success
        pdf_path.unlink()
        manual_path.unlink()

        if backup_dir and backup_dir.exists():
            shutil.rmtree(backup_dir)

        print(f"Imported: {piece_dir}")

    except Exception:
        # rollback
        if piece_dir.exists():
            shutil.rmtree(piece_dir)

        if backup_dir and backup_dir.exists():
            backup_dir.rename(piece_dir)

        raise


# -------------------------
# CLI
# -------------------------

def main():
    parser = argparse.ArgumentParser(description="Import a piece into the library")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--manual", type=Path, required=True)
    parser.add_argument("--library", type=Path, default=Path("library"))
    parser.add_argument("--aliases", type=Path, default=Path("config/aliases.yaml"))
    parser.add_argument("--force", action="store_true")

    args = parser.parse_args()

    try:
        aliases = load_aliases(args.aliases)
        import_piece(args.pdf, args.manual, args.library, args.force, aliases)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
