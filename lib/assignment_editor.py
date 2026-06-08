"""
BandBook Assignment Editor — dialog for setting piece-level part assignments.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QScrollArea, QWidget, QFrame, QMessageBox,
    QGridLayout, QSizePolicy,
)

from .library import load_ensemble, load_piece
from .models import EnsemblePart, Piece


# ---------------------------------------------------------------------------
# Assignment Editor Dialog
# ---------------------------------------------------------------------------

class AssignmentEditor(QDialog):
    def __init__(
        self,
        piece: Piece,
        ensemble_parts: list[EnsemblePart],
        yaml_path: Path,
        parent=None,
    ):
        super().__init__(parent)
        self._piece = piece
        self._ensemble_parts = ensemble_parts
        self._yaml_path = yaml_path

        self.setWindowTitle(f"Assignments — {piece.title}")
        self.resize(640, 500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setObjectName("panelHeader")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 10, 12, 10)
        h_layout.addWidget(QLabel(f"<b>{piece.title}</b>  [{piece.slug}]"))
        h_layout.addStretch()
        layout.addWidget(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("separator")
        layout.addWidget(sep)

        # Column headers
        col_headers = QWidget()
        col_headers.setObjectName("colHeaders")
        ch_layout = QGridLayout(col_headers)
        ch_layout.setContentsMargins(16, 8, 16, 8)
        ch_layout.setColumnStretch(0, 2)
        ch_layout.setColumnStretch(1, 3)
        ch_layout.addWidget(QLabel("Ensemble Part"), 0, 0)
        ch_layout.addWidget(QLabel("Piece Part"), 0, 1)
        layout.addWidget(col_headers)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setObjectName("separator")
        layout.addWidget(sep2)

        # Scrollable assignment rows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("assignmentScroll")

        scroll_content = QWidget()
        self._grid = QGridLayout(scroll_content)
        self._grid.setContentsMargins(16, 8, 16, 8)
        self._grid.setVerticalSpacing(6)
        self._grid.setColumnStretch(0, 2)
        self._grid.setColumnStretch(1, 3)

        # Part options for dropdowns: "— none —" + all piece part ids
        self._part_options = [("— none —", None)] + [
            (f"{p.label}  [{p.id}]", p.id)
            for p in piece.parts_by_id.values()
        ]

        self._combos: dict[str, QComboBox] = {}

        for row, ep in enumerate(ensemble_parts):
            # Ensemble part label
            ep_label = QLabel(ep.label)
            ep_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self._grid.addWidget(ep_label, row, 0)

            # Dropdown for piece part
            combo = QComboBox()
            for display, value in self._part_options:
                combo.addItem(display, userData=value)

            # Pre-populate from existing assignments
            current = piece.assignments.get(ep.id)
            if current:
                for i, (_, value) in enumerate(self._part_options):
                    if value == current:
                        combo.setCurrentIndex(i)
                        break
            else:
                # Check for a direct match and pre-select it
                if ep.id in piece.parts_by_id:
                    for i, (_, value) in enumerate(self._part_options):
                        if value == ep.id:
                            combo.setCurrentIndex(i)
                            break

            self._combos[ep.id] = combo
            self._grid.addWidget(combo, row, 1)

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, stretch=1)

        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.HLine)
        sep3.setObjectName("separator")
        layout.addWidget(sep3)

        # Button row
        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(12, 10, 12, 10)
        btn_layout.setSpacing(8)

        clear_btn = QPushButton("Clear All")
        clear_btn.setToolTip("Remove all assignments from this piece")
        save_btn = QPushButton("Save")
        save_btn.setObjectName("importBtn")
        cancel_btn = QPushButton("Cancel")

        for btn in (clear_btn, save_btn, cancel_btn):
            btn.setFixedHeight(30)

        btn_layout.addWidget(clear_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)

        layout.addWidget(btn_row)

        clear_btn.clicked.connect(self._clear_all)
        save_btn.clicked.connect(self._save)
        cancel_btn.clicked.connect(self.reject)

    def _clear_all(self):
        for combo in self._combos.values():
            combo.setCurrentIndex(0)

    def _save(self):
        # Build new assignments dict (only non-None selections)
        assignments = {}
        for ep_id, combo in self._combos.items():
            value = combo.currentData()
            if value is not None:
                assignments[ep_id] = value

        try:
            with self._yaml_path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if assignments:
                data["assignments"] = assignments
            elif "assignments" in data:
                del data["assignments"]

            with self._yaml_path.open("w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, sort_keys=False)

            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))


# ---------------------------------------------------------------------------
# Helper: open assignment editor for a piece
# ---------------------------------------------------------------------------

def open_assignment_editor(
    slug: str,
    library: Path,
    ensemble_path: Path,
    parent=None,
) -> bool:
    """
    Load the piece and ensemble, open the assignment editor dialog.
    Returns True if saved, False if cancelled.
    """
    try:
        piece = load_piece(library, slug)
        _, _, ensemble_parts = load_ensemble(ensemble_path)
    except Exception as e:
        QMessageBox.critical(parent, "Error", str(e))
        return False

    yaml_path = library / slug / f"{slug}.yaml"

    dlg = AssignmentEditor(
        piece=piece,
        ensemble_parts=ensemble_parts,
        yaml_path=yaml_path,
        parent=parent,
    )
    return dlg.exec() == QDialog.DialogCode.Accepted
