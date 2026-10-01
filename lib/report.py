"""
Fallback and assignment consistency analysis for BandBook.

Builds a read-only picture of how each ensemble's chairs resolve against
the library, and flags inconsistencies in ensembles, pieces and assignments.
"""

from __future__ import annotations

import difflib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .library import list_pieces, load_ensemble, load_piece
from .matcher import match_part
from .models import EnsemblePart, MatchResult, Piece
from .reading_groups import default_groups_path, is_flex, load_reading_groups
from .validator import check_readability

CLEF_TOKENS = {"tc", "bc"}
KEY_TOKENS = {"c", "bb", "eb", "f", "g", "d", "a", "ab", "db"}


@dataclass(frozen=True)
class Finding:
    severity: str  # "warning" or "info"
    category: str
    message: str
    ensemble: str | None = None


@dataclass
class EnsembleReport:
    key: str  # file stem, e.g. "serscb"
    name: str
    band: str
    parts: list[EnsemblePart]
    # grid[chair_id][piece_slug] -> MatchResult
    grid: dict[str, dict[str, MatchResult]]
    counts: Counter = field(default_factory=Counter)


@dataclass
class Report:
    pieces: list[Piece]
    load_errors: list[str]
    ensembles: list[EnsembleReport]
    findings: list[Finding]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tokens(part_id: str) -> list[str]:
    """Split an id into comparable tokens, ignoring 'in' and plural 's'."""
    out = []
    for tok in part_id.split("_"):
        if tok == "in" or not tok:
            continue
        if tok.isalpha() and len(tok) > 3 and tok.endswith("s"):
            tok = tok[:-1]
        out.append(tok)
    return out


def _is_minor(tok: str) -> bool:
    """Tokens that legitimately distinguish parts: numbers, keys and clefs."""
    return any(c.isdigit() for c in tok) or tok in CLEF_TOKENS or tok in KEY_TOKENS


def _possible_duplicate(a: str, b: str) -> bool:
    """Heuristic for ids that probably name the same part (typos, variants)."""
    ta, tb = _tokens(a), _tokens(b)
    if ta == tb:
        return True
    diff = set(ta) ^ set(tb)
    if diff and all(_is_minor(t) for t in diff):
        return False
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.9


def _strip_number(part_id: str) -> str:
    return "_".join(t for t in part_id.split("_") if not t.isdigit())


def _same_chair_different_name(a: str, b: str) -> bool:
    """
    True when one id is the unnumbered form of the other (flute vs flute_1).
    Ids that both carry a number (clarinet_1 vs clarinet_2) are different chairs.
    """
    if a == b or _strip_number(a) != _strip_number(b):
        return False
    return (_strip_number(a) == a) != (_strip_number(b) == b)


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def build_report(library: Path, ensemble_paths: list[Path]) -> Report:
    pieces: list[Piece] = []
    load_errors: list[str] = []
    for slug in list_pieces(library):
        try:
            pieces.append(load_piece(library, slug))
        except Exception as e:
            load_errors.append(f"{slug}: {e}")

    findings: list[Finding] = []
    ensembles: list[EnsembleReport] = []

    library_ids: Counter = Counter()
    for piece in pieces:
        library_ids.update(piece.parts_by_id.keys())

    for path in ensemble_paths:
        name, band, parts = load_ensemble(path)
        key = path.stem
        grid: dict[str, dict[str, MatchResult]] = {}
        counts: Counter = Counter()
        for ep in parts:
            grid[ep.id] = {}
            for piece in pieces:
                result = match_part(piece, ep)
                grid[ep.id][piece.slug] = result
                counts[result.match_reason or "missing"] += 1
        ensembles.append(EnsembleReport(key, name, band, parts, grid, counts))
        findings.extend(_ensemble_findings(key, parts, pieces, grid, library_ids))
        groups = load_reading_groups(default_groups_path(path))
        for problem in check_readability(parts, groups):
            findings.append(Finding("warning", "Chair lists a part it can't read", problem, key))

    findings.extend(_library_findings(library_ids))
    findings.extend(_assignment_findings(pieces, ensembles))
    findings.extend(_cross_ensemble_findings(ensembles))

    return Report(pieces, load_errors, ensembles, findings)


def _ensemble_findings(
    key: str,
    parts: list[EnsemblePart],
    pieces: list[Piece],
    grid: dict[str, dict[str, MatchResult]],
    library_ids: Counter,
) -> list[Finding]:
    out: list[Finding] = []

    for ep in parts:
        # Substitutes naming parts that no piece in the library contains
        for fb in ep.prefer_spec + ep.compromise_spec:
            if not is_flex(fb) and fb not in library_ids:
                out.append(Finding(
                    "info", "Substitute not in any piece yet",
                    f"{ep.label}: '{fb}' isn't in any piece yet. That's fine if you "
                    f"expect one; otherwise check the spelling.",
                    key,
                ))

        # Fallbacks to another chair: matched by part id, not followed as a chain
        # Missing although the piece has the unnumbered/numbered form of this chair
        near_misses = []
        for slug, r in grid[ep.id].items():
            if r.matched_id is not None:
                continue
            piece = next(p for p in pieces if p.slug == slug)
            near = [pid for pid in piece.parts_by_id if _same_chair_different_name(ep.id, pid)]
            if near:
                near_misses.append(f"{slug} ({', '.join(near)})")
        if near_misses:
            out.append(Finding(
                "warning", "Missing although a matching part exists",
                f"{ep.label} gets nothing in {len(near_misses)} piece(s) that have a "
                f"part with the same instrument name: {'; '.join(near_misses)}",
                key,
            ))

        # Chairs with nothing to fall back on that are missing somewhere
        missing = [s for s, r in grid[ep.id].items() if r.matched_id is None]
        if missing and not ep.fallback:
            out.append(Finding(
                "warning", "Missing with no fallback",
                f"{ep.label} has no fallbacks and gets nothing in "
                f"{len(missing)} piece(s): {', '.join(missing)}",
                key,
            ))

    # Compromises in use, per chair
    for ep in parts:
        used = [
            f"{slug} ({r.matched_id})" for slug, r in grid[ep.id].items()
            if r.match_reason == "compromise"
        ]
        if used:
            out.append(Finding(
                "info", "Compromise in use",
                f"{ep.label} reads a compromise part in {len(used)} piece(s): "
                f"{'; '.join(used)}",
                key,
            ))

    # Piece parts that no chair in this ensemble ever reads
    used: dict[str, set[str]] = defaultdict(set)
    for results in grid.values():
        for slug, r in results.items():
            if r.matched_id:
                used[slug].add(r.matched_id)
    unused: dict[str, list[str]] = defaultdict(list)
    for piece in pieces:
        for pid in piece.parts_by_id:
            if pid not in used[piece.slug]:
                unused[pid].append(piece.slug)
    for pid, slugs in sorted(unused.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        # Only report parts that are common enough to matter
        if len(slugs) >= 2:
            out.append(Finding(
                "info", "Part never used (2+ pieces)",
                f"'{pid}' is not read by any chair in {len(slugs)} piece(s)",
                key,
            ))

    return out


def _library_findings(library_ids: Counter) -> list[Finding]:
    out: list[Finding] = []
    ids = sorted(library_ids)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if _possible_duplicate(a, b):
                out.append(Finding(
                    "warning", "Possible duplicate part name",
                    f"'{a}' ({library_ids[a]} piece(s)) and "
                    f"'{b}' ({library_ids[b]} piece(s)) may name the same part",
                ))
    return out


def _assignment_findings(
    pieces: list[Piece],
    ensembles: list[EnsembleReport],
) -> list[Finding]:
    out: list[Finding] = []
    all_chairs = {ep.id for e in ensembles for ep in e.parts}

    for piece in pieces:
        unassigned = Piece(
            slug=piece.slug, title=piece.title, pdf_path=piece.pdf_path,
            parts_by_id=piece.parts_by_id, assignments={},
        )
        for chair_id, source_id in piece.assignments.items():
            if chair_id not in all_chairs:
                out.append(Finding(
                    "warning", "Assignment for unknown chair",
                    f"{piece.slug}: '{chair_id}' ← '{source_id}' — no ensemble has "
                    f"a chair called '{chair_id}'",
                ))
                continue

            auto_results = []
            for e in ensembles:
                for ep in e.parts:
                    if ep.id == chair_id:
                        auto_results.append((e.key, match_part(unassigned, ep)))

            if all(r.matched_id == source_id for _, r in auto_results):
                out.append(Finding(
                    "info", "Redundant assignment",
                    f"{piece.slug}: '{chair_id}' ← '{source_id}' matches what the "
                    f"automatic rules already choose",
                ))
            for key, r in auto_results:
                if r.match_reason == "direct" and source_id != chair_id:
                    out.append(Finding(
                        "info", "Assignment overrides a direct match",
                        f"{piece.slug}: '{chair_id}' is assigned '{source_id}' although "
                        f"the piece has its own '{chair_id}' part",
                        key,
                    ))
    return out


def _cross_ensemble_findings(ensembles: list[EnsembleReport]) -> list[Finding]:
    out: list[Finding] = []
    for i, a in enumerate(ensembles):
        for b in ensembles[i + 1:]:
            a_parts = {ep.id: ep for ep in a.parts}
            b_parts = {ep.id: ep for ep in b.parts}
            for cid in sorted(a_parts.keys() & b_parts.keys()):
                fa, fb = a_parts[cid].fallback, b_parts[cid].fallback
                if fa != fb:
                    out.append(Finding(
                        "info", "Same chair, different fallbacks",
                        f"{a_parts[cid].label}: {a.name} → {', '.join(fa) or 'none'}; "
                        f"{b.name} → {', '.join(fb) or 'none'}",
                    ))
            pairs = [
                (x, y) for x in sorted(a_parts) for y in sorted(b_parts)
                if _same_chair_different_name(x, y)
                and x not in b_parts and y not in a_parts
            ]
            for x, y in pairs:
                out.append(Finding(
                    "warning", "Same chair, different name",
                    f"{a.name} calls it '{x}', {b.name} calls it '{y}' — assignments "
                    f"made for one band don't carry over to the other",
                ))
    return out
