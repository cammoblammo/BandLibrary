# BandBook

A toolchain for managing a band music library.

## Overview

BandBook provides a set of tools to:

- create structured metadata for PDF scores and parts
- import pieces into a organised library
- generate instrument-specific booklets for any combination of pieces
- support real-world edge cases such as publisher naming inconsistencies and non-standard part layouts

## Directory Structure

```
library/                    One folder per imported piece
tools/                      Scripts and GUI tools
config/
  ensembles/                Ensemble definition files
  aliases.yaml              Instrument name normalisation
docs/                       Project documentation
output/                     Generated files (not version-controlled)
```

## Tools

### bandbook_gui.py

The main graphical interface. Combines the manual mapping editor and booklet
builder in a single tabbed window.

```
python3 tools/bandbook_gui.py
```

### manual_editor.py

A graphical tool for creating manual mapping files from PDF scores.
This is the recommended starting point when importing a new piece.

```
python3 tools/manual_editor.py
```

### import_piece.py

Imports a PDF and its manual mapping file into the library,
creating structured YAML metadata.

```
python3 tools/import_piece.py "Tune A.pdf" --manual "Tune A.manual.txt"
```

### build_booklets.py

Generates per-instrument PDF booklets from one or more imported pieces.

```
python3 tools/build_booklets.py \
  --ensemble config/ensembles/my-ensemble.yaml \
  tune-a tune-b tune-c
```

### validate_library.py

Validates the integrity of all imported pieces, and optionally checks
ensemble coverage.

```
python3 tools/validate_library.py [--ensemble config/ensembles/my-ensemble.yaml]
```

Appends an additional part PDF to an existing imported piece.
The new pages are merged into the piece PDF and the YAML is updated automatically.

```
python3 tools/add_part.py <piece-slug> "<Part Label>" part.pdf
```

## Quick Start

See `docs/quickstart.md` for a full walkthrough.

## Design Principles

- Deterministic behaviour over clever inference
- Explicit data over hidden logic
- Manual override always possible
- Separation of concerns: piece data, ensemble config, and build logic are independent
- Incremental complexity: build only what is needed now

## Further Reading

- `docs/quickstart.md` — end-to-end workflow
- `docs/manual-editor.md` — graphical mapping editor
- `docs/importer.md` — importer reference
- `docs/booklet-builder.md` — booklet builder reference
- `docs/add-part.md` — adding parts to existing pieces
- `docs/validator.md` — library validation tool reference
- `docs/data-model.md` — YAML schemas and data structures
- `docs/roadmap.md` — project history and future plans
