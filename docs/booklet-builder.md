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

For each chair in the ensemble, the builder checks each piece in order:

1. The piece's `assignments` for this chair, if any
2. A direct match: a piece part with the same ID as the chair
3. Each entry in the chair's `prefer` list, in order (reported as **fallback**)
4. Each entry in the chair's `compromise` list, in order (reported as
   **compromise**, with a note to check the part suits the player)
5. If nothing matches, a warning, and the piece is left out of that chair's booklet

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

Tenor Horn:
  hound-dog -> tenor_horn
  cast-in-blues -> alto_sax_1 (compromise)
  modal-mixup -> part_3_in_eb (fallback)

Trombone:
  hound-dog -> trombone
WARNING: cast-in-blues has no matching part for Trombone
NOTE: cast-in-blues: Tenor Horn reads alto_sax_1 as a compromise — check it suits
```

Use dry run to check matches, fallbacks, compromises and assignments before
building. The Assignments… review screen shows the same information for one
piece, with previews of each part.

---

## Ensemble Definition

```yaml
parts:
  - id: trumpet_3
    label: Trumpet 3
    reads: [bb_treble]
    prefer: [trumpet_2, trumpet_1, flex 2]

  - id: tenor_horn
    label: Tenor Horn
    reads: [eb_treble]
    prefer: [flex 3]
    compromise: [alto_clarinet, alto_sax_1]
```

Each chair has an `id` and a `label`, the reading groups it can play, and
ordered `prefer` and `compromise` lists. See `docs/data-model.md` for the
full format, including `flex N` and reading groups.

---

## Cover Sheets

Each generated booklet PDF has a cover sheet prepended as the first page.

The cover sheet displays:

- Band name (from `ensemble.band` in the ensemble YAML)
- Instrument/part name (large, prominent)
- Edition name (if specified)
- Contents list: every piece in the build, numbered in build order so the
  numbers match across booklets. Pieces this instrument has no part for are
  shown greyed in brackets, with a note explaining the brackets

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

Most chairs are matched automatically, including parts of flexible
arrangements (`Part 3 in Eb` and so on) through `flex N`. When one piece
needs a different choice, set an assignment with the Assignments… review
screen, or add an `assignments` block to the piece YAML:

```yaml
assignments:
  tenor_sax: part_4_in_bb_tc
```

Assignments are checked before direct matching, preferred substitutes and
compromises.

See `docs/data-model.md` for the full YAML schema.
