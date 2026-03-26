# BandLibrary

A toolchain for managing a band music library.

## Goals

- Store source PDFs of band music
- Extract and catalogue parts using YAML metadata
- Build instrument booklets across multiple pieces

## Structure

- `library/` — one folder per piece (PDF + YAML)
- `config/` — ensemble / booklet configuration
- `tools/` — scripts
- `output/` — generated files (ignored by git)

## Notes

- PDFs are stored using Git LFS
- Generated outputs are not tracked
