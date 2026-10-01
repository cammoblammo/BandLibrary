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
  reading_groups.yaml       Which written parts each kind of chair can read
docs/                       Project documentation
output/                     Generated files (not version-controlled)
```

## Tools

### bandbook_gui.py

The BandBook app, and the normal way to use BandBook. Its Piece Importer and
Booklet Builder tabs cover importing, reviewing and building, and its Tools
menu runs the library check and consistency report. The other tools below
are the same functions for the command line.

```
python3 tools/bandbook_gui.py
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

### add_part.py

Appends an additional part PDF to an existing imported piece.
The new pages are merged into the piece PDF and the YAML is updated automatically.

```
python3 tools/add_part.py <piece-slug> "<Part Label>" part.pdf
```

### consistency_report.py

Reports how every chair in each ensemble gets its music across the whole
library, and flags inconsistencies in fallbacks, part names and assignments.

```
python3 tools/consistency_report.py [--html report.html]
```

## Installation

Requires Python 3 (developed on 3.13 and 3.14) and the packages below.

```
python3 -m pip install -r requirements.txt
```

Library PDFs are stored with Git LFS; run `git lfs install` before cloning.

## Tests

```
python3 -m unittest discover -s tests -t .
```

The tests use the sample pieces in `test/` and `testdata/`, work on temporary
copies, and also check that the real library and ensembles are consistent.

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
- `docs/assignment-editor.md` — setting piece-level part assignments
- `docs/ensembles.md` — setting up ensembles and chairs
- `docs/validator.md` — library check (Tools menu and command line)
- `docs/consistency-report.md` — library-wide matching report
- `docs/data-model.md` — YAML schemas and data structures
- `docs/roadmap.md` — project history and future plans
