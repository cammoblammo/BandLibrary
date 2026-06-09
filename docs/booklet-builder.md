# Booklet Builder

## Purpose

The booklet builder reads ensemble and piece metadata and generates
one PDF booklet per ensemble part, containing the relevant pages from
each piece in the specified order.

---

## Usage

```
python3 tools/build_booklets.py \
  --ensemble <ensemble.yaml> \
  [--dry-run] \
  [--edition <label>] \
  [--piece-list <file>] \
  <piece-slug> [<piece-slug> ...]
```

Pieces may be specified directly on the command line or via a piece list file.

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--ensemble <path>` | required | Ensemble definition file |
| `--library <path>` | `library/` | Library directory |
| `--output <path>` | `output/` | Output directory |
| `--dry-run` | off | Report matches without generating files |
| `--edition <label>` | none | Label to include in output filenames |
| `--piece-list <file>` | none | Read piece slugs from a file |
| `--test` | off | Write output to `test-output/` instead of `output/` |

---

## Library Browser

The Booklet Builder tab includes a library browser showing all imported pieces.
Each piece can be expanded to show its slug and available parts.

Double-clicking a piece (or selecting it and clicking `Add to Build`) adds it
to the build list.

When a piece is selected, three additional buttons become active:

| Button | Action |
|--------|--------|
| `Assignments…` | Open the assignment editor for the selected piece (requires an ensemble to be selected) |
| `Regen YAML` | Regenerate the piece YAML from its manual file using current aliases |
| `Add Part…` | Append an additional part PDF to the piece |

---

## Piece List File

A plain text file listing one piece slug per line:

```
# Spring concert
hound-dog
cast-in-blues
modal-mixup
```

Blank lines and lines beginning with `#` are ignored.
Slugs must match existing library entries exactly.

---

## Matching Logic

For each ensemble part, the builder searches each piece in order:

1. Check `assignments` in the piece YAML for an explicit mapping
2. Try a direct match against piece part IDs
3. Try each entry in the ensemble part's `fallback` list in order
4. If nothing matches, emit a warning and omit the piece from that part's booklet

---

## Output

```
output/
  trumpet_1.pdf
  trumpet_2.pdf
  trombone.pdf
  ...
  bundle-<timestamp>.zip
```

With `--edition`:

```
output/
  trumpet_1.pdf
  ...
  bundle-spring-concert-20260605-221530.zip
```

One PDF is generated per ensemble part.
Parts with no matches across any piece produce no output file.
All generated PDFs are bundled into a timestamped ZIP archive.

---

## Dry Run Output

```
Trumpet 1:
  hound-dog -> trumpet_1
  cast-in-blues -> trumpet_1
  modal-mixup -> trumpet_2 (fallback)

Trombone:
  hound-dog -> trombone
WARNING: cast-in-blues has no matching part for Trombone
WARNING: modal-mixup has no matching part for Trombone
```

Use dry run to verify matches, fallbacks, and assignments before building.

---

## Ensemble Definition

```yaml
parts:
  - id: trumpet_1
    label: Trumpet 1

  - id: trumpet_2
    label: Trumpet 2

  - id: trumpet_3
    label: Trumpet 3
    fallback: [trumpet_2, trumpet_1]

  - id: trombone
    label: Trombone
```

Each part has an `id` and a `label`. An optional `fallback` list specifies
alternative part IDs to try if a direct match is not found.

---

## Cover Sheets

Each generated booklet PDF has a cover sheet prepended as the first page.

The cover sheet displays:

- Band name (from `ensemble.band` in the ensemble YAML)
- Instrument/part name (large, prominent)
- Edition name (if specified)
- Contents list (piece titles in build order)

To enable cover sheets, add a `band` field to your ensemble YAML:

```yaml
ensemble:
  id: serscb
  name: SERSCB
  band: South Eastern Region Schools Concert Band
```

If `band` is omitted, the cover sheet is still generated without a band name.

---

## Repertoire Files

Piece lists can be saved to and loaded from plain text repertoire files,
allowing named setlists to be version-controlled alongside the library.

```
repertoire/
  spring-concert.txt
  christmas-2026.txt
```

Repertoire files use the same format as `--piece-list`:

```
# Spring Concert 2026
hound-dog
cast-in-blues
modal-mixup
```

In the GUI (Booklet Builder tab), use the Load and Save buttons in the
Build List panel to manage repertoire files.

---

## Assignments

Some pieces use generic part labels (e.g. `Part 1 Bb`) that do not map
directly to instrument names. In these cases, add an `assignments` block
to the piece YAML:

```yaml
assignments:
  trumpet_1: part_1_bb
  trumpet_2: part_2_bb
  alto_sax: part_1_eb
```

Assignments are checked before direct matching and fallbacks.

See `docs/data-model.md` for the full YAML schema.
