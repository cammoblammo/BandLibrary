# Piece Importer (Manual Part Mapping Editor)

## Purpose

The Manual Part Mapping Editor is a graphical tool for creating `.manual.txt` files.
These files map part labels to PDF page numbers and are the input to the importer.

The editor displays the PDF on the left and a text editor on the right,
allowing parts to be mapped page by page without typing page numbers manually.

---

## Usage

The editor is the **Piece Importer** tab in BandBook:

```
python3 tools/bandbook_gui.py
```

The aliases file (`config/aliases.yaml`) is loaded automatically from the project root
and enables part name autocomplete if present.

---

## Dependencies

```
sudo apt install python3-pymupdf python3-pyqt6
```

---

## Interface

### Left pane — PDF viewer

Displays the current page of the loaded PDF.

Controls:

- `◀ Prev` / `Next ▶` — navigate pages (also Page Up / Page Down)
- `－` / `＋` — zoom out / in
- `↻ 90°` — rotate view 90° clockwise (display only, does not modify the PDF)

The page number is shown prominently in the toolbar.

On load, the page is automatically scaled to fit the viewer.

### Right pane — Manual file editor

A plain text editor with special behaviour for the mapping workflow.

The editor toolbar contains:

- Current filename indicator
- Alias status indicator (shows how many aliases are loaded)
- New / Open / Save / Save As buttons
- Force checkbox and Import button

---

## Workflow

### Opening a PDF

Use the `Open PDF…` button in the top toolbar, or `Ctrl+P`.

### Starting the first entry

Navigate to the first page of the first part.
Press `Enter` on an empty line.

The editor inserts:

```
: 12
```

where `12` is the current PDF page. The cursor is placed before the colon.

Type the part name:

```
Trumpet 1: 12
```

### Multi-page parts

Navigate forward through the PDF with `Page Down` while the entry sits unfinished.
The editor tracks the current page automatically.

### Finalising an entry

When you reach the last page of the part, press `Enter`.

If the current page differs from the start page, the editor converts the
entry to a range automatically:

```
Trumpet 1: 12-14
```

The PDF advances to the next page and a new entry line is inserted:

```
: 15
```

Type the next part name and continue.

### End of PDF

Pressing `Enter` on the last page finalises the current entry without
inserting a new line. The status bar shows a message indicating the
end of the PDF has been reached.

### Autocomplete

If an aliases file is loaded, pressing `Tab` while typing a part name
cycles through matching alias labels.

- Matching is case-insensitive and searches within the label (not just the start)
- Each `Tab` press advances to the next match, wrapping around
- Any other keypress accepts the current completion and resets the cycle
- The status bar shows the current match count

### Saving

- `Ctrl+S` — save (prompts for filename if new file)
- `Ctrl+Shift+S` — save as
- Save As prefills the filename from the PDF name, slugified (e.g. `hound-dog.manual.txt`)
- Closing with unsaved changes prompts to save

### Importing

The `Import…` button runs `import_piece.py` directly from the editor.

- The manual file is saved automatically before import if needed
- The `Force` checkbox (checked by default) passes `--force` to the importer,
  allowing reimport of an existing piece
- Success is shown in the status bar
- Failure opens a dialog with the full error output

---

## Key Bindings

| Key | Action |
|-----|--------|
| Enter | Start entry / finalise entry and advance |
| Tab | Cycle autocomplete matches |
| Page Down | Next PDF page |
| Page Up | Previous PDF page |
| Ctrl+P | Open PDF |
| Ctrl+O | Open manual file |
| Ctrl+S | Save |
| Ctrl+Shift+S | Save As |

---

## Output Format

The editor produces a standard `.manual.txt` file:

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

This format is the sole contract between the editor and the rest of the system.
The editor does not interact with the library, YAML files, or ensemble definitions.

---

## Architecture

The editor is deliberately isolated from the rest of BandBook.
It reads PDFs and writes `.manual.txt` files. Nothing else.

This means it can be developed, tested, or replaced independently
without affecting the importer or booklet builder.

The Import button is the only point of integration, and it works by
invoking `import_piece.py` as a subprocess — the same tool you would
run from the command line.
