# Design: automatic part detection on import

Status: **design only, not built.** Sketched 2026-10-01.

## Goal

Save the work of mapping parts by hand. A **Detect Parts** button in the
Piece Importer reads the open PDF and fills the part list with a draft
(`Trumpet 1: 12-14` lines). The user checks and corrects it against the PDF,
then imports as now.

Non-goals: importing without review; changing the library, matching or
build. The draft is plain manual-file text, so everything downstream is
unchanged. This keeps the design principles: data is authoritative, a person
confirms it, manual override is always possible.

## What the PDFs look like (library survey, Oct 2026)

| Kind | Pieces | Example |
|------|--------|---------|
| Text layer from notation software (MuseScore, Sibelius, LilyPond) | 8 of 20 | Going Quackers: page text starts "Alto Saxophone 2 / Going Quackers" |
| Image only (scans, phone captures) | 12 of 20 | Hound Dog, Yellow Submarine, Hang On Sloopy |

So a text-only version helps about 40% of pieces; scans need OCR or AI.

## User flow

1. Open a PDF in the Piece Importer.
2. Click **Detect Parts** (asks before replacing a non-empty part list).
3. Progress shows in the status bar; detection runs in a background thread.
4. The part list fills with a draft:

   ```
   Title: Going Quackers
   # Detected by BandBook — check every line before importing
   # pages 1-2: score (skipped)
   Flute 1: 7
   Alto Sax 1: 12
   Tenor Sax: 14-15        # check: page 15 has no instrument name
   Part 4 in C BC: 19      # check: clef guessed from header "Part 4 (C)"
   ```

5. The user steps through the PDF beside the draft (the existing Enter /
   Page Down workflow still works for fixes), then clicks **Import…**.

Lines marked `# check` are the ones to look at first. `#` comments are
already ignored by the manual parser, so the draft imports as-is.

## Architecture

New package `lib/detect/`, no Qt imports, so it is testable and usable
from a future CLI (`tools/detect_parts.py`):

| Module | Job |
|--------|-----|
| `pages.py` | Per page, produce a `PageReading`: header text, whether the page looks like a score, page-number marks, source (`text` / `ocr` / `ai`) |
| `sources/text_layer.py` | Read every text span on the page with PyMuPDF, with its position and size |
| `sources/ocr.py` or `sources/ai.py` | Fallback for pages with no text (stage 2; see open questions) |
| `names.py` | Turn header text into a part label: alias keys (`config/aliases.yaml`), flex patterns (`Part N in X`, with ♭/♯ normalised and TC/BC kept), instrument words ("Trumpet in B♭ 1" → "Trumpet 1"). Returns label + confidence + reason |
| `labels.py` | Find each page's part label among its text (see "Finding the label") |
| `segment.py` | Pure function: list of `PageReading` → list of `DraftPart(label, start, end, confidence, notes)`. A new part starts where the label changes; pages without a label continue the previous part; score pages are skipped and noted |
| `render.py` | `DraftPart`s → manual-file text with `# check` comments |

## Finding the label

Part names are not always at the top. In Things That Go Bump in the Night
they are at the bottom left ("Trumpet 1", "Flute or Oboe"), and the top of
every page carries the title and story text. So the label is found by its
behaviour rather than its position:

1. **Ignore page furniture**: text repeated on most pages (title, composer,
   narration, web addresses, copyright lines).
2. **Prefer instrument-like text**: spans matching alias keys, instrument
   words, or `Part N in X`.
3. **Prefer text that changes where parts change**: the label stays the
   same across a part's pages and differs from its neighbours'.
4. **Position as a tie-breaker only**: margins (top or bottom ~15%) over
   the body of the page.

Other findings from the same piece:

- Accidentals drawn from the music font disappear from the text layer:
  "Clarinet in B♭" reads as "Clarinet in B". Band instruments are never in
  B or E natural, so "in B" / "in E" become B♭ / E♭, marked `# check`.
- One part can serve several chairs: "Beginners B♭" is used for both
  Clarinet 2 and Trumpet 3. Detection reports the part once under its own
  label (`Beginners Bb: 22-25`); choosing chairs stays with the ensemble
  rules and the review screen. It never invents chair names.

Key rule: **sources only read pages; all decisions are made locally in
`segment.py`**, so results are repeatable and testable, even when an AI
supplies the page readings.

GUI: a button and a `QThread` in `lib/editor_widget.py`, following the
`BuildThread` pattern in `lib/build_widget.py`.

## Stages

1. **Text layer only.** Detect Parts works for PDFs with text; pages without
   text become `# check: no text on pages 5-9` gaps. Free, offline,
   deterministic.
2. **Scans with local OCR.** Tesseract reads pages without text, with word
   positions, so the same label-finding rules apply. Free, offline, nothing leaves the computer. This is the
   default for scans.
3. **Optional AI reader.** For scans OCR can't handle. Off unless chosen for
   the current import (see "AI and copyright" below).
4. **Polish.** Spot two parts on one page; learn names the user corrects
   (offer to add them to `aliases.yaml`).

Title detection is part of stage 1: the largest text on the first page with
a text layer (or the most common non-instrument header text) becomes the
`Title:` line, marked `# check`.

## AI and copyright

Publishers are unlikely to approve sending their music to an outside
service, so:

- The AI reader is never used by default. Detect Parts uses the text layer,
  then OCR. AI is a separate choice for one import at a time (e.g. a
  **Detect with AI…** menu item) with a note about what will be sent.
- Whole pages are sent (downscaled), since labels can be anywhere on the
  page. Only a label per page comes back. The owner's view: part names
  aren't copyrighted, and whether to upload a publisher's pages is their
  call for each piece.
- Intended for scans OCR can't handle, and the owner's own arrangements.

## Testing

The library is the test set: 20 pieces with hand-checked `.manual.txt`
files. A test script runs detection on each library PDF and compares
with the stored mapping, reporting per piece: parts found, page ranges
right, labels right. Track this score as stages are added.

Unit tests for `segment.py` and `names.py` with hand-made `PageReading`
lists (continuation pages, score pages, combined headers).

## Hard cases

- Score or conductor pages at the front (many instrument names on one page)
- Continuation pages with no instrument name, or only "2" / "Tpt. 1"
- Two parts on one page, or a part starting mid-page
- Combined headers: "Clarinet/Trumpet", "Bb Part 2"
- Abbreviations: "Tpt. 1", "A. Sx.", "Euph. T.C."
- Instrument name printed at the bottom or side (Things That Go Bump), or not at all
- Accidentals missing from the text layer ("Clarinet in B")
- One part shared by several chairs ("Beginners B♭")
- Transposition shown only as "in B♭" with the number elsewhere

## Decisions (owner, 2026-10-01)

1. Scans: offer both. Local OCR is the default; AI is optional.
2. Copyright: AI is opt-in per import. Whole pages may be sent; only
   labels come back (see "AI and copyright").
3. API key: no preference. Suggested: read `ANTHROPIC_API_KEY` from the
   environment, or a key saved in `~/.config/bandbook/gui.yaml` from a
   settings dialog. Never stored in the project.
4. Title: yes, detect it (stage 1).

## Still to settle when building

- OCR setup: Tesseract is a system package (`apt install tesseract-ocr`)
  plus `pytesseract`; check how it copes with music symbols near labels.
- AI setup effort: API account, key entry, cost per piece. Check the
  current model and API details first (the `claude-api` skill), rather
  than relying on memory.
