# BandBook Roadmap

## Overview

BandBook is a toolchain for managing a band music library. It provides
tools to import PDF scores, store structured metadata, and generate
instrument-specific booklets automatically.

## Design Philosophy

- Deterministic behaviour over clever inference
- Explicit data over hidden logic
- Manual override always possible
- Separation of concerns: piece data, ensemble config, and build logic are independent
- Incremental complexity: build only what is needed now

---

## Completed

### Phase 0 — Foundation

- Importer (manual mode)
  - Manual mapping file format
  - Slugified directory and file naming
  - Canonical YAML output per piece
  - Validation: malformed lines, invalid ranges, duplicate parts
  - `--force` overwrite with safe backup and rollback
- Ensemble definition schema
  - YAML-based part list
  - Explicit fallback chains
- Booklet builder (dry run)
  - Reads ensemble and piece YAMLs
  - Reports matches, fallbacks, and missing parts

### Phase 1 — Working System

- Booklet builder (full)
  - PDF page extraction
  - Per-instrument PDF generation
  - Fallback resolution
  - Timestamped ZIP archive output

### Phase 2 — Quality of Life

- Alias system
  - `config/aliases.yaml` for normalising publisher naming inconsistencies
  - Case-insensitive, punctuation-tolerant matching
- Layered part assignments
  - `assignments` block in piece YAML
  - Checked before direct matching and fallbacks

### Phase 3 — Manual Mapping Editor

- Graphical split-pane editor (`tools/manual_editor.py`)
  - PDF viewer with page navigation, zoom, and rotation
  - Fit-to-page on load
  - Smart text editor with Enter-to-advance workflow
  - Tab-cycling autocomplete from aliases file
  - `--aliases` flag with `config/aliases.yaml` as default
  - Save / Save As with slugified filename suggestion
  - Import button invoking `import_piece.py` directly
  - Force checkbox for reimport

---

### CLI Enhancements

- `--piece-list <file>` for the booklet builder
  Read repertoire from a plain text file rather than the command line;
  blank lines and `#` comments ignored; combinable with command-line slugs
- `--edition <label>` for the booklet builder
  Include a user-defined label in the ZIP archive filename
- `add_part.py`
  Append an additional part PDF to an existing imported piece;
  merges PDFs, calculates page range, updates YAML, removes source PDF;
  full rollback on failure

- `--test` flag for the importer — writes to `test/` instead of `library/`
- `--test` flag for the booklet builder — writes to `test-output/` instead of `output/`
- Library validation tool (`validate_library.py`)
  Check PDFs exist, YAML is valid and well-formed, page ranges within bounds,
  assignments reference real parts; optional ensemble coverage report via `--ensemble`

## Current Development

---

## Planned

### Phase 4 — Backend Extraction

Extract core logic from CLI scripts into reusable modules:

```
bandbook/
  importer.py
  builder.py
  models.py
```

Required before the GUI can call build and import logic directly
rather than via subprocess.

### Phase 5 — Graphical Interface

A unified PyQt6 application combining the manual editor and a
booklet builder interface in a tabbed window.

#### Editor tab

The existing manual editor, largely unchanged.

#### Build tab

- Ensemble selector
- Piece list (add, remove, reorder)
- Edition label field
- Dry run / Build buttons
- Output report panel

#### Help menu

In-application help drawn from the `docs/` directory.

### Phase 6 — Advanced Features (Future)

- `add_part.py` — append additional part PDFs to existing pieces
- Importer preview mode (`--dry-run`) showing labels and resolved IDs before committing
- Alias feedback — report unmapped labels to help grow `aliases.yaml`
- Assignment editor in the GUI — visual mapping without YAML editing
- Library browser — browse pieces, inspect parts and assignments
- Named repertoire files in `repertoire/` for version-controlled setlist tracking
- Structured JSON output from the builder for GUI integration
- Part duplication (e.g. multiple copies of trumpet parts)
- Divider pages between pieces
- Page rotation correction on import

---

## Key Design Principles

These should not be broken.

1. Data is authoritative — YAML defines truth; scripts do not silently guess
2. Manual override always possible — automation must be bypassable
3. No silent substitutions — fallback must be explicit or predictable
4. Separation of concerns — piece metadata, ensemble config, and build logic are independent
5. Incremental complexity — build only what is needed now

---

## Long-Term Goal

A system that imports new music quickly, stores structured metadata,
builds instrument booklets automatically, and handles real-world
edge cases without friction.
