"""
Reading, checking, writing and comparing bands for the Ensembles tab.

No Qt here. A band being edited is a BandSpec: the file's contents as
written (prefer/compromise entries such as "flex 3" unexpanded). It is
checked with the same rules as loading a file (`parse_ensemble`), and
written back in one standard layout.
"""

from __future__ import annotations

import copy
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .library import LibraryError, list_pieces, load_piece, load_yaml_file, parse_ensemble
from .matcher import match_part
from .models import TAKES_ALL, TAKES_ONE, EnsemblePart, MatchResult, Piece
from .reading_groups import ReadingGroup, can_read, expand_entry, is_flex
from .utils import default_normalise_part_id
from .validator import check_own_parts, check_readability

HEADER = """\
# Written by BandBook (Ensembles tab). Each chair:
#   reads:      reading groups (config/reading_groups.yaml) this chair can play
#   prefer:     good substitutes when the piece has no part for this chair, best first
#   compromise: readable but not ideal (range, style); used last and flagged in builds
#   takes: all  the chair gets every part it reads, in PDF order, instead of one
#               part (the Percussion chair: percussionists move between
#               instruments); a piece's assignment can list the parts instead
# "flex N" means part N of a flexible arrangement, in any group the chair reads.
"""


@dataclass
class ChairSpec:
    id: str
    label: str
    reads: list[str] = field(default_factory=list)
    prefer: list[str] = field(default_factory=list)
    compromise: list[str] = field(default_factory=list)
    takes: str = TAKES_ONE


@dataclass
class BandSpec:
    id: str          # file name stem, e.g. "serscb"
    name: str        # short name, e.g. "SERSCB"
    band: str        # name on booklet covers
    chairs: list[ChairSpec] = field(default_factory=list)


def suggest_id(label: str) -> str:
    """The ID a chair or band would get from its name: Tenor Horn -> tenor_horn."""
    return default_normalise_part_id(label)


# ---------------------------------------------------------------------------
# Reading and writing
# ---------------------------------------------------------------------------

def read_band(path: Path) -> BandSpec:
    data = load_yaml_file(path)
    meta = data.get("ensemble") or {}
    chairs = []
    for item in data.get("parts") or []:
        if not isinstance(item, dict):
            continue
        chairs.append(ChairSpec(
            id=str(item.get("id", "")),
            label=str(item.get("label", "")),
            reads=list(item.get("reads") or []),
            # Schema 1 "fallback" is read as "prefer"
            prefer=list(item.get("prefer", item.get("fallback")) or []),
            compromise=list(item.get("compromise") or []),
            takes=str(item.get("takes", TAKES_ONE)),
        ))
    return BandSpec(
        id=str(meta.get("id") or path.stem),
        name=str(meta.get("name") or path.stem),
        band=str(meta.get("band") or ""),
        chairs=chairs,
    )


def band_data(band: BandSpec) -> dict:
    """The band as file data, for `parse_ensemble`."""
    parts = []
    for c in band.chairs:
        item: dict = {"id": c.id, "label": c.label}
        if c.reads:
            item["reads"] = list(c.reads)
        if c.takes != TAKES_ONE:
            item["takes"] = c.takes
        if c.prefer:
            item["prefer"] = list(c.prefer)
        if c.compromise:
            item["compromise"] = list(c.compromise)
        parts.append(item)
    return {
        "schema_version": 2,
        "ensemble": {"id": band.id, "name": band.name, "band": band.band},
        "parts": parts,
    }


def _flow(value) -> str:
    """A YAML scalar or flow list on one line, quoted only where needed."""
    text = yaml.safe_dump([value] if not isinstance(value, list) else value,
                          default_flow_style=True, width=10**6, allow_unicode=True).strip()
    return text if isinstance(value, list) else text[1:-1]


def band_text(band: BandSpec) -> str:
    data = band_data(band)
    lines = ["schema_version: 2", "", "ensemble:"]
    for key in ("id", "name", "band"):
        lines.append(f"  {key}: {_flow(data['ensemble'][key])}")
    lines += ["", HEADER.rstrip("\n"), "", "parts:"]
    for item in data["parts"]:
        lines.append(f"  - id: {_flow(item['id'])}")
        for key in ("label", "reads", "takes", "prefer", "compromise"):
            if key in item:
                lines.append(f"    {key}: {_flow(item[key])}")
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def write_band(path: Path, band: BandSpec) -> None:
    path.write_text(band_text(band), encoding="utf-8")


# ---------------------------------------------------------------------------
# Checking
# ---------------------------------------------------------------------------

@dataclass
class BandCheck:
    errors: list[str] = field(default_factory=list)            # stop saving
    chair_errors: dict[int, list[str]] = field(default_factory=dict)
    chair_notes: dict[int, list[str]] = field(default_factory=dict)  # fine to save
    parts: list[EnsemblePart] | None = None                      # when it loads

    @property
    def ok(self) -> bool:
        return not self.errors and not any(self.chair_errors.values())


def check_band(band: BandSpec, groups: dict[str, ReadingGroup],
               other_bands: dict[str, BandSpec] | None = None) -> BandCheck:
    """
    Problems with a band, per chair where possible. The same rules as
    loading the file; anything that would stop it loading is an error.
    other_bands (id -> band) are used to say which chair IDs are shared.
    """
    result = BandCheck()

    def chair_error(i: int, message: str):
        result.chair_errors.setdefault(i, []).append(message)

    if not band.name.strip():
        result.errors.append("The band needs a short name.")
    if not band.chairs:
        result.errors.append("The band has no chairs.")

    ids = Counter(c.id for c in band.chairs)
    for i, c in enumerate(band.chairs):
        if not c.label.strip():
            chair_error(i, "The chair needs a name.")
        if not c.id.strip():
            chair_error(i, "The chair needs an ID.")
        elif c.id != suggest_id(c.id):
            chair_error(i, f"IDs use lowercase letters, digits and _ (e.g. {suggest_id(c.id)}).")
        elif ids[c.id] > 1:
            chair_error(i, f"Another chair has the ID {c.id!r}.")
        for name in c.reads:
            if name not in groups:
                chair_error(i, f"Unknown reading group {name!r}.")
        if c.takes == TAKES_ALL:
            if not c.reads:
                chair_error(i, "A chair that gets every part it reads needs a reading group.")
            if c.prefer or c.compromise:
                chair_error(i, "A chair that gets every part it reads doesn't use "
                               "Prefers or Compromises: remove them.")
            continue
        for kind, specs in (("Prefers", c.prefer), ("Compromises", c.compromise)):
            for spec in specs:
                if spec == c.id:
                    chair_error(i, f"{kind} lists the chair's own part ({spec}).")
                elif is_flex(spec):
                    try:
                        expand_entry(spec, c.reads, groups, c.label)
                    except ValueError:
                        chair_error(i, f"{kind}: '{spec}' needs the chair to read a group.")
                elif c.reads and not can_read(spec, c.reads, groups):
                    chair_error(i, f"{kind}: ⚠ '{spec}' isn't in what this chair reads.")

    # Loading the whole band catches anything the checks above missed
    if result.ok:
        try:
            _, _, parts = parse_ensemble(band_data(band), groups, f"band {band.name}")
        except LibraryError as exc:
            result.errors.append(str(exc))
        else:
            result.parts = parts
            # (check_readability repeats the per-chair test above, as a safety net)
            result.errors.extend(check_readability(parts, groups))
            for i, ep in enumerate(parts):
                for note in check_own_parts([ep], groups):
                    result.chair_notes.setdefault(i, []).append(
                        note.split(": ", 1)[1][:1].upper() + note.split(": ", 1)[1][1:] + ".")

    for i, c in enumerate(band.chairs):
        sharing = [b.name for b_id, b in (other_bands or {}).items()
                   if b_id != band.id and any(o.id == c.id for o in b.chairs)]
        if sharing:
            result.chair_notes.setdefault(i, []).append(
                f"{', '.join(sharing)} also has a chair with this ID, so they share "
                f"its assignments.")
    return result


def readable_library_parts(library: Path, chair: ChairSpec,
                           groups: dict[str, ReadingGroup]) -> list[tuple[str, int]]:
    """Part IDs in the library this chair can read, with how many pieces have each."""
    counts: Counter = Counter()
    for piece in load_pieces(library):
        counts.update(piece.parts_by_id.keys())
    return sorted(((pid, n) for pid, n in counts.items()
                   if pid != chair.id and can_read(pid, chair.reads, groups)),
                  key=lambda x: (-x[1], x[0]))


# ---------------------------------------------------------------------------
# What changes
# ---------------------------------------------------------------------------

def load_pieces(library: Path) -> list[Piece]:
    pieces = []
    for slug in list_pieces(library):
        try:
            pieces.append(load_piece(library, slug))
        except Exception:
            pass        # the library check reports broken pieces
    return pieces


@dataclass
class Change:
    chair: str               # chair label
    piece: str               # piece title
    before: MatchResult | None
    after: MatchResult | None
    kind: str                # "filled", "lost", "changed", "compromise", "new chair", "removed chair"


def _describe(r: MatchResult | None) -> str:
    if r is None:
        return "(no chair)"
    if not r.matched_ids:
        return "nothing"
    text = ", ".join(r.matched_ids)
    if r.match_reason in ("compromise", "assignment"):
        text += f" ({r.match_reason})"
    return text


def describe_change(change: Change) -> str:
    return f"{change.chair} — {change.piece}: {_describe(change.before)} → {_describe(change.after)}"


def compare(pieces: list[Piece], before: list[EnsemblePart] | None,
            after: list[EnsemblePart]) -> list[Change]:
    """
    What every chair gets in every piece, before and after. For a new band
    (before None) every chair is new; its results are listed as "new chair".
    """
    old = {ep.id: ep for ep in before or []}
    new = {ep.id: ep for ep in after}
    changes: list[Change] = []
    for ep in after:
        for piece in pieces:
            a = match_part(piece, ep)
            if ep.id not in old:
                changes.append(Change(ep.label, piece.title, None, a, "new chair"))
                continue
            b = match_part(piece, old[ep.id])
            if (a.matched_ids, a.match_reason) == (b.matched_ids, b.match_reason):
                continue
            if not b.matched_ids:
                kind = "filled"
            elif not a.matched_ids:
                kind = "lost"
            elif a.matched_ids == b.matched_ids:
                kind = "compromise" if a.match_reason == "compromise" else "changed"
            else:
                kind = "changed"
            changes.append(Change(ep.label, piece.title, b, a, kind))
    for ep in before or []:
        if ep.id not in new:
            changes.append(Change(ep.label, "every piece", None, None, "removed chair"))
    return changes


def summarise(changes: list[Change]) -> str:
    counts = Counter(c.kind for c in changes)
    words = {"filled": ("gap filled", "gaps filled"),
             "changed": ("part changed", "parts changed"),
             "lost": ("part lost", "parts lost"),
             "compromise": ("now flagged as compromise", "now flagged as compromise"),
             "new chair": ("result for a new chair", "results for new chairs"),
             "removed chair": ("chair removed", "chairs removed")}
    parts = [f"{counts[k]} {words[k][counts[k] != 1]}" for k in words if counts[k]]
    return ", ".join(parts) if parts else "No chair gets anything different."


# ---------------------------------------------------------------------------
# Bands and assignments on disk
# ---------------------------------------------------------------------------

def copy_band(source: BandSpec, new_id: str, name: str, band_name: str) -> BandSpec:
    """A copy with a new identity; chair IDs (and so assignments) are kept."""
    new = copy.deepcopy(source)
    new.id, new.name, new.band = new_id, name, band_name
    return new


def bands_using_chair(ensembles_dir: Path, chair_id: str, except_band: str) -> list[str]:
    out = []
    for path in sorted(ensembles_dir.glob("*.yaml")):
        if path.stem == except_band:
            continue
        try:
            if any(c.id == chair_id for c in read_band(path).chairs):
                out.append(path.stem)
        except LibraryError:
            continue
    return out


def copy_assignments(library: Path, old_id: str, new_id: str, keep_old: bool) -> list[Path]:
    """
    Give chair new_id the assignments chair old_id has in every piece.
    old_id's are removed unless keep_old (another band still uses it).
    Returns the piece files changed.
    """
    changed = []
    for slug in list_pieces(library):
        path = library / slug / f"{slug}.yaml"
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        assignments = (data or {}).get("assignments") or {}
        if old_id not in assignments or new_id in assignments:
            continue
        assignments[new_id] = assignments[old_id]
        if not keep_old:
            del assignments[old_id]
        data["assignments"] = assignments
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        changed.append(path)
    return changed


def pieces_assigning(library: Path, chair_id: str) -> list[str]:
    """Slugs of pieces with an assignment for this chair."""
    return [p.slug for p in load_pieces(library) if chair_id in p.assignments]
