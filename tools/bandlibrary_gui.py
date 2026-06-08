#!/usr/bin/env python3
"""
BandLibrary GUI — tabbed application combining the manual editor and booklet builder.

Usage:
  python3 tools/bandlibrary_gui.py [--aliases config/aliases.yaml]
"""

from __future__ import annotations

import argparse
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path

import yaml
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QStatusBar
)

from lib.editor_widget import EditorWidget, load_alias_labels
from lib.build_widget import BuildWidget


# ---------------------------------------------------------------------------
# User config (~/.config/bandlibrary/gui.yaml)
# ---------------------------------------------------------------------------

CONFIG_PATH = Path.home() / ".config" / "bandlibrary" / "gui.yaml"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            with CONFIG_PATH.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


def save_config(config: dict) -> None:
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with CONFIG_PATH.open("w", encoding="utf-8") as f:
            yaml.safe_dump(config, f, sort_keys=False)
    except Exception:
        pass  # config saving is best-effort


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------

class BandLibraryWindow(QMainWindow):
    def __init__(self, alias_labels: list[str], config: dict):
        super().__init__()
        self._config = config
        self.setWindowTitle("BandLibrary")
        self.resize(
            config.get("window_width", 1400),
            config.get("window_height", 900),
        )

        status = QStatusBar()
        self.setStatusBar(status)

        # Tab widget
        tabs = QTabWidget()
        tabs.setObjectName("mainTabs")

        # Editor tab
        importer_path = Path(__file__).parent / "import_piece.py"
        self.editor_widget = EditorWidget(
            alias_labels=alias_labels,
            status_bar=status,
            importer_path=importer_path,
        )
        self.editor_widget.set_window_title_callback(
            lambda t: self.setWindowTitle(t)
        )
        tabs.addTab(self.editor_widget, "Editor")

        # Build tab
        self.build_widget = BuildWidget(
            status_bar=status,
            config=config,
            save_config_callback=save_config,
        )
        tabs.addTab(self.build_widget, "Build")

        self.setCentralWidget(tabs)
        self._apply_style()

        # Restore last active tab
        last_tab = config.get("last_tab", 0)
        tabs.setCurrentIndex(last_tab)
        tabs.currentChanged.connect(self._on_tab_changed)

    def _on_tab_changed(self, index: int):
        self._config["last_tab"] = index
        save_config(self._config)

    def closeEvent(self, event):
        # Save window size
        self._config["window_width"] = self.width()
        self._config["window_height"] = self.height()
        save_config(self._config)

        if self.editor_widget.prompt_save_on_close():
            event.accept()
        else:
            event.ignore()

    def _apply_style(self):
        self.setStyleSheet("""
            QMainWindow { background: #1e1e2e; }
            QWidget {
                background: #1e1e2e;
                color: #cdd6f4;
                font-family: 'DejaVu Sans', sans-serif;
                font-size: 13px;
            }
            QTabWidget::pane {
                border: none;
                background: #1e1e2e;
            }
            QTabBar::tab {
                background: #181825;
                color: #a6adc8;
                border: 1px solid #313244;
                border-bottom: none;
                padding: 6px 24px;
                font-size: 13px;
            }
            QTabBar::tab:selected {
                background: #1e1e2e;
                color: #cdd6f4;
                border-bottom: 2px solid #89b4fa;
            }
            QTabBar::tab:hover { background: #313244; color: #cdd6f4; }
            QWidget#pdfToolbar, QWidget#editorToolbar,
            QWidget#mainToolbar, QWidget#buildControls,
            QWidget#panelHeader {
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
            QPushButton#importBtn {
                background: #1e4a2e; color: #a6e3a1; border: 1px solid #40a060;
            }
            QPushButton#importBtn:hover { background: #2a5e3a; border-color: #50c070; }
            QPushButton#buildBtn {
                background: #1e3a5f; color: #89b4fa; border: 1px solid #4080c0;
            }
            QPushButton#buildBtn:hover { background: #2a4e7a; border-color: #5090d0; }
            QPushButton#buildBtn:disabled {
                background: #1e1e2e; color: #585b70; border-color: #313244;
            }
            QTextEdit, QTextEdit#outputView {
                background: #181825;
                color: #cdd6f4;
                border: none;
                padding: 12px;
                font-family: 'DejaVu Sans Mono', 'Courier New', monospace;
                font-size: 12px;
                selection-background-color: #45475a;
            }
            QTreeWidget#libraryTree, QListWidget#pieceList {
                background: #181825;
                color: #cdd6f4;
                border: none;
                font-size: 12px;
            }
            QTreeWidget#libraryTree::item:hover,
            QListWidget#pieceList::item:hover {
                background: #313244;
            }
            QTreeWidget#libraryTree::item:selected,
            QListWidget#pieceList::item:selected {
                background: #45475a;
            }
            QComboBox {
                background: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
            }
            QComboBox:hover { border-color: #585b70; }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background: #313244;
                color: #cdd6f4;
                selection-background-color: #45475a;
                border: 1px solid #585b70;
            }
            QLineEdit {
                background: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
            }
            QLineEdit:focus { border-color: #89b4fa; }
            QScrollArea#pdfScroll { background: #11111b; border: none; }
            QLabel#pdfPage { background: #11111b; }
            QLabel#fileLabel { color: #a6adc8; font-size: 12px; }
            QLabel#aliasIndicator { color: #a6e3a1; font-size: 11px; padding: 0 6px; }
            QLabel#aliasIndicatorOff { color: #585b70; font-size: 11px; padding: 0 6px; }
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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="BandLibrary GUI")
    parser.add_argument(
        "--aliases",
        type=Path,
        default=Path("config/aliases.yaml"),
        help="Path to aliases.yaml (default: config/aliases.yaml)",
    )
    args = parser.parse_args()

    alias_labels = load_alias_labels(args.aliases)
    config = load_config()

    app = QApplication(sys.argv)
    app.setApplicationName("BandLibrary")
    window = BandLibraryWindow(alias_labels, config)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
