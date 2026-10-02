"""
BandBook Ensembles tab: create (by copying), edit and delete bands.

The rules live in lib/ensemble_io.py and lib/library.py (shared with
loading a band from its file); this module is only the screen. Saving
shows what changes for every chair in every piece first, then writes the
file and, if Git push is ticked, commits and pushes it.
"""

from __future__ import annotations

import copy
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QFrame,
    QGridLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QProgressBar, QPushButton, QScrollArea,
    QSpinBox, QSplitter, QStatusBar, QTextEdit, QVBoxLayout, QWidget,
)

from .editor_widget import MAIN_BRANCH, CommitThread, current_branch
from .ensemble_io import (
    BandSpec, ChairSpec, assignments_by_chair, bands_using_chair, check_band, compare,
    copy_assignments,
    copy_band, describe_change, load_pieces, pieces_assigning, read_band,
    readable_library_parts, summarise, suggest_id, write_band,
)
from .library import LibraryError, parse_ensemble
from .ensemble_io import band_data
from .models import TAKES_ALL, TAKES_ONE
from .reading_groups import load_reading_groups


def _header(text: str) -> QWidget:
    header = QWidget()
    header.setObjectName("panelHeader")
    layout = QHBoxLayout(header)
    layout.setContentsMargins(8, 6, 8, 6)
    layout.addWidget(QLabel(f"<b>{text}</b>"))
    layout.addStretch()
    return header


def _buttons(*labels: str) -> tuple[QWidget, list[QPushButton]]:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(8, 4, 8, 6)
    layout.setSpacing(6)
    buttons = []
    for label in labels:
        btn = QPushButton(label)
        btn.setFixedHeight(28)
        layout.addWidget(btn)
        buttons.append(btn)
    layout.addStretch()
    return row, buttons


# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------

class AddEntryDialog(QDialog):
    """Choose a substitute for a chair: only what it can read is offered."""

    def __init__(self, chair: ChairSpec, groups: dict, library: Path, kind: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Add to {chair.label}'s {kind}")
        self.setMinimumSize(460, 520)
        self._chair, self._groups = chair, groups
        self._result: str | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            f"Parts {chair.label} can read ({', '.join(groups[g].label for g in chair.reads)}),\n"
            "most common in the library first:"))
        self.parts = QListWidget()
        for pid, count in readable_library_parts(library, chair, groups):
            item = QListWidgetItem(f"{pid}    — in {count} piece{'s' if count != 1 else ''}")
            item.setData(Qt.ItemDataRole.UserRole, pid)
            self.parts.addItem(item)
        self.parts.itemDoubleClicked.connect(lambda _: self._accept_part())
        layout.addWidget(self.parts, stretch=1)

        # Flexible arrangements
        flex_row = QHBoxLayout()
        flex_row.addWidget(QLabel("Or flexible part"))
        self.flex_n = QSpinBox()
        self.flex_n.setRange(1, 12)
        flex_row.addWidget(self.flex_n)
        self.flex_group = QComboBox()
        self.flex_group.addItem("in any group it reads", userData=None)
        for name in chair.reads:
            if groups[name].flex:
                self.flex_group.addItem(f"in {groups[name].label} only", userData=name)
        flex_row.addWidget(self.flex_group)
        flex_btn = QPushButton("Add flexible part")
        flex_btn.clicked.connect(self._accept_flex)
        flex_row.addWidget(flex_btn)
        flex_row.addStretch()
        layout.addLayout(flex_row)

        # A part that isn't in the library yet
        typed_row = QHBoxLayout()
        typed_row.addWidget(QLabel("Or a part ID not in the library yet:"))
        self.typed = QLineEdit()
        self.typed.setPlaceholderText("e.g. alto_sax_3")
        typed_row.addWidget(self.typed)
        layout.addLayout(typed_row)
        self.problem = QLabel()
        self.problem.setStyleSheet("color: #f38ba8;")
        layout.addWidget(self.problem)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept_part(self):
        item = self.parts.currentItem()
        if item is not None:
            self._result = item.data(Qt.ItemDataRole.UserRole)
            self.accept()

    def _accept_flex(self):
        group = self.flex_group.currentData()
        self._result = f"flex {self.flex_n.value()}" + (f" {group}" if group else "")
        self.accept()

    def _accept_ok(self):
        typed = self.typed.text().strip()
        if not typed:
            self._accept_part()
            return
        from .reading_groups import can_read
        pid = suggest_id(typed)
        if pid == self._chair.id:
            self.problem.setText("That's the chair's own part.")
        elif not can_read(pid, self._chair.reads, self._groups):
            self.problem.setText(f"'{pid}' isn't in what {self._chair.label} reads, so it "
                                 "can't be a substitute.")
        else:
            self._result = pid
            self.accept()

    def result_entry(self) -> str | None:
        return self._result


class NewBandDialog(QDialog):
    """A new band, made by copying an existing one."""

    def __init__(self, bands: dict[str, BandSpec], ensembles_dir: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New band")
        self._bands, self._dir = bands, ensembles_dir
        form = QFormLayout(self)
        self.source = QComboBox()
        for band_id, band in bands.items():
            self.source.addItem(f"{band.name} ({band.band})" if band.band else band.name,
                                userData=band_id)
        self.short = QLineEdit()
        self.short.setPlaceholderText("e.g. JUNIORS")
        self.cover = QLineEdit()
        self.cover.setPlaceholderText("e.g. South East Junior Band")
        self.file_label = QLabel()
        self.file_label.setStyleSheet("color: #a6adc8;")
        self.problem = QLabel()
        self.problem.setStyleSheet("color: #f38ba8;")
        form.addRow("Copy chairs from", self.source)
        form.addRow("Short name", self.short)
        form.addRow("Name on covers", self.cover)
        form.addRow("", self.file_label)
        form.addRow("", self.problem)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.short.textChanged.connect(self._update)
        self._update()

    def band_id(self) -> str:
        return suggest_id(self.short.text())

    def _update(self):
        bid = self.band_id()
        self.file_label.setText(f"Saved as config/ensembles/{bid}.yaml" if bid else "")

    def _accept(self):
        bid = self.band_id()
        if not bid:
            self.problem.setText("Give the band a short name.")
        elif bid in self._bands or (self._dir / f"{bid}.yaml").exists():
            self.problem.setText(f"There is already a band file {bid}.yaml.")
        else:
            self.accept()


class PreviewDialog(QDialog):
    """What saving would change, chair by chair and piece by piece."""

    def __init__(self, title: str, summary: str, lines: list[str], extra: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(760, 560)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>{summary}</b>"))
        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText("\n".join(lines + ([""] + extra if extra else [])) or
                          "No chair gets anything different in any piece.")
        layout.addWidget(text, stretch=1)
        buttons = QDialogButtonBox()
        buttons.addButton("Save", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


# ---------------------------------------------------------------------------
# The tab
# ---------------------------------------------------------------------------

class EnsembleWidget(QWidget):
    ensembles_changed = pyqtSignal()

    def __init__(self, status_bar: QStatusBar | None = None,
                 project_root: Path | None = None, parent=None):
        super().__init__(parent)
        self._status = status_bar or QStatusBar()
        self._root = project_root or Path(__file__).parent.parent
        self._dir = self._root / "config" / "ensembles"
        self._library = self._root / "library"
        self._groups = load_reading_groups(self._root / "config" / "reading_groups.yaml")

        self._saved: dict[str, BandSpec] = {}     # band id -> as saved on disk
        self._band: BandSpec | None = None         # working copy being edited
        self._is_new = False                       # not saved yet
        self._dirty = False
        self._fresh: set[int] = set()              # chairs added since last save (id())
        self._id_changes: list[tuple[str, str, bool]] = []   # old, new, copy assignments
        self._git_thread: CommitThread | None = None
        self._loading = False                      # filling the form, not editing

        self._build_ui()
        self.reload_bands()

    # -----------------------------------------------------------------------
    # Layout
    # -----------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Activity (saving / pushing), top right
        top = QWidget()
        top.setObjectName("mainToolbar")
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(8, 6, 8, 6)
        top_layout.addWidget(QLabel("Create a band by copying one, then adjust its chairs."))
        top_layout.addStretch()
        self.activity_label = QLabel()
        self.activity_bar = QProgressBar()
        self.activity_bar.setRange(0, 0)
        self.activity_bar.setFixedSize(140, 14)
        self.activity_bar.setTextVisible(False)
        self.activity_bar.hide()
        top_layout.addWidget(self.activity_label)
        top_layout.addWidget(self.activity_bar)
        self._activity_timer = QTimer(self)
        self._activity_timer.setSingleShot(True)
        self._activity_timer.timeout.connect(lambda: self.activity_label.setText(""))
        layout.addWidget(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Bands
        bands = QWidget()
        b_layout = QVBoxLayout(bands)
        b_layout.setContentsMargins(0, 0, 0, 0)
        b_layout.setSpacing(0)
        b_layout.addWidget(_header("Bands"))
        self.band_list = QListWidget()
        b_layout.addWidget(self.band_list, stretch=1)
        row, (self.new_btn, self.delete_btn) = _buttons("New (copy)…", "Delete")
        b_layout.addWidget(row)
        splitter.addWidget(bands)

        # Chairs
        chairs = QWidget()
        c_layout = QVBoxLayout(chairs)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(0)
        c_layout.addWidget(_header("Chairs (booklet order)"))
        self.chair_list = QListWidget()
        c_layout.addWidget(self.chair_list, stretch=1)
        row, (self.add_chair_btn, self.remove_chair_btn, self.up_btn, self.down_btn) = \
            _buttons("Add", "Remove", "↑", "↓")
        c_layout.addWidget(row)
        splitter.addWidget(chairs)

        # Chair details
        detail = QWidget()
        d_outer = QVBoxLayout(detail)
        d_outer.setContentsMargins(0, 0, 0, 0)
        d_outer.setSpacing(0)
        d_outer.addWidget(_header("Chair"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        grid = QGridLayout(body)
        grid.setContentsMargins(12, 10, 12, 10)
        grid.setVerticalSpacing(8)
        r = 0
        grid.addWidget(QLabel("Name"), r, 0)
        self.name_edit = QLineEdit()
        self.name_edit.setToolTip("The chair's name, as on its booklet cover")
        grid.addWidget(self.name_edit, r, 1, 1, 2)
        r += 1
        grid.addWidget(QLabel("ID"), r, 0)
        self.id_label = QLabel()
        self.id_label.setToolTip("Booklet file name, and the key for assignments")
        self.change_id_btn = QPushButton("Change…")
        self.change_id_btn.setToolTip("Change this chair's ID (offers to carry its assignments over)")
        id_row = QHBoxLayout()
        id_row.addWidget(self.id_label)
        id_row.addWidget(self.change_id_btn)
        id_row.addStretch()
        grid.addLayout(id_row, r, 1, 1, 2)
        r += 1
        grid.addWidget(QLabel("Reads"), r, 0, Qt.AlignmentFlag.AlignTop)
        reads = QWidget()
        reads_layout = QVBoxLayout(reads)
        reads_layout.setContentsMargins(0, 0, 0, 0)
        reads_layout.setSpacing(2)
        self.read_boxes: dict[str, QCheckBox] = {}
        for name, group in self._groups.items():
            box = QCheckBox(group.label)
            box.setToolTip(name)
            reads_layout.addWidget(box)
            self.read_boxes[name] = box
        grid.addWidget(reads, r, 1, 1, 2)
        r += 1
        self.takes_all_box = QCheckBox("Gets every part it reads (like Percussion)")
        grid.addWidget(self.takes_all_box, r, 1, 1, 2)
        r += 1
        self.lists: dict[str, QListWidget] = {}
        self.list_buttons: dict[str, list[QPushButton]] = {}
        for kind, label in (("prefer", "Prefers"), ("compromise", "Compromises")):
            grid.addWidget(QLabel(label), r, 0, Qt.AlignmentFlag.AlignTop)
            lst = QListWidget()
            lst.setMaximumHeight(130)
            grid.addWidget(lst, r, 1)
            col = QVBoxLayout()
            btns = []
            for text in ("Add…", "↑", "↓", "Remove"):
                btn = QPushButton(text)
                btn.setFixedHeight(26)
                col.addWidget(btn)
                btns.append(btn)
            col.addStretch()
            holder = QWidget()
            holder.setLayout(col)
            grid.addWidget(holder, r, 2)
            self.lists[kind] = lst
            self.list_buttons[kind] = btns
            r += 1
        self.problems_label = QLabel()
        self.problems_label.setWordWrap(True)
        self.problems_label.setStyleSheet("color: #f38ba8;")
        grid.addWidget(self.problems_label, r, 0, 1, 3)
        r += 1
        self.notes_label = QLabel()
        self.notes_label.setWordWrap(True)
        self.notes_label.setStyleSheet("color: #a6adc8;")
        grid.addWidget(self.notes_label, r, 0, 1, 3)
        grid.setRowStretch(r + 1, 1)
        grid.setColumnStretch(1, 1)
        scroll.setWidget(body)
        d_outer.addWidget(scroll, stretch=1)
        splitter.addWidget(detail)
        splitter.setSizes([220, 280, 620])
        layout.addWidget(splitter, stretch=1)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("separator")
        layout.addWidget(sep)

        # Band names, git, save
        foot = QWidget()
        f_layout = QHBoxLayout(foot)
        f_layout.setContentsMargins(8, 8, 8, 8)
        f_layout.addWidget(QLabel("Short name"))
        self.short_edit = QLineEdit()
        self.short_edit.setMaximumWidth(140)
        f_layout.addWidget(self.short_edit)
        f_layout.addWidget(QLabel("Name on covers"))
        self.cover_edit = QLineEdit()
        f_layout.addWidget(self.cover_edit, stretch=1)
        self.git_checkbox = QCheckBox("Git push")
        self.git_checkbox.setChecked(True)
        self.git_checkbox.setToolTip("After saving, commit the band and push the current branch")
        f_layout.addWidget(self.git_checkbox)
        self.revert_btn = QPushButton("Revert")
        self.save_btn = QPushButton("Save…")
        self.save_btn.setObjectName("importBtn")
        for btn in (self.revert_btn, self.save_btn):
            btn.setFixedHeight(30)
            f_layout.addWidget(btn)
        layout.addWidget(foot)

        # Connections
        self.band_list.currentRowChanged.connect(self._on_band_selected)
        self.new_btn.clicked.connect(self.new_band)
        self.delete_btn.clicked.connect(self.delete_band)
        self.chair_list.currentRowChanged.connect(lambda _: self._show_chair())
        self.add_chair_btn.clicked.connect(self.add_chair)
        self.remove_chair_btn.clicked.connect(self.remove_chair)
        self.up_btn.clicked.connect(lambda: self.move_chair(-1))
        self.down_btn.clicked.connect(lambda: self.move_chair(1))
        self.name_edit.textEdited.connect(self._on_name_edited)
        self.change_id_btn.clicked.connect(self.change_id)
        for name, box in self.read_boxes.items():
            box.toggled.connect(lambda checked, n=name: self._on_read_toggled(n, checked))
        self.takes_all_box.toggled.connect(self._on_takes_all)
        for kind, (add, up, down, remove) in self.list_buttons.items():
            add.clicked.connect(lambda _, k=kind: self.add_entry(k))
            up.clicked.connect(lambda _, k=kind: self.move_entry(k, -1))
            down.clicked.connect(lambda _, k=kind: self.move_entry(k, 1))
            remove.clicked.connect(lambda _, k=kind: self.remove_entry(k))
        self.short_edit.textEdited.connect(self._on_band_names_edited)
        self.cover_edit.textEdited.connect(self._on_band_names_edited)
        self.revert_btn.clicked.connect(self.revert)
        self.save_btn.clicked.connect(self.save)

    # -----------------------------------------------------------------------
    # Bands
    # -----------------------------------------------------------------------

    def reload_bands(self, select: str | None = None):
        # Which chairs have assignments, for the "shares assignments" notes
        self._assigned = assignments_by_chair(self._library)
        self._saved = {}
        for path in sorted(self._dir.glob("*.yaml")):
            try:
                self._saved[path.stem] = read_band(path)
            except LibraryError as exc:
                self._status.showMessage(f"Could not read {path.name}: {exc}", 6000)
        self._loading = True
        self.band_list.clear()
        for band_id, band in self._saved.items():
            item = QListWidgetItem(band.name)
            item.setData(Qt.ItemDataRole.UserRole, band_id)
            item.setToolTip(f"{band.band}\nconfig/ensembles/{band_id}.yaml")
            self.band_list.addItem(item)
        self._loading = False
        ids = list(self._saved)
        if ids:
            self.band_list.setCurrentRow(ids.index(select) if select in ids else 0)

    def _on_band_selected(self, row: int):
        if self._loading or row < 0:
            return
        band_id = self.band_list.item(row).data(Qt.ItemDataRole.UserRole)
        if self._band is not None and band_id == self._band.id:
            return
        if not self._confirm_discard():
            self._select_band_row(self._band.id if self._band else None)
            return
        self._open(copy.deepcopy(self._saved[band_id]), new=False)

    def _select_band_row(self, band_id: str | None):
        self._loading = True
        for i in range(self.band_list.count()):
            if self.band_list.item(i).data(Qt.ItemDataRole.UserRole) == band_id:
                self.band_list.setCurrentRow(i)
        self._loading = False

    def _open(self, band: BandSpec, new: bool):
        self._band, self._is_new = band, new
        self._fresh = set()
        self._id_changes = []
        self._set_dirty(new)
        self._loading = True
        self.short_edit.setText(band.name)
        self.cover_edit.setText(band.band)
        self._loading = False
        self._fill_chairs(0)

    def _confirm_discard(self) -> bool:
        if not self._dirty:
            return True
        r = QMessageBox.question(
            self, "Unsaved changes",
            f"Discard your unsaved changes to {self._band.name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        return r == QMessageBox.StandardButton.Yes

    def new_band(self):
        if not self._confirm_discard():
            return
        dlg = NewBandDialog(self._saved, self._dir, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        source = self._saved[dlg.source.currentData()]
        band = copy_band(source, dlg.band_id(), dlg.short.text().strip(), dlg.cover.text().strip())
        # Show it in the list until it's saved
        self._loading = True
        item = QListWidgetItem(f"{band.name}  (new, not saved)")
        item.setData(Qt.ItemDataRole.UserRole, band.id)
        self.band_list.addItem(item)
        self.band_list.setCurrentItem(item)
        self._loading = False
        self._open(band, new=True)
        self._status.showMessage(
            f"New band {band.name}, copied from {source.name}. Adjust its chairs, then Save.", 8000)

    def delete_band(self):
        if self._band is None:
            return
        band = self._band
        if self._is_new:
            self._dirty = False
            self.reload_bands()
            return
        r = QMessageBox.question(
            self, "Delete band",
            f"Delete {band.name} (config/ensembles/{band.id}.yaml)?\n\n"
            "Pieces' assignments are left as they are. "
            + ("The deletion is committed and pushed." if self._pushing() else ""),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if r != QMessageBox.StandardButton.Yes or not self._confirm_branch():
            return
        path = self._dir / f"{band.id}.yaml"
        path.unlink()
        self._dirty = False
        self._band = None
        self.reload_bands()
        self.ensembles_changed.emit()
        if self._pushing():
            self._commit([path], f"Ensemble: delete {band.name}", band.name)
        else:
            self._idle(f"✓ Deleted {band.name}")

    # -----------------------------------------------------------------------
    # Chairs
    # -----------------------------------------------------------------------

    def _chair(self) -> ChairSpec | None:
        row = self.chair_list.currentRow()
        if self._band is None or not 0 <= row < len(self._band.chairs):
            return None
        return self._band.chairs[row]

    def _fill_chairs(self, select: int | None = None):
        row = self.chair_list.currentRow() if select is None else select
        self._loading = True
        self.chair_list.clear()
        for c in self._band.chairs if self._band else []:
            self.chair_list.addItem(c.label or "(no name)")
        self._loading = False
        if self.chair_list.count():
            self.chair_list.setCurrentRow(max(0, min(row, self.chair_list.count() - 1)))
        self._show_chair()

    def _show_chair(self):
        if self._loading:
            return
        chair = self._chair()
        enabled = chair is not None
        for w in (self.name_edit, self.change_id_btn, self.takes_all_box,
                  *self.read_boxes.values(), *self.lists.values(),
                  *[b for bs in self.list_buttons.values() for b in bs]):
            w.setEnabled(enabled)
        self._loading = True
        if chair is None:
            self.name_edit.clear()
            self.id_label.clear()
            for box in self.read_boxes.values():
                box.setChecked(False)
            for lst in self.lists.values():
                lst.clear()
        else:
            self.name_edit.setText(chair.label)
            fresh = id(chair) in self._fresh
            self.id_label.setText(f"{chair.id}" + ("   (follows the name)" if fresh else ""))
            self.change_id_btn.setVisible(not fresh)
            for name, box in self.read_boxes.items():
                box.setChecked(name in chair.reads)
            self.takes_all_box.setChecked(chair.takes == TAKES_ALL)
            for kind, lst in self.lists.items():
                lst.clear()
                lst.addItems(getattr(chair, kind))
                lst.setEnabled(chair.takes != TAKES_ALL)
                for btn in self.list_buttons[kind]:
                    btn.setEnabled(chair.takes != TAKES_ALL)
        self._loading = False
        self._refresh_checks()

    def _unique_id(self, wanted: str, chair: ChairSpec) -> str:
        taken = {c.id for c in self._band.chairs if c is not chair}
        base = wanted or "chair"
        new, n = base, 2
        while new in taken:
            new, n = f"{base}_{n}", n + 1
        return new

    def add_chair(self):
        if self._band is None:
            return
        chair = ChairSpec(id="", label="New chair")
        chair.id = self._unique_id("new_chair", chair)
        row = self.chair_list.currentRow() + 1
        self._band.chairs.insert(row, chair)
        self._fresh.add(id(chair))
        self._changed()
        self._fill_chairs(row)
        self.name_edit.setFocus()
        self.name_edit.selectAll()

    def remove_chair(self):
        chair = self._chair()
        if chair is None:
            return
        r = QMessageBox.question(
            self, "Remove chair", f"Remove {chair.label} from {self._band.name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r != QMessageBox.StandardButton.Yes:
            return
        row = self.chair_list.currentRow()
        del self._band.chairs[row]
        self._changed()
        self._fill_chairs(row)

    def move_chair(self, step: int):
        row = self.chair_list.currentRow()
        chairs = self._band.chairs if self._band else []
        if not 0 <= row < len(chairs) or not 0 <= row + step < len(chairs):
            return
        chairs[row], chairs[row + step] = chairs[row + step], chairs[row]
        self._changed()
        self._fill_chairs(row + step)

    def _on_name_edited(self, text: str):
        chair = self._chair()
        if chair is None or self._loading:
            return
        chair.label = text
        if id(chair) in self._fresh:
            chair.id = self._unique_id(suggest_id(text), chair)
            self.id_label.setText(f"{chair.id}   (follows the name)")
        self.chair_list.currentItem().setText(text or "(no name)")
        self._changed()

    def change_id(self):
        chair = self._chair()
        if chair is None:
            return
        new, ok = QInputDialog.getText(
            self, "Change chair ID",
            f"New ID for {chair.label} (booklet file name, and the key for assignments):",
            text=chair.id)
        new = suggest_id(new) if ok else ""
        if not new or new == chair.id:
            return
        if any(c.id == new for c in self._band.chairs if c is not chair):
            QMessageBox.warning(self, "Change chair ID", f"Another chair already has the ID {new!r}.")
            return
        old = chair.id
        copy_them = False
        assigned = pieces_assigning(self._library, old)
        if assigned:
            others = bands_using_chair(self._dir, old, self._band.id)
            keep = f" They stay under {old!r} too, because {', '.join(others)} still uses it." \
                if others else ""
            r = QMessageBox.question(
                self, "Assignments",
                f"{len(assigned)} piece(s) have assignments for {old!r}. Copy them to "
                f"{new!r} when you save?{keep}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes)
            copy_them = r == QMessageBox.StandardButton.Yes
        chair.id = new
        self._id_changes.append((old, new, copy_them))
        self._changed()
        self._show_chair()

    def _on_read_toggled(self, name: str, checked: bool):
        chair = self._chair()
        if chair is None or self._loading:
            return
        if checked and name not in chair.reads:
            chair.reads.append(name)
        elif not checked and name in chair.reads:
            chair.reads.remove(name)
        # Keep the order the groups are listed in
        chair.reads.sort(key=list(self._groups).index)
        self._changed()

    def _on_takes_all(self, checked: bool):
        chair = self._chair()
        if chair is None or self._loading:
            return
        if checked and (chair.prefer or chair.compromise):
            r = QMessageBox.question(
                self, "Gets every part it reads",
                f"{chair.label} would get every part it reads, so its Prefers and "
                "Compromises lists are no longer used. Clear them?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if r != QMessageBox.StandardButton.Yes:
                self._loading = True
                self.takes_all_box.setChecked(False)
                self._loading = False
                return
            chair.prefer, chair.compromise = [], []
        chair.takes = TAKES_ALL if checked else TAKES_ONE
        self._changed()
        self._show_chair()

    # Prefers / Compromises

    def add_entry(self, kind: str):
        chair = self._chair()
        if chair is None:
            return
        if not chair.reads:
            QMessageBox.information(self, "Add", "Tick what this chair reads first.")
            return
        dlg = AddEntryDialog(chair, self._groups, self._library,
                             "Prefers" if kind == "prefer" else "Compromises", parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.result_entry():
            return
        entry = dlg.result_entry()
        entries = getattr(chair, kind)
        if entry in chair.prefer + chair.compromise:
            QMessageBox.information(self, "Add", f"'{entry}' is already listed.")
            return
        row = self.lists[kind].currentRow()
        entries.insert(row + 1 if row >= 0 else len(entries), entry)
        self._changed()
        self._show_chair()
        self.lists[kind].setCurrentRow(entries.index(entry))

    def move_entry(self, kind: str, step: int):
        chair = self._chair()
        row = self.lists[kind].currentRow()
        entries = getattr(chair, kind) if chair else []
        if not 0 <= row < len(entries) or not 0 <= row + step < len(entries):
            return
        entries[row], entries[row + step] = entries[row + step], entries[row]
        self._changed()
        self._show_chair()
        self.lists[kind].setCurrentRow(row + step)

    def remove_entry(self, kind: str):
        chair = self._chair()
        row = self.lists[kind].currentRow()
        entries = getattr(chair, kind) if chair else []
        if 0 <= row < len(entries):
            del entries[row]
            self._changed()
            self._show_chair()

    def _on_band_names_edited(self, _):
        if self._band is None or self._loading:
            return
        self._band.name = self.short_edit.text().strip()
        self._band.band = self.cover_edit.text().strip()
        self._changed()

    # -----------------------------------------------------------------------
    # Checks
    # -----------------------------------------------------------------------

    def _changed(self):
        self._set_dirty(True)
        self._refresh_checks()

    def _set_dirty(self, dirty: bool):
        self._dirty = dirty
        self.save_btn.setEnabled(dirty)
        self.revert_btn.setEnabled(dirty)

    def _refresh_checks(self):
        if self._band is None:
            self.problems_label.clear()
            self.notes_label.clear()
            return
        check = check_band(self._band, self._groups, self._saved, self._assigned)
        for i in range(self.chair_list.count()):
            label = self._band.chairs[i].label or "(no name)"
            self.chair_list.item(i).setText(("⚠ " if check.chair_errors.get(i) else "") + label)
        row = self.chair_list.currentRow()
        problems = check.chair_errors.get(row, []) + (check.errors if row >= 0 else [])
        self.problems_label.setText("\n".join(problems))
        self.notes_label.setText("\n".join(check.chair_notes.get(row, [])))

    # -----------------------------------------------------------------------
    # Save
    # -----------------------------------------------------------------------

    def revert(self):
        if self._band is None or not self._confirm_discard():
            return
        self._dirty = False
        if self._is_new:
            self.reload_bands()
        else:
            self._open(copy.deepcopy(self._saved[self._band.id]), new=False)

    def save(self) -> bool:
        band = self._band
        if band is None:
            return False
        check = check_band(band, self._groups, self._saved)
        if not check.ok:
            problems = list(check.errors)
            for i, errors in sorted(check.chair_errors.items()):
                problems += [f"{band.chairs[i].label}: {e}" for e in errors]
            QMessageBox.warning(self, "Save", "Fix these first:\n\n" + "\n".join(problems))
            return False

        before = None
        if not self._is_new:
            try:
                _, _, before = parse_ensemble(band_data(self._saved[band.id]), self._groups)
            except LibraryError:
                before = None
        # Old chair IDs line up with the new ones for the comparison
        renamed = {new: old for old, new, _ in self._id_changes}
        if before is not None and renamed:
            before = [copy.replace(ep, id=next((n for n, o in renamed.items() if o == ep.id), ep.id))
                      for ep in before]
        pieces = load_pieces(self._library)
        changes = compare(pieces, before, check.parts)
        extra = []
        for old, new, copy_them in self._id_changes:
            if copy_them:
                n = len(pieces_assigning(self._library, old))
                extra.append(f"Assignments for {old!r} copied to {new!r} in {n} piece(s).")
        title = f"Save {band.name}" + (" (new band)" if self._is_new else "")
        dlg = PreviewDialog(title, summarise(changes),
                            [describe_change(c) for c in changes], extra, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return False
        if self._pushing() and not self._confirm_branch():
            return False

        path = self._dir / f"{band.id}.yaml"
        write_band(path, band)
        changed = [path]
        for old, new, copy_them in self._id_changes:
            if copy_them:
                keep = bool(bands_using_chair(self._dir, old, band.id))
                changed += copy_assignments(self._library, old, new, keep_old=keep)
        self._is_new = False
        self._set_dirty(False)
        self._fresh = set()
        self._id_changes = []
        self.reload_bands(select=band.id)
        self.ensembles_changed.emit()
        if self._pushing():
            self._commit(changed, f"Ensemble: {band.name}", band.name)
        else:
            self._idle(f"✓ Saved {band.name}")
        return True

    # -----------------------------------------------------------------------
    # Git and activity
    # -----------------------------------------------------------------------

    def _pushing(self) -> bool:
        return self.git_checkbox.isChecked()

    def _confirm_branch(self) -> bool:
        if not self._pushing():
            return True
        branch = current_branch(self._root)
        if branch is None or branch == MAIN_BRANCH:
            return True
        r = QMessageBox.question(
            self, "Not on main",
            f'You\'re on branch "{branch}", not {MAIN_BRANCH}. The change will be '
            f'committed and pushed to "{branch}", and only reaches {MAIN_BRANCH} '
            "when that branch is merged.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        return r == QMessageBox.StandardButton.Yes

    def _commit(self, paths: list[Path], message: str, what: str):
        thread = CommitThread(self._root, paths, message, what)
        thread.progress.connect(self._busy)
        thread.done.connect(self._on_git_done)
        self._git_thread = thread
        self.save_btn.setEnabled(False)
        thread.start()

    def _on_git_done(self, ok: bool, message: str):
        self._set_dirty(self._dirty)
        if ok:
            self._idle(f"✓ {message}")
            return
        self._idle("Saved, but the git push failed", ok=False)
        QMessageBox.critical(self, "Git Error",
                             f"The band was saved, but the git step failed:\n\n{message}")

    def _busy(self, text: str):
        self._activity_timer.stop()
        self.activity_label.setText(text)
        self.activity_label.setStyleSheet("color: #f9e2af;")
        self.activity_bar.show()
        self._status.showMessage(text)

    def _idle(self, text: str = "", ok: bool = True):
        self.activity_bar.hide()
        self.activity_label.setText(text)
        self.activity_label.setStyleSheet(f"color: {'#a6e3a1' if ok else '#f38ba8'};")
        self._status.showMessage(text, 6000)
        if text:
            self._activity_timer.start(8000)

    def is_busy(self) -> str | None:
        if self._git_thread is not None and self._git_thread.isRunning():
            return "pushing a band to GitHub"
        return None

    def has_unsaved_changes(self) -> bool:
        return self._dirty

    def unsaved_band(self) -> str | None:
        return self._band.name if self._dirty and self._band else None
