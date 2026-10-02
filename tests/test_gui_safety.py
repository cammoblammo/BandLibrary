"""The app doesn't crash or freeze: bad files, background git, closing while busy."""

from __future__ import annotations

import subprocess
import unittest
from unittest import mock

from tests.helpers import ROOT, TempDir

from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox, QStatusBar

from lib.editor_widget import EditorWidget, GitThread

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

    def test_nothing_to_commit(self):
        self.run_thread()
        results, _ = self.run_thread()
        self.assertEqual(results, [(True, "No changes to commit for bad-guy.")])


class BusyTests(unittest.TestCase):
    def test_reports_a_running_push(self):
        widget = EditorWidget([], status_bar=QStatusBar())
        self.assertIsNone(widget.is_busy())
        widget._git_thread = mock.Mock(isRunning=mock.Mock(return_value=True))
        self.assertIn("pushing", widget.is_busy())


if __name__ == "__main__":
    unittest.main()
