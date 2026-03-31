#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required. Install it with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


class BookletBuildError(Exception):
    """Base exception for booklet build failures."""


@dataclass(frozen=True)
class EnsemblePart:
    id: str
    label: str
    fallback: list[str]


@dataclass(frozen=True)
class Piece:
    slug: str
    title: str
    part_ids: set[str]


@dataclass(frozen=True)
class MatchResult:
    requested_id: str
    requested_label: str
    piece_slug: str
    piece_title: str
    matched_id: str | None
    fallback_used: bool


def load_yaml_file(path: Path) -> dict:
    if not path.exists():
        raise BookletBuildError(f"YAML file not found: {path}")
    if not path.is_file():
        raise BookletBuildError(f"Path is not a file: {path}")

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise BookletBuildError(f"Failed to parse YAML file {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise BookletBuildError(f"Expected a YAML mapping at top level in {path}")

    return data


def load_ensemble(path: Path) -> tuple[str, list[EnsemblePart]]:
    data = load_yaml_file(path)

    ensemble = data.get("ensemble")
    parts = data.get("parts")

    if not isinstance(ensemble, dict):
        raise BookletBuildError(f"Missing or invalid 'ensemble' section in {path}")
    if not isinstance(parts, list):
        raise BookletBuildError(f"Missing or invalid 'parts' section in {path}")

    ensemble_name = ensemble.get("name")
    if not isinstance(ensemble_name, str) or not ensemble_name.strip():
        raise BookletBuildError(f"Missing or invalid ensemble.name in {path}")

    loaded_parts: list[EnsemblePart] = []
    seen_ids: set[str] = set()

    for index, item in enumerate(parts):
        if not isinstance(item, dict):
            raise BookletBuildError(f"parts[{index}] in {path} must be a mapping")

        part_id = item.get("id")
        label = item.get("label")
        fallback = item.get("fallback", [])

        if not isinstance(part_id, str) or not part_id.strip():
            raise BookletBuildError(f"parts[{index}].id in {path} must be a non-empty string")
        if not isinstance(label, str) or not label.strip():
            raise BookletBuildError(f"parts[{index}].label in {path} must be a non-empty string")
        if not isinstance(fallback, list) or not all(isinstance(x, str) for x in fallback):
            raise BookletBuildError(f"parts[{index}].fallback in {path} must be a list of strings")

        if part_id in seen_ids:
            raise BookletBuildError(f"Duplicate ensemble part id {part_id!r} in {path}")
        seen_ids.add(part_id)

        loaded_parts.append(
            EnsemblePart(
                id=part_id,
                label=label,
                fallback=fallback,
            )
        )

        for part in loaded_parts:
            if part.id in part.fallback:
                raise BookletBuildError(
                f"Ensemble part {part.id!r} in {path} includes itself in fallback"
                )

    return ensemble_name, loaded_parts


def load_piece(library_dir: Path, slug: str) -> Piece:
    piece_dir = library_dir / slug
    piece_yaml = piece_dir / f"{slug}.yaml"

    data = load_yaml_file(piece_yaml)

    piece = data.get("piece")
    parts = data.get("parts")

    if not isinstance(piece, dict):
        raise BookletBuildError(f"Missing or invalid 'piece' section in {piece_yaml}")
    if not isinstance(parts, list):
        raise BookletBuildError(f"Missing or invalid 'parts' section in {piece_yaml}")

    title = piece.get("title")
    if not isinstance(title, str) or not title.strip():
        raise BookletBuildError(f"Missing or invalid piece.title in {piece_yaml}")

    part_ids: set[str] = set()

    for index, item in enumerate(parts):
        if not isinstance(item, dict):
            raise BookletBuildError(f"parts[{index}] in {piece_yaml} must be a mapping")

        part_id = item.get("id")
        if not isinstance(part_id, str) or not part_id.strip():
            raise BookletBuildError(f"parts[{index}].id in {piece_yaml} must be a non-empty string")

        if part_id in part_ids:
            raise BookletBuildError(f"Duplicate piece part id {part_id!r} in {piece_yaml}")
        part_ids.add(part_id)

    return Piece(
        slug=slug,
        title=title,
        part_ids=part_ids,
    )


def match_part(piece: Piece, ensemble_part: EnsemblePart) -> MatchResult:
    if ensemble_part.id in piece.part_ids:
        return MatchResult(
            requested_id=ensemble_part.id,
            requested_label=ensemble_part.label,
            piece_slug=piece.slug,
            piece_title=piece.title,
            matched_id=ensemble_part.id,
            fallback_used=False,
        )

    for fallback_id in ensemble_part.fallback:
        if fallback_id in piece.part_ids:
            return MatchResult(
                requested_id=ensemble_part.id,
                requested_label=ensemble_part.label,
                piece_slug=piece.slug,
                piece_title=piece.title,
                matched_id=fallback_id,
                fallback_used=True,
            )

    return MatchResult(
        requested_id=ensemble_part.id,
        requested_label=ensemble_part.label,
        piece_slug=piece.slug,
        piece_title=piece.title,
        matched_id=None,
        fallback_used=False,
    )


def build_report(
    *,
    ensemble_name: str,
    ensemble_parts: list[EnsemblePart],
    pieces: list[Piece],
) -> tuple[list[str], list[str]]:
    report_lines: list[str] = []
    warning_lines: list[str] = []

    report_lines.append(f"Ensemble: {ensemble_name}")
    report_lines.append("")

    for ensemble_part in ensemble_parts:
        report_lines.append(f"{ensemble_part.label}:")
        missing_for_this_part: list[str] = []

        for piece in pieces:
            result = match_part(piece, ensemble_part)

            if result.matched_id is None:
                report_lines.append(f"  {piece.slug} -> [missing]")
                missing_for_this_part.append(piece.slug)
                warning_lines.append(
                    f"WARNING: {piece.slug} has no matching part for {ensemble_part.label}"
                )
            elif result.fallback_used:
                report_lines.append(
                    f"  {piece.slug} -> {result.matched_id} (fallback)"
                )
            else:
                report_lines.append(
                    f"  {piece.slug} -> {result.matched_id}"
                )

        report_lines.append("")

    return report_lines, warning_lines


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Dry-run booklet builder for the band library."
    )
    parser.add_argument(
        "--ensemble",
        type=Path,
        required=True,
        help="Path to the ensemble YAML file.",
    )
    parser.add_argument(
        "--library",
        type=Path,
        default=Path("library"),
        help='Library root directory (default: "library").',
    )
    parser.add_argument(
        "pieces",
        nargs="+",
        help="Piece slugs to include, in booklet order.",
    )
    return parser


def main() -> int:
    parser = build_argument_parser()
    args = parser.parse_args()

    try:
        ensemble_name, ensemble_parts = load_ensemble(args.ensemble)
        pieces = [load_piece(args.library, slug) for slug in args.pieces]
        report_lines, warning_lines = build_report(
            ensemble_name=ensemble_name,
            ensemble_parts=ensemble_parts,
            pieces=pieces,
        )
    except BookletBuildError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: unexpected failure: {exc}", file=sys.stderr)
        return 1

    print("\n".join(report_lines))

    if warning_lines:
        print("Warnings:", file=sys.stderr)
        for line in warning_lines:
            print(line, file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
