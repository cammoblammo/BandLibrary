#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required. Install it with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    print("ERROR: pypdf is required. Install it with: pip install pypdf", file=sys.stderr)
    sys.exit(1)


class BookletBuildError(Exception):
    """Base exception for booklet build failures."""


@dataclass(frozen=True)
class EnsemblePart:
    id: str
    label: str
    fallback: list[str]


@dataclass(frozen=True)
class PiecePart:
    id: str
    label: str
    start_page: int
    end_page: int


@dataclass(frozen=True)
class Piece:
    slug: str
    title: str
    pdf_path: Path
    parts_by_id: dict[str, PiecePart]
    assignments: dict[str, str]


@dataclass(frozen=True)
class MatchResult:
    requested_id: str
    requested_label: str
    piece_slug: str
    piece_title: str
    matched_id: str | None
    match_reason: str | None  # "assignment", "direct", "fallback", or None


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

        loaded_parts.append(EnsemblePart(id=part_id, label=label, fallback=fallback))

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

    piece_meta = data.get("piece")
    parts = data.get("parts")
    assignments_raw = data.get("assignments", {})

    if not isinstance(piece_meta, dict):
        raise BookletBuildError(f"Missing or invalid 'piece' section in {piece_yaml}")
    if not isinstance(parts, list):
        raise BookletBuildError(f"Missing or invalid 'parts' section in {piece_yaml}")
    if not isinstance(assignments_raw, dict):
        raise BookletBuildError(f"Invalid 'assignments' section in {piece_yaml}: must be a mapping")

    title = piece_meta.get("title")
    source_pdf = piece_meta.get("source_pdf")

    if not isinstance(title, str) or not title.strip():
        raise BookletBuildError(f"Missing or invalid piece.title in {piece_yaml}")
    if not isinstance(source_pdf, str) or not source_pdf.strip():
        raise BookletBuildError(f"Missing or invalid piece.source_pdf in {piece_yaml}")

    pdf_path = piece_dir / source_pdf
    if not pdf_path.exists():
        raise BookletBuildError(f"Source PDF not found for piece {slug}: {pdf_path}")

    reader = PdfReader(str(pdf_path))
    total_pages = len(reader.pages)

    parts_by_id: dict[str, PiecePart] = {}

    for index, item in enumerate(parts):
        if not isinstance(item, dict):
            raise BookletBuildError(f"parts[{index}] in {piece_yaml} must be a mapping")

        part_id = item.get("id")
        label = item.get("label")
        pages = item.get("pages")

        if not isinstance(part_id, str) or not part_id.strip():
            raise BookletBuildError(f"parts[{index}].id in {piece_yaml} must be a non-empty string")
        if not isinstance(label, str) or not label.strip():
            raise BookletBuildError(f"parts[{index}].label in {piece_yaml} must be a non-empty string")
        if (
            not isinstance(pages, list)
            or len(pages) != 2
            or not all(isinstance(x, int) for x in pages)
        ):
            raise BookletBuildError(
                f"parts[{index}].pages in {piece_yaml} must be a two-element integer list"
            )

        start_page, end_page = pages

        if start_page <= 0 or end_page <= 0 or start_page > end_page:
            raise BookletBuildError(
                f"Invalid page range for part {part_id!r} in {piece_yaml}: {pages}"
            )

        if end_page > total_pages:
            raise BookletBuildError(
                f"Part {part_id!r} in piece {slug} references page {end_page}, "
                f"but PDF only has {total_pages} pages"
            )

        if part_id in parts_by_id:
            raise BookletBuildError(f"Duplicate piece part id {part_id!r} in {piece_yaml}")

        parts_by_id[part_id] = PiecePart(
            id=part_id,
            label=label,
            start_page=start_page,
            end_page=end_page,
        )

    assignments: dict[str, str] = {}
    for target_id, source_id in assignments_raw.items():
        if not isinstance(target_id, str) or not target_id.strip():
            raise BookletBuildError(
                f"Invalid assignment key in {piece_yaml}: assignment targets must be non-empty strings"
            )
        if not isinstance(source_id, str) or not source_id.strip():
            raise BookletBuildError(
                f"Invalid assignment value for {target_id!r} in {piece_yaml}: "
                f"assignment sources must be non-empty strings"
            )
        if source_id not in parts_by_id:
            raise BookletBuildError(
                f"Assignment for {target_id!r} in {piece_yaml} refers to unknown part id {source_id!r}"
            )
        assignments[target_id] = source_id

    return Piece(
        slug=slug,
        title=title,
        pdf_path=pdf_path,
        parts_by_id=parts_by_id,
        assignments=assignments,
    )


def match_part(piece: Piece, ensemble_part: EnsemblePart) -> MatchResult:
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

    # 3. Ensemble fallback
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


def build_report(
    *,
    ensemble_name: str,
    ensemble_parts: list[EnsemblePart],
    pieces: list[Piece],
) -> tuple[list[str], list[str], dict[str, list[MatchResult]]]:
    report_lines: list[str] = []
    warning_lines: list[str] = []
    grouped_matches: dict[str, list[MatchResult]] = {}

    report_lines.append(f"Ensemble: {ensemble_name}")
    report_lines.append("")

    for ensemble_part in ensemble_parts:
        report_lines.append(f"{ensemble_part.label}:")
        part_matches: list[MatchResult] = []

        for piece in pieces:
            result = match_part(piece, ensemble_part)
            part_matches.append(result)

            if result.matched_id is None:
                report_lines.append(f"  {piece.slug} -> [missing]")
                warning_lines.append(
                    f"WARNING: {piece.slug} has no matching part for {ensemble_part.label}"
                )
            elif result.match_reason == "assignment":
                report_lines.append(f"  {piece.slug} -> {result.matched_id} (assignment)")
            elif result.match_reason == "fallback":
                report_lines.append(f"  {piece.slug} -> {result.matched_id} (fallback)")
            else:
                report_lines.append(f"  {piece.slug} -> {result.matched_id}")

        grouped_matches[ensemble_part.id] = part_matches
        report_lines.append("")

    return report_lines, warning_lines, grouped_matches


def append_part_pages(writer: PdfWriter, piece: Piece, part: PiecePart) -> None:
    reader = PdfReader(str(piece.pdf_path))
    total_pages = len(reader.pages)

    if part.end_page > total_pages:
        raise BookletBuildError(
            f"Part {part.id!r} in piece {piece.slug} references page {part.end_page}, "
            f"but PDF only has {total_pages} pages"
        )

    for page_number in range(part.start_page, part.end_page + 1):
        writer.add_page(reader.pages[page_number - 1])


def generate_booklets(
    *,
    output_dir: Path,
    ensemble_parts: list[EnsemblePart],
    pieces_by_slug: dict[str, Piece],
    grouped_matches: dict[str, list[MatchResult]],
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_files: list[Path] = []

    for ensemble_part in ensemble_parts:
        writer = PdfWriter()
        matched_any = False

        for result in grouped_matches[ensemble_part.id]:
            if result.matched_id is None:
                continue

            piece = pieces_by_slug[result.piece_slug]
            part = piece.parts_by_id[result.matched_id]
            append_part_pages(writer, piece, part)
            matched_any = True

        if matched_any:
            output_path = output_dir / f"{ensemble_part.id}.pdf"
            with output_path.open("wb") as handle:
                writer.write(handle)
            generated_files.append(output_path)

    return generated_files


def create_zip_archive(output_dir: Path, files: list[Path], archive_stem: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    zip_path = output_dir / f"{archive_stem}-{timestamp}.zip"

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in files:
            zf.write(file_path, arcname=file_path.name)

    return zip_path


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build booklet PDFs for an ensemble from imported library pieces."
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
        "--output",
        type=Path,
        default=Path("output"),
        help='Output directory for generated booklet PDFs (default: "output").',
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
        pieces_by_slug = {piece.slug: piece for piece in pieces}

        report_lines, warning_lines, grouped_matches = build_report(
            ensemble_name=ensemble_name,
            ensemble_parts=ensemble_parts,
            pieces=pieces,
        )

        print("\n".join(report_lines))

        generated_files = generate_booklets(
            output_dir=args.output,
            ensemble_parts=ensemble_parts,
            pieces_by_slug=pieces_by_slug,
            grouped_matches=grouped_matches,
        )

        archive_stem = args.ensemble.stem
        zip_path = create_zip_archive(args.output, generated_files, archive_stem)

    except BookletBuildError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: unexpected failure: {exc}", file=sys.stderr)
        return 1

    if warning_lines:
        print("Warnings:", file=sys.stderr)
        for line in warning_lines:
            print(line, file=sys.stderr)

    print(f"Generated {len(generated_files)} booklet PDF(s) in {args.output}")
    print(f"Created archive: {zip_path}")

    print("Summary:")
    for ensemble_part in ensemble_parts:
        matches = grouped_matches[ensemble_part.id]
        total = len(matches)
        covered = sum(1 for match in matches if match.matched_id is not None)
        print(f"  {ensemble_part.id}: {covered}/{total} pieces")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
