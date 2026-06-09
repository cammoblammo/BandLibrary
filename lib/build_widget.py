"""
BandBook Build Widget — embeddable booklet builder UI.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QListWidget, QListWidgetItem,
    QTreeWidget, QTreeWidgetItem, QSplitter, QFrame,
    QStatusBar, QMessageBox, QFileDialog, QTextEdit,
    QCheckBox, QSizePolicy,
)

from .library import list_pieces, load_piece, load_ensemble
from .assignment_editor import open_assignment_editor
from .importer import regenerate_yaml
from .aliases import load_aliases
from .matcher import build_match_plan, build_report
from .builder import generate_booklets, create_zip_archive
from .utils import slugify_edition


# ---------------------------------------------------------------------------
# Background build thread
# ---------------------------------------------------------------------------

class BuildThread(QThread):
    log = pyqtSignal(str)
    finished = pyqtSignal(bool, str)  # success, message

    def __init__(self, ensemble_path, slugs, library, output_dir, edition, dry_run):
        super().__init__()
        self.ensemble_path = ensemble_path
        self.slugs = slugs
        self.library = library
        self.output_dir = output_dir
        self.edition = edition
        self.dry_run = dry_run

    def run(self):
        try:
            ensemble_name, band_name, ensemble_parts = load_ensemble(self.ensemble_path)
            pieces = [load_piece(self.library, slug) for slug in self.slugs]
            pieces_by_slug = {p.slug: p for p in pieces}

            grouped_matches = build_match_plan(ensemble_parts, pieces)
            report_lines, warning_lines = build_report(
                ensemble_name, ensemble_parts, pieces, grouped_matches
            )

            for line in report_lines:
                self.log.emit(line)
            for line in warning_lines:
                self.log.emit(line)

            if self.dry_run:
                self.log.emit("\nDry run — no files generated.")
                self.finished.emit(True, "Dry run complete.")
                return

            generated = generate_booklets(
                output_dir=self.output_dir,
                ensemble_parts=ensemble_parts,
                pieces_by_slug=pieces_by_slug,
                grouped_matches=grouped_matches,
                band_name=band_name,
                edition=self.edition or "",
            )

            for f in generated:
                self.log.emit(f"Written: {f}")

            archive_stem = self.ensemble_path.stem
            if self.edition:
                archive_stem = f"{archive_stem}-{slugify_edition(self.edition)}"

            zip_path = create_zip_archive(self.output_dir, generated, archive_stem)
            self.log.emit(f"\nArchive: {zip_path}")
            self.log.emit(f"\nGenerated {len(generated)} booklet PDF(s).")

            # Summary
            self.log.emit("\nSummary:")
            for ep in ensemble_parts:
                matches = grouped_matches[ep.id]
                covered = sum(1 for m in matches if m.matched_id is not None)
                self.log.emit(f"  {ep.label}: {covered}/{len(matches)} pieces covered")

            self.finished.emit(True, f"Build complete — {len(generated)} PDF(s) generated.")

        except Exception as e:
            self.log.emit(f"\nERROR: {e}")
            self.finished.emit(False, str(e))


# ---------------------------------------------------------------------------
# Build Widget
# ---------------------------------------------------------------------------

class BuildWidget(QWidget):
    def __init__(self, status_bar: QStatusBar | None = None,
                 config: dict | None = None,
                 save_config_callback=None,
                 parent=None):
        super().__init__(parent)
        self._status = status_bar
        self._config = config or {}
        self._save_config = save_config_callback
        self._build_thread = None

        # Infer project root from this file's location (lib/ -> project root)
        self._project_root = Path(__file__).parent.parent
        self._library = self._project_root / "library"
        self._output = self._project_root / "output"
        self._ensembles_dir = self._project_root / "config" / "ensembles"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Top controls bar
        controls = QWidget()
        controls.setObjectName("buildControls")
        ctrl_layout = QHBoxLayout(controls)
        ctrl_layout.setContentsMargins(10, 8, 10, 8)
        ctrl_layout.setSpacing(12)

        # Ensemble selector
        ctrl_layout.addWidget(QLabel("Ensemble:"))
        self.ensemble_combo = QComboBox()
        self.ensemble_combo.setMinimumWidth(200)
        self.ensemble_combo.setToolTip("Select ensemble definition")
        ctrl_layout.addWidget(self.ensemble_combo)

        ctrl_layout.addSpacing(16)

        # Edition label
        ctrl_layout.addWidget(QLabel("Edition:"))
        self.edition_edit = QLineEdit()
        self.edition_edit.setPlaceholderText("e.g. SpringConcert (optional)")
        self.edition_edit.setMinimumWidth(180)
        ctrl_layout.addWidget(self.edition_edit)

        ctrl_layout.addSpacing(16)

        # Test mode checkbox
        self.test_checkbox = QCheckBox("Test mode")
        self.test_checkbox.setToolTip("Write output to test-output/ instead of output/")
        ctrl_layout.addWidget(self.test_checkbox)

        ctrl_layout.addStretch()

        # Action buttons
        self.dry_run_btn = QPushButton("Dry Run")
        self.dry_run_btn.setToolTip("Check matches without generating files")
        self.build_btn = QPushButton("Build")
        self.build_btn.setObjectName("buildBtn")
        self.build_btn.setToolTip("Generate booklet PDFs")

        for btn in (self.dry_run_btn, self.build_btn):
            btn.setFixedHeight(32)
            btn.setMinimumWidth(90)

        ctrl_layout.addWidget(self.dry_run_btn)
        ctrl_layout.addWidget(self.build_btn)

        layout.addWidget(controls)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("separator")
        layout.addWidget(sep)

        # Main splitter: library browser | piece list + output
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.setHandleWidth(4)

        # ---- Left: Library browser ----
        browser_widget = QWidget()
        browser_layout = QVBoxLayout(browser_widget)
        browser_layout.setContentsMargins(0, 0, 0, 0)
        browser_layout.setSpacing(0)

        browser_header = QWidget()
        browser_header.setObjectName("panelHeader")
        bh_layout = QHBoxLayout(browser_header)
        bh_layout.setContentsMargins(10, 6, 10, 6)
        bh_layout.addWidget(QLabel("Library"))
        bh_layout.addStretch()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedHeight(26)
        refresh_btn.setToolTip("Refresh library")
        self.assign_btn = QPushButton("Assignments…")
        self.assign_btn.setFixedHeight(26)
        self.assign_btn.setToolTip("Edit assignments for selected piece")
        self.assign_btn.setEnabled(False)
        self.regen_btn = QPushButton("Regen YAML")
        self.regen_btn.setFixedHeight(26)
        self.regen_btn.setToolTip("Regenerate YAML from manual file using current aliases")
        self.regen_btn.setEnabled(False)
        self.add_part_btn = QPushButton("Add Part…")
        self.add_part_btn.setFixedHeight(26)
        self.add_part_btn.setToolTip("Append an additional part PDF to this piece")
        self.add_part_btn.setEnabled(False)
        bh_layout.addWidget(self.assign_btn)
        bh_layout.addWidget(self.regen_btn)
        bh_layout.addWidget(self.add_part_btn)
        bh_layout.addWidget(refresh_btn)
        browser_layout.addWidget(browser_header)

        sep_b = QFrame()
        sep_b.setFrameShape(QFrame.Shape.HLine)
        sep_b.setObjectName("separator")
        browser_layout.addWidget(sep_b)

        self.library_tree = QTreeWidget()
        self.library_tree.setHeaderHidden(True)
        self.library_tree.setObjectName("libraryTree")
        self.library_tree.setToolTip("Double-click a piece to add it to the build list")
        browser_layout.addWidget(self.library_tree, stretch=1)

        add_piece_btn = QPushButton("Add to Build")
        add_piece_btn.setFixedHeight(30)
        add_piece_btn.setToolTip("Add selected piece to the build list")
        browser_layout.addWidget(add_piece_btn)

        main_splitter.addWidget(browser_widget)

        # ---- Right: piece list + output ----
        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_splitter.setHandleWidth(4)

        # Piece list panel
        piece_panel = QWidget()
        piece_layout = QVBoxLayout(piece_panel)
        piece_layout.setContentsMargins(0, 0, 0, 0)
        piece_layout.setSpacing(0)

        piece_header = QWidget()
        piece_header.setObjectName("panelHeader")
        ph_layout = QHBoxLayout(piece_header)
        ph_layout.setContentsMargins(10, 6, 10, 6)
        ph_layout.addWidget(QLabel("Build List"))
        ph_layout.addStretch()
        load_rep_btn = QPushButton("Load")
        save_rep_btn = QPushButton("Save")
        load_rep_btn.setFixedHeight(26)
        save_rep_btn.setFixedHeight(26)
        load_rep_btn.setToolTip("Load a repertoire file")
        save_rep_btn.setToolTip("Save build list as a repertoire file")
        ph_layout.addWidget(load_rep_btn)
        ph_layout.addWidget(save_rep_btn)
        ph_layout.addSpacing(8)

        self.up_btn = QPushButton("Up")
        self.down_btn = QPushButton("Down")
        self.remove_btn = QPushButton("Remove")
        for btn in (self.up_btn, self.down_btn, self.remove_btn):
            btn.setFixedHeight(26)
        ph_layout.addWidget(self.up_btn)
        ph_layout.addWidget(self.down_btn)
        ph_layout.addSpacing(4)
        ph_layout.addWidget(self.remove_btn)
        piece_layout.addWidget(piece_header)

        sep_p = QFrame()
        sep_p.setFrameShape(QFrame.Shape.HLine)
        sep_p.setObjectName("separator")
        piece_layout.addWidget(sep_p)

        self.piece_list = QListWidget()
        self.piece_list.setObjectName("pieceList")
        piece_layout.addWidget(self.piece_list, stretch=1)

        right_splitter.addWidget(piece_panel)

        # Output report panel
        output_panel = QWidget()
        output_layout = QVBoxLayout(output_panel)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.setSpacing(0)

        output_header = QWidget()
        output_header.setObjectName("panelHeader")
        oh_layout = QHBoxLayout(output_header)
        oh_layout.setContentsMargins(10, 6, 10, 6)
        self.output_header_label = QLabel("Output")
        oh_layout.addWidget(self.output_header_label)
        oh_layout.addStretch()
        clear_btn = QPushButton("Clear")
        clear_btn.setFixedHeight(24)
        oh_layout.addWidget(clear_btn)
        output_layout.addWidget(output_header)

        sep_o = QFrame()
        sep_o.setFrameShape(QFrame.Shape.HLine)
        sep_o.setObjectName("separator")
        output_layout.addWidget(sep_o)

        self.output_view = QTextEdit()
        self.output_view.setReadOnly(True)
        self.output_view.setObjectName("outputView")
        font = QFont("Monospace", 11)
        font.setStyleHint(QFont.StyleHint.TypeWriter)
        self.output_view.setFont(font)
        output_layout.addWidget(self.output_view, stretch=1)

        right_splitter.addWidget(output_panel)
        right_splitter.setSizes([200, 400])

        main_splitter.addWidget(right_splitter)
        main_splitter.setSizes([300, 700])

        layout.addWidget(main_splitter, stretch=1)

        # Connections
        refresh_btn.clicked.connect(self.refresh_library)
        self.assign_btn.clicked.connect(self._edit_assignments)
        self.regen_btn.clicked.connect(self._regen_yaml)
        self.add_part_btn.clicked.connect(self._add_part)
        self.library_tree.itemSelectionChanged.connect(self._on_library_selection_changed)
        add_piece_btn.clicked.connect(self.add_selected_piece)
        self.library_tree.itemDoubleClicked.connect(self._on_library_double_click)
        self.up_btn.clicked.connect(self.move_up)
        self.down_btn.clicked.connect(self.move_down)
        self.remove_btn.clicked.connect(self.remove_piece)
        load_rep_btn.clicked.connect(self.load_repertoire)
        save_rep_btn.clicked.connect(self.save_repertoire)
        self.dry_run_btn.clicked.connect(self.run_dry_run)
        self.build_btn.clicked.connect(self.run_build)
        clear_btn.clicked.connect(self.output_view.clear)
        self.ensemble_combo.currentIndexChanged.connect(self._on_ensemble_changed)
        self.test_checkbox.stateChanged.connect(lambda _: self.refresh_library())

        # Initialise
        self._populate_ensemble_combo()
        self.refresh_library()
        self._restore_config()

    # -----------------------------------------------------------------------
    # Ensemble selector
    # -----------------------------------------------------------------------

    def _populate_ensemble_combo(self):
        self.ensemble_combo.clear()
        if not self._ensembles_dir.exists():
            return
        ensembles = sorted(self._ensembles_dir.glob("*.yaml"))
        for path in ensembles:
            self.ensemble_combo.addItem(path.stem, userData=path)

    def _on_ensemble_changed(self, index):
        if self._save_config and index >= 0:
            path = self.ensemble_combo.itemData(index)
            if path:
                self._config["last_ensemble"] = str(path)
                self._save_config(self._config)

    def _restore_config(self):
        last = self._config.get("last_ensemble")
        if not last:
            return
        for i in range(self.ensemble_combo.count()):
            if str(self.ensemble_combo.itemData(i)) == last:
                self.ensemble_combo.setCurrentIndex(i)
                return

    # -----------------------------------------------------------------------
    # Library browser
    # -----------------------------------------------------------------------

    def _on_library_selection_changed(self):
        items = self.library_tree.selectedItems()
        has_slug = bool(items and items[0].data(0, Qt.ItemDataRole.UserRole))
        self.assign_btn.setEnabled(has_slug and self._get_ensemble_path() is not None)
        self.regen_btn.setEnabled(has_slug)
        self.add_part_btn.setEnabled(has_slug)

    def _edit_assignments(self):
        items = self.library_tree.selectedItems()
        if not items:
            return
        slug = items[0].data(0, Qt.ItemDataRole.UserRole)
        if not slug:
            return
        ensemble_path = self._get_ensemble_path()
        if ensemble_path is None:
            QMessageBox.warning(self, "Assignments", "Select an ensemble first.")
            return
        library = self._project_root / ("test" if self.test_checkbox.isChecked() else "library")
        saved = open_assignment_editor(slug, library, ensemble_path, parent=self)
        if saved:
            self.refresh_library()
            if self._status:
                self._status.showMessage(f"Assignments saved for {slug}.", 4000)

    def _regen_yaml(self):
        items = self.library_tree.selectedItems()
        if not items:
            return
        slug = items[0].data(0, Qt.ItemDataRole.UserRole)
        if not slug:
            return

        library = self._project_root / ("test" if self.test_checkbox.isChecked() else "library")
        manual_path = library / slug / f"{slug}.manual.txt"

        if not manual_path.exists():
            QMessageBox.warning(self, "Regen YAML",
                f"No manual file found for {slug}:\n{manual_path}")
            return

        aliases_path = self._project_root / "config" / "aliases.yaml"
        try:
            from .aliases import load_aliases
            aliases = load_aliases(aliases_path)
            unaliased = regenerate_yaml(slug, manual_path, library, aliases)
            self.refresh_library()
            if self._status:
                self._status.showMessage(f"YAML regenerated for {slug}.", 4000)
            if unaliased:
                msg = "Unaliased labels:\n" + "\n".join(
                    f"  {label!r:30s} ->  {part_id}"
                    for label, part_id in unaliased
                )
                QMessageBox.information(self, "Unaliased Labels", msg)
        except Exception as e:
            QMessageBox.critical(self, "Regen YAML Failed", str(e))

    def _add_part(self):
        items = self.library_tree.selectedItems()
        if not items:
            return
        slug = items[0].data(0, Qt.ItemDataRole.UserRole)
        if not slug:
            return

        library = self._project_root / ("test" if self.test_checkbox.isChecked() else "library")

        # Ask for part label
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton
        dlg = QDialog(self)
        dlg.setWindowTitle("Add Part")
        dlg.resize(400, 140)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(QLabel("Part label (e.g. 'Tenor Horn'):"))
        label_edit = QLineEdit()
        label_edit.setPlaceholderText("Part label")
        layout.addWidget(label_edit)

        btn_row = QHBoxLayout()
        ok_btn = QPushButton("Choose PDF…")
        ok_btn.setFixedHeight(30)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(30)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

        ok_btn.clicked.connect(dlg.accept)
        cancel_btn.clicked.connect(dlg.reject)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        label = label_edit.text().strip()
        if not label:
            QMessageBox.warning(self, "Add Part", "Part label cannot be empty.")
            return

        # Pick PDF
        pdf_path, _ = QFileDialog.getOpenFileName(
            self, f"Select PDF for '{label}'", "",
            "PDF files (*.pdf);;All files (*)"
        )
        if not pdf_path:
            return

        aliases_path = self._project_root / "config" / "aliases.yaml"
        try:
            aliases = load_aliases(aliases_path)
            # Import add_part logic
            import sys as _sys
            import shutil as _shutil
            import yaml as _yaml
            from pypdf import PdfReader as _PdfReader, PdfWriter as _PdfWriter
            from .aliases import normalise_part_id

            source_pdf = Path(pdf_path)
            piece_dir = library / slug
            yaml_path = piece_dir / f"{slug}.yaml"

            with yaml_path.open("r", encoding="utf-8") as f:
                data = _yaml.safe_load(f)

            piece_meta = data.get("piece", {})
            existing_parts = data.get("parts", [])
            part_id = normalise_part_id(label, aliases)

            existing_ids = {p["id"] for p in existing_parts if isinstance(p, dict)}
            existing_labels = {p.get("label", "") for p in existing_parts if isinstance(p, dict)}

            if part_id in existing_ids:
                QMessageBox.critical(self, "Add Part",
                    f"Part id '{part_id}' already exists in {slug}.")
                return
            if label in existing_labels:
                QMessageBox.critical(self, "Add Part",
                    f"Part label '{label}' already exists in {slug}.")
                return

            piece_pdf_path = piece_dir / piece_meta.get("source_pdf", f"{slug}.pdf")
            existing_reader = _PdfReader(str(piece_pdf_path))
            existing_page_count = len(existing_reader.pages)
            new_reader = _PdfReader(str(source_pdf))
            new_page_count = len(new_reader.pages)

            if new_page_count == 0:
                QMessageBox.critical(self, "Add Part", "Source PDF has no pages.")
                return

            start_page = existing_page_count + 1
            end_page = existing_page_count + new_page_count
            new_part = {"id": part_id, "label": label, "pages": [start_page, end_page]}

            if start_page == end_page:
                page_spec = str(start_page)
            else:
                page_spec = f"{start_page}-{end_page}"
            manual_line = f"{label}: {page_spec}\n"
            manual_path = piece_dir / f"{slug}.manual.txt"

            backup_pdf = piece_pdf_path.with_suffix(".pdf.backup")
            backup_yaml = yaml_path.with_suffix(".yaml.backup")
            backup_manual = manual_path.with_suffix(".manual.txt.backup") if manual_path.exists() else None

            _shutil.copy2(piece_pdf_path, backup_pdf)
            _shutil.copy2(yaml_path, backup_yaml)
            if manual_path.exists():
                _shutil.copy2(manual_path, backup_manual)

            try:
                writer = _PdfWriter()
                for page in existing_reader.pages:
                    writer.add_page(page)
                for page in new_reader.pages:
                    writer.add_page(page)
                with piece_pdf_path.open("wb") as f:
                    writer.write(f)

                data["parts"] = existing_parts + [new_part]
                with yaml_path.open("w", encoding="utf-8") as f:
                    _yaml.safe_dump(data, f, sort_keys=False)

                if not manual_path.exists():
                    print(f"WARNING: no manual file found for {slug} — creating {manual_path.name}")
                with manual_path.open("a", encoding="utf-8") as f:
                    f.write(manual_line)

                backup_pdf.unlink()
                backup_yaml.unlink()
                if backup_manual and backup_manual.exists():
                    backup_manual.unlink()

                self.refresh_library()
                if self._status:
                    self._status.showMessage(
                        f"Added '{label}' ({part_id}) to {slug}: pages {start_page}-{end_page}.", 5000)

            except Exception as e:
                if backup_pdf.exists():
                    _shutil.copy2(backup_pdf, piece_pdf_path)
                    backup_pdf.unlink()
                if backup_yaml.exists():
                    _shutil.copy2(backup_yaml, yaml_path)
                    backup_yaml.unlink()
                if backup_manual and backup_manual.exists():
                    _shutil.copy2(backup_manual, manual_path)
                    backup_manual.unlink()
                raise

        except Exception as e:
            QMessageBox.critical(self, "Add Part Failed", str(e))

    def refresh_library(self):
        self.library_tree.clear()
        library = self._project_root / ("test" if self.test_checkbox.isChecked() else "library")
        slugs = list_pieces(library)

        for slug in slugs:
            try:
                piece = load_piece(library, slug)
                item = QTreeWidgetItem([piece.title])
                item.setData(0, Qt.ItemDataRole.UserRole, slug)
                item.setToolTip(0, slug)

                # Slug as child item
                slug_child = QTreeWidgetItem([f"  {slug}"])
                slug_child.setData(0, Qt.ItemDataRole.UserRole, slug)
                item.addChild(slug_child)

                # Parts as child items
                for part in piece.parts_by_id.values():
                    part_item = QTreeWidgetItem(
                        [f"  {part.label}  (pp. {part.start_page}–{part.end_page})"]
                    )
                    item.addChild(part_item)

                self.library_tree.addTopLevelItem(item)
            except Exception as e:
                item = QTreeWidgetItem([f"{slug} — ERROR: {e}"])
                self.library_tree.addTopLevelItem(item)

        if self._status:
            self._status.showMessage(f"Library: {len(slugs)} piece(s) loaded.", 3000)

    def _on_library_double_click(self, item: QTreeWidgetItem, column: int):
        slug = item.data(0, Qt.ItemDataRole.UserRole)
        if slug:
            self._add_piece(slug)

    def add_selected_piece(self):
        items = self.library_tree.selectedItems()
        if not items:
            return
        slug = items[0].data(0, Qt.ItemDataRole.UserRole)
        if slug:
            self._add_piece(slug)

    def _add_piece(self, slug: str):
        # Check not already in list
        for i in range(self.piece_list.count()):
            if self.piece_list.item(i).data(Qt.ItemDataRole.UserRole) == slug:
                if self._status:
                    self._status.showMessage(f"{slug} is already in the build list.", 3000)
                return
        library = self._project_root / ("test" if self.test_checkbox.isChecked() else "library")
        try:
            piece = load_piece(library, slug)
            item = QListWidgetItem(f"{piece.title}  [{slug}]")
            item.setData(Qt.ItemDataRole.UserRole, slug)
            item.setToolTip(f"{len(piece.parts_by_id)} part(s)")
            self.piece_list.addItem(item)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not load piece {slug}:\n{e}")

    # -----------------------------------------------------------------------
    # Piece list management
    # -----------------------------------------------------------------------

    def move_up(self):
        row = self.piece_list.currentRow()
        if row <= 0:
            return
        item = self.piece_list.takeItem(row)
        self.piece_list.insertItem(row - 1, item)
        self.piece_list.setCurrentRow(row - 1)

    def move_down(self):
        row = self.piece_list.currentRow()
        if row < 0 or row >= self.piece_list.count() - 1:
            return
        item = self.piece_list.takeItem(row)
        self.piece_list.insertItem(row + 1, item)
        self.piece_list.setCurrentRow(row + 1)

    def remove_piece(self):
        row = self.piece_list.currentRow()
        if row >= 0:
            self.piece_list.takeItem(row)

    def _get_slugs(self) -> list[str]:
        return [
            self.piece_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.piece_list.count())
        ]

    # -----------------------------------------------------------------------
    # Repertoire load / save
    # -----------------------------------------------------------------------

    def load_repertoire(self):
        repertoire_dir = str(self._project_root / "repertoire")
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Repertoire", repertoire_dir,
            "Repertoire files (*.txt);;All files (*)"
        )
        if not path:
            return
        try:
            slugs = []
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    slugs.append(line)
            if not slugs:
                QMessageBox.warning(self, "Load Repertoire", "No pieces found in file.")
                return
            self.piece_list.clear()
            errors = []
            for slug in slugs:
                try:
                    library = self._project_root / ("test" if self.test_checkbox.isChecked() else "library")
                    piece = load_piece(library, slug)
                    item = QListWidgetItem(f"{piece.title}  [{slug}]")
                    item.setData(Qt.ItemDataRole.UserRole, slug)
                    item.setToolTip(f"{len(piece.parts_by_id)} part(s)")
                    self.piece_list.addItem(item)
                except Exception as e:
                    errors.append(f"{slug}: {e}")
            if errors:
                QMessageBox.warning(self, "Load Repertoire",
                    f"Some pieces could not be loaded:\n" + "\n".join(errors))
            if self._status:
                self._status.showMessage(
                    f"Loaded repertoire: {len(slugs)} piece(s) from {Path(path).name}", 4000)
        except Exception as e:
            QMessageBox.critical(self, "Load Repertoire", str(e))

    def save_repertoire(self):
        slugs = self._get_slugs()
        if not slugs:
            QMessageBox.warning(self, "Save Repertoire", "Build list is empty.")
            return
        repertoire_dir = self._project_root / "repertoire"
        repertoire_dir.mkdir(exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Repertoire", str(repertoire_dir),
            "Repertoire files (*.txt);;All files (*)"
        )
        if not path:
            return
        if not path.endswith(".txt"):
            path += ".txt"
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# BandBook repertoire\n")
                for slug in slugs:
                    f.write(f"{slug}\n")
            if self._status:
                self._status.showMessage(f"Saved repertoire: {Path(path).name}", 4000)
        except Exception as e:
            QMessageBox.critical(self, "Save Repertoire", str(e))

    # -----------------------------------------------------------------------
    # Build / dry run
    # -----------------------------------------------------------------------

    def _get_ensemble_path(self) -> Path | None:
        idx = self.ensemble_combo.currentIndex()
        if idx < 0:
            return None
        return self.ensemble_combo.itemData(idx)

    def run_dry_run(self):
        self._run(dry_run=True)

    def run_build(self):
        self._run(dry_run=False)

    def _run(self, dry_run: bool):
        ensemble_path = self._get_ensemble_path()
        if ensemble_path is None:
            QMessageBox.warning(self, "Build", "No ensemble selected.")
            return

        slugs = self._get_slugs()
        if not slugs:
            QMessageBox.warning(self, "Build", "No pieces in the build list.")
            return

        test_mode = self.test_checkbox.isChecked()
        output_dir = self._project_root / ("test-output" if test_mode else "output")
        library = self._project_root / ("test" if test_mode else "library")
        edition = self.edition_edit.text().strip() or None

        # Clear and head the output panel
        self.output_view.clear()
        run_type = "Dry run" if dry_run else "Build"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.output_header_label.setText(f"Output — {run_type} — {timestamp}")
        self._log(f"{run_type} started: {timestamp}")
        self._log(f"Ensemble: {ensemble_path.stem}")
        self._log(f"Library: {library}")
        self._log(f"Pieces: {', '.join(slugs)}")
        if edition:
            self._log(f"Edition: {edition}")
        self._log("")

        self.dry_run_btn.setEnabled(False)
        self.build_btn.setEnabled(False)

        self._build_thread = BuildThread(
            ensemble_path=ensemble_path,
            slugs=slugs,
            library=library,
            output_dir=output_dir,
            edition=edition,
            dry_run=dry_run,
        )
        self._build_thread.log.connect(self._log)
        self._build_thread.finished.connect(self._on_build_finished)
        self._build_thread.start()

    def _log(self, message: str):
        self.output_view.append(message)

    def _on_build_finished(self, success: bool, message: str):
        self.dry_run_btn.setEnabled(True)
        self.build_btn.setEnabled(True)
        if self._status:
            self._status.showMessage(message, 6000)
