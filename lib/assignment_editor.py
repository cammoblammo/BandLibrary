"""
BandBook Assignment Editor — review what every chair gets in a piece,
and override it where needed.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pymupdf
import yaml
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QScrollArea, QWidget, QFrame, QMessageBox,
    QGridLayout, QSizePolicy, QCheckBox,
)

from .editor_widget import PdfViewer
from .library import load_ensemble, load_piece
from .matcher import match_part
from .models import EnsemblePart, MatchResult, Piece
from .reading_groups import (
    ReadingGroup, can_read, default_groups_path, expand_entry, load_reading_groups,
)
from .utils import display_title


# Badge text and colours (matching the app's dark palette)
REASONS = {
    "direct":     ("Direct",     "#a6adc8", "#313244"),
    "fallback":   ("Fallback",   "#f9e2af", "#3a3a35"),
    "compromise": ("Compromise", "#1e1e2e", "#fab387"),
    "assignment": ("Assigned",   "#1e1e2e", "#89b4fa"),
    "missing":    ("Missing",    "#1e1e2e", "#f38ba8"),
}
ATTENTION = {"compromise", "assignment", "missing"}


@dataclass
class RowState:
    reason: str            # key of REASONS
    part_id: str | None    # the part the chair will read
    note: str              # explanation shown beside the badge
    save: bool             # whether the selection is stored as an assignment


def _matching_spec(
    specs: list[str],
    part_id: str | None,
    ep: EnsemblePart,
    groups: dict[str, ReadingGroup],
) -> str | None:
    """The entry in a prefer/compromise list (as written) that produced part_id."""
    for spec in specs:
        try:
            ids = expand_entry(spec, ep.reads, groups, ep.id)
        except ValueError:
            continue
        if part_id in ids:
            return spec
    return None


def describe_selection(
    ep: EnsemblePart,
    auto: MatchResult,
    selected: str | None,
    piece: Piece,
    groups: dict[str, ReadingGroup],
) -> RowState:
    """Work out what a chair gets for a given dropdown selection, and why."""
    auto_reason = auto.match_reason or "missing"

    def part_name(part_id: str | None) -> str:
        if part_id is None:
            return "nothing"
        part = piece.parts_by_id.get(part_id)
        return part.label if part else part_id

    if selected is None:
        if auto_reason == "fallback":
            spec = _matching_spec(ep.prefer_spec, auto.matched_id, ep, groups)
            note = f"Preferred: {spec}" if spec else "Preferred substitute"
        elif auto_reason == "compromise":
            spec = _matching_spec(ep.compromise_spec, auto.matched_id, ep, groups)
            note = f"Compromise: {spec} — check it suits" if spec else "Compromise — check it suits"
        elif auto_reason == "direct":
            note = "The piece has this chair's own part"
        else:
            note = "Nothing in this piece matches this chair"
        return RowState(auto_reason, auto.matched_id, note, save=False)

    if selected == auto.matched_id and auto_reason in ("direct", "fallback"):
        return RowState(
            auto_reason, selected,
            "Same as automatic — no assignment needed", save=False,
        )

    if selected == auto.matched_id and auto_reason == "compromise":
        note = "Compromise approved for this piece"
    else:
        note = f"Automatic would be {part_name(auto.matched_id)}"
        if auto.matched_id is not None:
            note += f" ({REASONS[auto_reason][0].lower()})"

    if ep.reads and groups and not can_read(selected, ep.reads, groups):
        note += f" — ⚠ not in what this chair reads ({', '.join(ep.reads)})"

    return RowState("assignment", selected, note, save=True)


# ---------------------------------------------------------------------------
# Part preview
# ---------------------------------------------------------------------------

class PartPreview(QDialog):
    """A separate window showing just the pages of one part."""

    def __init__(self, piece: Piece, part_id: str, chair_label: str, parent=None):
        super().__init__(parent)
        part = piece.parts_by_id[part_id]
        pages = (
            f"p. {part.start_page}" if part.start_page == part.end_page
            else f"pp. {part.start_page}–{part.end_page}"
        )
        self.setWindowTitle(
            f"{chair_label} — {part.label} ({pages}) — {display_title(piece.title)}"
        )
        self.resize(760, 980)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.viewer = PdfViewer()
        layout.addWidget(self.viewer)

        # Copy only this part's pages into an in-memory document
        source = pymupdf.open(str(piece.pdf_path))
        try:
            doc = pymupdf.open()
            doc.insert_pdf(source, from_page=part.start_page - 1, to_page=part.end_page - 1)
        finally:
            source.close()
        self._doc = doc

        QShortcut(QKeySequence("PgDown"), self).activated.connect(self.viewer.next_page)
        QShortcut(QKeySequence("PgUp"), self).activated.connect(self.viewer.prev_page)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self.close)

    def showEvent(self, event):
        super().showEvent(event)
        if self._doc is not None:
            # Load once the window has its size, so the page fits it
            doc, self._doc = self._doc, None
            QTimer.singleShot(0, lambda: self.viewer.set_document(doc))


# ---------------------------------------------------------------------------
# Assignment Editor Dialog
# ---------------------------------------------------------------------------

class AssignmentEditor(QDialog):
    def __init__(
        self,
        piece: Piece,
        ensemble_parts: list[EnsemblePart],
        yaml_path: Path,
        groups: dict[str, ReadingGroup] | None = None,
        ensemble_name: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._piece = piece
        self._ensemble_parts = ensemble_parts
        self._yaml_path = yaml_path
        self._groups = groups or {}

        # What each chair gets with no assignment at all
        unassigned = Piece(
            slug=piece.slug, title=piece.title, pdf_path=piece.pdf_path,
            parts_by_id=piece.parts_by_id, assignments={},
        )
        self._auto = {ep.id: match_part(unassigned, ep) for ep in ensemble_parts}

        title = f"Review — {display_title(piece.title)}"
        if ensemble_name:
            title += f" — {ensemble_name}"
        self.setWindowTitle(title)
        self.resize(980, 640)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header: piece, summary, filter
        header = QWidget()
        header.setObjectName("panelHeader")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 10, 12, 10)
        heading = f"<b>{display_title(piece.title)}</b>  [{piece.slug}]"
        if ensemble_name:
            heading += f"  ·  {ensemble_name}"
        h_layout.addWidget(QLabel(heading))
        h_layout.addStretch()
        self._summary = QLabel()
        self._summary.setTextFormat(Qt.TextFormat.RichText)
        h_layout.addWidget(self._summary)
        h_layout.addSpacing(12)
        self._attention_only = QCheckBox("Only chairs that need a look")
        self._attention_only.setToolTip("Hide chairs with a direct match or a preferred fallback")
        h_layout.addWidget(self._attention_only)
        layout.addWidget(header)

        layout.addWidget(self._separator())

        # Column headers
        col_headers = QWidget()
        ch_layout = QGridLayout(col_headers)
        ch_layout.setContentsMargins(16, 8, 16, 8)
        self._set_columns(ch_layout)
        for col, text in enumerate(("Chair", "Gets", "", "Why", "")):
            ch_layout.addWidget(QLabel(f"<b>{text}</b>"), 0, col)
        layout.addWidget(col_headers)

        layout.addWidget(self._separator())

        # Scrollable rows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("assignmentScroll")

        scroll_content = QWidget()
        self._grid = QGridLayout(scroll_content)
        self._grid.setContentsMargins(16, 8, 16, 8)
        self._grid.setVerticalSpacing(6)
        self._set_columns(self._grid)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._combos: dict[str, QComboBox] = {}
        self._badges: dict[str, QLabel] = {}
        self._notes: dict[str, QLabel] = {}
        self._row_widgets: dict[str, list[QWidget]] = {}
        self._view_buttons: dict[str, QPushButton] = {}

        for row, ep in enumerate(ensemble_parts):
            chair = QLabel(ep.label)
            chair.setMinimumHeight(28)
            chair.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            chair.setToolTip(self._chair_tooltip(ep))

            combo = QComboBox()
            combo.setMinimumHeight(28)
            auto = self._auto[ep.id]
            auto_text = (
                f"Automatic — {self._part_display(auto.matched_id)}"
                if auto.matched_id else "Automatic — nothing"
            )
            combo.addItem(auto_text, userData=None)
            for p in piece.parts_by_id.values():
                combo.addItem(f"{p.label}  [{p.id}]", userData=p.id)

            current = piece.assignments.get(ep.id)
            if current:
                index = combo.findData(current)
                if index >= 0:
                    combo.setCurrentIndex(index)

            view_btn = QPushButton("View")
            view_btn.setFixedHeight(26)
            view_btn.setToolTip(f"Show the pages {ep.label} will read")
            view_btn.clicked.connect(lambda _, e=ep: self._preview(e))

            badge = QLabel()
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setFixedSize(104, 24)
            note = QLabel()
            note.setWordWrap(True)
            note.setStyleSheet("color: #a6adc8;")

            self._grid.addWidget(chair, row, 0)
            self._grid.addWidget(combo, row, 1)
            self._grid.addWidget(view_btn, row, 2)
            self._grid.addWidget(badge, row, 3)
            self._grid.addWidget(note, row, 4)

            self._combos[ep.id] = combo
            self._badges[ep.id] = badge
            self._notes[ep.id] = note
            self._view_buttons[ep.id] = view_btn
            self._row_widgets[ep.id] = [chair, combo, view_btn, badge, note]

            combo.currentIndexChanged.connect(self._refresh)

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, stretch=1)

        layout.addWidget(self._separator())

        # Button row
        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(12, 10, 12, 10)
        btn_layout.setSpacing(8)

        clear_btn = QPushButton("Reset All to Automatic")
        clear_btn.setToolTip("Remove every assignment for this ensemble's chairs in this piece")
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
        self._attention_only.toggled.connect(self._refresh)

        self._refresh()

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _separator() -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("separator")
        return sep

    @staticmethod
    def _set_columns(grid: QGridLayout) -> None:
        grid.setColumnStretch(0, 2)
        grid.setColumnStretch(1, 4)
        grid.setColumnMinimumWidth(2, 56)
        grid.setColumnMinimumWidth(3, 104)
        grid.setColumnStretch(4, 4)
        grid.setHorizontalSpacing(12)

    def _part_display(self, part_id: str | None) -> str:
        if part_id is None:
            return "nothing"
        part = self._piece.parts_by_id.get(part_id)
        return f"{part.label}  [{part_id}]" if part else part_id

    @staticmethod
    def _chair_tooltip(ep: EnsemblePart) -> str:
        lines = [f"{ep.label}  [{ep.id}]"]
        if ep.reads:
            lines.append(f"Reads: {', '.join(ep.reads)}")
        if ep.prefer_spec:
            lines.append(f"Prefers: {', '.join(ep.prefer_spec)}")
        if ep.compromise_spec:
            lines.append(f"Compromise: {', '.join(ep.compromise_spec)}")
        return "\n".join(lines)

    def _state(self, ep: EnsemblePart) -> RowState:
        selected = self._combos[ep.id].currentData()
        return describe_selection(ep, self._auto[ep.id], selected, self._piece, self._groups)

    def _refresh(self, *_):
        counts: Counter = Counter()
        attention_only = self._attention_only.isChecked()

        for ep in self._ensemble_parts:
            state = self._state(ep)
            counts[state.reason] += 1

            text, fg, bg = REASONS[state.reason]
            badge = self._badges[ep.id]
            badge.setText(text)
            badge.setStyleSheet(
                f"background: {bg}; color: {fg}; border-radius: 4px; "
                f"padding: 3px 6px; font-weight: bold;"
            )
            self._notes[ep.id].setText(state.note)
            self._view_buttons[ep.id].setEnabled(state.part_id is not None)

            visible = not attention_only or state.reason in ATTENTION
            for widget in self._row_widgets[ep.id]:
                widget.setVisible(visible)

        parts = []
        for key in ("direct", "fallback", "compromise", "assignment", "missing"):
            if counts[key]:
                text, fg, bg = REASONS[key]
                colour = bg if key in ATTENTION else fg
                parts.append(f'<span style="color:{colour}">{counts[key]} {text.lower()}</span>')
        self._summary.setText("  ·  ".join(parts))

    def _preview(self, ep: EnsemblePart):
        state = self._state(ep)
        if state.part_id is None:
            return
        try:
            preview = PartPreview(self._piece, state.part_id, ep.label, parent=self)
        except Exception as e:
            QMessageBox.critical(self, "Preview", f"Could not open the part:\n{e}")
            return
        preview.show()

    def _clear_all(self):
        for combo in self._combos.values():
            combo.setCurrentIndex(0)

    def assignments(self) -> dict[str, str]:
        """The assignments to store for this ensemble's chairs."""
        result = {}
        for ep in self._ensemble_parts:
            state = self._state(ep)
            if state.save and state.part_id is not None:
                result[ep.id] = state.part_id
        return result

    def _save(self):
        assignments = self.assignments()

        try:
            with self._yaml_path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            # Keep assignments for chairs not shown here (e.g. other ensembles)
            existing = data.get("assignments") or {}
            for ep_id, value in existing.items():
                if ep_id not in self._combos:
                    assignments[ep_id] = value

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
        ensemble_name, _, ensemble_parts = load_ensemble(ensemble_path)
        groups = load_reading_groups(default_groups_path(ensemble_path))
    except Exception as e:
        QMessageBox.critical(parent, "Error", str(e))
        return False

    yaml_path = library / slug / f"{slug}.yaml"

    dlg = AssignmentEditor(
        piece=piece,
        ensemble_parts=ensemble_parts,
        yaml_path=yaml_path,
        groups=groups,
        ensemble_name=ensemble_name,
        parent=parent,
    )
    return dlg.exec() == QDialog.DialogCode.Accepted
