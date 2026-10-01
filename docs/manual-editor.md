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
covers. Without it, the PDF file name is used.

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
