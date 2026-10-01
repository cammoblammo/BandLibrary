# Booklet Builder

## Purpose

The **Booklet Builder** tab turns a list of pieces into one PDF booklet per
chair in an ensemble. Each booklet has a cover page and the pages that chair
reads from each piece, in the order you choose.

---

## The Booklet Builder tab

### Top bar

| Control | Purpose |
|---------|---------|
| **Ensemble** | Which band's chairs to build booklets for (a file in `config/ensembles/`). Remembered between sessions |
| **Edition** | Optional name for this set, e.g. `Spring Concert 2026`. Shown on every cover and used in the ZIP file name |
| **Test mode** | Use the test library (`test/`) and write to `test-output/` instead of `library/` and `output/` |
| **Dry Run** | Show what every chair would get, without writing files |
| **Build** | Write the booklets |

### Library (left)

Every piece in the library. Expand a piece to see its parts and their pages.
A piece that can't be loaded is shown with its error.

| Button | Action |
|--------|--------|
| **Add to Build** (or double-click) | Add the selected piece to the build list |
| **Assignments…** | Open the review screen for the selected piece and ensemble (see **Assignment Editor**) |
| **Regen YAML** | Rebuild the piece's data from its stored part list, keeping its assignments. Use after editing the part list or the aliases |
| **Add Part…** | Append another part's PDF to the piece (see **Add Part**) |
| **Refresh** | Reload the library |

### Build List (top right)

The pieces to build, in booklet order. The order also sets the numbering on
every contents page.

| Button | Action |
|--------|--------|
| **Load** | Replace the list with a repertoire file from `repertoire/` |
| **Save** | Save the list as a repertoire file |
| **Up** / **Down** | Move the selected piece |
| **Remove** | Take the selected piece out of the list |

### Output (bottom right)

Shows the result of the last Dry Run or Build: for each chair, the part it
gets from each piece and why, then warnings and notes. **Clear** empties it.

---

## Dry Run output

```
Trumpet 1:
  hound-dog -> trumpet_1
  modal-mixup -> trumpet_2 (fallback)

Tenor Horn:
  hound-dog -> tenor_horn
  cast-in-blues -> alto_sax_1 (compromise)

Trombone:
  hound-dog -> trombone
  cast-in-blues -> [missing]

WARNING: cast-in-blues has no matching part for Trombone
NOTE: cast-in-blues: Tenor Horn reads alto_sax_1 as a compromise — check it suits
```

- No label: the piece has the chair's own part (direct)
- `(fallback)`: a preferred substitute from the ensemble's rules
- `(compromise)`: a substitute that may not suit the player; check it
- `(assignment)`: chosen for this piece in the review screen
- `[missing]`: nothing for this chair; the piece is bracketed on its cover

To fix a result for one piece, use **Assignments…**. To fix it for every
piece, change the ensemble (see **Setting Up Ensembles**).

---

## How each chair's part is chosen

For each chair and each piece, the first of these that applies:

1. The piece's **assignment** for this chair (set in the review screen)
2. A **direct** match: the piece has the chair's own part
3. The chair's **preferred** substitutes, in order (reported as fallback)
4. The chair's **compromise** substitutes, in order (reported as compromise)
5. **Missing**: a warning, and the piece is left out of that chair's booklet

---

## Output

Booklets are written to `output/` (or `test-output/` in test mode):

```
output/
  trumpet_1.pdf
  trumpet_2.pdf
  trombone.pdf
  ...
  serscb-spring-concert-2026-20261001-193000.zip
```

- One PDF per chair, named after the chair's ID. A chair that gets nothing
  from any piece gets no PDF.
- A ZIP of the booklets from this build, named
  `<ensemble>-<edition>-<date>-<time>.zip` (without an edition:
  `<ensemble>-<date>-<time>.zip`).
- Each build overwrites PDFs of the same name, but PDFs and ZIPs from
  earlier builds stay in the folder. Send the ZIP to be sure you send only
  this build.

### Cover pages

Each booklet starts with a cover showing:

- The band name (`band` in the ensemble file), if set
- The chair's name, large
- The edition, if set
- A contents list of every piece in the build, numbered in build order so
  numbers match across booklets. Pieces this chair has no part for are
  shown greyed in brackets, with a note explaining the brackets

---

## Repertoire files

A repertoire file is a plain text list of pieces, one per line, in order:

```
# Spring Concert 2026
hound-dog
cast-in-blues
modal-mixup
```

Lines starting with `#` and blank lines are ignored. Each line is a piece's
library name, as shown in brackets in the Build List. Keep them in
`repertoire/` so they are saved in the project with everything else.

---

## Command line

The same build can be run without the app:

```
python3 tools/build_booklets.py \
  --ensemble config/ensembles/serscb.yaml \
  [--dry-run] [--edition "Spring Concert 2026"] [--test] \
  [--piece-list repertoire/spring.txt] [<piece> ...]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--ensemble <path>` | required | Ensemble file |
| `--library <path>` | `library/` | Library folder |
| `--output <path>` | `output/` | Output folder |
| `--dry-run` | off | Report matches without writing files |
| `--edition <label>` | none | Edition name |
| `--piece-list <file>` | none | Read pieces from a repertoire file |
| `--test` | off | Write to `test-output/` |
