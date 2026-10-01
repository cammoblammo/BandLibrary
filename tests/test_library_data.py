"""The real configuration and library stay consistent."""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

from tests.helpers import CONFIG, GROUPS_PATH, ROOT, TEST_LIBRARY

from lib.library import list_pieces, load_ensemble, load_piece, load_piece_list
from lib.models import ValidationResult
from lib.reading_groups import load_reading_groups
from lib.validator import check_library, check_readability, validate_ensemble, validate_piece

ENSEMBLES = sorted((CONFIG / "ensembles").glob("*.yaml"))
LIBRARY = ROOT / "library"


class ConfigTests(unittest.TestCase):
    def test_every_ensemble_loads_and_every_chair_can_read_its_parts(self):
        groups = load_reading_groups(GROUPS_PATH)
        self.assertTrue(ENSEMBLES)
        for path in ENSEMBLES:
            with self.subTest(path.name):
                _, _, parts = load_ensemble(path)
                self.assertEqual(check_readability(parts, groups), [])


class LibraryTests(unittest.TestCase):
    def check_library(self, library):
        slugs = list_pieces(library)
        self.assertTrue(slugs)
        result = ValidationResult()
        data = {}
        for slug in slugs:
            d = validate_piece(slug, library, result)
            if d is not None:
                data[slug] = d
        self.assertEqual(result.errors, [])
        return data

    def test_library_validates_against_every_ensemble(self):
        data = self.check_library(LIBRARY)
        for path in ENSEMBLES:
            with self.subTest(path.name):
                result = ValidationResult()
                with redirect_stdout(io.StringIO()):
                    validate_ensemble(path, data, result)
                self.assertEqual(result.errors, [])

    def test_test_library_validates(self):
        self.check_library(TEST_LIBRARY)

    def test_check_library_matches_the_gui_and_cli(self):
        ok, text = check_library(LIBRARY, ENSEMBLES)
        self.assertTrue(ok, text)
        for path in ENSEMBLES:
            self.assertIn(f"Ensemble definition valid: {path.name}", text)

    def test_check_library_reports_a_missing_library(self):
        ok, text = check_library(ROOT / "no-such-library")
        self.assertFalse(ok)
        self.assertIn("not found", text)

    def test_repertoire_files_name_real_pieces(self):
        for path in sorted((ROOT / "repertoire").glob("*.txt")):
            with self.subTest(path.name):
                for slug in load_piece_list(path):
                    load_piece(LIBRARY, slug)


if __name__ == "__main__":
    unittest.main()
