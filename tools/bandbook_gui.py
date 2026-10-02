#!/usr/bin/env python3
"""
BandBook GUI — tabbed application combining the manual editor and booklet builder.

Usage:
  python3 tools/bandbook_gui.py [--aliases config/aliases.yaml]
"""

from __future__ import annotations

import argparse
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path

import yaml
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QMainWindow, QMessageBox, QPushButton,
    QStatusBar, QTabWidget, QTextEdit, QVBoxLayout,
)

from lib.editor_widget import EditorWidget, load_alias_labels
from lib.build_widget import BuildWidget
from lib.ensemble_widget import EnsembleWidget
from lib.help_window import HelpWindow
from lib.report import build_report
from lib.report_html import render_html
from lib.validator import check_library


# ---------------------------------------------------------------------------
# User config (~/.config/bandbook/gui.yaml)
# ---------------------------------------------------------------------------

CONFIG_PATH = Path.home() / ".config" / "bandbook" / "gui.yaml"


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

class BandBookWindow(QMainWindow):
    def __init__(self, alias_labels: list[str], config: dict,
                 aliases_path: Path | None = None):
        super().__init__()
        self._config = config
        self.setWindowTitle("BandBook")
        self.resize(
            config.get("window_width", 1400),
            config.get("window_height", 900),
        )
        icon_path = Path(__file__).parent.parent / "resources" / "icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

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
            aliases_path=aliases_path,
        )
        self.editor_widget.set_window_title_callback(
            lambda t: self.setWindowTitle(t)
        )
        tabs.addTab(self.editor_widget, "Piece Importer")

        # Build tab
        self.build_widget = BuildWidget(
            status_bar=status,
            config=config,
            save_config_callback=save_config,
        )
        tabs.addTab(self.build_widget, "Booklet Builder")

        # Ensembles tab: saving a band refreshes the Booklet Builder's list
        self.ensemble_widget = EnsembleWidget(status_bar=status)
        self.ensemble_widget.ensembles_changed.connect(self.build_widget.reload_ensembles)
        tabs.addTab(self.ensemble_widget, "Ensembles")
        self._tabs = tabs

        self.setCentralWidget(tabs)
        self._build_menu()
        self._apply_style()

        # Restore last active tab
        last_tab = config.get("last_tab", 0)
        tabs.setCurrentIndex(last_tab)
        self._last_tab = tabs.currentIndex()
        tabs.currentChanged.connect(self._on_tab_changed)

    def _build_menu(self):
        menubar = self.menuBar()

        tools_menu = menubar.addMenu("Tools")
        check_action = tools_menu.addAction("Check Library…")
        check_action.setToolTip("Validate every piece and ensemble")
        check_action.triggered.connect(self._check_library)
        report_action = tools_menu.addAction("Consistency Report…")
        report_action.setToolTip("Open a report of what every chair gets, in your browser")
        report_action.triggered.connect(self._consistency_report)

        help_menu = menubar.addMenu("Help")
        help_action = help_menu.addAction("BandBook Help…")
        help_action.setShortcut("F1")
        help_action.triggered.connect(self._show_help)

    def _ensemble_paths(self) -> list[Path]:
        return sorted((Path(__file__).parent.parent / "config" / "ensembles").glob("*.yaml"))

    def _check_library(self):
        library = self.build_widget.current_library()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            ok, text = check_library(library, self._ensemble_paths())
        except Exception as e:
            ok, text = False, f"ERROR: {e}"
        finally:
            QApplication.restoreOverrideCursor()

        title = "Library Check — no problems found" if ok else "Library Check — problems found"
        TextReportDialog(title, f"Library: {library}\n\n{text}", parent=self).exec()

    def _consistency_report(self):
        library = self.build_widget.current_library()
        output = self.build_widget.current_output()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            report = build_report(library, self._ensemble_paths())
            output.mkdir(parents=True, exist_ok=True)
            path = output / "consistency-report.html"
            path.write_text(render_html(report), encoding="utf-8")
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Consistency Report", f"Could not build the report:\n{e}")
            return
        QApplication.restoreOverrideCursor()

        warnings = sum(1 for f in report.findings if f.severity == "warning")
        self.statusBar().showMessage(
            f"Consistency report: {warnings} warning(s) — saved to {path}", 8000
        )
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            QMessageBox.information(
                self, "Consistency Report",
                f"The report was saved but could not be opened automatically:\n{path}",
            )

    def _show_help(self):
        docs_dir = Path(__file__).parent.parent / "docs"
        dlg = HelpWindow(docs_dir, parent=self)
        dlg.exec()

    def _on_tab_changed(self, index: int):
        # Leaving the Ensembles tab with unsaved changes: builds would use
        # the saved band, so offer to go back and save
        leaving = self._tabs.widget(self._last_tab)
        if leaving is self.ensemble_widget and self.ensemble_widget.unsaved_band():
            r = QMessageBox.question(
                self, "Unsaved band",
                f"{self.ensemble_widget.unsaved_band()} has unsaved changes. Builds use "
                "the saved version.\n\nGo back to the Ensembles tab to save them?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes)
            if r == QMessageBox.StandardButton.Yes:
                self._tabs.blockSignals(True)
                self._tabs.setCurrentIndex(self._last_tab)
                self._tabs.blockSignals(False)
                return
        self._last_tab = index
        self._config["last_tab"] = index
        save_config(self._config)

    def closeEvent(self, event):
        # Closing while a background job runs would kill BandBook mid-job
        busy = self.editor_widget.is_busy() or self.ensemble_widget.is_busy()
        build = getattr(self.build_widget, "_build_thread", None)
        if busy is None and build is not None and build.isRunning():
            busy = "building booklets"
        if busy:
            QMessageBox.information(
                self, "Still working",
                f"BandBook is still {busy}. Close it once that has finished "
                "(the status bar shows progress).")
            event.ignore()
            return

        # Save window size
        self._config["window_width"] = self.width()
        self._config["window_height"] = self.height()
        save_config(self._config)

        if self.ensemble_widget.unsaved_band():
            r = QMessageBox.question(
                self, "Unsaved band",
                f"Discard your unsaved changes to {self.ensemble_widget.unsaved_band()}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if r != QMessageBox.StandardButton.Yes:
                event.ignore()
                return

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
            QMenuBar {
                background: #11111b;
                color: #cdd6f4;
                border-bottom: 1px solid #313244;
                font-size: 13px;
            }
            QMenuBar::item:selected { background: #313244; }
            QMenu {
                background: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
            }
            QMenu::item:selected { background: #45475a; }
            QListWidget#helpDocList {
                background: #181825;
                color: #cdd6f4;
                border: none;
                font-size: 12px;
            }
            QListWidget#helpDocList::item:hover { background: #313244; }
            QListWidget#helpDocList::item:selected { background: #45475a; }
            QTextEdit#helpContentView {
                background: #181825;
                color: #cdd6f4;
                border: none;
                padding: 12px;
            }
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
            QPushButton#importBtn:disabled { background: #2a2a3a; color: #6c7086; border-color: #45475a; }
            QPushButton#buildBtn {
                background: #1e3a5f; color: #89b4fa; border: 1px solid #4080c0;
            }
            QPushButton#buildBtn:hover { background: #2a4e7a; border-color: #5090d0; }
            QPushButton#buildBtn:disabled { background: #2a2a3a; color: #6c7086; border-color: #45475a; }
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
            QCheckBox:disabled { color: #585b70; }
            QCheckBox::indicator:disabled { background: #1e1e2e; border-color: #313244; }
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
# Text report dialog
# ---------------------------------------------------------------------------

class TextReportDialog(QDialog):
    """A read-only, copyable text report."""

    def __init__(self, title: str, text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(820, 620)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        view = QTextEdit()
        view.setReadOnly(True)
        view.setObjectName("outputView")
        font = QFont("Monospace", 11)
        font.setStyleHint(QFont.StyleHint.TypeWriter)
        view.setFont(font)
        view.setPlainText(text)
        layout.addWidget(view, stretch=1)

        buttons = QHBoxLayout()
        copy_btn = QPushButton("Copy")
        close_btn = QPushButton("Close")
        for btn in (copy_btn, close_btn):
            btn.setFixedHeight(30)
        buttons.addWidget(copy_btn)
        buttons.addStretch()
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(text))
        close_btn.clicked.connect(self.accept)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _show_unexpected_error(exc_type, exc, tb):
    """
    Show an unexpected error instead of letting PyQt end the program
    (its default for errors raised by buttons and menus).
    """
    import traceback
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    print(text, file=sys.stderr)
    if QApplication.instance() is None:
        return
    box = QMessageBox(QMessageBox.Icon.Critical, "Something went wrong",
                      f"BandBook hit an unexpected error:\n\n{exc}\n\n"
                      "It is still running, but check the last thing you did. "
                      "The details below help when reporting this.")
    box.setDetailedText(text)
    box.exec()


def main():
    sys.excepthook = _show_unexpected_error
    parser = argparse.ArgumentParser(description="BandBook GUI")
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
    app.setApplicationName("BandBook")
    window = BandBookWindow(alias_labels, config, args.aliases)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
