"""
Part matching and report generation for BandLibrary.
"""

from __future__ import annotations

from .models import EnsemblePart, MatchResult, Piece, assigned_ids


def match_part(piece: Piece, ensemble_part: EnsemblePart) -> MatchResult:
    """
    Match an ensemble part against a piece.
    Returns a MatchResult with match_reason of "assignment", "direct",
    "fallback" (a preferred substitute), "compromise", "all" (a "takes: all"
    chair's parts), or None (missing).
    """
    # 1. Piece-specific assignment override (one part, or a list of parts)
    if ensemble_part.id in piece.assignments:
        assigned = assigned_ids(piece.assignments[ensemble_part.id])
        return MatchResult(
            requested_id=ensemble_part.id,
            requested_label=ensemble_part.label,
            piece_slug=piece.slug,
            piece_title=piece.title,
            matched_id=assigned[0],
            match_reason="assignment",
            matched_ids=assigned,
        )

    # A "takes: all" chair (e.g. Percussion) gets every part it reads,
    # in the order they appear in the PDF
    if ensemble_part.takes_all:
        taken = tuple(p.id for p in sorted(
            (p for p in piece.parts_by_id.values() if ensemble_part.reads_part(p.id)),
            key=lambda p: (p.start_page, p.end_page)))
        return MatchResult(
            requested_id=ensemble_part.id,
            requested_label=ensemble_part.label,
            piece_slug=piece.slug,
            piece_title=piece.title,
            matched_id=taken[0] if taken else None,
            match_reason="all" if taken else None,
            matched_ids=taken,
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

    # 3. Preferred substitutes, then compromises
    for reason, candidates in (
        ("fallback", ensemble_part.prefer),
        ("compromise", ensemble_part.compromise),
    ):
        for candidate_id in candidates:
            if candidate_id in piece.parts_by_id:
                return MatchResult(
                    requested_id=ensemble_part.id,
                    requested_label=ensemble_part.label,
                    piece_slug=piece.slug,
                    piece_title=piece.title,
                    matched_id=candidate_id,
                    match_reason=reason,
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
                    f"  {result.piece_slug} -> {', '.join(result.matched_ids)} (assignment)"
                )
            elif result.match_reason == "all":
                report_lines.append(
                    f"  {result.piece_slug} -> {', '.join(result.matched_ids)}"
                )
            elif result.match_reason == "fallback":
                report_lines.append(
                    f"  {result.piece_slug} -> {result.matched_id} (fallback)"
                )
            elif result.match_reason == "compromise":
                report_lines.append(
                    f"  {result.piece_slug} -> {result.matched_id} (compromise)"
                )
                warning_lines.append(
                    f"NOTE: {result.piece_slug}: {ep.label} reads "
                    f"{result.matched_id} as a compromise — check it suits"
                )
            else:
                report_lines.append(f"  {result.piece_slug} -> {result.matched_id}")

        report_lines.append("")

    return report_lines, warning_lines
