# Ensembles Tab

## Purpose

The **Ensembles** tab creates and edits bands: which chairs a band has, in
what order, what each chair reads, and which substitutes it takes when a
piece has no part of its own. **Setting Up Ensembles** in Help explains
the ideas (reading groups, prefer and compromise, flexible parts); this
page explains the tab.

---

## The tab

Three panels, left to right, with the band's names and **Save…** below:

### Bands

- The bands, by short name. Click one to edit it.
- **New (copy)…**: a new band starts as a copy of an existing one. Choose
  which band to copy, give it a short name (e.g. `JUNIORS`) and the name
  printed on covers. It is saved as `config/ensembles/<short name>.yaml`.
- **Delete**: asks first. Pieces' assignments are left as they are.

### Chairs

The selected band's chairs in booklet order (the order of the booklets and
of the review screen). **Add** inserts a new chair below the selected one;
**Remove** asks first; **↑** / **↓** move the selected chair.

A chair with a problem is marked ⚠ (see "Problems" below).

### Chair

| Field | Meaning |
|-------|---------|
| **Name** | The chair's name, as on its booklet cover |
| **ID** | The booklet's file name and the key for assignments. A new chair's ID follows its name (Tenor Horn → `tenor_horn`); an existing chair's ID only changes with **Change…** |
| **Reads** | The reading groups this player can read, e.g. B♭ treble clef |
| **Gets every part it reads** | Like Percussion: every part of a piece in those groups goes in the booklet, and Prefers / Compromises aren't used |
| **Prefers** | Good substitutes, best first, used when a piece has no part for this chair |
| **Compromises** | Readable but not ideal, used last; builds flag them so you can check |

**Add…** beside Prefers or Compromises offers only what the chair can
read:

- part IDs found in your library, most common first, with how many pieces
  have each (double-click to add);
- **a flexible part**: "part 3 in any group it reads", or limited to one
  group;
- a part ID that isn't in the library yet (it must still be one the chair
  can read).

The new entry goes below the selected one; use **↑** / **↓** to order the
list and **Remove** to take an entry out.

Notes under the chair (grey) are for information, for example when another
band has a chair with the same ID, so they share its assignments.

### Band names and saving

- **Short name** and **Name on covers** are the band's names. The file
  name doesn't change.
- **Revert** throws away unsaved changes.
- **Save…** (see below). With **Git push** ticked, saving commits the band
  and pushes the current branch, with progress at the top right, like an
  import. Off the `main` branch, BandBook asks first.

Unsaved changes are kept while you move around the tab. Choosing another
band, leaving the tab or closing BandBook asks first; builds always use the
saved version.

---

## Problems

These stop **Save** until fixed, and are shown in red under the chair:

- a Prefers or Compromises entry the chair can't read (marked ⚠, e.g. after
  unticking a reading group);
- a missing name or ID, an ID used by two chairs, or an ID with capitals or
  spaces;
- "Gets every part it reads" with no reading group, or with Prefers /
  Compromises still listed;
- a chair listing its own part as a substitute.

A chair whose own ID isn't in any group it reads (say a new "Tuba 2" chair)
is fine: it just never has a part of its own, and gets its Prefers.

---

## What Save shows first

Before writing anything, **Save…** works out what every chair would get in
every piece with your changes and compares it with the saved band:

```
1 gap filled
Tenor Horn — You Really Got Me: nothing → part_3_in_bb
```

The summary counts gaps filled, parts changed, parts lost and new
compromises; below it is each change, chair by chair and piece by piece.
For a new band it lists what every chair gets. **Save** writes the band;
**Cancel** goes back to editing.

---

## Chair IDs and assignments

Assignments (set in the review screen) are stored in each piece under the
chair's ID:

- A band made with **New (copy)…** keeps the original's chair IDs, so it
  **shares** its assignments. That's usually what you want; the chair's
  notes say when an ID is shared.
- **Change…** on an existing chair's ID asks whether to copy its
  assignments to the new ID. They are copied when you save; the old ones
  are removed unless another band still uses the old ID. The changed
  pieces are committed with the band.

---

## The file

The tab writes `config/ensembles/<band>.yaml` in one standard layout, with
an explanation of the fields at the top. Comments you add elsewhere in the
file by hand are not kept. Reading groups (`config/reading_groups.yaml`)
and aliases are still edited by hand; see **Setting Up Ensembles**.
