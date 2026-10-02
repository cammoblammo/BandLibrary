# Design: an Ensembles tab for creating and editing bands

Status: **design approved, being built.** Branch `ensemble-editor`,
2026-10-02. Nothing built yet.

## Why

Changing a band means editing `config/ensembles/<band>.yaml` by hand, and
a mistake (a substitute the chair can't read, a typo in a part ID) only
shows up at build time. The owner uses only the app.

## Decisions (owner, 2026-10-02)

1. New bands are made by **copying** an existing band and adjusting it.
2. Saving a band **commits and pushes** it, like an import: same **Git
   push** box, same "not on main" question, same progress indicator.
3. It is a third **tab**, Ensembles, beside the Piece Importer and Booklet
   Builder.
4. A chair's **ID is suggested from its name** (Tenor Horn → `tenor_horn`)
   and stays out of the way unless the owner changes it.

## The tab

```
┌ Bands ──────┐┌ Chairs (booklet order) ┐┌ Chair ──────────────────────────┐
│ SERSCB      ││ Flute                  ││ Name   [Tenor Horn          ]   │
│ Workshop    ││ Clarinet 1             ││ ID     tenor_horn   (Change…)   │
│             ││ …                      ││ Reads  ☐ B♭ treble ☑ E♭ treble  │
│ New (copy)… ││ Tenor Horn          ◀  ││        ☐ C treble  ☐ C bass …   │
│             ││ …                      ││ ☐ Gets every part it reads      │
│ Delete      ││ [Add] [Remove] [↑] [↓] ││ Prefers      [list] Add… ↑ ↓ ✕  │
└─────────────┘└────────────────────────┘│ Compromises  [list] Add… ↑ ↓ ✕  │
                                          └─────────────────────────────────┘
   Short name [SERSCB]   Name on covers [South East Regional Schools Concert Band]
   [☑ Git push]                              [Revert]  [Save…]
```

- **Bands**: **New (copy)…** asks which band to copy, the short name
  (`SERSCB`) and the name on covers. The file is
  `config/ensembles/<id>.yaml`, ID from the short name. **Delete** asks
  first; pieces' assignments are left alone. The short name and the name
  on covers are fields at the foot of the tab (the file name doesn't
  change).
- **Chairs**: in booklet order; add, remove, move up/down.
- **Chair details**:
  - **Name** (on the cover). **ID** follows the name while the chair is
    new; for an existing chair it only changes through **Change…** (see
    "Chair IDs").
  - **Reads**: a tick box per reading group, with the group's label.
  - **Gets every part it reads** (`takes: all`, e.g. Percussion): greys
    out Prefers and Compromises.
  - **Prefers** / **Compromises**: ordered lists. **Add…** offers only
    what the chair can read: part IDs found in the library (with how many
    pieces have each), and "Flexible part N" (optionally limited to one
    group). An ID not in the library yet can be typed, but is refused if
    the chair can't read it.
- Unsaved changes are marked; switching band or tab, or closing, asks
  first. **Revert** discards them.

## Checks while editing

The same rules as loading a band now, shown next to the chair instead of
failing at build time:

- a Prefers/Compromises entry the chair can't read (e.g. after unticking
  a group) is marked ⚠; Save is refused until it's fixed;
- duplicate chair IDs, empty names, a chair listing itself;
- `takes: all` needs at least one reading group.

## Save: show what changes first

**Save…** builds the band in memory and compares what every chair gets in
every piece with the saved version (the before/after check used for rule
changes), then shows:

- a summary: gaps filled, parts changed, parts lost, new compromises;
- each change: "Tenor Horn — Hound Dog: nothing → Alto Sax (compromise)";
- for a new band, what each chair gets and where it gets nothing.

**Save** writes the file; **Cancel** goes back to editing. Then, with
**Git push** ticked, the file is committed ("Ensemble: SERSCB") and the
branch pushed in the background, as for imports. The Booklet Builder's
band list updates.

## Chair IDs

- Assignments are keyed by chair ID. A copied band keeps the original's
  IDs, so it **shares** its assignments (usually what's wanted). The chair
  panel says when an ID is also used by another band.
- **Change…** on an existing chair's ID offers to copy that chair's
  assignments to the new ID in every piece. They are also kept under the
  old ID if another band still uses it. The piece files changed are listed
  in the preview and committed with the band.
- The ID is also the booklet's file name.

## The file

BandBook writes the file in one standard layout: the explanatory header
(what `reads`, `prefer`, `compromise`, `takes` and `flex N` mean), the
`ensemble` section, then the chairs, leaving out empty fields. Hand-written
comments elsewhere are not kept; today the only one is the Percussion
note, whose content moves into the header.

## Code

- `lib/library.py`: split `load_ensemble` so a band can be checked from
  data in memory (the tab and the loader share the same rules).
- `lib/ensemble_io.py` (new, no Qt): write a band file; copy and delete
  bands; carry assignments to a new chair ID.
- `lib/ensemble_widget.py` (new): the tab and the Add… and preview dialogs.
- `lib/editor_widget.py`: the git thread commits given paths with a given
  message, so imports and bands share it.
- `tools/bandbook_gui.py`: the tab; refresh the Booklet Builder's list.
- Docs: a Help page for the tab; Setting Up Ensembles stops saying there
  is no editing screen.
- Tests: write → load gives the same band; the checks; the preview diff;
  copy, delete and ID change; the tab offscreen.

## Not in this version

- Editing reading groups or aliases.
- Booklet layout options.
