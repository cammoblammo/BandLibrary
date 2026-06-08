#!/usr/bin/env python3
"""
BandLibrary Manual Part Mapping Editor — standalone launcher.

Wraps EditorWidget in a QMainWindow for standalone use.
The editor functionality lives in lib/editor_widget.py.

Usage:
  python3 tools/manual_editor.py [--aliases config/aliases.yaml]
"""

from __future__ import annotations

import argparse
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path

from PyQt6.QtWidgets import QApplication, QMainWindow, QStatusBar
from PyQt6.QtGui import QKeySequence, QShortcut

from lib.editor_widget import EditorWidget, load_alias_labels


class EditorWindow(QMainWindow):
    def __init__(self, alias_labels: list[str]):
        super().__init__()
        self.setWindowTitle("BandLibrary — Manual Part Mapping Editor")
        self.resize(1200, 800)

        status = QStatusBar()
        self.setStatusBar(status)

        self.editor_widget = EditorWidget(
            alias_labels=alias_labels,
            status_bar=status,
            importer_path=Path(__file__).parent / "import_piece.py",
        )
        self.editor_widget.set_window_title_callback(self.setWindowTitle)
        self.setCentralWidget(self.editor_widget)

        self._apply_style()

    def _apply_style(self):
        self.setStyleSheet("""
            QMainWindow { background: #1e1e2e; }
            QWidget {
                background: #1e1e2e;
                color: #cdd6f4;
                font-family: 'DejaVu Sans', sans-serif;
                font-size: 13px;
            }
            QWidget#pdfToolbar, QWidget#editorToolbar, QWidget#mainToolbar {
                background: #181825;
                border-bottom: 1px solid #313244;
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
                background: #1e4a2e; color: #a6e3a1; border: 1px solid #40a060;
            }
            QPushButton#importBtn:hover { background: #2a5e3a; border-color: #50c070; }
            QPushButton#importBtn:disabled {
                background: #1e1e2e; color: #585b70; border-color: #313244;
            }
            QCheckBox { color: #a6adc8; font-size: 12px; }
            QCheckBox::indicator {
                width: 14px; height: 14px;
                border: 1px solid #45475a; border-radius: 3px; background: #313244;
            }
            QCheckBox::indicator:checked { background: #40a060; border-color: #50c070; }
            QFrame#separator { color: #313244; background: #313244; max-height: 1px; }
            QSplitter::handle { background: #313244; }
            QSplitter::handle:hover { background: #585b70; }
            QStatusBar {
                background: #11111b; color: #a6adc8;
                border-top: 1px solid #313244; font-size: 12px; padding: 2px 8px;
            }
            QScrollBar:vertical { background: #181825; width: 10px; border: none; }
            QScrollBar::handle:vertical {
                background: #45475a; border-radius: 5px; min-height: 20px;
            }
            QScrollBar::handle:vertical:hover { background: #585b70; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar:horizontal { background: #181825; height: 10px; border: none; }
            QScrollBar::handle:horizontal {
                background: #45475a; border-radius: 5px; min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover { background: #585b70; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
        """)

    def closeEvent(self, event):
        if self.editor_widget.prompt_save_on_close():
            event.accept()
        else:
            event.ignore()


def main():
    parser = argparse.ArgumentParser(description="BandLibrary Manual Part Mapping Editor")
    parser.add_argument(
        "--aliases",
        type=Path,
        default=Path("config/aliases.yaml"),
        help="Path to aliases.yaml (default: config/aliases.yaml)",
    )
    args = parser.parse_args()

    alias_labels = load_alias_labels(args.aliases)

    app = QApplication(sys.argv)
    app.setApplicationName("BandLibrary Manual Editor")
    window = EditorWindow(alias_labels)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
