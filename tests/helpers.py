"""
Shared helpers for the BandBook test suite.

Run all tests from the project root with:

    python3 -m unittest discover -s tests -t .
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# GUI tests run without a display
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

CONFIG = ROOT / "config"
GROUPS_PATH = CONFIG / "reading_groups.yaml"
TESTDATA = ROOT / "testdata"
TEST_LIBRARY = ROOT / "test"


class TempDir:
    """A temporary directory that cleans itself up; use in setUp/tearDown."""

    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="bandbook-test-")
        self.path = Path(self._tmp.name)

    def cleanup(self):
        self._tmp.cleanup()

    def copy_piece(self, slug: str, source_library: Path = TEST_LIBRARY) -> Path:
        """Copy a piece from a library into <tmp>/library and return the library path."""
        library = self.path / "library"
        library.mkdir(exist_ok=True)
        shutil.copytree(source_library / slug, library / slug)
        return library

    def write(self, relative: str, text: str) -> Path:
        path = self.path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def ensemble(self, body: str, name: str = "test") -> Path:
        """Write an ensemble file beside a copy of the real reading groups."""
        groups = self.path / "config" / "reading_groups.yaml"
        if not groups.exists():
            groups.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(GROUPS_PATH, groups)
        return self.write(
            f"config/ensembles/{name}.yaml",
            "schema_version: 2\nensemble: {id: t, name: T, band: Test Band}\nparts:\n" + body,
        )
