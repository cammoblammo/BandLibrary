# Piece Importer

## Purpose

The **Piece Importer** tab maps the pages of a piece's PDF to its parts and
imports the piece into the library.

The PDF is shown on the left and the part list on the right. You move
through the PDF and name each part as you reach it; BandBook records the
page numbers.

---

## Interface

### Top toolbar

- **Open PDF…** (Ctrl+P): choose the PDF containing all the parts
- **Detect Parts**: read the part names in the PDF and fill the part list
  with a draft to check (see "Detecting the parts" below)

The PDF's file name becomes the piece's name in the library, so rename the
file first if needed (`Hound Dog.pdf` becomes `hound-dog`).

### Left: PDF viewer

- **◀ Prev** / **Next ▶**: change page (also Page Up / Page Down)
- **－** / **＋**: zoom out / in
- **↻ 90°**: rotate the view (display only; the PDF is not changed)

The page is scaled to fit when a PDF opens.

### Right: part list

A text editor holding one line per part, e.g. `Trumpet 1: 12-14`.

The toolbar above it has:

- The current file name, and how many aliases are loaded for autocomplete
- **New**, **Open…**, **Save**, **Save As…**: work with `.manual.txt` files
- **Force**, **Test** and **Git push** checkboxes, and **Import…**

---

## Detecting the parts

**Detect Parts** can do most of the mapping for you. It reads PDFs made by
notation software (MuseScore, Sibelius, Finale and so on) directly, and
reads scanned pages with OCR (text recognition on this computer; nothing
is sent anywhere). Scans take a few seconds a page; the status bar shows
progress.

1. Open the PDF and click **Detect Parts**. If the part list already has
   text, BandBook asks before replacing it.
2. The part list fills with a draft, for example:

   ```
   # check: title read from the PDF
   Title: Going Quackers
   # pages 1-6: score (skipped)
   Flute 1: 7
   # check: there is also a "Trombone 2": is this "Trombone 1"?
   Trombone: 19
   Trombone 2: 20
   # check: clef added from the first staff (bass clef)
   Part 4 in C BC: 17
   ```

3. Check every line against the PDF, starting with the `# check` notes
   just above an entry. Fix names and page numbers by typing, or use the
   usual Enter / Page Down steps below. Delete parts you don't want.
4. Click **Import…** as usual. Lines starting with `#` are ignored, so the
   notes can stay.

What the notes mean:

| Note | What to do |
|------|-----------|
| `title read from the PDF` | Check the title line; shorten it if needed |
| `score (skipped)` | Pages with many staves; nothing to do |
| `Read from scanned images (OCR)` | OCR makes mistakes: check those pages' names and page numbers closely |
| `no text found` | Map these pages by hand |
| `no part name found` | Usually a cover or notes page; map by hand if it is a part |
| `page N shows no part name` | A page without a name was added to the part above it. Check it belongs there |
| `read "in B" as "in Bb"` | The flat was missing from the PDF's text |
| `clef added from the first staff (bass clef)` | A C part's name didn't say its clef, so BandBook added `TC` or `BC` from the clef of the first staff. Check it |
| `clef not printed: add TC or BC` | BandBook couldn't see the clef (e.g. a scan): add `TC` or `BC` after the key, as in `Part 3 in C BC: 13-14`, or no chair will get the part automatically |
| `the first staff is in treble clef, but "Euphonium" is read as a bass-clef part` | The PDF's clef doesn't match the name: rename the part (e.g. `Euphonium TC`) if that's right |
| `not a known part name` | Rename it to a name the aliases know, or add an alias |
| `is this "Trombone 1"?` | The PDF prints just "Trombone" beside a "Trombone 2" |
| `looks like a second page (no title)` | Every other part starts on a page with the title, but this one doesn't: its header may be misprinted. If the page belongs to the part above, delete this line and extend that part's range |
| `printed more than once` | The PDF uses the same name for two parts. The note says what differs (clef, or the instruments printed with it). Rename one (e.g. add TC / BC) or remove one you don't need: the import refuses duplicate names |

Clefs are read only from PDFs made by notation software (not scans), and
only from the first staff. Apart from adding TC / BC to C parts, BandBook
never changes a name because of a clef.
Detection never guesses a clef or which chair should play a part (for
example a "Beginners B♭" part shared by two chairs): set that up in
**Assignments…** as usual.

OCR copes with most scans, but not all: small names in boxes, stylised
fonts and poor copies may not be read. Those pages show up as `no part
name` notes or are added to the part before them, so check them by hand.
If OCR isn't installed (`sudo apt install tesseract-ocr python3-pytesseract`),
Detect Parts says so and leaves the part list alone.

---

## Mapping the parts

### Starting

Go to the first page of the first part and press **Enter** on an empty
line. BandBook inserts `: 12` (the current page) with the cursor before the
colon. Type the part name:

```
Trumpet 1: 12
```

### Parts longer than one page

Press **Page Down** to move through the part. On its last page, press
**Enter**. The line becomes a range, the PDF moves to the next page and a
new line starts:

```
Trumpet 1: 12-14
: 15
```

### The end of the PDF

Pressing **Enter** on the last page finishes the line without starting a
new one.

If you stop early (for example the last pages are a score you don't need),
delete any leftover line that has no part name, such as `: 31`. The import
refuses a line without a name.

### Autocomplete

While typing a part name, press **Tab** to cycle through matching known
names (from `config/aliases.yaml`). Matching ignores case and looks anywhere
in the name. Any other key accepts the current suggestion.

### Naming parts

- Use instrument names the aliases know, so parts get standard IDs.
- For flexible arrangements, use `Part N in <key>`, e.g. `Part 3 in Eb`,
  `Part 4 in Bb TC`.
- For parts in C, always add the clef: `Part 1 in C TC`, `Part 4 in C BC`.
  Without it no chair can be given the part automatically.

### Title

Add a line `Title: Hound Dog` anywhere to set the title used on booklet
covers. It is printed exactly as written, so punctuation and small words
come through: `Title: Don't Stop Believin'`, `Title: T.W.A.`,
`Title: Cast in Blues`. Detect Parts fills it in from the PDF.

Without it, the title is made from the PDF file name (`dont-stop-believin`
becomes "Dont Stop Believin"), which loses punctuation. To fix an existing
piece's title, open its `.manual.txt` here, add or change the `Title:`
line, **Save**, then select the piece in the Booklet Builder and click
**Regen YAML**.

---

## Importing

Click **Import…** when the list is complete.

| Checkbox | Default | Effect |
|----------|---------|--------|
| **Force** | on | If the piece is already in the library, replace it |
| **Test** | off | Import into the test library (`test/`) instead of `library/`. Turns off Git push |
| **Git push** | on | After a successful import, commit the piece and push it to GitHub |

What happens:

1. If the part list is unsaved, BandBook imports from a temporary copy.
   Your `.manual.txt` file is not saved; use **Save** if you want one.
2. The PDF and part list are copied into `library/<piece>/`, and the piece's
   data file (`<piece>.yaml`) is created. The original PDF is left where it was.
3. On success the status bar says so. On failure a window shows the reason,
   e.g. a line without a part name, or the piece already exists and Force is off.
4. An **Import Notes** window may follow, listing:
   - **Unaliased labels**: names BandBook didn't recognise. Check the IDs
     they were given; add common ones to `config/aliases.yaml`.
   - **Parts outside every reading group**: parts no chair will get
     automatically. Rename and import again, or assign them by hand.
5. With **Git push** ticked, BandBook commits just that piece's folder with
   the message `Import: <title>` and pushes the current branch to GitHub.
   If nothing changed (an identical re-import) it skips the commit. If git
   fails, the piece is still imported; a window explains what went wrong.
   If the project folder isn't on the `main` branch, BandBook says which
   branch the piece will go to and asks before importing.
   Pushing uploads the PDF and can take a while: it runs in the
   background, with a moving bar and a note of what's happening at the top
   right ("Importing…", "Pushing … to GitHub"), and **Import…** is greyed
   out until it finishes. A green ✓ message says when it's done. If you try to close BandBook meanwhile, it asks
   you to wait.

### Re-importing a piece

With **Force** ticked, importing a piece that is already in the library
replaces its PDF and page mapping. Its assignments are kept as long as the
part they point to still exists; any that don't are removed, and the import
output says which.

To change only the page mapping without re-importing the PDF, edit the
piece's part list and use **Regen YAML** in the Booklet Builder tab.

---

## Key Bindings

| Key | Action |
|-----|--------|
| Enter | Start a line / finish the current part and move on |
| Tab | Cycle autocomplete suggestions |
| Page Down / Page Up | Next / previous PDF page |
| Ctrl+P | Open PDF |
| Ctrl+O | Open a `.manual.txt` file |
| Ctrl+S | Save |
| Ctrl+Shift+S | Save As |

---

## The part list format

The part list is saved as a plain `.manual.txt` file:

```
Title: Hound Dog

Flute: 15
Clarinet 1: 13
Trumpet 1: 7
Auxiliary Percussion: 1-2
```

Blank lines and lines starting with `#` are ignored. A copy is stored in the
library with each piece, and **Regen YAML** rebuilds the piece's data from it.

The **Import…** button runs the same importer as `tools/import_piece.py`;
see **Importer (command line)** in Help for its options.
