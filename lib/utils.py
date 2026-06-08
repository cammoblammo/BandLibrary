"""
Shared utility functions for BandLibrary.
"""

from __future__ import annotations

import re
import unicodedata


def slugify(text: str) -> str:
    """Convert text to a URL-safe slug (hyphens)."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    return text.strip("-")


def default_normalise_part_id(label: str) -> str:
    """Convert a part label to a canonical ID (underscores)."""
    return slugify(label).replace("-", "_")


def canonicalise_alias_key(label: str) -> str:
    """
    Normalise a label for alias lookup — tolerant of case,
    spacing, and punctuation differences.
    """
    text = unicodedata.normalize("NFKD", label)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def infer_title_from_filename(stem: str) -> str:
    """Derive a human-readable title from a filename stem."""
    return re.sub(r"[_\-]+", " ", stem).strip()


def slugify_edition(edition: str) -> str:
    """Convert an edition label to a safe filename component."""
    text = edition.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    return text.strip("-")
