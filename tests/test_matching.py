"""Reading groups, ensemble loading and the matching order."""

from __future__ import annotations

import unittest
from pathlib import Path

from tests.helpers import GROUPS_PATH, TempDir

from lib.library import LibraryError, load_ensemble
from lib.matcher import build_report, match_part
from lib.models import EnsemblePart, Piece, PiecePart
from lib.reading_groups import can_read, expand_entry, load_reading_groups, ungrouped_parts


def make_piece(*part_ids: str, assignments: dict[str, str] | None = None) -> Piece:
    parts = {
        pid: PiecePart(id=pid, label=pid, start_page=i + 1, end_page=i + 1)
        for i, pid in enumerate(part_ids)
    }
    return Piece(
        slug="piece", title="Piece", pdf_path=Path("piece.pdf"),
        parts_by_id=parts, assignments=assignments or {},
    )


class ReadingGroupTests(unittest.TestCase):
    def setUp(self):
        self.groups = load_reading_groups(GROUPS_PATH)

    def test_flex_expands_in_reads_order(self):
        self.assertEqual(
            expand_entry("flex 3", ["eb_treble", "c_bass"], self.groups, "test"),
            ["part_3_in_eb", "part_3_in_eb_tc", "part_3_in_c_bc"],
        )

    def test_flex_limited_to_one_group(self):
        self.assertEqual(
            expand_entry("flex 4 c_bass", ["eb_treble"], self.groups, "test"),
            ["part_4_in_c_bc"],
        )

    def test_plain_entry_is_unchanged(self):
        self.assertEqual(expand_entry("alto_sax_1", [], self.groups, "test"), ["alto_sax_1"])

    def test_flex_needs_reads(self):
        with self.assertRaises(ValueError):
            expand_entry("flex 1", [], self.groups, "test")

    def test_can_read(self):
        self.assertTrue(can_read("trumpet_2", ["bb_treble"], self.groups))
        self.assertTrue(can_read("part_4_in_bb_tc", ["bb_treble"], self.groups))
        self.assertFalse(can_read("alto_sax_1", ["bb_treble"], self.groups))
        # Bare "in C" has no clef, so no group covers it
        self.assertFalse(can_read("part_1_in_c", ["c_treble", "c_bass"], self.groups))
        # trombone_tc must not be swept into bass clef by a glob
        self.assertFalse(can_read("trombone_tc", ["c_bass"], self.groups))

    def test_ungrouped_parts(self):
        parts = [
            {"id": "flute", "label": "Flute"},
            {"id": "part_1_in_c", "label": "Part 1 in C"},
            {"id": "viola", "label": "Viola"},
        ]
        self.assertEqual(
            ungrouped_parts(parts, self.groups),
            [("Part 1 in C", "part_1_in_c"), ("Viola", "viola")],
        )


class EnsembleLoadingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_schema_2_expands_prefer_and_compromise(self):
        path = self.tmp.ensemble(
            "  - id: tenor_sax\n    label: Tenor Sax\n    reads: [bb_treble]\n"
            "    prefer: [flex 3]\n    compromise: [baritone_tc, flex 3]\n"
        )
        _, band, parts = load_ensemble(path)
        self.assertEqual(band, "Test Band")
        ep = parts[0]
        self.assertEqual(ep.prefer, ["part_3_in_bb", "part_3_in_bb_tc"])
        # Anything already preferred is not repeated as a compromise
        self.assertEqual(ep.compromise, ["baritone_tc"])
        self.assertEqual(ep.prefer_spec, ["flex 3"])

    def test_schema_1_fallback_still_loads_as_prefer(self):
        path = self.tmp.write(
            "config/ensembles/old.yaml",
            "schema_version: 1\nensemble: {id: o, name: O}\nparts:\n"
            "  - {id: clarinet_2, label: Clarinet 2, fallback: [clarinet_1]}\n",
        )
        _, _, parts = load_ensemble(path)
        self.assertEqual(parts[0].prefer, ["clarinet_1"])
        self.assertEqual(parts[0].compromise, [])

    def test_errors(self):
        cases = {
            "unknown group": "  - {id: flute, label: Flute, reads: [c_trebel]}\n",
            "flex without reads": "  - {id: flute, label: Flute, prefer: [flex 1]}\n",
            "both formats": "  - {id: flute, label: Flute, fallback: [oboe], prefer: [oboe]}\n",
            "self reference": "  - {id: flute, label: Flute, prefer: [flute]}\n",
            "duplicate chair": "  - {id: flute, label: Flute}\n  - {id: flute, label: Flute}\n",
        }
        for name, body in cases.items():
            with self.subTest(name):
                path = self.tmp.ensemble(body, name=name.replace(" ", "_"))
                with self.assertRaises(LibraryError):
                    load_ensemble(path)


class MatchingOrderTests(unittest.TestCase):
    def setUp(self):
        self.chair = EnsemblePart(
            id="tenor_horn", label="Tenor Horn",
            prefer=["part_3_in_eb"], compromise=["alto_sax_1"],
        )

    def reason(self, piece):
        result = match_part(piece, self.chair)
        return result.match_reason, result.matched_id

    def test_assignment_beats_everything(self):
        piece = make_piece("tenor_horn", "alto_sax_1", assignments={"tenor_horn": "alto_sax_1"})
        self.assertEqual(self.reason(piece), ("assignment", "alto_sax_1"))

    def test_direct(self):
        self.assertEqual(self.reason(make_piece("tenor_horn", "part_3_in_eb")), ("direct", "tenor_horn"))

    def test_prefer_before_compromise(self):
        piece = make_piece("alto_sax_1", "part_3_in_eb")
        self.assertEqual(self.reason(piece), ("fallback", "part_3_in_eb"))

    def test_compromise(self):
        self.assertEqual(self.reason(make_piece("alto_sax_1")), ("compromise", "alto_sax_1"))

    def test_missing(self):
        self.assertEqual(self.reason(make_piece("flute")), (None, None))

    def test_report_notes_compromises(self):
        piece = make_piece("alto_sax_1")
        plan = {self.chair.id: [match_part(piece, self.chair)]}
        lines, notes = build_report("Test", [self.chair], [piece], plan)
        self.assertIn("  piece -> alto_sax_1 (compromise)", lines)
        self.assertTrue(any("compromise" in n for n in notes))


if __name__ == "__main__":
    unittest.main()
