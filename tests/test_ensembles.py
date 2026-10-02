"""The Ensembles tab and the band code behind it (lib/ensemble_io.py)."""

from __future__ import annotations

import shutil
import subprocess
import unittest
from unittest import mock

import yaml

from tests.helpers import CONFIG, GROUPS_PATH, TEST_LIBRARY, TempDir

from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

from lib.ensemble_io import (
    BandSpec, ChairSpec, band_data, band_text, check_band, compare, copy_assignments,
    copy_band, load_pieces, read_band, readable_library_parts, suggest_id, write_band,
)
from lib.library import load_ensemble, parse_ensemble
from lib.reading_groups import load_reading_groups

APP = QApplication.instance() or QApplication([])
GROUPS = load_reading_groups(GROUPS_PATH)


def chair(id, label=None, **kw):
    return ChairSpec(id=id, label=label or id.replace("_", " ").title(), **kw)


class FileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_real_bands_round_trip(self):
        for path in sorted((CONFIG / "ensembles").glob("*.yaml")):
            with self.subTest(path.stem):
                text = band_text(read_band(path))
                self.assertEqual(parse_ensemble(yaml.safe_load(text), GROUPS),
                                 load_ensemble(path))
                self.assertIn("takes: all", text)       # explained in the header

    def test_names_needing_quotes_survive(self):
        band = BandSpec("b", "B: Band", "St Mary's #1 Band",
                        [chair("flute", "Flute: piccolo too", reads=["c_treble"])])
        path = self.tmp.path / "b.yaml"
        write_band(path, band)
        again = read_band(path)
        self.assertEqual((again.name, again.band, again.chairs[0].label),
                         ("B: Band", "St Mary's #1 Band", "Flute: piccolo too"))

    def test_empty_fields_are_left_out(self):
        text = band_text(BandSpec("b", "B", "", [chair("flute", reads=["c_treble"])]))
        chairs = text.split("parts:")[1]
        for field in ("prefer", "compromise", "takes"):
            self.assertNotIn(field, chairs)

    def test_suggest_id(self):
        self.assertEqual(suggest_id("Tenor Horn"), "tenor_horn")
        self.assertEqual(suggest_id("Alto Sax 1"), "alto_sax_1")


class CheckTests(unittest.TestCase):
    def check(self, *chairs, others=None):
        return check_band(BandSpec("b", "B", "", list(chairs)), GROUPS, others)

    def test_a_good_band_loads(self):
        result = self.check(chair("trumpet_1", reads=["bb_treble"], prefer=["flex 1"]))
        self.assertTrue(result.ok)
        self.assertEqual(result.parts[0].prefer, ["part_1_in_bb", "part_1_in_bb_tc"])

    def test_substitute_it_cannot_read(self):
        result = self.check(chair("flute", reads=["c_treble"], prefer=["alto_sax_1"]))
        self.assertFalse(result.ok)
        self.assertIn("isn't in what this chair reads", result.chair_errors[0][0])

    def test_errors_are_per_chair(self):
        result = self.check(chair("flute", reads=["c_treble"]),
                            chair("flute", reads=["c_treble"]),
                            chair("Bad Id", reads=["c_treble"]),
                            chair("percussion", reads=[], takes="all"),
                            chair("drums", reads=["percussion"], takes="all", prefer=["claves"]))
        self.assertEqual(sorted(result.chair_errors), [0, 1, 2, 3, 4])

    def test_own_id_outside_its_groups_is_only_a_note(self):
        result = self.check(chair("tuba_2", reads=["c_bass"], prefer=["tuba"]))
        self.assertTrue(result.ok)
        self.assertIn("only gets substitutes", result.chair_notes[0][0])

    def test_shared_chair_ids_are_noted(self):
        other = BandSpec("serscb", "SERSCB", "", [chair("flute", reads=["c_treble"])])
        result = self.check(chair("flute", reads=["c_treble"]), others={"serscb": other})
        self.assertIn("SERSCB also has a chair with this ID", result.chair_notes[0][0])


class CompareTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()
        self.library = self.tmp.copy_piece("castinblues")
        self.pieces = load_pieces(self.library)

    def tearDown(self):
        self.tmp.cleanup()

    def parts(self, *chairs):
        return check_band(BandSpec("b", "B", "", list(chairs)), GROUPS).parts

    def test_gaps_filled_lost_and_chairs_added_or_removed(self):
        before = self.parts(chair("oboe", reads=["c_treble"]),
                            chair("trumpet_1", reads=["bb_treble"]),
                            chair("violin", reads=["c_treble"]))
        after = self.parts(chair("oboe", reads=["c_treble"], compromise=["flute"]),
                           chair("trumpet_1", reads=["bb_treble"]),
                           chair("horn", reads=["f_treble"]))
        kinds = sorted(c.kind for c in compare(self.pieces, before, after))
        self.assertEqual(kinds, ["filled", "new chair", "removed chair"])

    def test_a_new_band_lists_every_chair(self):
        after = self.parts(chair("trumpet_1", reads=["bb_treble"]))
        changes = compare(self.pieces, None, after)
        self.assertEqual([c.kind for c in changes], ["new chair"])

    def test_readable_library_parts(self):
        found = dict(readable_library_parts(
            self.library, chair("horn", reads=["eb_treble"]), GROUPS))
        self.assertIn("alto_sax_1", found)
        self.assertNotIn("trumpet_1", found)


class DiskTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()
        self.library = self.tmp.copy_piece("castinblues")
        self.yaml_path = self.library / "castinblues" / "castinblues.yaml"
        data = yaml.safe_load(self.yaml_path.read_text())
        data["assignments"] = {"tenor_horn": "alto_sax_1"}
        self.yaml_path.write_text(yaml.safe_dump(data, sort_keys=False))

    def tearDown(self):
        self.tmp.cleanup()

    def assignments(self):
        return yaml.safe_load(self.yaml_path.read_text())["assignments"]

    def test_copy_band_keeps_chair_ids(self):
        source = read_band(CONFIG / "ensembles" / "serscb.yaml")
        new = copy_band(source, "juniors", "JUNIORS", "Junior Band")
        self.assertEqual([c.id for c in new.chairs], [c.id for c in source.chairs])
        self.assertEqual((new.id, new.name), ("juniors", "JUNIORS"))
        self.assertEqual(source.name, "SERSCB")          # the original is untouched

    def test_moving_assignments_to_a_new_chair_id(self):
        changed = copy_assignments(self.library, "tenor_horn", "horn", keep_old=False)
        self.assertEqual(changed, [self.yaml_path])
        self.assertEqual(self.assignments(), {"horn": "alto_sax_1"})

    def test_keeping_them_when_another_band_uses_the_old_id(self):
        copy_assignments(self.library, "tenor_horn", "horn", keep_old=True)
        self.assertEqual(self.assignments(), {"tenor_horn": "alto_sax_1", "horn": "alto_sax_1"})


class TabTests(unittest.TestCase):
    """The tab on a throwaway copy of the project (config and a small library)."""

    def setUp(self):
        from lib.ensemble_widget import EnsembleWidget
        self.tmp = TempDir()
        root = self.tmp.path
        shutil.copytree(CONFIG, root / "config")
        self.tmp.copy_piece("castinblues")
        self.tmp.copy_piece("hounddog", TEST_LIBRARY)
        self.root = root
        self.widget = EnsembleWidget(project_root=root)
        self.widget.git_checkbox.setChecked(False)

    def tearDown(self):
        self.tmp.cleanup()

    def save(self):
        from lib.ensemble_widget import PreviewDialog
        with mock.patch.object(PreviewDialog, "exec", return_value=QDialog.DialogCode.Accepted):
            return self.widget.save()

    def test_opens_the_first_band(self):
        w = self.widget
        self.assertEqual(w.band_list.count(), 2)
        self.assertEqual(w.short_edit.text(), "SERSCB")
        self.assertEqual(w.chair_list.item(0).text(), "Flute")
        self.assertFalse(w.save_btn.isEnabled())

    def test_add_a_chair_its_id_follows_its_name_and_it_saves(self):
        w = self.widget
        w.chair_list.setCurrentRow(0)
        w.add_chair()
        w.name_edit.setText("Tuba 2")
        w._on_name_edited("Tuba 2")
        self.assertEqual(w._chair().id, "tuba_2")
        w.read_boxes["c_bass"].setChecked(True)
        w._chair().prefer.append("tuba")
        w._changed()
        self.assertTrue(self.save())
        saved = read_band(self.root / "config" / "ensembles" / "serscb.yaml")
        self.assertEqual(saved.chairs[1].id, "tuba_2")
        self.assertEqual(saved.chairs[1].reads, ["c_bass"])
        self.assertFalse(w.has_unsaved_changes())

    def test_save_is_refused_while_a_chair_has_a_problem(self):
        w = self.widget
        w.chair_list.setCurrentRow(0)                   # Flute reads C treble
        w._chair().prefer.append("alto_sax_1")
        w._changed()
        self.assertIn("⚠", w.chair_list.item(0).text())
        with mock.patch.object(QMessageBox, "warning") as warning:
            self.assertFalse(w.save())
        self.assertIn("Fix these first", warning.call_args[0][2])

    def test_a_new_band_copied_from_another(self):
        w = self.widget
        new = copy_band(w._saved["workshop"], "juniors", "JUNIORS", "Junior Band")
        w._open(new, new=True)
        self.assertTrue(self.save())
        path = self.root / "config" / "ensembles" / "juniors.yaml"
        name, band, parts = load_ensemble(path)
        self.assertEqual((name, band), ("JUNIORS", "Junior Band"))
        self.assertEqual(w.band_list.count(), 3)

    def test_delete_a_band(self):
        w = self.widget
        with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            w.delete_band()
        self.assertFalse((self.root / "config" / "ensembles" / "serscb.yaml").exists())
        self.assertEqual(w.band_list.count(), 1)

    def test_changing_a_chair_id_carries_its_assignments(self):
        data_path = self.root / "library" / "castinblues" / "castinblues.yaml"
        data = yaml.safe_load(data_path.read_text())
        data["assignments"] = {"tenor_horn": "alto_sax_1"}
        data_path.write_text(yaml.safe_dump(data, sort_keys=False))
        w = self.widget
        row = next(i for i, c in enumerate(w._band.chairs) if c.id == "tenor_horn")
        w.chair_list.setCurrentRow(row)
        yes = QMessageBox.StandardButton.Yes
        with mock.patch("lib.ensemble_widget.QInputDialog.getText", return_value=("horn", True)), \
                mock.patch.object(QMessageBox, "question", return_value=yes):
            w.change_id()
        self.assertTrue(self.save())
        # Workshop has no Tenor Horn chair, so the old ID's assignment moves
        self.assertEqual(yaml.safe_load(data_path.read_text())["assignments"],
                         {"horn": "alto_sax_1"})


class CommitThreadTests(unittest.TestCase):
    def test_commits_a_change_and_a_deletion_and_pushes(self):
        from lib.editor_widget import CommitThread
        tmp = TempDir()
        try:
            def git(cwd, *args):
                return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                                      text=True, check=True).stdout.strip()
            remote, repo = tmp.path / "remote.git", tmp.path / "repo"
            git(tmp.path, "init", "-q", "--bare", str(remote))
            git(tmp.path, "clone", "-q", str(remote), str(repo))
            git(repo, "config", "user.email", "t@example.com")
            git(repo, "config", "user.name", "T")
            (repo / "a.yaml").write_text("a\n")
            (repo / "b.yaml").write_text("b\n")
            git(repo, "add", ".")
            git(repo, "commit", "-q", "-m", "start")
            git(repo, "push", "-q", "origin", "HEAD")

            (repo / "a.yaml").write_text("changed\n")
            (repo / "b.yaml").unlink()
            thread = CommitThread(repo, [repo / "a.yaml", repo / "b.yaml"], "Ensemble: X", "X")
            results = []
            thread.done.connect(lambda ok, msg: results.append((ok, msg)))
            thread.start()
            thread.wait()
            APP.processEvents()
            self.assertEqual(results, [(True, "Saved and pushed X.")])
            self.assertEqual(git(remote, "log", "-1", "--format=%s"), "Ensemble: X")
            self.assertEqual(git(remote, "ls-tree", "--name-only", "HEAD"), "a.yaml")
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
