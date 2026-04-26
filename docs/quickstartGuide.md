# BandLibrary Quickstart

## 1. Create a manual file

Example: `Hound Dog.manual.txt`

Title: Hound Dog

Flute: 15
Clarinet 1: 13
Clarinet 2: 12
Alto sax: 10
Tenor sax: 9
Trumpet 1: 7
Trumpet 2: 6
Trombone: 5
Drum kit: 3
Auxiliary percussion: 1-2

## 2. Import the piece

python3 tools/import_piece.py "Hound Dog.pdf" --manual "Hound Dog.manual.txt"

This creates:

library/hound-dog/
  hound-dog.pdf
  hound-dog.manual.txt
  hound-dog.yaml

## 3. Check the generated YAML

Open:

library/hound-dog/hound-dog.yaml

Check:

- part IDs are sensible
- page ranges are correct
- source_pdf points to the right PDF

If a part ID is wrong, add an alias to:

config/aliases.yaml

Then reimport with:

python3 tools/import_piece.py "Hound Dog.pdf" --manual "Hound Dog.manual.txt" --force

## 4. For layered pieces, add assignments

Example:

assignments:
  trumpet_1: part_1_bb
  trumpet_2: part_2_bb
  trumpet_3: part_3_bb
  alto_sax: part_1_eb
  bass_guitar: tuba

Assignments go in the piece YAML.

## 5. Dry-run the booklet build

python3 tools/build_booklets.py \
  --ensemble config/ensembles/serscb.yaml \
  --dry-run \
  hound-dog another-piece

Check:

- direct matches
- fallbacks
- assignments
- missing parts

## 6. Build the actual booklets

python3 tools/build_booklets.py \
  --ensemble config/ensembles/serscb.yaml \
  hound-dog another-piece

Output appears in:

output/

The builder creates:

- one PDF per ensemble part
- a timestamped ZIP archive

## 7. Normal workflow

1. Create manual file
2. Import piece
3. Check YAML
4. Add aliases if needed
5. Add assignments if needed
6. Dry-run build
7. Build PDFs