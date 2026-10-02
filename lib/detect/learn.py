"""
Learn part names the owner corrects in a Detect Parts draft.

After an import, each imported part is matched to the draft part on the
same pages. Where the owner changed the name to one that resolves to a
different part ID, BandBook offers to remember the printed name as an
alias, so the same publisher's next piece needs no correcting. The alias
keeps the printed name (it becomes the part's label next time) and points
it at the ID the owner chose.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..manual import FLEX_ID_RE
from ..utils import canonicalise_alias_key
from .pages import DraftPart

LEARNED_HEADING = "  # Learned from imports (Detect Parts drafts you corrected)"


@dataclass
class Suggestion:
    printed: str            # the name Detect Parts wrote, e.g. "Drum Set"
    part_id: str            # the ID the owner's name resolves to, e.g. drum_kit
    final_label: str        # the name the owner imported, e.g. "Drum kit"
    existing: str | None    # the ID this name already means, if any
    tick: bool              # offered ticked


def suggestions(draft: list[DraftPart], imported: list[dict],
                aliases: dict[str, str]) -> list[Suggestion]:
    """
    imported: the parts as imported, as parse_manual_file returns them
    (dicts with label, id, pages). Only renames that change the part ID are
    offered; clefs added to "Part N in C" and the like are not, because
    they depend on the piece.
    """
    by_start = {p.start: p for p in draft}
    out: list[Suggestion] = []
    seen: set[str] = set()
    for part in imported:
        found = by_start.get(part["pages"][0])
        if found is None:
            continue
        key = canonicalise_alias_key(found.label)
        if (not key or key in seen or found.part_id == part["id"]
                or FLEX_ID_RE.fullmatch(part["id"]) or FLEX_ID_RE.fullmatch(found.part_id)):
            continue
        seen.add(key)
        existing = aliases.get(key)
        out.append(Suggestion(
            printed=found.label,
            part_id=part["id"],
            final_label=part["label"],
            existing=existing,
            tick=existing is None,      # changing what a name already means: unticked
        ))
    return out


def remember(aliases_path: Path, chosen: list[Suggestion]) -> int:
    """
    Add the chosen names to the aliases file, under a "learned" heading.
    A name that already had an alias is changed in place. Returns how many
    names were added or changed.
    """
    if not chosen:
        return 0
    lines = aliases_path.read_text(encoding="utf-8").rstrip("\n").split("\n")
    wanted = {canonicalise_alias_key(s.printed): s for s in chosen}

    # Change existing entries in place: every spelling of the name ("Drum
    # kit", "Drum Kit"), or the file would contradict itself
    changed: set[str] = set()
    in_aliases = False
    for i, line in enumerate(lines):
        if line.startswith("aliases:"):
            in_aliases = True
            continue
        stripped = line.strip()
        if not in_aliases or not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        name = stripped.rsplit(":", 1)[0].strip().strip('"').strip("'")
        key = canonicalise_alias_key(name)
        if key in wanted and wanted[key].existing is not None:
            lines[i] = f"  {json.dumps(name)}: {wanted[key].part_id}"
            changed.add(key)

    new = [s for key, s in wanted.items() if key not in changed]
    if new:
        if LEARNED_HEADING not in lines:
            lines += ["", LEARNED_HEADING]
        lines += [f"  {json.dumps(s.printed)}: {s.part_id}" for s in new]
    aliases_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(chosen)
