# BandBook Quickstart

A complete walkthrough of the normal import-and-build workflow.

---

## 1. Create a manual mapping file

The recommended way to create a manual mapping file is with the BandBook GUI:

```
python3 tools/bandbook_gui.py
```

This opens the tabbed interface. Use the Editor tab to map parts.

See `docs/manual-editor.md` for full instructions.

The editor produces a `.manual.txt` file like this:

```
Title: Hound Dog

Flute: 15
Clarinet 1: 13
Clarinet 2: 12
Alto Sax: 10
Tenor Sax: 9
Trumpet 1: 7
Trumpet 2: 6
Trombone: 5
Drum Kit: 3
Auxiliary Percussion: 1-2
```

Each line maps a part label to a PDF page number or range.
Page numbers are 1-based and ranges are inclusive.

---

## 2. Import the piece

```
python3 tools/import_piece.py "Hound Dog.pdf" --manual "Hound Dog.manual.txt"
```

This creates:

```
library/hound-dog/
  hound-dog.pdf
  hound-dog.manual.txt
  hound-dog.yaml
```

The source PDF and manual file are moved into the library.
The YAML file contains the structured metadata used by the booklet builder.

---

## 3. Check the generated YAML

Open `library/hound-dog/hound-dog.yaml` and verify:

- part IDs look sensible
- page ranges are correct
- `source_pdf` points to the right file

If a part ID is wrong (e.g. a publisher uses an unusual instrument name),
add an alias to `config/aliases.yaml` and reimport:

```
python3 tools/import_piece.py "Hound Dog.pdf" --manual "Hound Dog.manual.txt" --force
```

`--force` safely overwrites the existing library entry.

---

## 4. Review the piece, and assign parts where needed

Most chairs get a part automatically: their own part, a preferred substitute,
or, for flexible arrangements labelled like `Part 3 in Eb`, the matching
`flex` part. Label flexible parts as `Part N in <key>`, adding `TC` or `BC`
for parts in C (e.g. `Part 4 in C BC`), so they are matched by clef.

In the GUI, select the piece and an ensemble and click `Assignments…` to see
what every chair gets and why. Use `View` to check a part, and choose a
different part for any chair that needs one. Choices are saved as
assignments in the piece YAML:

```yaml
assignments:
  tenor_sax: part_4_in_bb_tc
```

Assignments map chair IDs to piece part IDs, and are checked before any
automatic matching.

---

## 5. Dry-run the booklet build

```
python3 tools/build_booklets.py \
  --ensemble config/ensembles/serscb.yaml \
  --dry-run \
  hound-dog another-piece
```

The dry run prints a report without generating any files:

```
Trumpet 1:
  hound-dog -> trumpet_1
  another-piece -> trumpet_2 (fallback)

Trombone:
  hound-dog -> trombone
WARNING: another-piece has no matching part for Trombone
```

Check for missing parts, unexpected fallbacks and compromises before building.

---

## 6. Build the booklets

```
python3 tools/build_booklets.py \
  --ensemble config/ensembles/serscb.yaml \
  hound-dog another-piece
```

Output appears in `output/`:

```
output/
  trumpet_1.pdf
  trumpet_2.pdf
  trombone.pdf
  ...
  bundle-20260605-221530.zip
```

One PDF is generated per ensemble part, containing the relevant pages
from each piece in the order specified on the command line.
A timestamped ZIP archive bundles all generated PDFs.

---

## 7. Normal workflow summary

1. Open the manual editor
2. Load PDF, map parts, save `.manual.txt`
3. Import piece (editor has an Import button)
4. Check generated YAML
5. Add aliases if part IDs are wrong
6. Add assignments if piece uses non-standard part labels
7. Dry-run build
8. Build PDFs
