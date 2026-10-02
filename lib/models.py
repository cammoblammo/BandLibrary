"""
Shared data models for BandLibrary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .reading_groups import in_group


TAKES_ONE = "one"   # a chair gets one part per piece (the usual case)
TAKES_ALL = "all"   # a chair gets every part it reads (e.g. Percussion)


@dataclass(frozen=True)
class EnsemblePart:
    id: str
    label: str
    prefer: list[str]                       # expanded part ids, best first
    compromise: list[str] = field(default_factory=list)
    reads: list[str] = field(default_factory=list)
    prefer_spec: list[str] = field(default_factory=list)      # as written,
    compromise_spec: list[str] = field(default_factory=list)  # e.g. "flex 3"
    takes: str = TAKES_ONE
    # The reading groups named in `reads`, for "takes: all" matching
    read_groups: tuple = ()

    @property
    def fallback(self) -> list[str]:
        """Every substitute in matching order: preferred, then compromises."""
        return self.prefer + self.compromise

    @property
    def takes_all(self) -> bool:
        return self.takes == TAKES_ALL

    def reads_part(self, part_id: str) -> bool:
        """True if part_id is in one of the reading groups this chair reads."""
        return any(in_group(part_id, group) for group in self.read_groups)


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
    # chair id -> a part id, or a tuple of part ids (for a "takes: all" chair)
    assignments: dict[str, str | tuple[str, ...]]


def assigned_ids(value: str | tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    """An assignment's part ids, whether it names one part or several."""
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(value)


@dataclass(frozen=True)
class MatchResult:
    requested_id: str
    requested_label: str
    piece_slug: str
    piece_title: str
    matched_id: str | None    # the (first) part the chair gets, or None
    # "assignment", "direct", "fallback", "compromise", "all", or None (missing)
    match_reason: str | None
    # Every part the chair gets, in booklet order. One part for most chairs;
    # several for a "takes: all" chair or a list assignment.
    matched_ids: tuple[str, ...] = ()

    def __post_init__(self):
        if not self.matched_ids and self.matched_id is not None:
            object.__setattr__(self, "matched_ids", (self.matched_id,))
        elif self.matched_ids and self.matched_id is None:
            object.__setattr__(self, "matched_id", self.matched_ids[0])


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warning(self, msg: str) -> None:
        self.warnings.append(msg)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0
