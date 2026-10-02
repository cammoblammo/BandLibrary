"""
Compare detection with a hand-checked manual file.

The library's .manual.txt files are the answer key. Page ranges are what
detection is responsible for; names are compared by part ID, and will
differ wherever the owner chose a chair-friendly name (e.g. "Snare Drum"
mapped as aux perc), so treat name mismatches as information.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..manual import parse_manual_file
from .pages import Draft


@dataclass
class Score:
    slug: str
    page_count: int
    text_pages: int
    expected: int
    ranges_right: int = 0
    names_right: int = 0
    extra: int = 0
    differences: list[str] = field(default_factory=list)


def score_draft(slug: str, draft: Draft, manual_path: Path,
                aliases: dict[str, str]) -> Score:
    _, expected, _ = parse_manual_file(manual_path, aliases)
    found = {(p.start, p.end): p for p in draft.parts}
    expected_ranges = {tuple(e["pages"]) for e in expected}

    score = Score(slug, draft.page_count, draft.text_pages, len(expected))
    for e in expected:
        start, end = e["pages"]
        part = found.get((start, end))
        if part is None:
            score.differences.append(f"missed  {e['label']}: {start}-{end}")
            continue
        score.ranges_right += 1
        if part.part_id == e["id"]:
            score.names_right += 1
        else:
            score.differences.append(
                f"name    {part.label} ({part.part_id}) — expected "
                f"{e['label']} ({e['id']}) for {start}-{end}")
    for (start, end), part in found.items():
        if (start, end) not in expected_ranges:
            score.extra += 1
            score.differences.append(f"extra   {part.label}: {start}-{end}")
    return score
