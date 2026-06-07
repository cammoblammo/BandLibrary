# Library Validator

## Purpose

The library validator checks the integrity of imported pieces and optionally
validates an ensemble definition and reports coverage.

Run it after importing a batch of pieces, after manually editing a YAML file,
or any time you want confidence the library is clean before building booklets.

---

## Usage

```
python3 tools/validate_library.py [options] [slug ...]
```

Validates all pieces by default. Pass one or more slugs to check specific pieces.

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--library <path>` | `library/` | Library root directory |
| `--ensemble <path>` | none | Ensemble file to validate and check coverage against |

### Examples

```bash
# Validate all pieces
python3 tools/validate_library.py

# Validate specific pieces
python3 tools/validate_library.py hound-dog cast-in-blues

# Validate library and check ensemble coverage
python3 tools/validate_library.py --ensemble config/ensembles/serscb.yaml
```

---

## What It Checks

### Per piece

- Required files are present (`<slug>.yaml`, `<slug>.pdf`)
- YAML parses cleanly and has the expected structure
- `piece.id` matches the directory slug
- `piece.source_pdf` matches the actual PDF filename
- All page ranges are within the PDF's actual page count
- No duplicate part IDs
- All assignment targets reference part IDs that exist in the piece

### Library-wide

- Every directory in `library/` is a valid piece entry

### With `--ensemble`

- Ensemble YAML is valid and well-formed
- Fallback IDs exist within the ensemble part list
- Coverage report: for each ensemble part, how many library pieces have a match

---

## Output

### Clean library

```
Validating 4 piece(s)...

All 4 piece(s) valid.
```

### Errors found

```
Validating 4 piece(s)...

Errors (2):
  ERROR: hound-dog: part trumpet_1: page range 7-9 exceeds PDF page count (8)
  ERROR: cast-in-blues: assignment for alto_sax references unknown part id part_1_eb

2 error(s) found in 4 piece(s).
```

### Coverage report

```
Coverage report: SERSCB vs 4 piece(s)

  Flute:          4/4
  Clarinet 1:     4/4
  Clarinet 2:     3/4  [missing: modal-mixup]
  Trumpet 1:      4/4
  Trumpet 2:      4/4
  Trumpet 3:      2/4  [missing: hound-dog, cast-in-blues]
  Trombone:       4/4
  Drum Kit:       4/4
  Bass Guitar:    0/4  [no matches]
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All checks passed |
| 1 | One or more errors found |

Warnings are printed but do not affect the exit code.