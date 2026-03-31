# Band Library Tooling Roadmap

## Overview

This project provides a toolchain for managing a band music library.

It consists of two primary tools:

1. Importer  
   Converts source PDFs and manual definitions into structured piece metadata.

2. Booklet Builder  
   Uses piece metadata and ensemble definitions to generate part booklets.

## Design Philosophy

- Prefer deterministic behaviour over clever inference
- Prefer explicit data over hidden logic
- Always allow manual override
- Build complexity incrementally
- Keep piece data, ensemble config, and build logic separate

## Phase 0 — Foundation (Current)

### Goals

- Establish core data model
- Prove basic workflow
- Avoid over-engineering

### Importer (v1)

Features:

- Manual mode only
- One PDF per invocation
- Simple manual file format:

  Trumpet 1: 12  
  Trumpet 2: 13-14  

- Slugified:
  - directory names
  - filenames
  - internal IDs

- Output:
  - canonical YAML per piece

- Validation:
  - malformed lines
  - invalid page ranges
  - duplicate parts

- --force overwrite support

Out of scope:

- automatic detection
- OCR
- alias handling
- layered part mapping

### Ensemble Definition (v1)

Features:

- YAML-based schema
- Explicit part list
- Explicit fallback chains

Example:

parts:
  - id: trumpet_3
    label: Trumpet 3
    fallback: [trumpet_2, trumpet_1]

Out of scope:

- alias mapping
- automatic fallback inference
- instrument families

### Booklet Builder (v1 — dry run)

Features:

- Reads:
  - ensemble YAML
  - piece YAMLs

- Outputs:
  - console report of:
    - part matches
    - fallback usage
    - missing parts warnings

Out of scope:

- PDF extraction
- merging
- zip output

## Phase 1 — Minimal Working System

### Goals

- Generate usable part booklets

### Booklet Builder (v2)

Features:

- Extract pages from PDFs
- Build one PDF per ensemble part
- Respect command-line piece order
- Apply fallback rules
- Emit warnings for missing parts

Output:

output/
  trumpet_1.pdf
  trumpet_2.pdf
  ...
  bundle-<timestamp>.zip

## Phase 2 — Quality of Life

### Importer Enhancements

- Auto-detection of part labels (assist only)
- --dry-run detection preview
- Hybrid mode (--manual + --merge)

### Booklet Builder Enhancements

- Cleaner output naming
- Optional output directories
- Summary reports:
  - fallback usage
  - missing parts
  - coverage

## Phase 3 — Layered / Non-standard Parts

### Problem

Some pieces provide parts like:

- Part 1 Bb
- Part 2 Eb

These do not map directly to instruments.

### Solution (Planned)

Add optional piece-level assignment:

assignments:
  trumpet_1: part_1_bb
  trumpet_2: part_2_bb

### Matching Logic (Future)

1. Check explicit assignment
2. Else try direct match
3. Else try fallback
4. Else warn and omit

## Phase 4 — Naming & Alias System

### Problem

Publisher naming inconsistencies:

- Bb Clarinet vs Clarinet in Bb
- Drum Kit vs Drumset
- Horn vs French Horn

### Solution

Alias mapping layer:

aliases:
  "Clarinet in Bb 1": bb_clarinet_1
  "Bb Clarinet 1": bb_clarinet_1

## Phase 5 — Ensemble Flexibility

Features:

- Multiple ensemble configs
- Select ensemble per build
- Optional setlist file

Example usage:

build_booklets.py --ensemble school.yaml --setlist concert.yaml

## Phase 6 — Advanced Features (Optional)

- Part duplication (e.g. multiple trumpet copies)
- Booklet formatting (covers, layout)
- Instrument grouping
- Repertoire/setlist tracking
- Library query tools
- Divider pages between pieces
- When loading a piece, compare every pages entry against the source PDF page count.

## Key Design Principles

These should not be broken.

1. Data is authoritative  
   - YAML defines truth  
   - Scripts do not silently guess  

2. Manual override always possible  
   - Automation must be bypassable  

3. No silent substitutions  
   - Fallback must be explicit or predictable  

4. Separation of concerns  
   - Piece metadata ≠ ensemble config ≠ build logic  

5. Incremental complexity  
   - Build only what is needed now  

## Current Status

- Importer: implemented, tested
- Ensemble schema: defined
- Booklet builder: dry-run implemented

## Immediate Next Steps

1. Generate real booklet PDFs
2. Extract page ranges from source PDFs
3. Merge extracted parts per ensemble target
4. Add zip output with timestamped archive name

## Long-Term Goal

A system that:

- imports new music quickly
- stores structured metadata
- builds instrument booklets automatically
- handles real-world edge cases without friction