"""
BandLibrary Manual Part Mapping Editor — reusable widget.

Provides EditorWidget (a QWidget) that can be embedded in a tab or
used standalone. Also exports PdfViewer and ManualEditor for testing.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pymupdf
from PyQt6.QtCore import Qt, QProcess
from PyQt6.QtGui import QImage, QPixmap, QFont, QTextCursor, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication, QWidget, QSplitter, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QFileDialog, QMessageBox,
    QScrollArea, QFrame, QStatusBar, QCheckBox, QToolBar, QMainWindow,
)

import yaml


# ---------------------------------------------------------------------------
# Alias loading
# ---------------------------------------------------------------------------

def load_alias_labels(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            return []
        aliases = data.get("aliases", {})
        if not isinstance(aliases, dict):
            return []
        return sorted(aliases.keys())
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Slugify (for Save As suggestion)
# ---------------------------------------------------------------------------

def _slugify(text: str) -> str:
    import unicodedata
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"-{2,}", "-", text).strip("-")


# ---------------------------------------------------------------------------
# PDF Viewer
# ---------------------------------------------------------------------------

class PdfViewer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._doc = None
        self._page_index = 0
        self._zoom = 1.5
        self._fit_on_load = True
        self._rotation = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QWidget()
        toolbar.setObjectName("pdfToolbar")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(8, 6, 8, 6)
        tb_layout.setSpacing(8)

        self.prev_btn = QPushButton("◀ Prev")
        self.next_btn = QPushButton("Next ▶")
        self.page_label = QLabel("No PDF loaded")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        for btn in (self.prev_btn, self.next_btn):
            btn.setFixedHeight(30)
            btn.setMinimumWidth(80)

        self.zoom_in_btn = QPushButton("＋")
        self.zoom_out_btn = QPushButton("－")
        self.zoom_in_btn.setFixedSize(30, 30)
        self.zoom_out_btn.setFixedSize(30, 30)

        self.rotate_btn = QPushButton("↻ 90°")
        self.rotate_btn.setFixedHeight(30)
        self.rotate_btn.setToolTip("Rotate view 90° clockwise (display only)")

        tb_layout.addWidget(self.prev_btn)
        tb_layout.addWidget(self.page_label, stretch=1)
        tb_layout.addWidget(self.next_btn)
        tb_layout.addSpacing(16)
        tb_layout.addWidget(self.zoom_out_btn)
        tb_layout.addWidget(self.zoom_in_btn)
        tb_layout.addSpacing(8)
        tb_layout.addWidget(self.rotate_btn)

        layout.addWidget(toolbar)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("separator")
        layout.addWidget(sep)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll.setObjectName("pdfScroll")

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setObjectName("pdfPage")
        self.scroll.setWidget(self.image_label)

        layout.addWidget(self.scroll, stretch=1)

        self.prev_btn.clicked.connect(self.prev_page)
        self.next_btn.clicked.connect(self.next_page)
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        self.rotate_btn.clicked.connect(self.rotate_90)

        self._update_buttons()

    def load(self, path: Path):
        self._doc = pymupdf.open(str(path))
        self._page_index = 0
        self._rotation = 0
        self._fit_on_load = True
        self._render()

    def current_page_number(self) -> int:
        return self._page_index + 1

    def page_count(self) -> int:
        return len(self._doc) if self._doc else 0

    def is_at_last_page(self) -> bool:
        return self._doc is not None and self._page_index >= len(self._doc) - 1

    def next_page(self):
        if self._doc and self._page_index < len(self._doc) - 1:
            self._page_index += 1
            self._render()

    def prev_page(self):
        if self._doc and self._page_index > 0:
            self._page_index -= 1
            self._render()

    def zoom_in(self):
        self._zoom = min(self._zoom + 0.25, 4.0)
        self._render()

    def zoom_out(self):
        self._zoom = max(self._zoom - 0.25, 0.5)
        self._render()

    def rotate_90(self):
        self._rotation = (self._rotation + 90) % 360
        self._render()

    def _render(self):
        if self._doc is None:
            return
        page = self._doc[self._page_index]
        total_rotation = (page.rotation + self._rotation) % 360
        if self._fit_on_load:
            aw = self.scroll.viewport().width() - 4
            ah = self.scroll.viewport().height() - 4
            pw, ph = page.rect.width, page.rect.height
            if pw > 0 and ph > 0 and aw > 0 and ah > 0:
                self._zoom = min(aw / pw, ah / ph)
            self._fit_on_load = False
        mat = pymupdf.Matrix(self._zoom, self._zoom).prerotate(total_rotation)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = QImage(pix.samples, pix.width, pix.height,
                     pix.stride, QImage.Format.Format_RGB888)
        self.image_label.setPixmap(QPixmap.fromImage(img))
        self._update_buttons()

    def _update_buttons(self):
        has_doc = self._doc is not None
        cur = self.current_page_number()
        count = self.page_count()
        self.prev_btn.setEnabled(has_doc and cur > 1)
        self.next_btn.setEnabled(has_doc and cur < count)
        self.page_label.setText(f"Page {cur} of {count}" if has_doc else "No PDF loaded")


# ---------------------------------------------------------------------------
# Manual File Editor
# ---------------------------------------------------------------------------

PENDING_RE = re.compile(r"^:\s*(\d+)(?:-(\d+))?$")
ENTRY_RE = re.compile(r"^(.+):\s*(\d+)(?:-(\d+))?$")


class ManualEditor(QTextEdit):
    def __init__(self, pdf_viewer: PdfViewer, status_bar: QStatusBar,
                 alias_labels: list[str], parent=None):
        super().__init__(parent)
        self._pdf = pdf_viewer
        self._status = status_bar
        self._current_file: Path | None = None
        self._modified = False
        self._alias_labels = alias_labels
        self._cycle_matches: list[str] = []
        self._cycle_index: int = -1
        self._cycle_prefix: str = ""

        font = QFont("Monospace", 12)
        font.setStyleHint(QFont.StyleHint.TypeWriter)
        self.setFont(font)
        self.setTabChangesFocus(False)
        self.setAcceptRichText(False)
        self.document().contentsChanged.connect(self._on_change)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._cycle_reset()
            self._handle_enter()
        elif event.key() == Qt.Key.Key_Tab:
            self._handle_tab_complete()
        elif event.key() == Qt.Key.Key_PageDown:
            self._pdf.next_page()
        elif event.key() == Qt.Key.Key_PageUp:
            self._pdf.prev_page()
        else:
            self._cycle_reset()
            super().keyPressEvent(event)

    def _handle_enter(self):
        if self._pdf._doc is None:
            self._status.showMessage("No PDF loaded — open a PDF first.", 4000)
            return

        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        line = cursor.selectedText().strip()
        current_page = self._pdf.current_page_number()

        if not line:
            self._insert_pending(cursor, current_page)
            return

        m = PENDING_RE.match(line)
        if m:
            self._finalise_entry(cursor, line, int(m.group(1)), current_page)
            return

        m = ENTRY_RE.match(line)
        if m:
            self._finalise_entry(cursor, line, int(m.group(2)), current_page)
            return

        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.EndOfLine)
        cursor.insertText("\n")
        self.setTextCursor(cursor)

    def _insert_pending(self, cursor: QTextCursor, page: int):
        cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        if cursor.selectedText().strip():
            cursor.movePosition(QTextCursor.MoveOperation.EndOfLine)
            cursor.insertText(f"\n: {page}")
        else:
            cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
            cursor.movePosition(QTextCursor.MoveOperation.EndOfLine,
                                QTextCursor.MoveMode.KeepAnchor)
            cursor.insertText(f": {page}")
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        self.setTextCursor(cursor)
        self._status.showMessage(
            f"Page {page} — type part name, Page Down to navigate, Enter to finalise.", 0)

    def _finalise_entry(self, cursor: QTextCursor, line: str,
                        start_page: int, end_page: int):
        m_entry = ENTRY_RE.match(line)
        label = m_entry.group(1).strip() if m_entry else ""

        if start_page == end_page:
            page_spec = str(start_page)
        elif end_page < start_page:
            page_spec = str(start_page)
            self._status.showMessage(
                f"Warning: end page {end_page} < start page {start_page}; kept as single page.", 5000)
        else:
            page_spec = f"{start_page}-{end_page}"

        new_line = f"{label}: {page_spec}" if label else f": {page_spec}"

        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfLine,
                            QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(new_line)

        if self._pdf.is_at_last_page():
            self.setTextCursor(cursor)
            self._status.showMessage(
                f"Finalised '{label}: {page_spec}' — end of PDF reached. Save when ready.", 0)
            return

        self._pdf.next_page()
        next_page = self._pdf.current_page_number()
        cursor.movePosition(QTextCursor.MoveOperation.EndOfLine)
        cursor.insertText(f"\n: {next_page}")
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        self.setTextCursor(cursor)

        msg = f"Finalised '{label}: {page_spec}'" if label else "Finalised entry"
        self._status.showMessage(f"{msg} — type next part name.", 0)

    def _handle_tab_complete(self):
        if not self._alias_labels:
            self._status.showMessage("No aliases loaded — autocomplete unavailable.", 3000)
            return

        if not self._cycle_matches:
            prefix = self._current_label_prefix()
            if not prefix:
                return
            self._cycle_prefix = prefix
            lower = prefix.lower()
            self._cycle_matches = [l for l in self._alias_labels if lower in l.lower()]
            self._cycle_index = -1

        if not self._cycle_matches:
            self._status.showMessage(f"No matches for '{self._cycle_prefix}'.", 2000)
            self._cycle_reset()
            return

        self._cycle_index = (self._cycle_index + 1) % len(self._cycle_matches)
        completion = self._cycle_matches[self._cycle_index]
        self._insert_completion(completion)

        count = len(self._cycle_matches)
        self._status.showMessage(
            f"Match {self._cycle_index + 1}/{count}: '{completion}' — Tab to cycle, Enter to accept.", 0)

    def _cycle_reset(self):
        self._cycle_matches = []
        self._cycle_index = -1
        self._cycle_prefix = ""

    def _current_label_prefix(self) -> str:
        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        line = cursor.selectedText()
        if ":" not in line:
            return ""
        return line.split(":")[0].strip()

    def _insert_completion(self, completion: str):
        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        line = cursor.selectedText()
        if ":" not in line:
            return
        after_colon = line.split(":", 1)[1]
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfLine,
                            QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(f"{completion}:{after_colon}")
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfLine)
        self.setTextCursor(cursor)

    def _on_change(self):
        self._modified = True

    def is_modified(self) -> bool:
        return self._modified

    def current_file(self) -> Path | None:
        return self._current_file

    def load_file(self, path: Path):
        with path.open("r", encoding="utf-8") as f:
            self.setPlainText(f.read())
        self._current_file = path
        self._modified = False

    def save(self) -> bool:
        if self._current_file is None:
            return self.save_as()
        return self._write(self._current_file)

    def save_as(self) -> bool:
        if self._current_file is not None:
            suggested = str(self._current_file)
        elif self._pdf._doc is not None:
            slug = _slugify(Path(self._pdf._doc.name).stem)
            suggested = f"{slug}.manual.txt"
        else:
            suggested = "untitled.manual.txt"

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Manual File", suggested,
            "Manual files (*.manual.txt);;Text files (*.txt);;All files (*)"
        )
        if not path:
            return False
        p = Path(path)
        if p.suffix == "" or (p.suffix != ".txt" and not path.endswith(".manual.txt")):
            path = path + ".manual.txt"
        return self._write(Path(path))

    def _write(self, path: Path) -> bool:
        try:
            with path.open("w", encoding="utf-8") as f:
                f.write(self.toPlainText())
            self._current_file = path
            self._modified = False
            self._status.showMessage(f"Saved: {path}", 4000)
            return True
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))
            return False


# ---------------------------------------------------------------------------
# Editor Widget (embeddable)
# ---------------------------------------------------------------------------

class EditorWidget(QWidget):
    """
    The full manual mapping editor as an embeddable QWidget.
    Can be placed in a tab or wrapped in a QMainWindow.

    Requires a QStatusBar to be passed in (so the parent window controls it),
    or pass None to create an internal one.
    """

    def __init__(self, alias_labels: list[str], status_bar: QStatusBar | None = None,
                 importer_path: Path | None = None, parent=None):
        super().__init__(parent)
        self._importer_path = importer_path or Path(__file__).parent.parent / "tools" / "import_piece.py"

        # Use provided status bar or create internal one
        if status_bar is not None:
            self._status = status_bar
            self._owns_status = False
        else:
            self._status = QStatusBar()
            self._owns_status = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Top toolbar (Open PDF)
        top_toolbar = QWidget()
        top_toolbar.setObjectName("mainToolbar")
        top_layout = QHBoxLayout(top_toolbar)
        top_layout.setContentsMargins(8, 6, 8, 6)
        top_layout.setSpacing(8)

        open_pdf_btn = QPushButton("Open PDF…")
        open_pdf_btn.setFixedHeight(28)
        top_layout.addWidget(open_pdf_btn)
        top_layout.addStretch()

        layout.addWidget(top_toolbar)

        sep0 = QFrame()
        sep0.setFrameShape(QFrame.Shape.HLine)
        sep0.setObjectName("separator")
        layout.addWidget(sep0)

        # Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("mainSplitter")

        self.pdf_viewer = PdfViewer()
        splitter.addWidget(self.pdf_viewer)

        # Right pane
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        editor_toolbar = QWidget()
        editor_toolbar.setObjectName("editorToolbar")
        et_layout = QHBoxLayout(editor_toolbar)
        et_layout.setContentsMargins(8, 6, 8, 6)
        et_layout.setSpacing(8)

        self.file_label = QLabel("New file")
        self.file_label.setObjectName("fileLabel")

        new_btn = QPushButton("New")
        open_btn = QPushButton("Open…")
        save_btn = QPushButton("Save")
        save_as_btn = QPushButton("Save As…")
        import_btn = QPushButton("Import…")
        import_btn.setObjectName("importBtn")
        import_btn.setToolTip("Save and run import_piece.py")

        self.force_checkbox = QCheckBox("Force")
        self.force_checkbox.setChecked(True)
        self.force_checkbox.setToolTip("Pass --force to importer")
        self.test_checkbox = QCheckBox("Test")
        self.test_checkbox.setChecked(False)
        self.test_checkbox.setToolTip("Pass --test to importer (imports to test/ instead of library/)")

        if alias_labels:
            alias_indicator = QLabel(f"✓ {len(alias_labels)} aliases")
            alias_indicator.setObjectName("aliasIndicator")
            alias_indicator.setToolTip("Autocomplete active — press Tab while typing a part name")
        else:
            alias_indicator = QLabel("No aliases")
            alias_indicator.setObjectName("aliasIndicatorOff")
            alias_indicator.setToolTip("No aliases.yaml found — autocomplete unavailable")

        for btn in (new_btn, open_btn, save_btn, save_as_btn, import_btn):
            btn.setFixedHeight(30)

        et_layout.addWidget(self.file_label, stretch=1)
        et_layout.addWidget(alias_indicator)
        et_layout.addWidget(new_btn)
        et_layout.addWidget(open_btn)
        et_layout.addWidget(save_btn)
        et_layout.addWidget(save_as_btn)
        et_layout.addSpacing(8)
        et_layout.addWidget(self.force_checkbox)
        et_layout.addWidget(self.test_checkbox)
        et_layout.addWidget(import_btn)

        right_layout.addWidget(editor_toolbar)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setObjectName("separator")
        right_layout.addWidget(sep2)

        self.editor = ManualEditor(self.pdf_viewer, self._status, alias_labels)
        right_layout.addWidget(self.editor, stretch=1)

        splitter.addWidget(right)
        splitter.setSizes([600, 600])
        splitter.setHandleWidth(4)

        layout.addWidget(splitter, stretch=1)

        if self._owns_status:
            layout.addWidget(self._status)

        # Connections
        open_pdf_btn.clicked.connect(self.open_pdf)
        new_btn.clicked.connect(self.new_file)
        open_btn.clicked.connect(self.open_manual)
        save_btn.clicked.connect(self.editor.save)
        save_as_btn.clicked.connect(self.editor.save_as)
        import_btn.clicked.connect(self.run_importer)

        # Shortcuts (scoped to this widget)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.editor.save)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self).activated.connect(self.editor.save_as)
        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(self.open_manual)
        QShortcut(QKeySequence("Ctrl+P"), self).activated.connect(self.open_pdf)
        QShortcut(QKeySequence("PgUp"), self).activated.connect(self.pdf_viewer.prev_page)
        QShortcut(QKeySequence("PgDown"), self).activated.connect(self.pdf_viewer.next_page)

        self._status.showMessage(
            "Ready — open a PDF (Ctrl+P), navigate to first part, press Enter to begin.")

    def set_window_title_callback(self, callback):
        """Allow parent window to update its title when PDF is loaded."""
        self._title_callback = callback

    def open_pdf(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open PDF", "", "PDF files (*.pdf);;All files (*)"
        )
        if path:
            p = Path(path)
            if self.editor.is_modified():
                r = QMessageBox.question(
                    self, "Unsaved changes", "Opening a new PDF will clear the editor. Discard changes?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if r != QMessageBox.StandardButton.Yes:
                    return
            self.pdf_viewer.load(p)
            self.editor.setPlainText("")
            self.editor._current_file = None
            self.editor._modified = False
            self.file_label.setText("New file")
            if hasattr(self, "_title_callback"):
                self._title_callback(f"BandLibrary — {p.name}")
            self._status.showMessage(
                f"Loaded: {p.name} ({self.pdf_viewer.page_count()} pages) — "
                f"navigate to first part and press Enter.")

    def new_file(self):
        if self.editor.is_modified():
            r = QMessageBox.question(
                self, "Unsaved changes", "Discard unsaved changes?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if r != QMessageBox.StandardButton.Yes:
                return
        self.editor.setPlainText("")
        self.editor._current_file = None
        self.editor._modified = False
        self.file_label.setText("New file")
        self._status.showMessage("New file — navigate to the first part and press Enter.")

    def open_manual(self):
        if self.editor.is_modified():
            r = QMessageBox.question(
                self, "Unsaved changes", "Discard unsaved changes?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if r != QMessageBox.StandardButton.Yes:
                return
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Manual File", "",
            "Manual files (*.manual.txt);;Text files (*.txt);;All files (*)"
        )
        if path:
            p = Path(path)
            self.editor.load_file(p)
            self.file_label.setText(p.name)
            self._status.showMessage(f"Loaded: {p.name}")

    def run_importer(self):
        if self.pdf_viewer._doc is None:
            QMessageBox.warning(self, "Import", "No PDF loaded.")
            return

        if not self._importer_path.exists():
            QMessageBox.critical(self, "Import Error",
                f"Could not find import_piece.py at:\n{self._importer_path}")
            return

        pdf_file = Path(self.pdf_viewer._doc.name)
        manual_path = self.editor.current_file()
        temp_manual: Path | None = None

        if manual_path is not None and not self.editor.is_modified():
            # File already saved — use it directly
            pass
        else:
            # Auto-save to a temp location — user never sees a dialog
            project_root = self._importer_path.parent.parent
            temp_dir = project_root / "temp"
            temp_dir.mkdir(exist_ok=True)
            slug = _slugify(pdf_file.stem)
            temp_manual = temp_dir / f"{slug}.manual.txt"
            try:
                with temp_manual.open("w", encoding="utf-8") as f:
                    f.write(self.editor.toPlainText())
            except Exception as e:
                QMessageBox.critical(self, "Import Error",
                    f"Could not write temporary manual file:\n{e}")
                return
            manual_path = temp_manual

        self._status.showMessage("Running importer…")

        proc = QProcess(self)
        proc.start(sys.executable, [str(self._importer_path), str(pdf_file),
                                     "--manual", str(manual_path)]
                   + (["--force"] if self.force_checkbox.isChecked() else [])
                   + (["--test"] if self.test_checkbox.isChecked() else []))
        proc.waitForFinished(15000)

        stdout = proc.readAllStandardOutput().data().decode(errors="replace").strip()
        stderr = proc.readAllStandardError().data().decode(errors="replace").strip()
        exit_code = proc.exitCode()

        # Clean up temp file if it wasn't consumed by the importer
        # (importer deletes manual file on success, so only clean up on failure)
        if temp_manual and temp_manual.exists():
            temp_manual.unlink(missing_ok=True)

        if exit_code == 0:
            self.editor._modified = False
            self._status.showMessage(f"Import successful: {stdout or 'done'}", 6000)
        else:
            detail = stderr or stdout or "No output."
            QMessageBox.critical(self, "Import Failed",
                f"import_piece.py exited with code {exit_code}:\n\n{detail}")
            self._status.showMessage("Import failed.", 5000)

    def has_unsaved_changes(self) -> bool:
        return self.editor.is_modified()

    def prompt_save_on_close(self) -> bool:
        """
        Prompt to save if there are unsaved changes.
        Returns True if it's safe to close, False if the user cancelled.
        """
        if not self.editor.is_modified():
            return True
        r = QMessageBox.question(
            self, "Unsaved changes", "You have unsaved changes. Save before closing?",
            QMessageBox.StandardButton.Save |
            QMessageBox.StandardButton.Discard |
            QMessageBox.StandardButton.Cancel
        )
        if r == QMessageBox.StandardButton.Save:
            return self.editor.save()
        elif r == QMessageBox.StandardButton.Cancel:
            return False
        return True
