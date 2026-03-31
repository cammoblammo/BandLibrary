# Importer

## Purpose

The importer converts a PDF and a simple manual description into structured YAML metadata.

## Usage

python tools/import_piece.py <pdf> --manual <manual.txt>

Optional:

--force     overwrite existing piece

## Manual File Format

Each line describes a part:

Trumpet 1: 12  
Trumpet 2: 13-14  

Optional title:

Title: My Piece

## Rules

- page numbers are PDF pages (1-based)
- ranges are inclusive
- blank lines and comments (#) are ignored

## Output

Creates:

library/<slug>/
  <slug>.pdf
  <slug>.manual.txt
  <slug>.yaml

## YAML Structure

schema_version: 1

piece:
  id: tune-a
  title: Tune A
  source_pdf: tune-a.pdf
  status: manual

parts:
  - id: trumpet_1
    label: Trumpet 1
    pages: [12, 12]

## Notes

- filenames are slugified
- part IDs are normalised from labels
- validation catches:
  - malformed lines
  - invalid ranges
  - duplicate IDs

## Limitations (v1)

- no automatic detection
- no alias handling
- no layered part mapping