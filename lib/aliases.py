"""
Alias loading and part ID normalisation for BandLibrary.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .utils import canonicalise_alias_key, default_normalise_part_id


def load_aliases(path: Path | None) -> dict[str, str]:
    """
    Load alias mappings from a YAML file.

    Expected format:

        schema_version: 1
        aliases:
          "Electric guitar": guitar
          "Alto sax 1": alto_sax_1

    Returns an empty dict if path is None or the file does not exist.
    Raises ValueError or FileNotFoundError on malformed input.
    """
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
            raise ValueError(
                f"Conflicting alias entries for {raw_label!r} in {path}"
            )
        loaded[key] = target_id.strip()

    return loaded


def normalise_part_id(label: str, aliases: dict[str, str]) -> str:
    """Resolve a part label to a canonical ID via aliases or slugification."""
    key = canonicalise_alias_key(label)
    if key in aliases:
        return aliases[key]
    return default_normalise_part_id(label)
