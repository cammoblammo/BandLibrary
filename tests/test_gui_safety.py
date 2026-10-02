"""The app doesn't crash or freeze: bad files, background git, closing while busy."""

from __future__ import annotations

import subprocess
import unittest
from unittest import mock

from tests.helpers import ROOT, TempDir

from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox, QStatusBar

from lib.editor_widget import EditorWidget, GitThread, current_branch

APP = QApplication.instance() or QApplication([])


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          check=True).stdout.strip()


class OpenManualTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_opening_a_pdf_as_a_part_list_warns_instead_of_crashing(self):
        pdf = self.tmp.path / "piece.pdf"
        pdf.write_bytes(b"%PDF-1.7\n%\xf6\xe4\xfc\xdf\n")
        widget = EditorWidget([], status_bar=QStatusBar())
        with mock.patch.object(QFileDialog, "getOpenFileName", return_value=(str(pdf), "")), \
                mock.patch.object(QMessageBox, "warning") as warning:
            widget.open_manual()
        warning.assert_called_once()
        self.assertIn("Open PDF", warning.call_args[0][2])
        self.assertEqual(widget.editor.toPlainText(), "")


class GitThreadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()
        remote = self.tmp.path / "remote.git"
        git(self.tmp.path, "init", "-q", "--bare", str(remote))
        self.repo = self.tmp.path / "repo"
        git(self.tmp.path, "clone", "-q", str(remote), str(self.repo))
        git(self.repo, "config", "user.email", "test@example.com")
        git(self.repo, "config", "user.name", "Test")
        (self.repo / "README").write_text("x\n")
        git(self.repo, "add", "README")
        git(self.repo, "commit", "-q", "-m", "start")
        git(self.repo, "push", "-q", "origin", "HEAD")
        self.remote = remote

    def tearDown(self):
        self.tmp.cleanup()

    def run_thread(self):
        piece = self.repo / "library" / "bad-guy"
        piece.mkdir(parents=True, exist_ok=True)
        (piece / "bad-guy.yaml").write_text("piece:\n  title: Bad Guy\n")
        thread = GitThread(self.repo, piece, "bad-guy")
        results, progress = [], []
        thread.done.connect(lambda ok, msg: results.append((ok, msg)))
        thread.progress.connect(progress.append)
        thread.start()
        thread.wait()
        APP.processEvents()
        return results, progress

    def test_commits_and_pushes_in_the_background(self):
        results, progress = self.run_thread()
        self.assertEqual(results, [(True, "Imported and pushed 'Bad Guy'.")])
        self.assertTrue(any("Pushing" in p for p in progress))
        self.assertEqual(git(self.remote, "log", "-1", "--format=%s"), "Import: Bad Guy")

    def test_current_branch(self):
        self.assertEqual(current_branch(self.repo),
                         git(self.repo, "rev-parse", "--abbrev-ref", "HEAD"))
        self.assertIsNone(current_branch(self.tmp.path))   # not a repository

    def test_nothing_to_commit(self):
        self.run_thread()
        results, _ = self.run_thread()
        self.assertEqual(results, [(True, "No changes to commit for bad-guy.")])


class BranchWarningTests(unittest.TestCase):
    def confirm(self, branch, git_push=True, test_mode=False, answer=QMessageBox.StandardButton.No):
        widget = EditorWidget([], status_bar=QStatusBar())
        widget.git_checkbox.setChecked(git_push)
        widget.test_checkbox.setChecked(test_mode)
        with mock.patch("lib.editor_widget.current_branch", return_value=branch), \
                mock.patch.object(QMessageBox, "question", return_value=answer) as question:
            return widget._confirm_branch(), question

    def test_asks_before_pushing_to_another_branch(self):
        ok, question = self.confirm("part-detection")
        self.assertFalse(ok)
        self.assertIn('"part-detection", not main', question.call_args[0][2])
        ok, _ = self.confirm("part-detection", answer=QMessageBox.StandardButton.Yes)
        self.assertTrue(ok)

    def test_no_question_on_main_in_test_mode_or_without_push(self):
        for kwargs in ({"branch": "main"}, {"branch": "x", "test_mode": True},
                       {"branch": "x", "git_push": False}, {"branch": None}):
            with self.subTest(**kwargs):
                ok, question = self.confirm(**kwargs)
                self.assertTrue(ok)
                question.assert_not_called()


class BuildListTests(unittest.TestCase):
    """The Booklet Builder checks the build list against the library in use."""

    def widget(self):
        from lib.build_widget import BuildWidget
        widget = BuildWidget(status_bar=QStatusBar(), config={})
        widget._add_piece("hound-dog")          # from the real library
        return widget

    def test_real_pieces_in_test_mode_are_explained_not_built(self):
        widget = self.widget()
        widget.test_checkbox.setChecked(True)
        self.assertIn("TEST", widget.library_label.text())
        with mock.patch.object(QMessageBox, "warning") as warning:
            widget.run_build()
        warning.assert_called_once()
        self.assertIn("Untick Test mode", warning.call_args[0][2])
        self.assertIsNone(widget._build_thread)

    def test_dry_run_from_the_real_library(self):
        widget = self.widget()
        self.assertEqual(widget.library_label.text(), "Library")
        with mock.patch.object(QMessageBox, "warning") as warning:
            widget.run_dry_run()
            widget._build_thread.wait()
            APP.processEvents()
        warning.assert_not_called()
        self.assertIn("Percussion:", widget.output_view.toPlainText())


class BusyTests(unittest.TestCase):
    def test_activity_indicator(self):
        widget = EditorWidget([], status_bar=QStatusBar())
        self.assertTrue(widget.activity_bar.isHidden())
        widget._busy("Pushing to GitHub…")
        self.assertFalse(widget.activity_bar.isHidden())
        self.assertEqual(widget.activity_label.text(), "Pushing to GitHub…")
        widget._git_thread = None
        widget._on_git_done(True, "Imported and pushed 'X'.")
        self.assertTrue(widget.activity_bar.isHidden())
        self.assertEqual(widget.activity_label.text(), "✓ Imported and pushed 'X'.")

    def test_reports_a_running_push(self):
        widget = EditorWidget([], status_bar=QStatusBar())
        self.assertIsNone(widget.is_busy())
        widget._git_thread = mock.Mock(isRunning=mock.Mock(return_value=True))
        self.assertIn("pushing", widget.is_busy())


if __name__ == "__main__":
    unittest.main()
