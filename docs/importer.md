# BandLibrary

A toolchain for managing a band music library.

## Overview

This project provides tools to:

- import PDF scores and parts into a structured library
- define ensembles and their instrumentation
- generate instrument-specific booklets from multiple pieces

## Directory Structure

library/  
  One folder per piece (PDF + YAML metadata)

tools/  
  Scripts for importing and building booklets

config/ensembles/  
  Ensemble definition files

docs/  
  Project documentation

output/  
  Generated files (ignored by git)

## Quick Start

### Import a piece

python tools/import_piece.py "Tune A.pdf" --manual "Tune A.manual.txt"

### Build booklets (dry run)

python tools/build_booklets.py \
  --ensemble config/ensembles/current-band.yaml \
  tune-a tune-b

## Design Principles

- deterministic behaviour
- explicit data over inference
- manual override always possible
- incremental complexity

See ROADMAP.md for full project plan.