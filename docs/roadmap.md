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
  - Explicit fallback chains (replaced in Phase 6 by prefer/compromise lists)
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
  merges PDFs, calculates page range, updates YAML;
  full rollback on failure

- `--test` flag for the importer — writes to `test/` instead of `library/`
- `--test` flag for the booklet builder — writes to `test-output/` instead of `output/`
- Library validation tool (`validate_library.py`)
  Check PDFs exist, YAML is valid and well-formed, page ranges within bounds,
  assignments reference real parts; optional ensemble coverage report via `--ensemble`

### Phase 4 — Backend Extraction

- Core logic moved into `lib/` (library, importer, builder, matcher,
  validator, models), shared by the command-line tools and the app

### Phase 5 — Graphical Interface

- **BandBook** app: one PyQt6 window with Piece Importer and Booklet
  Builder tabs
- Booklet Builder: ensemble selector, edition, test mode, build list with
  repertoire Load/Save, Dry Run/Build with an output panel
- Library browser with Assignments…, Regen YAML and Add Part…
- Import with optional git commit and push
- Help menu showing the `docs/` pages; cover pages with contents

### Phase 6 — Reading Groups and Review

- Reading groups (`config/reading_groups.yaml`): which written parts each
  kind of chair can read
- Ensemble chairs with `reads`, ordered `prefer` and `compromise` lists,
  and `flex N` for flexible arrangements; compromises flagged in builds
- Review screen (Assignments…): what every chair gets and why, with part
  previews; saves only real overrides
- Consistency report and library check, in the Tools menu and as
  command-line tools
- Import notes for parts outside every reading group
- Contents pages bracket pieces a booklet has no part for
- Automated test suite (`tests/`)

---

## Known Issues

- Re-importing a piece with Force replaces its assignments; use Regen YAML
  to change a mapping and keep them
- Desktop launcher icon not displaying — likely a path or PNG conversion
  issue in the `.desktop` file

---

## Planned

### Ideas

- Keep assignments when a piece is re-imported
- Mark pieces as reviewed for an ensemble, and warn about unreviewed ones
- Page rotation correction on import
- Library browser filter/search
- Part duplication (e.g. multiple copies of trumpet parts)
- Divider pages between pieces

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
