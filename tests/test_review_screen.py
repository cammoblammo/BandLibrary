"""The assignment editor's review logic, saving and the import notes dialog."""

from __future__ import annotations

import unittest

import yaml

from tests.helpers import GROUPS_PATH, TempDir

from PyQt6.QtWidgets import QApplication

from lib.assignment_editor import AssignmentEditor, describe_selection
from lib.library import load_ensemble, load_piece
from lib.matcher import match_part
from lib.models import EnsemblePart
from lib.reading_groups import load_reading_groups

APP = QApplication.instance() or QApplication([])


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()
        self.library = self.tmp.copy_piece("castinblues")
        self.yaml_path = self.library / "castinblues" / "castinblues.yaml"
        self.groups = load_reading_groups(GROUPS_PATH)
        ensemble = self.tmp.ensemble(
            "  - {id: trumpet_1, label: Trumpet 1, reads: [bb_treble]}\n"
            "  - {id: tenor_horn, label: Tenor Horn, reads: [eb_treble], compromise: [alto_sax_1]}\n"
            "  - {id: clarinet_2, label: Clarinet 2, reads: [bb_treble], prefer: [clarinet_1]}\n"
        )
        _, _, self.parts = load_ensemble(ensemble)
        self.chairs = {ep.id: ep for ep in self.parts}

    def tearDown(self):
        self.tmp.cleanup()

    def editor(self) -> AssignmentEditor:
        return AssignmentEditor(
            load_piece(self.library, "castinblues"), self.parts, self.yaml_path, self.groups
        )

    def select(self, editor, chair_id, part_id):
        combo = editor._combos[chair_id]
        combo.setCurrentIndex(combo.findData(part_id))

    def test_automatic_rows(self):
        editor = self.editor()
        self.assertEqual(editor._state(self.chairs["trumpet_1"]).reason, "direct")
        horn = editor._state(self.chairs["tenor_horn"])
        self.assertEqual((horn.reason, horn.part_id), ("compromise", "alto_sax_1"))
        self.assertIn("alto_sax_1", horn.note)

    def test_only_real_overrides_are_saved(self):
        editor = self.editor()
        self.select(editor, "trumpet_1", "trumpet_1")    # same as direct: not saved
        self.select(editor, "tenor_horn", "alto_sax_1")  # approving a compromise: saved
        self.select(editor, "clarinet_2", "flute")       # different part: saved, with warning
        self.assertEqual(editor.assignments(), {"tenor_horn": "alto_sax_1", "clarinet_2": "flute"})
        self.assertIn("⚠", editor._state(self.chairs["clarinet_2"]).note)

    def test_save_keeps_other_ensembles_assignments(self):
        data = yaml.safe_load(self.yaml_path.read_text())
        data["assignments"] = {"flute_1": "flute", "trumpet_1": "trumpet_2"}
        self.yaml_path.write_text(yaml.safe_dump(data, sort_keys=False))

        editor = self.editor()
        editor._clear_all()
        editor._save()

        # trumpet_1 belongs to this ensemble and was reset; flute_1 is another band's
        self.assertEqual(yaml.safe_load(self.yaml_path.read_text())["assignments"], {"flute_1": "flute"})

    def test_preview_shows_the_selected_part(self):
        editor = self.editor()
        piece = load_piece(self.library, "castinblues")
        from lib.assignment_editor import PartPreview
        preview = PartPreview(piece, "bass_guitar", "Bass Guitar")
        self.assertEqual(len(preview._doc), 2)  # bass guitar is pages 29-30
        preview.close()
        editor.close()


class DescribeSelectionTests(unittest.TestCase):
    def test_missing_chair(self):
        from tests.test_matching import make_piece
        chair = EnsemblePart(id="oboe", label="Oboe", prefer=[])
        piece = make_piece("flute")
        state = describe_selection(chair, match_part(piece, chair), None, piece, {})
        self.assertEqual((state.reason, state.part_id, state.save), ("missing", None, False))


class ImportNotesTests(unittest.TestCase):
    def test_dialog_collects_both_sections(self):
        from lib.editor_widget import EditorWidget
        from lib.reading_groups import UNGROUPED_HEADING

        widget = EditorWidget([])
        shown = {}

        output = (
            "Imported: library/x\n\n"
            "Unaliased labels (consider adding to config/aliases.yaml):\n"
            "  'Viola'  ->  viola\n\n"
            f"{UNGROUPED_HEADING}\n"
            "  'Viola'  ->  viola\n"
        )
        # Capture the text instead of opening the dialog
        from PyQt6.QtWidgets import QDialog, QTextEdit
        original_exec = QDialog.exec
        QDialog.exec = lambda dlg: shown.setdefault("text", dlg.findChild(QTextEdit).toPlainText())
        try:
            widget._show_unaliased_dialog(output)
        finally:
            QDialog.exec = original_exec

        self.assertIn("Unaliased labels", shown["text"])
        self.assertIn(UNGROUPED_HEADING, shown["text"])
        self.assertEqual(shown["text"].count("'Viola'"), 2)


if __name__ == "__main__":
    unittest.main()
