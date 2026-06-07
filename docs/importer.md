# Importer

## Purpose

The importer converts a source PDF and a manual mapping file into a structured
library entry consisting of a YAML metadata file, the source PDF, and the
original manual file.

---

## Usage

```
python3 tools/import_piece.py <pdf> --manual <manual.txt> [options]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--manual <path>` | required | Path to the manual mapping file |
| `--library <path>` | `library/` | Path to the library directory |
| `--aliases <path>` | `config/aliases.yaml` | Path to aliases file |
| `--force` | off | Overwrite existing library entry |
| `--test` | off | Write output to `test/` instead of `library/` |

---

## Manual File Format

Each line maps a part label to a PDF page or range:

```
Trumpet 1: 12
Trumpet 2: 13-14
```

An optional title line may appear anywhere in the file:

```
Title: Hound Dog
```

Rules:

- page numbers are 1-based PDF pages
- ranges are inclusive
- blank lines are ignored
- lines beginning with `#` are ignored
- duplicate part labels are an error

If no title is given, the title is inferred from the PDF filename.

The recommended way to create manual files is with the graphical editor.
See `docs/manual-editor.md`.

---

## Alias Resolution

Part labels are normalised to canonical IDs before being written to YAML.

Normalisation:

1. Check `config/aliases.yaml` for an explicit mapping
2. If not found, slugify the label (lowercase, punctuation to underscores)

Example:

```yaml
aliases:
  "Electric guitar": guitar
  "Alto sax 1": alto_sax_1
  "Bb Clarinet": bb_clarinet
```

Alias keys are matched case-insensitively with punctuation and spacing normalised.

---

## Output

Creates a directory in the library:

```
library/<slug>/
  <slug>.pdf
  <slug>.manual.txt
  <slug>.yaml
```

The source PDF and manual file are moved into the library (not copied).
The slug is derived from the PDF filename.

### YAML structure

```yaml
schema_version: 1

piece:
  id: hound-dog
  title: Hound Dog
  source_pdf: hound-dog.pdf
  status: manual

parts:
  - id: trumpet_1
    label: Trumpet 1
    pages: [12, 12]

  - id: trumpet_2
    label: Trumpet 2
    pages: [13, 14]
```

---

## Force Overwrite

If a piece with the same slug already exists, the importer skips it with a warning
unless `--force` is given.

With `--force`:

- the existing directory is backed up before the operation begins
- the backup is removed only after a successful import
- on failure, the original is restored

---

## Validation

The importer checks for:

- missing or unreadable PDF or manual file
- malformed lines in the manual file
- invalid or out-of-order page ranges
- duplicate part labels

Errors are reported and the import is aborted without modifying the library.