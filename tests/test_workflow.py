"""Import, regenerate, add part and build, on temporary copies."""

from __future__ import annotations

import io
import shutil
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import yaml
from pypdf import PdfReader

from tests.helpers import TESTDATA, TempDir

from lib.builder import generate_booklets
from lib.importer import import_piece, regenerate_yaml
from lib.library import LibraryError, load_ensemble, load_piece
from lib.manual import parse_manual_file
from lib.matcher import build_match_plan
from lib.models import Piece, PiecePart
from lib.parts import add_part
from lib.utils import display_title, slugify


def quiet(fn, *args, **kwargs):
    with redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


class UtilityTests(unittest.TestCase):
    def test_display_title(self):
        # A file-name title is capitalised; a written title is kept as written
        self.assertEqual(display_title("dont stop believin"), "Dont Stop Believin")
        self.assertEqual(display_title("Don't Stop Believin'"), "Don't Stop Believin'")
        self.assertEqual(display_title("Cast in Blues"), "Cast in Blues")
        self.assertEqual(display_title("T.W.A."), "T.W.A.")

    def test_slugify(self):
        self.assertEqual(slugify("Cast In Blues (Workshop)"), "cast-in-blues-workshop")


class ManualFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_flexible_part_names_need_no_alias(self):
        path = self.tmp.write("x.manual.txt",
                              "Part 3 in C BC: 1\nPart 2 in Bb: 2\nPart 1 in C: 3\nKazoo: 4\n")
        _, _, unaliased = parse_manual_file(path, {})
        self.assertEqual(unaliased, [("Kazoo", "kazoo")])

    def test_rejects_entry_without_label(self):
        path = self.tmp.write("x.manual.txt", "Flute: 1\n: 2\n")
        with self.assertRaisesRegex(ValueError, "Line 2"):
            parse_manual_file(path, {})

    def test_rejects_bad_range(self):
        path = self.tmp.write("x.manual.txt", "Flute: 3-2\n")
        with self.assertRaises(ValueError):
            parse_manual_file(path, {})


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()
        self.library = self.tmp.path / "library"
        self.pdf = self.tmp.path / "Cast In Blues.pdf"
        shutil.copy2(TESTDATA / "CastInBlues.pdf", self.pdf)
        self.manual = TESTDATA / "CastInBlues.manual.txt"

    def tearDown(self):
        self.tmp.cleanup()

    def test_import_then_refuse_without_force(self):
        quiet(import_piece, self.pdf, self.manual, self.library, False, {})
        piece = load_piece(self.library, "cast-in-blues")
        self.assertIn("trumpet_1", piece.parts_by_id)
        with self.assertRaises(FileExistsError):
            quiet(import_piece, self.pdf, self.manual, self.library, False, {})
        # --force replaces it
        quiet(import_piece, self.pdf, self.manual, self.library, True, {})

    def test_forced_reimport_keeps_valid_assignments_only(self):
        quiet(import_piece, self.pdf, self.manual, self.library, False, {})
        yaml_path = self.library / "cast-in-blues" / "cast-in-blues.yaml"
        data = yaml.safe_load(yaml_path.read_text())
        data["assignments"] = {"tenor_horn": "alto_sax_1", "oboe": "no_such_part"}
        yaml_path.write_text(yaml.safe_dump(data, sort_keys=False))

        quiet(import_piece, self.pdf, self.manual, self.library, True, {})
        self.assertEqual(
            yaml.safe_load(yaml_path.read_text())["assignments"], {"tenor_horn": "alto_sax_1"}
        )

    def test_regenerate_keeps_valid_assignments_only(self):
        quiet(import_piece, self.pdf, self.manual, self.library, False, {})
        yaml_path = self.library / "cast-in-blues" / "cast-in-blues.yaml"
        data = yaml.safe_load(yaml_path.read_text())
        data["assignments"] = {"tenor_horn": "alto_sax_1", "oboe": "no_such_part"}
        yaml_path.write_text(yaml.safe_dump(data, sort_keys=False))

        quiet(regenerate_yaml, "cast-in-blues",
              self.library / "cast-in-blues" / "cast-in-blues.manual.txt", self.library, {})
        self.assertEqual(
            yaml.safe_load(yaml_path.read_text())["assignments"], {"tenor_horn": "alto_sax_1"}
        )

    def test_reimport_keeps_surviving_parts_of_a_list_assignment(self):
        quiet(import_piece, self.pdf, self.manual, self.library, False, {})
        yaml_path = self.library / "cast-in-blues" / "cast-in-blues.yaml"
        data = yaml.safe_load(yaml_path.read_text())
        data["assignments"] = {"percussion": ["drum_kit", "gone"], "horn": ["gone"]}
        yaml_path.write_text(yaml.safe_dump(data, sort_keys=False))

        quiet(import_piece, self.pdf, self.manual, self.library, True, {})
        self.assertEqual(
            yaml.safe_load(yaml_path.read_text())["assignments"], {"percussion": ["drum_kit"]}
        )

    def test_list_assignments_load_and_are_checked(self):
        quiet(import_piece, self.pdf, self.manual, self.library, False, {})
        yaml_path = self.library / "cast-in-blues" / "cast-in-blues.yaml"
        data = yaml.safe_load(yaml_path.read_text())
        data["assignments"] = {"percussion": ["drum_kit", "trombone"]}
        yaml_path.write_text(yaml.safe_dump(data, sort_keys=False))
        piece = load_piece(self.library, "cast-in-blues")
        self.assertEqual(piece.assignments["percussion"], ("drum_kit", "trombone"))

        data["assignments"] = {"percussion": ["drum_kit", "no_such_part"]}
        yaml_path.write_text(yaml.safe_dump(data, sort_keys=False))
        with self.assertRaisesRegex(LibraryError, "no_such_part"):
            load_piece(self.library, "cast-in-blues")

    def test_regenerate_accepts_empty_assignments(self):
        quiet(import_piece, self.pdf, self.manual, self.library, False, {})
        yaml_path = self.library / "cast-in-blues" / "cast-in-blues.yaml"
        yaml_path.write_text(yaml_path.read_text() + "assignments:\n")
        load_piece(self.library, "cast-in-blues")
        quiet(regenerate_yaml, "cast-in-blues",
              self.library / "cast-in-blues" / "cast-in-blues.manual.txt", self.library, {})


class AddPartTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()
        self.library = self.tmp.copy_piece("castinblues")
        self.source = self.tmp.path / "extra.pdf"
        shutil.copy2(TESTDATA / "CastInBlues.pdf", self.source)

    def tearDown(self):
        self.tmp.cleanup()

    def test_appends_pages_and_keeps_source(self):
        before = len(PdfReader(str(self.library / "castinblues" / "castinblues.pdf")).pages)
        added = len(PdfReader(str(self.source)).pages)

        part_id, start, end = quiet(add_part, "castinblues", "Tenor Horn", self.source, self.library, {})

        self.assertEqual((part_id, start, end), ("tenor_horn", before + 1, before + added))
        self.assertTrue(self.source.exists(), "the source PDF must be left in place")
        piece = load_piece(self.library, "castinblues")
        self.assertEqual(piece.parts_by_id["tenor_horn"].end_page, before + added)
        manual = (self.library / "castinblues" / "castinblues.manual.txt").read_text()
        self.assertTrue(manual.rstrip().endswith(f"Tenor Horn: {start}-{end}"))

    def test_rejects_existing_part(self):
        with self.assertRaises(ValueError):
            quiet(add_part, "castinblues", "Flute", self.source, self.library, {})


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()
        self.library = self.tmp.copy_piece("castinblues")
        self.ensemble = self.tmp.ensemble(
            "  - {id: trumpet_1, label: Trumpet 1, reads: [bb_treble]}\n"
            "  - {id: tenor_horn, label: Tenor Horn, reads: [eb_treble], compromise: [alto_sax_1]}\n"
            "  - {id: oboe, label: Oboe, reads: [c_treble]}\n"
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_booklets_have_cover_and_part_pages(self):
        _, band, parts = load_ensemble(self.ensemble)
        piece = load_piece(self.library, "castinblues")
        plan = build_match_plan(parts, [piece])
        out = self.tmp.path / "out"
        files = quiet(generate_booklets, out, parts, {piece.slug: piece}, plan, band, "Test")

        # Oboe has nothing, so it gets no booklet
        self.assertEqual(sorted(f.name for f in files), ["tenor_horn.pdf", "trumpet_1.pdf"])
        for f in files:
            reader = PdfReader(str(f))
            self.assertEqual(len(reader.pages), 2)  # cover + one part page
            cover = reader.pages[0].extract_text()
            self.assertIn("Test Band", cover)
            self.assertIn("CastInBlues", cover)

    def test_contents_brackets_pieces_missing_from_the_booklet(self):
        _, band, parts = load_ensemble(self.ensemble)
        piece = load_piece(self.library, "castinblues")
        other = load_piece(self.library, "castinblues")
        # A second piece with no trumpet part at all
        other = type(other)(
            slug="no-trumpets", title="No Trumpets Here", pdf_path=other.pdf_path,
            parts_by_id={k: v for k, v in other.parts_by_id.items() if not k.startswith("trumpet")},
            assignments={},
        )
        pieces = [piece, other]
        plan = build_match_plan(parts, pieces)
        out = self.tmp.path / "out"
        quiet(generate_booklets, out, parts, {p.slug: p for p in pieces}, plan, band, "")

        trumpet_cover = PdfReader(str(out / "trumpet_1.pdf")).pages[0].extract_text()
        horn_cover = PdfReader(str(out / "tenor_horn.pdf")).pages[0].extract_text()
        # Same numbering in every booklet; missing pieces in brackets
        self.assertIn("2.  (No Trumpets Here)", trumpet_cover)
        self.assertIn("have no part for this instrument", trumpet_cover)
        self.assertIn("2.  No Trumpets Here", horn_cover)
        self.assertNotIn("(No Trumpets Here)", horn_cover)
        self.assertNotIn("have no part", horn_cover)


class PercussionBookletTests(unittest.TestCase):
    """A "takes: all" chair's booklet holds several parts per piece."""

    def setUp(self):
        self.tmp = TempDir()
        self.library = self.tmp.copy_piece("castinblues")
        self.ensemble = self.tmp.ensemble(
            "  - {id: percussion, label: Percussion, reads: [percussion], takes: all}\n"
            "  - {id: trumpet_1, label: Trumpet 1, reads: [bb_treble]}\n"
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_every_part_and_contents_page_numbers(self):
        _, band, parts = load_ensemble(self.ensemble)
        piece = load_piece(self.library, "castinblues")
        drum = piece.parts_by_id["drum_kit"]
        # Pretend two more percussion parts, borrowing real pages
        extra = {
            "percussion_2": PiecePart("percussion_2", "Percussion 2", drum.start_page - 1,
                                      drum.start_page - 1),
            "bells": PiecePart("bells", "Bells", drum.start_page - 2, drum.start_page - 2),
        }
        first = Piece(slug="first", title="First Piece", pdf_path=piece.pdf_path,
                      parts_by_id={**piece.parts_by_id, **extra}, assignments={})
        second = Piece(slug="second", title="Second Piece", pdf_path=piece.pdf_path,
                       parts_by_id=piece.parts_by_id, assignments={})
        pieces = [first, second]
        plan = build_match_plan(parts, pieces)
        self.assertEqual(plan["percussion"][0].matched_ids, ("bells", "percussion_2", "drum_kit"))

        out = self.tmp.path / "out"
        quiet(generate_booklets, out, parts, {p.slug: p for p in pieces}, plan, band, "")

        reader = PdfReader(str(out / "percussion.pdf"))
        # cover + three parts for the first piece + the drum kit for the second
        self.assertEqual(len(reader.pages), 5)
        cover = reader.pages[0].extract_text()
        self.assertIn("First Piece", cover)
        self.assertIn("p. 2", cover)
        self.assertIn("p. 5", cover)
        self.assertIn("count this cover as page 1", cover)

        trumpet = PdfReader(str(out / "trumpet_1.pdf")).pages[0].extract_text()
        self.assertIn("p. 2", trumpet)
        self.assertIn("p. 3", trumpet)

    def test_long_contents_keep_every_cover_page(self):
        from lib.builder import generate_cover_page
        titles = [(f"Piece number {i}", i + 2) for i in range(60)]
        cover = generate_cover_page("Band", "Percussion", "", titles)
        self.assertGreater(len(cover.pages), 1)
        text = "".join(page.extract_text() for page in cover.pages)
        self.assertIn("Piece number 59", text)


if __name__ == "__main__":
    unittest.main()
