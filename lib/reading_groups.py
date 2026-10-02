"""
Reading groups for BandBook.

A reading group is a set of written parts that share a transposition and
clef, so any chair that reads the group can play them (range permitting).
Groups are shared by every ensemble; chairs say which groups they read.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path

import yaml

FLEX_RE = re.compile(r"^flex\s+(\d+)(?:\s+([a-z0-9_]+))?$")


@dataclass(frozen=True)
class ReadingGroup:
    name: str
    label: str
    patterns: tuple[str, ...]   # part ids or globs, e.g. "alto_sax_*"
    flex: tuple[str, ...]       # flex templates, e.g. "part_{n}_in_bb"


def default_groups_path(ensemble_path: Path) -> Path:
    """config/ensembles/x.yaml -> config/reading_groups.yaml"""
    return ensemble_path.parent.parent / "reading_groups.yaml"


def load_reading_groups(path: Path) -> dict[str, ReadingGroup]:
    """
    Load reading groups from YAML. Returns an empty dict if the file is missing.

    Expected format:

        schema_version: 1
        groups:
          bb_treble:
            label: B♭ treble clef
            parts: [clarinet_*, trumpet_*, tenor_sax]
            flex: ["part_{n}_in_bb", "part_{n}_in_bb_tc"]
    """
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict) or not isinstance(data.get("groups"), dict):
        raise ValueError(f"Reading groups file must contain a 'groups' mapping: {path}")

    groups: dict[str, ReadingGroup] = {}
    for name, item in data["groups"].items():
        if not isinstance(item, dict):
            raise ValueError(f"Reading group {name!r} in {path} must be a mapping")
        patterns = item.get("parts", [])
        flex = item.get("flex", [])
        if not isinstance(patterns, list) or not all(isinstance(p, str) for p in patterns):
            raise ValueError(f"Reading group {name!r}: 'parts' must be a list of strings")
        if not isinstance(flex, list) or not all(isinstance(t, str) and "{n}" in t for t in flex):
            raise ValueError(
                f"Reading group {name!r}: 'flex' must be a list of templates containing {{n}}"
            )
        groups[name] = ReadingGroup(
            name=name,
            label=str(item.get("label", name)),
            patterns=tuple(patterns),
            flex=tuple(flex),
        )
    return groups


def is_flex(entry: str) -> bool:
    return FLEX_RE.match(entry.strip()) is not None


def expand_entry(
    entry: str,
    reads: list[str],
    groups: dict[str, ReadingGroup],
    context: str,
) -> list[str]:
    """
    Expand one prefer/compromise entry into concrete part ids.

    "alto_sax_1"        -> ["alto_sax_1"]
    "flex 3"            -> part 3 in every group the chair reads, in `reads` order
    "flex 3 c_bass"     -> part 3 in the named group only
    """
    m = FLEX_RE.match(entry.strip())
    if not m:
        return [entry.strip()]

    n, only = m.group(1), m.group(2)
    if only is not None:
        if only not in groups:
            raise ValueError(f"{context}: unknown reading group {only!r} in {entry!r}")
        names = [only]
    else:
        if not reads:
            raise ValueError(f"{context}: {entry!r} needs the chair to list 'reads'")
        names = reads

    ids: list[str] = []
    for name in names:
        if name not in groups:
            raise ValueError(f"{context}: unknown reading group {name!r}")
        for template in groups[name].flex:
            part_id = template.replace("{n}", n)
            if part_id not in ids:
                ids.append(part_id)
    return ids


def in_group(part_id: str, group: ReadingGroup) -> bool:
    """True if part_id belongs to the group, or is one of its flex parts."""
    if any(fnmatchcase(part_id, pattern) for pattern in group.patterns):
        return True
    return any(re.fullmatch(re.escape(template).replace(r"\{n\}", r"\d+"), part_id)
               for template in group.flex)


def can_read(part_id: str, reads: list[str], groups: dict[str, ReadingGroup]) -> bool:
    """True if part_id belongs to (or is a flex part of) any group in reads."""
    return any(name in groups and in_group(part_id, groups[name]) for name in reads)


UNGROUPED_HEADING = "Parts outside every reading group (no chair will get these automatically):"


def ungrouped_parts(
    parts: list[dict],
    groups: dict[str, ReadingGroup],
) -> list[tuple[str, str]]:
    """
    (label, id) for piece parts that no reading group covers. No chair can be
    given these automatically; they need an assignment, a group entry or a
    clearer label (e.g. "Part 1 in C TC" rather than "Part 1 in C").
    """
    if not groups:
        return []
    names = list(groups)
    return [
        (p.get("label", p["id"]), p["id"])
        for p in parts
        if isinstance(p, dict) and isinstance(p.get("id"), str)
        and not can_read(p["id"], names, groups)
    ]
