"""
Part matching and report generation for BandLibrary.
"""

from __future__ import annotations

from .models import EnsemblePart, MatchResult, Piece


def match_part(piece: Piece, ensemble_part: EnsemblePart) -> MatchResult:
    """
    Match an ensemble part against a piece.
    Returns a MatchResult with match_reason of "assignment", "direct",
    "fallback", or None (missing).
    """
    # 1. Piece-specific assignment override
    if ensemble_part.id in piece.assignments:
        assigned_id = piece.assignments[ensemble_part.id]
        return MatchResult(
            requested_id=ensemble_part.id,
            requested_label=ensemble_part.label,
            piece_slug=piece.slug,
            piece_title=piece.title,
            matched_id=assigned_id,
            match_reason="assignment",
        )

    # 2. Direct match
    if ensemble_part.id in piece.parts_by_id:
        return MatchResult(
            requested_id=ensemble_part.id,
            requested_label=ensemble_part.label,
            piece_slug=piece.slug,
            piece_title=piece.title,
            matched_id=ensemble_part.id,
            match_reason="direct",
        )

    # 3. Fallback
    for fallback_id in ensemble_part.fallback:
        if fallback_id in piece.parts_by_id:
            return MatchResult(
                requested_id=ensemble_part.id,
                requested_label=ensemble_part.label,
                piece_slug=piece.slug,
                piece_title=piece.title,
                matched_id=fallback_id,
                match_reason="fallback",
            )

    # 4. Missing
    return MatchResult(
        requested_id=ensemble_part.id,
        requested_label=ensemble_part.label,
        piece_slug=piece.slug,
        piece_title=piece.title,
        matched_id=None,
        match_reason=None,
    )


def build_match_plan(
    ensemble_parts: list[EnsemblePart],
    pieces: list[Piece],
) -> dict[str, list[MatchResult]]:
    """
    Build a complete match plan: for each ensemble part, a list of
    MatchResults across all pieces (in order).
    """
    return {
        ep.id: [match_part(piece, ep) for piece in pieces]
        for ep in ensemble_parts
    }


def build_report(
    ensemble_name: str,
    ensemble_parts: list[EnsemblePart],
    pieces: list[Piece],
    grouped_matches: dict[str, list[MatchResult]],
) -> tuple[list[str], list[str]]:
    """
    Build a human-readable report from a match plan.
    Returns (report_lines, warning_lines).
    """
    report_lines: list[str] = []
    warning_lines: list[str] = []

    report_lines.append(f"Ensemble: {ensemble_name}")
    report_lines.append("")

    for ep in ensemble_parts:
        report_lines.append(f"{ep.label}:")

        for result in grouped_matches[ep.id]:
            if result.matched_id is None:
                report_lines.append(f"  {result.piece_slug} -> [missing]")
                warning_lines.append(
                    f"WARNING: {result.piece_slug} has no matching part for {ep.label}"
                )
            elif result.match_reason == "assignment":
                report_lines.append(
                    f"  {result.piece_slug} -> {result.matched_id} (assignment)"
                )
            elif result.match_reason == "fallback":
                report_lines.append(
                    f"  {result.piece_slug} -> {result.matched_id} (fallback)"
                )
            else:
                report_lines.append(f"  {result.piece_slug} -> {result.matched_id}")

        report_lines.append("")

    return report_lines, warning_lines
