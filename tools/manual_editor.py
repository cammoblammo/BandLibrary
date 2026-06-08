#!/usr/bin/env python3
"""
BandLibrary Manual Part Mapping Editor

A split-pane tool for creating .manual.txt files.

Left pane:  PDF viewer with page navigation
Right pane: Text editor with Enter-to-advance, Tab-to-autocomplete workflow

Workflow:
  - Navigate PDF to first page of a part
  - Enter on empty line: inserts ': <page>' and parks cursor before colon
  - Type part name (Tab autocompletes from aliases)
  - Navigate PDF to last page of part with Page Down
  - Enter: finalises range, advances PDF, inserts next ': <page>'
  - Ctrl+S: save
  - Ctrl+O: open manual file
  - Ctrl+P: open PDF

Usage:
  python3 manual_editor.py [--aliases path/to/aliases.yaml]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)

try:
    import pymupdf
except ImportError:
    print("ERROR: pymupdf is required. Install with: sudo apt install python3-pymupdf")
    sys.exit(1)

try:
    from PyQt6.QtCore import Qt, QProcess
    from PyQt6.QtGui import (
        QImage, QPixmap, QKeySequence, QShortcut, QFont, QTextCursor
    )
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QSplitter,
        QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QTextEdit, QFileDialog, QMessageBox, QScrollArea,
        QFrame, QStatusBar, QToolBar, QCheckBox
    )
except ImportError:
    print("ERROR: PyQt6 is required. Install with: sudo apt install python3-pyqt6")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Alias loading
# ---------------------------------------------------------------------------

def load_alias_labels(path: Path) -> list[str]:
    """
    Load alias keys from aliases.yaml and return them as a sorted list
    of display labels for autocomplete.
    Returns empty list if file not found or malformed.
    """
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
# PDF Viewer
# ---------------------------------------------------------------------------

class PdfViewer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._doc = None
        self._page_index = 0  # 0-based internally
        self._zoom = 1.5
        self._fit_on_load = True  # fit page to pane on first load
        self._rotation = 0  # view-only rotation offset in degrees

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
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
        self.rotate_btn.setToolTip("Rotate view 90° clockwise (display only, does not modify PDF)")

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

        # Scroll area for page image
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
        """1-based page number."""
        return self._page_index + 1

    def page_count(self) -> int:
        if self._doc is None:
            return 0
        return len(self._doc)

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
            available_width = self.scroll.viewport().width() - 4
            available_height = self.scroll.viewport().height() - 4
            page_width = page.rect.width
            page_height = page.rect.height
            if page_width > 0 and page_height > 0 and available_width > 0 and available_height > 0:
                zoom_w = available_width / page_width
                zoom_h = available_height / page_height
                self._zoom = min(zoom_w, zoom_h)
            self._fit_on_load = False
        mat = pymupdf.Matrix(self._zoom, self._zoom).prerotate(total_rotation)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = QImage(pix.samples, pix.width, pix.height,
                     pix.stride, QImage.Format.Format_RGB888)
        self.image_label.setPixmap(QPixmap.fromImage(img))
        self._update_buttons()

    def _update_buttons(self):
        has_doc = self._doc is not None
        count = self.page_count()
        cur = self.current_page_number()

        self.prev_btn.setEnabled(has_doc and cur > 1)
        self.next_btn.setEnabled(has_doc and cur < count)

        if has_doc:
            self.page_label.setText(f"Page {cur} of {count}")
        else:
            self.page_label.setText("No PDF loaded")


# ---------------------------------------------------------------------------
# Manual File Editor
# ---------------------------------------------------------------------------

# Matches a pending line like ': 12' (no part name yet)
def _slugify(text: str) -> str:
    import unicodedata
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"-{2,}", "-", text).strip("-")


PENDING_RE = re.compile(r"^:\s*(\d+)(?:-(\d+))?$")

# Matches a complete entry like 'Trumpet 1: 12' or 'Alto Sax: 13-15'
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

        font = QFont("Monospace", 12)
        font.setStyleHint(QFont.StyleHint.TypeWriter)
        self.setFont(font)
        self.setTabChangesFocus(False)
        self.setAcceptRichText(False)

        # Autocomplete state
        self._cycle_matches: list[str] = []
        self._cycle_index: int = -1
        self._cycle_prefix: str = ""  # the original typed prefix

        self.document().contentsChanged.connect(self._on_change)

    # -----------------------------------------------------------------------
    # Key handling
    # -----------------------------------------------------------------------

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._cycle_reset()  # any Enter cancels cycling
            self._handle_enter()
        elif event.key() == Qt.Key.Key_Tab:
            self._handle_tab_complete()
        elif event.key() == Qt.Key.Key_PageDown:
            self._pdf.next_page()
        elif event.key() == Qt.Key.Key_PageUp:
            self._pdf.prev_page()
        else:
            self._cycle_reset()  # any other key cancels cycling
            super().keyPressEvent(event)

    # -----------------------------------------------------------------------
    # Enter: start entry / finalise entry
    # -----------------------------------------------------------------------

    def _handle_enter(self):
        if self._pdf._doc is None:
            self._status.showMessage("No PDF loaded — open a PDF first.", 4000)
            return

        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        line = cursor.selectedText().strip()
        current_page = self._pdf.current_page_number()

        # Empty line — start a new entry
        if not line:
            self._insert_pending(cursor, current_page)
            return

        # Pending line (': 12') — finalise it
        m = PENDING_RE.match(line)
        if m:
            start_page = int(m.group(1))
            self._finalise_entry(cursor, line, start_page, current_page)
            return

        # Complete entry line — re-finalise end page
        m = ENTRY_RE.match(line)
        if m:
            start_page = int(m.group(2))
            self._finalise_entry(cursor, line, start_page, current_page)
            return

        # Unrecognised line — just insert a newline
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.EndOfLine)
        cursor.insertText("\n")
        self.setTextCursor(cursor)

    def _insert_pending(self, cursor: QTextCursor, page: int):
        """Insert ': <page>' on current line and park cursor at start."""
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

    def _finalise_entry(self, cursor: QTextCursor, line: str, start_page: int, end_page: int):
        """Finalise the current entry and start the next one."""
        m_pending = PENDING_RE.match(line)
        m_entry = ENTRY_RE.match(line)

        label = ""
        if m_entry:
            label = m_entry.group(1).strip()

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

        # End of PDF — don't advance or insert
        if self._pdf.is_at_last_page():
            self.setTextCursor(cursor)
            self._status.showMessage(
                f"Finalised '{label}: {page_spec}' — end of PDF reached. Save when ready.", 0)
            return

        # Advance PDF and start next entry
        self._pdf.next_page()
        next_page = self._pdf.current_page_number()

        cursor.movePosition(QTextCursor.MoveOperation.EndOfLine)
        cursor.insertText(f"\n: {next_page}")
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        self.setTextCursor(cursor)

        msg = f"Finalised '{label}: {page_spec}'" if label else "Finalised entry"
        self._status.showMessage(f"{msg} — type next part name.", 0)

    # -----------------------------------------------------------------------
    # Tab: cycle autocomplete
    # -----------------------------------------------------------------------

    def _handle_tab_complete(self):
        if not self._alias_labels:
            self._status.showMessage("No aliases loaded — autocomplete unavailable.", 3000)
            return

        # If not currently cycling, build match list from current typed prefix
        if not self._cycle_matches:
            prefix = self._current_label_prefix()
            if not prefix:
                return
            self._cycle_prefix = prefix
            lower = prefix.lower()
            self._cycle_matches = [
                label for label in self._alias_labels
                if lower in label.lower()
            ]
            self._cycle_index = -1

        if not self._cycle_matches:
            self._status.showMessage(f"No matches for '{self._cycle_prefix}'.", 2000)
            self._cycle_reset()
            return

        # Advance to next match (wraps around)
        self._cycle_index = (self._cycle_index + 1) % len(self._cycle_matches)
        completion = self._cycle_matches[self._cycle_index]
        self._insert_completion(completion)

        count = len(self._cycle_matches)
        idx = self._cycle_index + 1
        self._status.showMessage(
            f"Match {idx}/{count}: '{completion}' — Tab to cycle, Enter to accept.", 0)

    def _cycle_reset(self):
        """Clear cycling state."""
        self._cycle_matches = []
        self._cycle_index = -1
        self._cycle_prefix = ""

    def _current_label_prefix(self) -> str:
        """Extract the part name typed so far (text before the colon on current line)."""
        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        line = cursor.selectedText()
        if ":" not in line:
            return ""
        return line.split(":")[0].strip()

    def _insert_completion(self, completion: str):
        """Replace the label portion of the current line with the completion."""
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

    # -----------------------------------------------------------------------
    # File operations
    # -----------------------------------------------------------------------

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
# Main Window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self, alias_labels: list[str]):
        super().__init__()
        self.setWindowTitle("BandLibrary — Manual Part Mapping Editor")
        self.resize(1200, 800)
        self._setup_style()

        status = QStatusBar()
        self.setStatusBar(status)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("mainSplitter")

        # Left: PDF viewer
        self.pdf_viewer = PdfViewer()
        splitter.addWidget(self.pdf_viewer)

        # Right: editor pane
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

        # Alias indicator
        if alias_labels:
            alias_indicator = QLabel(f"✓ {len(alias_labels)} aliases")
            alias_indicator.setObjectName("aliasIndicator")
            alias_indicator.setToolTip("Autocomplete active — press Tab while typing a part name")
        else:
            alias_indicator = QLabel("No aliases")
            alias_indicator.setObjectName("aliasIndicatorOff")
            alias_indicator.setToolTip("No aliases.yaml found — autocomplete unavailable")

        import_btn = QPushButton("Import…")
        import_btn.setObjectName("importBtn")
        import_btn.setToolTip("Save and run import_piece.py")
        self.force_checkbox = QCheckBox("Force")
        self.force_checkbox.setChecked(True)
        self.force_checkbox.setToolTip("Pass --force to importer (overwrite existing piece)")
        self.test_checkbox = QCheckBox("Test")
        self.test_checkbox.setChecked(False)
        self.test_checkbox.setToolTip("Pass --test to importer (import to test/ instead of library/)")

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

        self.editor = ManualEditor(self.pdf_viewer, status, alias_labels)
        right_layout.addWidget(self.editor, stretch=1)

        splitter.addWidget(right)
        splitter.setSizes([600, 600])
        splitter.setHandleWidth(4)

        self.setCentralWidget(splitter)

        # Top toolbar
        main_toolbar = QToolBar("Main")
        main_toolbar.setMovable(False)
        main_toolbar.setObjectName("mainToolbar")
        self.addToolBar(main_toolbar)

        open_pdf_btn = QPushButton("Open PDF…")
        open_pdf_btn.setFixedHeight(28)
        main_toolbar.addWidget(open_pdf_btn)

        open_pdf_btn.clicked.connect(self.open_pdf)
        new_btn.clicked.connect(self.new_file)
        open_btn.clicked.connect(self.open_manual)
        save_btn.clicked.connect(self.editor.save)
        save_as_btn.clicked.connect(self.editor.save_as)
        import_btn.clicked.connect(self.run_importer)

        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.editor.save)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self).activated.connect(self.editor.save_as)
        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(self.open_manual)
        QShortcut(QKeySequence("Ctrl+P"), self).activated.connect(self.open_pdf)
        QShortcut(QKeySequence("PgUp"), self).activated.connect(self.pdf_viewer.prev_page)
        QShortcut(QKeySequence("PgDown"), self).activated.connect(self.pdf_viewer.next_page)

        status.showMessage(
            "Ready — open a PDF (Ctrl+P), navigate to first part, press Enter to begin.")

    def _setup_style(self):
        self.setStyleSheet("""
            QMainWindow { background: #1e1e2e; }
            QWidget {
                background: #1e1e2e;
                color: #cdd6f4;
                font-family: 'DejaVu Sans', sans-serif;
                font-size: 13px;
            }
            QWidget#pdfToolbar, QWidget#editorToolbar {
                background: #181825;
                border-bottom: 1px solid #313244;
            }
            QToolBar#mainToolbar {
                background: #11111b;
                border-bottom: 1px solid #313244;
                padding: 4px 8px;
                spacing: 8px;
            }
            QPushButton {
                background: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 0 12px;
                font-size: 12px;
            }
            QPushButton:hover { background: #45475a; border-color: #585b70; }
            QPushButton:pressed { background: #585b70; }
            QPushButton:disabled { background: #1e1e2e; color: #585b70; border-color: #313244; }
            QTextEdit {
                background: #181825;
                color: #cdd6f4;
                border: none;
                padding: 12px;
                font-family: 'DejaVu Sans Mono', 'Courier New', monospace;
                font-size: 13px;
                selection-background-color: #45475a;
            }
            QScrollArea#pdfScroll { background: #11111b; border: none; }
            QLabel#pdfPage { background: #11111b; }
            QLabel#fileLabel { color: #a6adc8; font-size: 12px; }
            QLabel#aliasIndicator { color: #a6e3a1; font-size: 11px; padding: 0 6px; }
            QLabel#aliasIndicatorOff { color: #585b70; font-size: 11px; padding: 0 6px; }
            QPushButton#importBtn {
                background: #1e4a2e;
                color: #a6e3a1;
                border: 1px solid #40a060;
            }
            QPushButton#importBtn:hover {
                background: #2a5e3a;
                border-color: #50c070;
            }
            QPushButton#importBtn:disabled {
                background: #1e1e2e;
                color: #585b70;
                border-color: #313244;
            }
            QCheckBox { color: #a6adc8; font-size: 12px; }
            QCheckBox::indicator {
                width: 14px; height: 14px;
                border: 1px solid #45475a;
                border-radius: 3px;
                background: #313244;
            }
            QCheckBox::indicator:checked {
                background: #40a060;
                border-color: #50c070;
            }
            QFrame#separator { color: #313244; background: #313244; max-height: 1px; }
            QSplitter::handle { background: #313244; }
            QSplitter::handle:hover { background: #585b70; }
            QStatusBar {
                background: #11111b;
                color: #a6adc8;
                border-top: 1px solid #313244;
                font-size: 12px;
                padding: 2px 8px;
            }
            QAbstractItemView {
                background: #313244;
                color: #cdd6f4;
                border: 1px solid #585b70;
                selection-background-color: #45475a;
                font-family: 'DejaVu Sans Mono', monospace;
                font-size: 12px;
            }
            QScrollBar:vertical {
                background: #181825; width: 10px; border: none;
            }
            QScrollBar::handle:vertical {
                background: #45475a; border-radius: 5px; min-height: 20px;
            }
            QScrollBar::handle:vertical:hover { background: #585b70; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar:horizontal {
                background: #181825; height: 10px; border: none;
            }
            QScrollBar::handle:horizontal {
                background: #45475a; border-radius: 5px; min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover { background: #585b70; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
        """)

    def open_pdf(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open PDF", "", "PDF files (*.pdf);;All files (*)"
        )
        if path:
            p = Path(path)
            self.pdf_viewer.load(p)
            self.setWindowTitle(f"BandLibrary — {p.name}")
            self.statusBar().showMessage(
                f"Loaded: {p.name} ({self.pdf_viewer.page_count()} pages) — "
                f"navigate to first part and press Enter.")

    def new_file(self):
        if self.editor.is_modified():
            r = QMessageBox.question(
                self, "Unsaved changes", "You have unsaved changes. Discard them?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if r != QMessageBox.StandardButton.Yes:
                return
        self.editor.setPlainText("")
        self.editor._current_file = None
        self.editor._modified = False
        self.file_label.setText("New file")
        self.statusBar().showMessage("New file — navigate to the first part and press Enter.")

    def open_manual(self):
        if self.editor.is_modified():
            r = QMessageBox.question(
                self, "Unsaved changes", "You have unsaved changes. Discard them?",
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
            self.statusBar().showMessage(f"Loaded: {p.name}")

    def run_importer(self):
        # Must have both PDF and manual file
        pdf_path = self.pdf_viewer._doc  # check doc is loaded
        if pdf_path is None:
            QMessageBox.warning(self, "Import", "No PDF loaded.")
            return

        manual_path = self.editor.current_file()

        # Save first if needed
        if self.editor.is_modified() or manual_path is None:
            if not self.editor.save():
                return
            manual_path = self.editor.current_file()

        if manual_path is None:
            QMessageBox.warning(self, "Import", "Manual file has not been saved.")
            return

        # Recover the PDF path from the open document
        pdf_file = Path(self.pdf_viewer._doc.name)

        # Find import_piece.py relative to this script
        script_dir = Path(__file__).parent
        importer = script_dir / "import_piece.py"
        if not importer.exists():
            QMessageBox.critical(self, "Import Error",
                f"Could not find import_piece.py at:\n{importer}")
            return

        args = [str(importer), str(pdf_file), "--manual", str(manual_path)]
        if self.force_checkbox.isChecked():
            args.append("--force")

        self.statusBar().showMessage("Running importer…")

        process = QProcess(self)
        process.setProgram(sys.executable)
        process.setArguments(args[1:] if args[0] == sys.executable else args)

        # Run import_piece.py as a module via python3
        proc = QProcess(self)
        proc.start(sys.executable, [str(importer), str(pdf_file),
                                     "--manual", str(manual_path)]
                   + (["--force"] if self.force_checkbox.isChecked() else [])
                   + (["--test"] if self.test_checkbox.isChecked() else []))
        proc.waitForFinished(15000)

        stdout = proc.readAllStandardOutput().data().decode(errors="replace").strip()
        stderr = proc.readAllStandardError().data().decode(errors="replace").strip()
        exit_code = proc.exitCode()

        if exit_code == 0:
            self.statusBar().showMessage(
                f"Import successful: {stdout or 'done'}", 6000)
        else:
            detail = stderr or stdout or "No output."
            QMessageBox.critical(self, "Import Failed",
                f"import_piece.py exited with code {exit_code}:\n\n{detail}")
            self.statusBar().showMessage("Import failed.", 5000)

    def closeEvent(self, event):
        if self.editor.is_modified():
            r = QMessageBox.question(
                self, "Unsaved changes", "You have unsaved changes. Save before closing?",
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel
            )
            if r == QMessageBox.StandardButton.Save:
                if not self.editor.save():
                    event.ignore()
                    return
            elif r == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
        event.accept()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="BandLibrary Manual Part Mapping Editor")
    parser.add_argument(
        "--aliases",
        type=Path,
        default=Path("config/aliases.yaml"),
        help="Path to aliases.yaml (default: config/aliases.yaml)"
    )
    args = parser.parse_args()

    alias_labels = load_alias_labels(args.aliases)

    app = QApplication(sys.argv)
    app.setApplicationName("BandLibrary Manual Editor")
    window = MainWindow(alias_labels)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
