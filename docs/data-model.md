# Booklet Builder

## Purpose

The booklet builder matches ensemble parts to available parts in each piece.

Version 1 is a dry-run only.

## Usage

python tools/build_booklets.py \
  --ensemble <ensemble.yaml> \
  <piece-slug> <piece-slug> ...

Example:

python tools/build_booklets.py \
  --ensemble config/ensembles/current-band.yaml \
  tune-a tune-b

## Output

Grouped by ensemble part:

Trumpet 1:
  tune-a -> trumpet_1
  tune-b -> trumpet_1

Trumpet 3:
  tune-a -> trumpet_2 (fallback)

## Matching Logic

For each ensemble part:

1. try exact match
2. try fallback list (in order)
3. otherwise mark as missing

## Warnings

Missing parts produce warnings:

WARNING: tune-b has no matching part for Trombone

## Notes

- piece order follows command-line order
- fallback can refer to:
  - other ensemble parts
  - piece part IDs directly

## Limitations (v1)

- no PDF extraction
- no merging
- no output files

## Future

Next version will:

- extract pages from PDFs
- build per-instrument booklets
- output PDFs and zip archive