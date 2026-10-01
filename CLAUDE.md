# BandBook — notes for AI assistants

BandBook turns full-set PDFs of band music into one booklet per player.
Code in `lib/`, entry points in `tools/`, user docs in `docs/` (also shown in
the app's Help window). Read `docs/data-model.md` before touching matching.

## How it is used

- The owner uses **only the GUI** (`tools/bandbook_gui.py`, launched from a
  desktop entry with the project folder as working directory). Explain things
  in terms of tabs, buttons and menus; keep the GUI and its docs first-class.
  The CLI tools share the same `lib/` code and must keep giving the same results.
- Two ensembles: `serscb` (SERSCB) and `workshop` (South-East Sounds Workshop).
- The owner is musically expert. Never guess a part's clef or whether an
  instrument suits a part — ask.

## Matching model

Chair (ensemble part) → piece part, first match wins:
assignment (piece YAML) → direct (same ID) → `prefer` list → `compromise`
list (flagged in builds) → missing.

- `config/reading_groups.yaml` says which written parts each kind of chair
  can read; chairs list groups in `reads`. `flex N` expands to part N in
  those groups. Bare `part_N_in_c` (no `_tc`/`_bc`) is deliberately in no group.
- Lists are **not** chains: `prefer: [clarinet_2]` matches a piece part named
  `clarinet_2`, not what the Clarinet 2 chair would get.
- Assignments are keyed by chair ID, so a chair ID used by both ensembles
  shares assignments.

## Changing library or ensemble data

- Renaming a part means editing `<slug>.manual.txt`, `<slug>.yaml` (id and
  label) **and** any assignments together, or Regen YAML will undo it.
- Before changing rules, part names or assignments, snapshot every chair's
  result for every piece (`lib.report.build_report`), and diff afterwards:
  report gaps filled, parts changed and parts lost. Removing "redundant"
  assignments can silently change results later when a piece's parts change.
- Large redesigns go on a branch. Ask before committing, pushing or merging.

## Things that bite

- PDFs are stored with **Git LFS** (`.gitattributes`). A 131-byte PDF in git
  is an LFS pointer, not a broken file.
- The GUI importer's **Git push** box is on by default: each import commits
  `library/<slug>/` and pushes the current branch.
- `output/` and `test-output/` are build output and not tracked.
- `test/` is a sample library (used by Test mode); `testdata/` holds its
  source PDFs and manual files; `tests/` is the test suite.
- Piece slugs come from the PDF file name, not the `Title:` line.

## Planned work

- Automatic part detection on import: design and owner decisions in
  `docs/design/part-detection.md` (not built yet).

## Commands

```
python3 -m unittest discover -s tests -t .      # test suite (~2 s)
python3 tools/consistency_report.py --html r.html   # check after rule changes
python3 tools/validate_library.py --ensemble config/ensembles/serscb.yaml
```

## Design principles (from docs/roadmap.md)

Data is authoritative; no silent guessing; manual override always possible;
substitutions explicit and predictable; piece data, ensemble config and build
logic stay separate; build only what is needed now.
