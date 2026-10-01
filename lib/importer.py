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
    Returns a list of (label, id) tuples for unaliased labels.
    Raises FileNotFoundError or ValueError on bad input, and
    FileExistsError if the piece exists and force is False.
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
        raise FileExistsError(
            f"{slug} already exists in the library (use --force to overwrite)"
        )

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

    # On re-import, keep assignments that still point at a part
    if piece_dir.exists() and yaml_dest.exists():
        kept = _surviving_assignments(yaml_dest, {p["id"] for p in parts})
        if kept:
            yaml_data["assignments"] = kept

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


def regenerate_yaml(
    slug: str,
    manual_path: Path,
    library: Path,
    aliases: dict[str, str],
) -> list[tuple[str, str]]:
    """
    Regenerate the YAML for an existing library piece from its manual file.
    The PDF is not touched. Preserves existing assignments block if present.
    """
    piece_dir = library / slug
    if not piece_dir.exists():
        raise FileNotFoundError(f"Piece not found in library: {slug}")

    if not manual_path.exists():
        raise FileNotFoundError(f"Manual file not found: {manual_path}")

    yaml_path = piece_dir / f"{slug}.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"YAML not found: {yaml_path}")

    # Parse manual file with current aliases
    title, parts, unaliased = parse_manual_file(manual_path, aliases)
    if not title:
        title = infer_title_from_filename(slug)

    # Validate duplicate IDs
    seen: set[str] = set()
    for p in parts:
        if p["id"] in seen:
            raise ValueError(f"Duplicate part id: {p['id']}")
        seen.add(p["id"])

    # Load existing YAML to preserve assignments and other metadata
    with yaml_path.open("r", encoding="utf-8") as f:
        existing = yaml.safe_load(f)

    if not isinstance(existing, dict):
        raise ValueError(f"Malformed YAML in {yaml_path}")
    existing_assignments = existing.get("assignments") or {}
    if not isinstance(existing_assignments, dict):
        raise ValueError(f"'assignments' in {yaml_path} must be a mapping")

    yaml_data = {
        "schema_version": 1,
        "piece": {
            "id": slug,
            "title": title,
            "source_pdf": f"{slug}.pdf",
            "status": "manual",
        },
        "parts": parts,
    }

    valid_assignments = _filter_assignments(existing_assignments, {p["id"] for p in parts})
    if valid_assignments:
        yaml_data["assignments"] = valid_assignments

    # Backup and write
    backup = yaml_path.with_suffix(".yaml.backup")
    shutil.copy2(yaml_path, backup)

    try:
        with yaml_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(yaml_data, f, sort_keys=False)
        backup.unlink()
        print(f"Regenerated YAML: {yaml_path}")
        return unaliased
    except Exception:
        shutil.copy2(backup, yaml_path)
        backup.unlink()
        raise


def _filter_assignments(assignments: dict, part_ids: set[str]) -> dict[str, str]:
    """Keep assignments whose part still exists; warn about the rest."""
    kept = {k: v for k, v in assignments.items() if v in part_ids}
    dropped = sorted(f"{k} ({v})" for k, v in assignments.items() if k not in kept)
    if dropped:
        print(
            "WARNING: removed assignments whose part no longer exists: "
            + ", ".join(dropped)
        )
    return kept


def _surviving_assignments(yaml_path: Path, part_ids: set[str]) -> dict[str, str]:
    """Assignments from an existing piece YAML that still match part_ids."""
    try:
        with yaml_path.open("r", encoding="utf-8") as f:
            existing = yaml.safe_load(f)
    except (OSError, yaml.YAMLError):
        print(f"WARNING: could not read existing assignments from {yaml_path}")
        return {}
    assignments = existing.get("assignments") if isinstance(existing, dict) else None
    if not isinstance(assignments, dict):
        return {}
    kept = _filter_assignments(assignments, part_ids)
    if kept:
        print(f"Kept {len(kept)} assignment(s) from the previous import")
    return kept
