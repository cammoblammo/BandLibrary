"""
BandBook Help window — displays docs/ markdown files in a simple viewer.
"""

from __future__ import annotations

import re
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem,
    QTextEdit, QSplitter, QFrame, QLabel, QWidget,
)


# ---------------------------------------------------------------------------
# Markdown to plain text
# ---------------------------------------------------------------------------

def markdown_to_plain(text: str) -> str:
    """
    Convert Markdown to readable plain text.
    Strips formatting syntax while preserving structure.
    """
    lines = text.splitlines()
    result = []

    for line in lines:
        # ATX headings: # Heading -> HEADING (uppercased, underlined)
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            level = len(m.group(1))
            content = m.group(2).strip()
            if level == 1:
                result.append("")
                result.append(content.upper())
                result.append("=" * len(content))
                result.append("")
            elif level == 2:
                result.append("")
                result.append(content)
                result.append("-" * len(content))
                result.append("")
            else:
                result.append("")
                result.append(f"  {content}")
                result.append("")
            continue

        # Horizontal rules
        if re.match(r"^[-*_]{3,}\s*$", line):
            result.append("─" * 60)
            continue

        # Code blocks (``` ... ```) — preserve as-is
        if line.strip().startswith("```"):
            result.append("")
            continue

        # Inline code: `code` -> code
        line = re.sub(r"`([^`]+)`", r"\1", line)

        # Bold/italic: **text** or *text* -> text
        line = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", line)

        # Links: [text](url) -> text
        line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)

        # Table rows — keep as-is (already readable)

        result.append(line)

    return "\n".join(result)


# ---------------------------------------------------------------------------
# Doc file registry
# ---------------------------------------------------------------------------

# Order and labels for the sidebar
DOC_FILES = [
    ("Quick Start",      "quickstart.md"),
    ("Manual Editor",    "manual-editor.md"),
    ("Importer",         "importer.md"),
    ("Booklet Builder",  "booklet-builder.md"),
    ("Add Part",         "add-part.md"),
    ("Assignment Editor", "assignment-editor.md"),
    ("Validator",        "validator.md"),
    ("Data Model",       "data-model.md"),
    ("Roadmap",          "roadmap.md"),
]


# ---------------------------------------------------------------------------
# Help Window
# ---------------------------------------------------------------------------

class HelpWindow(QDialog):
    def __init__(self, docs_dir: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("BandBook Help")
        self.resize(900, 650)
        self._docs_dir = docs_dir

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(4)
        splitter.setObjectName("helpSplitter")

        # Sidebar
        sidebar = QWidget()
        sidebar.setObjectName("helpSidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        sidebar_header = QWidget()
        sidebar_header.setObjectName("panelHeader")
        sh_layout = QVBoxLayout(sidebar_header)
        sh_layout.setContentsMargins(12, 10, 12, 10)
        sh_layout.addWidget(QLabel("Contents"))
        sidebar_layout.addWidget(sidebar_header)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("separator")
        sidebar_layout.addWidget(sep)

        self.doc_list = QListWidget()
        self.doc_list.setObjectName("helpDocList")

        for label, filename in DOC_FILES:
            path = docs_dir / filename
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(filename)
            if not path.exists():
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                item.setToolTip(f"{filename} — not found")
            self.doc_list.addItem(item)

        sidebar_layout.addWidget(self.doc_list, stretch=1)
        splitter.addWidget(sidebar)

        # Content pane
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.content_header = QWidget()
        self.content_header.setObjectName("panelHeader")
        ch_layout = QVBoxLayout(self.content_header)
        ch_layout.setContentsMargins(12, 10, 12, 10)
        self.content_title = QLabel("Select a topic from the list")
        ch_layout.addWidget(self.content_title)
        content_layout.addWidget(self.content_header)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setObjectName("separator")
        content_layout.addWidget(sep2)

        self.content_view = QTextEdit()
        self.content_view.setReadOnly(True)
        self.content_view.setObjectName("helpContentView")
        font = QFont("Monospace", 11)
        font.setStyleHint(QFont.StyleHint.TypeWriter)
        self.content_view.setFont(font)
        content_layout.addWidget(self.content_view, stretch=1)

        splitter.addWidget(content_widget)
        splitter.setSizes([200, 700])

        layout.addWidget(splitter)

        self.doc_list.currentItemChanged.connect(self._on_selection_changed)

        # Select first available doc
        if self.doc_list.count() > 0:
            self.doc_list.setCurrentRow(0)

        QShortcut(QKeySequence("Escape"), self).activated.connect(self.close)

    def _on_selection_changed(self, current, previous):
        if current is None:
            return
        path: Path = current.data(Qt.ItemDataRole.UserRole)
        label = current.text()

        self.content_title.setText(label)

        if not path.exists():
            self.content_view.setPlainText(f"File not found: {path}")
            return

        try:
            raw = path.read_text(encoding="utf-8")
            self.content_view.setPlainText(markdown_to_plain(raw))
            self.content_view.verticalScrollBar().setValue(0)
        except Exception as e:
            self.content_view.setPlainText(f"Error reading file: {e}")
