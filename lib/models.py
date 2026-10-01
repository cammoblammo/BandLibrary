"""
Shared data models for BandLibrary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class EnsemblePart:
    id: str
    label: str
    prefer: list[str]                       # expanded part ids, best first
    compromise: list[str] = field(default_factory=list)
    reads: list[str] = field(default_factory=list)
    prefer_spec: list[str] = field(default_factory=list)      # as written,
    compromise_spec: list[str] = field(default_factory=list)  # e.g. "flex 3"

    @property
    def fallback(self) -> list[str]:
        """Every substitute in matching order: preferred, then compromises."""
        return self.prefer + self.compromise


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
    match_reason: str | None  # "assignment", "direct", "fallback", "compromise", or None


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
