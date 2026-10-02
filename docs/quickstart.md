# BandBook Quickstart

A walkthrough of the normal workflow in the BandBook app: import a piece,
check what every player gets, and build the booklets.

Start BandBook from its desktop icon, or from the project folder with:

```
python3 tools/bandbook_gui.py
```

The window has two tabs, **Piece Importer** and **Booklet Builder**, plus a
**Tools** menu and **Help** (F1).

---

## 1. Map the parts of a new piece

In the **Piece Importer** tab:

1. Click **Open PDF…** (Ctrl+P) and choose the full set of parts as one PDF.
   Name the file after the piece first: the file name becomes the piece's
   name in the library (`Hound Dog.pdf` becomes `hound-dog`).
   Click **Detect Parts** to get a draft part list (scans take a few
   seconds a page), check every line against the PDF (especially lines
   with a `# check` note above them), then skip to **2. Import it**. Or
   map the parts by hand:
2. Go to the first page of the first part and press **Enter**. A line like
   `: 3` appears with the page number.
3. Type the part name, e.g. `Trumpet 1`. **Tab** cycles through known names.
4. Use **Page Down** to move through the part. On its last page press
   **Enter**: the line becomes `Trumpet 1: 3-4` and the next part starts.
5. Repeat to the end of the PDF.

Optionally add a first line `Title: Hound Dog` to set the title shown on
booklet covers; otherwise the file name is used.

Name parts consistently:

- Use instrument names the aliases know (Tab completes them).
- For flexible arrangements, use `Part N in <key>`: `Part 3 in Eb`,
  `Part 4 in Bb TC`. For parts in C always add the clef: `Part 1 in C TC`,
  `Part 4 in C BC`.

See **Piece Importer** in Help for every key and button.

---

## 2. Import it

Check the boxes beside **Import…**:

| Box | Default | Meaning |
|-----|---------|---------|
| Force | on | Replace the piece if it is already in the library. Its assignments are kept where the parts still exist |
| Test | off | Import into the test library (`test/`) instead of the real one |
| Git push | on | After importing, commit the piece and push it to GitHub |

Click **Import…**. The status bar confirms the import. An **Import Notes**
window may list:

- **Unaliased labels**: part names BandBook didn't recognise and turned into
  IDs itself. Check they look right; add common ones to `config/aliases.yaml`.
- **Parts outside every reading group**: parts no chair will be given
  automatically, often a C part without TC/BC. Rename the line in the manual
  text and import again, or assign the part by hand in step 3.

You can save the mapping (Ctrl+S) as `<piece>.manual.txt` to keep a copy,
but the import doesn't need it: a copy is stored in the library either way.

---

## 3. Review what every player gets

In the **Booklet Builder** tab:

1. Choose the ensemble at the top.
2. In the **Library** list, select the piece and click **Assignments…**.

The review screen lists every chair with the part it will read and why:
**Direct**, **Fallback**, **Compromise**, **Assigned** or **Missing**. Tick
**Only chairs that need a look** to see just the compromises and gaps.

- Click **View** to see the pages a chair will get.
- Choose a different part from the dropdown to override a chair for this
  piece only. **Reset All to Automatic** removes the overrides.
- Choosing the part a **Compromise** already gives approves it, so builds
  stop flagging it.

Click **Save**. See **Assignment Editor** in Help for details.

Most chairs need nothing here. If the same problem shows up in many pieces,
change the ensemble's rules instead (see **Setting Up Ensembles**).

---

## 4. Build the booklets

Still in the **Booklet Builder** tab:

1. Add pieces to the **Build List**: double-click them in the Library, or
   click **Load** to open a repertoire file from `repertoire/`.
2. Put them in order with **Up** and **Down**. The order is the order in the
   booklets and the numbering on the contents pages.
3. Type an **Edition** name if you like (e.g. `Spring Concert 2026`). It
   appears on every cover and in the ZIP file name.
4. Click **Dry Run**. The output panel lists, for every chair, the part it
   gets from each piece, and warns about missing parts and compromises.
5. Click **Build**.

The booklets are written to `output/`, one PDF per chair (`trumpet_1.pdf`,
and so on), plus a ZIP of this build's booklets, e.g.
`serscb-spring-concert-2026-20261001-193000.zip`. Send the ZIP: the
`output/` folder also keeps PDFs from earlier builds.

Click **Save** above the build list to keep the list as a repertoire file.

---

## 5. Check the library now and then

The **Tools** menu has two checks:

- **Check Library…** validates every piece and ensemble and shows how many
  pieces each chair is covered for.
- **Consistency Report…** opens a page in your browser showing what every
  chair gets in every piece, with possible problems listed at the top.

Run them after importing several pieces or after changing an ensemble.

---

## Normal workflow summary

1. Piece Importer: open the PDF, map the parts, import
2. Booklet Builder: select the piece, Assignments…, check and save
3. Build list: add pieces, Dry Run, Build
4. Send the ZIP from `output/`
