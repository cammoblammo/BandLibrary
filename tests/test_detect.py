"""Automatic part detection: names, label finding, segmenting, the draft."""

from __future__ import annotations

import unittest

from tests.helpers import CONFIG, GROUPS_PATH, ROOT, TempDir

from lib.aliases import load_aliases
from lib.detect import detect_pages, detect_parts, render
from lib.detect.names import parse_name
from lib.detect.pages import PageReading, RawPage, TextLine
from lib.detect.score import score_draft
from lib.detect.segment import name_notes, segment
from lib.manual import parse_manual_file
from lib.reading_groups import load_reading_groups

ALIASES = load_aliases(CONFIG / "aliases.yaml")
GROUPS = load_reading_groups(GROUPS_PATH)
LIBRARY = ROOT / "library"


def line(text, y=0.05, size=14.0, x=0.07):
    return TextLine(text, x, y, x + 0.01 * len(text), y + 0.02, size)


def page(n, *lines):
    return RawPage(page=n, lines=list(lines))


def furniture():
    return [line("A Piece Title", y=0.05, size=22), line("A. Composer", y=0.1, size=10),
            line("&", y=0.3, size=20)]


class NameTests(unittest.TestCase):
    def name(self, text):
        return parse_name(text, ALIASES)

    def test_standard_transposition_is_dropped(self):
        m = self.name("Clarinet in B♭ 1")
        self.assertEqual((m.label, m.part_id, m.known), ("Clarinet 1", "clarinet_1", True))
        self.assertEqual(self.name("Trumpet in B♭ 2").label, "Trumpet 2")
        self.assertEqual(self.name("Horn in F").label, "French Horn")
        self.assertEqual(self.name("Tenor Horn in E♭").part_id, "tenor_horn")

    def test_missing_flat_is_added_and_flagged(self):
        m = self.name("Clarinet in B 2")
        self.assertEqual(m.part_id, "clarinet_2")
        self.assertTrue(any("flat" in n for n in m.notes))

    def test_flat_drawn_as_separate_glyph(self):
        self.assertEqual(self.name("Part 3 in E b").label, "Part 3 in Eb")
        self.assertEqual(self.name("Part 1 in Bb").part_id, "part_1_in_bb")

    def test_bare_c_part_keeps_no_clef_and_is_flagged(self):
        m = self.name("Part 4 in C")
        self.assertEqual(m.label, "Part 4 in C")
        self.assertTrue(any("TC or BC" in n for n in m.notes))
        self.assertEqual(self.name("Part 4 in C BC").part_id, "part_4_in_c_bc")

    def test_running_header_with_instruments(self):
        m = self.name("Part 5 in C, Trombone/Baritone")
        self.assertEqual((m.label, m.printed_for), ("Part 5 in C", "Trombone/Baritone"))
        self.assertIsNone(self.name("Hard Rock, fast"))

    def test_clef_words(self):
        self.assertEqual(self.name("Euphonium (treble clef)").part_id, "euphonium_tc")

    def test_unknown_instrument_is_kept(self):
        m = self.name("Tambourine")
        self.assertEqual((m.label, m.known), ("Tambourine", False))

    def test_other_text_is_not_a_name(self):
        for text in ("Hard Rock", "Remove mouthpiece", "Swing", "A", "Cameron Horsburgh",
                     "Trumpet Hero", "© 2021 www.superbrass.co.uk"):
            with self.subTest(text):
                self.assertIsNone(self.name(text))


class SegmentTests(unittest.TestCase):
    def reading(self, n, label=None, has_text=True, is_score=False):
        match = parse_name(label, ALIASES) if label else None
        return PageReading(n, has_text, is_score, match)

    def test_unnamed_pages_continue_and_gaps_are_reported(self):
        parts, skipped = segment([
            self.reading(1, is_score=True),
            self.reading(2, "Flute"),
            self.reading(3),
            self.reading(4, "Flute"),
            self.reading(5, has_text=False),
            self.reading(6, "Tuba"),
        ])
        self.assertEqual([(p.label, p.start, p.end) for p in parts],
                         [("Flute", 2, 4), ("Tuba", 6, 6)])
        self.assertIn("page 3 shows no part name", parts[0].notes)
        self.assertEqual([(s.start, s.end, s.reason) for s in skipped],
                         [(1, 1, "score"), (5, 5, "no-text")])

    def test_same_name_after_a_gap_is_flagged(self):
        parts, _ = segment([self.reading(1, "Part 5 in C"), self.reading(2, "Tuba"),
                            self.reading(3, "Part 5 in C")])
        name_notes(parts)
        self.assertEqual(len(parts), 3)
        self.assertTrue(any("more than once" in n for n in parts[0].notes))

    def test_same_name_in_different_clefs(self):
        a, b = self.reading(1, "Part 3 in C"), self.reading(3, "Part 3 in C")
        a.clef, b.clef = "bass", "treble"
        parts, _ = segment([a, self.reading(2, "Tuba"), b])
        name_notes(parts)
        self.assertIn("adding TC or BC will tell them apart", parts[0].notes[-1])
        self.assertIn("also page 3, treble clef", parts[0].notes[-1])

    def test_same_name_for_different_instruments(self):
        a, b = self.reading(1, "Part 5 in C"), self.reading(3, "Part 5 in C")
        a.label.printed_for, b.label.printed_for = "Trombone/Baritone", "Tuba"
        parts, _ = segment([a, self.reading(2, "Tuba"), b])
        name_notes(parts)
        self.assertIn("(this one for Trombone/Baritone); also page 3, for Tuba",
                      parts[0].notes[-1])

    def test_bare_name_beside_a_numbered_one(self):
        parts, _ = segment([self.reading(1, "Trumpet"), self.reading(2, "Trumpet 2")])
        name_notes(parts)
        self.assertTrue(any('"Trumpet 1"' in n for n in parts[0].notes))


class LabelFindingTests(unittest.TestCase):
    def test_furniture_score_and_cue_names(self):
        pages = [
            page(1, *furniture(), line("Flute", y=0.2, size=7), line("Clarinet 1", y=0.35, size=7),
                 line("Trumpet 1", y=0.5, size=7), line("Tuba", y=0.65, size=7)),
            page(2, *furniture(), line("Flute")),
            # Cue name in the music, smaller and in the body of the page
            page(3, *furniture(), line("Clarinet 1"), line("T. Sax", y=0.5, size=10)),
            page(4, *furniture(), line("Triangle", y=0.4, size=10)),
            page(5, *furniture(), line("Tuba")),
        ]
        draft = detect_pages(pages, ALIASES, GROUPS)
        self.assertEqual(draft.title, "A Piece Title")
        self.assertEqual([(p.label, p.start, p.end) for p in draft.parts],
                         [("Flute", 2, 2), ("Clarinet 1", 3, 4), ("Tuba", 5, 5)])
        self.assertEqual([(s.start, s.reason) for s in draft.skipped], [(1, "score")])

    def test_names_at_the_bottom_of_the_page(self):
        story = line("Once upon a time there was a band", y=0.12)
        pages = [page(n, *furniture(), story, line(name, y=0.95))
                 for n, name in enumerate(["Trumpet 1", "Trumpet 1", "Flute", "Flute"], 1)]
        draft = detect_pages(pages, ALIASES, GROUPS)
        self.assertEqual([(p.label, p.start, p.end) for p in draft.parts],
                         [("Trumpet 1", 1, 2), ("Flute", 3, 4)])

    def test_title_page_inside_a_part_does_not_split_it(self):
        pages = [page(1, *furniture(), line("Flute or Oboe", y=0.95)),
                 page(2, *furniture(), line("Flute")),
                 page(3, *furniture(), line("Flute or Oboe", y=0.95)),
                 page(4, *furniture(), line("Tuba", y=0.95))]
        draft = detect_pages(pages, ALIASES, GROUPS)
        self.assertEqual([(p.label, p.start, p.end) for p in draft.parts],
                         [("Flute or Oboe", 1, 3), ("Tuba", 4, 4)])

    def test_part_from_another_source_with_its_own_style(self):
        pages = [page(1, *furniture(), line("Part 1 in Bb", size=16)),
                 page(2, *furniture(), line("Part 2 in Bb", size=16)),
                 page(3, *furniture(), line("Bass Guitar", size=12))]
        draft = detect_pages(pages, ALIASES, GROUPS)
        self.assertEqual([p.label for p in draft.parts],
                         ["Part 1 in Bb", "Part 2 in Bb", "Bass Guitar"])

    def test_watermark_only_pages_have_no_text(self):
        mark = line("Sheet Music Plus Order 123. 1 copy purchased", y=0.97, size=9)
        draft = detect_pages([page(n, mark) for n in range(1, 5)], ALIASES, GROUPS)
        self.assertEqual(draft.text_pages, 0)
        self.assertEqual(draft.parts, [])
        self.assertIsNone(draft.title)


class SecondPageTests(unittest.TestCase):
    def test_misprinted_header_on_a_second_page_is_flagged(self):
        title = line("A Piece Title", y=0.05, size=30)

        def first(n, name):
            return page(n, title, line(name, y=0.1, size=16))

        def second(n, name):
            return page(n, line(name, y=0.05, size=10))

        pages = [first(1, "Part 1 in Bb"), second(2, "Part 1 in Bb"),
                 first(3, "Part 3 in Bb"), second(4, "Part 3 in F"),   # misprint
                 first(5, "Part 3 in F"), first(6, "Part 4 in Bb")]
        draft = detect_pages(pages, ALIASES, GROUPS)
        notes = {(p.label, p.start): p.notes for p in draft.parts}
        self.assertTrue(notes[("Part 3 in F", 4)][0].startswith(
            "page 4 looks like a second page (no title)"))
        self.assertEqual(notes[("Part 1 in Bb", 1)], [])


class TitleTests(unittest.TestCase):
    def test_music_glyphs_and_small_repeated_text_are_not_the_title(self):
        pages = [page(n, line("j#œ œ ‰ >", y=0.3, size=40), line("Moderate Rock", y=0.15, size=9),
                      line("T.W.A.", y=0.05, size=20) if n == 1 else line("x", y=0.9))
                 for n in range(1, 5)]
        self.assertEqual(detect_pages(pages, ALIASES, GROUPS).title, "T.W.A.")


class KnownNameTests(unittest.TestCase):
    def test_names_outside_aliases_and_groups_are_flagged(self):
        pages = [page(n, *furniture(), line(name))
                 for n, name in enumerate(["Flute 1", "Tambourine", "Harp", "Part 4 in C"], 1)]
        notes = {p.label: p.notes for p in detect_pages(pages, ALIASES, GROUPS).parts}
        self.assertEqual(notes["Flute 1"], [])            # a reading group covers flute_*
        self.assertEqual(notes["Tambourine"], [])         # …and percussion covers tambourine
        self.assertTrue(any("not a known" in n for n in notes["Harp"]))
        self.assertEqual(notes["Part 4 in C"], ["clef not printed: add TC or BC"])


class ClefHintTests(unittest.TestCase):
    def draft(self, *names_and_clefs):
        pages = [RawPage(n, [*furniture(), line(name)], clef=clef)
                 for n, (name, clef) in enumerate(names_and_clefs, 1)]
        return {p.label: p.notes for p in detect_pages(pages, ALIASES, GROUPS).parts}

    def test_clef_added_to_c_part_without_one(self):
        notes = self.draft(("Part 4 in C", "bass"), ("Part 1 in C", None))
        self.assertEqual(notes["Part 4 in C BC"],
                         ["clef added from the first staff (bass clef)"])
        self.assertEqual(notes["Part 1 in C"], ["clef not printed: add TC or BC"])

    def test_same_c_name_in_two_clefs_is_not_a_duplicate(self):
        notes = self.draft(("Part 3 in C", "bass"), ("Tuba", "bass"), ("Part 3 in C", "treble"))
        self.assertEqual(notes["Part 3 in C BC"], ["clef added from the first staff (bass clef)"])
        self.assertEqual(notes["Part 3 in C TC"], ["clef added from the first staff (treble clef)"])

    def test_name_read_in_the_other_clef(self):
        notes = self.draft(("Euphonium", "treble"), ("Trombone", "bass"),
                           ("Flute", "treble"), ("Piano", "bass"), ("Drum Kit", "treble"))
        self.assertEqual(notes["Euphonium"], [
            'the first staff is in treble clef, but "Euphonium" is read as a bass-clef part'])
        for name in ("Trombone", "Flute", "Piano", "Drum Kit"):
            self.assertEqual(notes[name], [], name)

    def test_clef_glyphs_in_the_text_layer(self):
        from lib.detect.sources.text_layer import _clef
        self.assertEqual(_clef("\ue050", "Leland"), "treble")
        self.assertEqual(_clef("\ue062", "MuseJazz"), "bass")
        self.assertEqual(_clef("?bb", "Inkpen2Std"), "bass")
        self.assertEqual(_clef("&", "ABCDEF+BroadwayCopyist"), "treble")
        self.assertIsNone(_clef("&", "Helvetica"))
        self.assertIsNone(_clef("?", "Inkpen2ScriptStd"))


class DraftTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_draft_imports_as_it_stands(self):
        pages = [page(1, *furniture(), line("Clarinet in B 1")),
                 page(2, *furniture()),
                 page(3, *furniture(), line("Tambourine"))]
        text = render(detect_pages(pages, ALIASES, GROUPS))
        for entry in text.splitlines():
            if not entry.startswith("#"):
                self.assertNotIn("#", entry)
        path = self.tmp.write("piece.manual.txt", text)
        title, parts, _ = parse_manual_file(path, ALIASES)
        self.assertEqual(title, "A Piece Title")
        self.assertEqual([(p["id"], p["pages"]) for p in parts],
                         [("clarinet_1", [1, 2]), ("tambourine", [3, 3])])


class LibraryDetectionTests(unittest.TestCase):
    """Detection finds every part range in pieces with a full text layer."""

    PIECES = ["cast-in-blues", "cast-in-blues-workshop", "going-quackers",
              "low-rider", "old-timester", "soundstorm",
              "things-that-go-bump-in-the-night"]

    def test_text_layer_pieces(self):
        for slug in self.PIECES:
            pdf = LIBRARY / slug / f"{slug}.pdf"
            if pdf.stat().st_size < 1000:
                self.skipTest("library PDFs are Git LFS pointers here")
            with self.subTest(slug):
                draft = detect_parts(pdf, ALIASES, GROUPS)
                score = score_draft(slug, draft, LIBRARY / slug / f"{slug}.manual.txt", ALIASES)
                self.assertEqual(score.ranges_right, score.expected, score.differences)

    def test_clef_hint_on_euphonium_in_treble_clef(self):
        pdf = LIBRARY / "soundstorm" / "soundstorm.pdf"
        if pdf.stat().st_size < 1000:
            self.skipTest("library PDFs are Git LFS pointers here")
        notes = {p.label: p.notes for p in detect_parts(pdf, ALIASES, GROUPS).parts}
        self.assertTrue(any("treble clef" in n for n in notes["Euphonium"]))


class BadGuyTests(unittest.TestCase):
    """
    Bad Guy (Superbrass flexible arrangement) has most of the awkward cases
    in one text-layer PDF: running headers with instruments after a comma,
    smaller second-page headers, C parts in both clefs, a name printed for
    two parts, and a misprinted second-page header (page 16).
    """

    @classmethod
    def setUpClass(cls):
        pdf = LIBRARY / "bad-guy" / "bad-guy.pdf"
        if not pdf.exists() or pdf.stat().st_size < 1000:
            raise unittest.SkipTest("Bad Guy PDF not available (Git LFS pointer?)")
        cls.draft = detect_parts(pdf, ALIASES, GROUPS)
        cls.parts = {(p.label, p.start, p.end): p.notes for p in cls.draft.parts}

    def test_title_and_skipped_pages(self):
        self.assertEqual(self.draft.title, "Bad Guy")
        self.assertEqual([(s.start, s.end, s.reason) for s in self.draft.skipped],
                         [(1, 2, "no-name"), (3, 10, "score")])

    def test_ranges_match_the_library_except_the_misprinted_page(self):
        score = score_draft("bad-guy", self.draft,
                            LIBRARY / "bad-guy" / "bad-guy.manual.txt", ALIASES)
        self.assertEqual(score.differences, [
            "missed  Part 3 in Bb: 15-16",
            # The owner renamed the Tuba version of "Part 5 in C"
            "name    Part 5 in C BC (part_5_in_c_bc) — expected Tuba (tuba) for 29-30",
            "extra   Part 3 in Bb: 15-15",
            "extra   Part 3 in C TC: 16-16",
        ])

    def test_running_headers_continue_parts(self):
        # Page 26 is headed "Part 5 in C, Trombone/Baritone"
        self.assertIn(("Part 5 in Bb", 27, 28), self.parts)
        for notes in self.parts.values():
            self.assertFalse(any("no part name" in n for n in notes), notes)

    def test_clef_added_from_the_first_staff(self):
        self.assertEqual(self.parts[("Part 3 in C BC", 13, 14)],
                         ["clef added from the first staff (bass clef)"])
        self.assertEqual(self.parts[("Part 4 in C BC", 21, 22)],
                         ["clef added from the first staff (bass clef)"])

    def test_misprinted_second_page_is_flagged_not_merged(self):
        notes = self.parts[("Part 3 in C TC", 16, 16)]
        self.assertTrue(notes[0].startswith("page 16 looks like a second page (no title)"))
        self.assertIn('"Part 3 in Bb" above', notes[0])

    def test_name_printed_for_two_parts_says_what_differs(self):
        first = self.parts[("Part 5 in C BC", 25, 26)][-1]
        second = self.parts[("Part 5 in C BC", 29, 30)][-1]
        self.assertIn("(this one for Trombone/Baritone); also pages 29-30, for Tuba", first)
        self.assertIn("(this one for Tuba); also pages 25-26, for Trombone/Baritone", second)


class DetectButtonTests(unittest.TestCase):
    """The Piece Importer's Detect Parts button, without a display."""

    def run_detect(self, slug, existing="", ocr_unavailable=None):
        from unittest import mock
        from PyQt6.QtWidgets import QApplication, QMessageBox, QStatusBar
        from lib.detect.sources import ocr
        from lib.editor_widget import EditorWidget

        # Kept on the class: a QApplication that is garbage-collected
        # takes its widgets with it
        app = DetectButtonTests.app = QApplication.instance() or QApplication([])
        pdf = LIBRARY / slug / f"{slug}.pdf"
        if pdf.stat().st_size < 1000:
            self.skipTest("library PDFs are Git LFS pointers here")
        status = QStatusBar()
        widget = EditorWidget([], status_bar=status)
        widget.pdf_viewer.load(pdf)
        widget.editor.setPlainText(existing)
        yes = QMessageBox.StandardButton.Yes
        with mock.patch.object(QMessageBox, "question", return_value=yes) as question, \
                mock.patch.object(QMessageBox, "information") as information, \
                mock.patch.object(ocr, "available", return_value=ocr_unavailable):
            widget.detect_parts()
            widget._detect_thread.wait()
            app.processEvents()
        self.assertTrue(widget.detect_btn.isEnabled())
        return widget, question, information

    def test_fills_the_part_list(self):
        widget, question, information = self.run_detect("going-quackers", "old text")
        question.assert_called_once()
        information.assert_not_called()
        text = widget.editor.toPlainText()
        self.assertIn("Flute 1: 7\n", text)
        self.assertNotIn("old text", text)

    def test_scan_without_ocr_leaves_the_part_list_alone(self):
        widget, _, information = self.run_detect("hound-dog", ocr_unavailable="no OCR here")
        information.assert_called_once()
        self.assertIn("no OCR here", information.call_args[0][2])
        self.assertEqual(widget.editor.toPlainText(), "")


class OcrTests(unittest.TestCase):
    """One real OCR read (a few seconds), when Tesseract is installed."""

    def test_reads_a_scanned_part_name(self):
        import pymupdf
        from lib.detect.sources import ocr

        if ocr.available():
            self.skipTest(ocr.available())
        pdf = LIBRARY / "hound-dog" / "hound-dog.pdf"
        if pdf.stat().st_size < 1000:
            self.skipTest("library PDFs are Git LFS pointers here")
        with pymupdf.open(pdf) as doc:
            page = ocr.read_page(doc[1], 2)
        ids = {m.part_id for m in (parse_name(l.text, ALIASES) for l in page.lines) if m}
        self.assertIn("clarinet_1", ids)


class OcrNameTests(unittest.TestCase):
    """Names as OCR reads them from scans."""

    def test_ocr_misreadings(self):
        cases = {
            "tst Bb CLARINET": "clarinet_1",
            "2nd Bb CLARINET": "clarinet_2",
            "EbALTO SAXOPHONE": "alto_sax_1",
            "E> BARITONE SAXOPHONE": "baritone_sax",
            "AltoSaxophone": "alto_sax_1",
            "Hornin F": "french_horn",
            "F HORN": "french_horn",
            "Bb BASS CLARINET": "bass_clarinet",
            "BARITONE T.C.": "baritone_tc",
        }
        for text, part_id in cases.items():
            with self.subTest(text):
                self.assertEqual(parse_name(text, ALIASES).part_id, part_id)

    def test_capitals_become_title_case(self):
        self.assertEqual(parse_name("Bb TRUMPET 1", ALIASES).label, "Trumpet 1")
        self.assertIsNone(parse_name("(Trumpets With Attitude)", ALIASES))


if __name__ == "__main__":
    unittest.main()
