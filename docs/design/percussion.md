# Design: one Percussion chair that gets every percussion part

Status: **design approved, not built.** Branch `percussion-chair`,
2026-10-02. Open question C (existing pieces) is for after the rule is
built.

## Why

Percussion parts are not standardised. "Percussion 1" is snare and bass
drum in one piece and mallets in another; "Snare Drum" went to Aux in
Things That Go Bump but to the Drum Kit in Going Quackers. So far this has
been handled by renaming parts while mapping ("Percussion 2 (Tambourine)"
typed as `aux percussion`) or by per-piece assignments. Neither suits
Detect Parts, which writes what the page says, and aliases would be wrong:
the same printed name means different things in different pieces.

Percussionists move between instruments anyway, so they should have
everything they need.

## Decisions (owner, 2026-10-02)

1. **One Percussion chair per band** replaces Drum Kit and Auxiliary
   Percussion. Its booklet holds **every percussion part** of each piece,
   in the order they appear in the PDF. Each player gets a copy.
2. **Overrides stay possible**: percussion is "about exceptions and special
   cases rather than norms". A piece can say which of its parts the
   Percussion chair gets (see Assignments below).
3. **Mallets** can double a treble-clef C instrument (oboe, guitar…) when a
   band lacks one. That is ordinary `prefer` / `compromise` lists on those
   chairs, decided chair by chair; no new mechanism.
4. **Keeping pieces apart in a booklet** is mostly the player's job; the
   finishing touch is **page numbers on the contents page** (all booklets).
5. **Mallets, bells and chimes go in the Percussion booklet** too, and stay
   available to other chairs for doubling.
6. **Copies**: the owner prints the Percussion booklet as many times as
   needed; BandBook builds one.

## How it works

### Ensemble file

A chair can say it takes every part it reads:

```yaml
  - id: percussion
    label: Percussion
    reads: [percussion]
    takes: all
```

`takes: all` gives the chair every piece part in its `reads` groups, in
page order. Without it (`takes: one`, the default) nothing changes for any
other chair. `prefer` / `compromise` are not used on a `takes: all` chair.

### Which parts count as percussion

Data, not guesswork: a part is percussion if its ID is in the `percussion`
reading group. The group is widened to the names publishers print, e.g.
`percussion`, `percussion_*`, `drums`, `drum_kit`, `drum_set`,
`snare_drum`, `bass_drum`, `auxiliary_percussion`, `timpani`, `tambourine`,
`triangle`, `claves`, `woodblock`, `cowbell`, `shaker`, `maracas`,
`cymbals`, `mallets`, `bells`, `glockenspiel`, `xylophone`,
`keyboard_percussion`, `chimes`. The owner checks the final list.

Detect Parts then stops calling these "unknown", and the importer stops
listing them as outside every reading group. No aliases are needed.

### Assignments (overrides)

For a `takes: all` chair, a piece's assignment can be a **list**, which
replaces "everything" for that piece:

```yaml
assignments:
  percussion: [percussion_2, bells]
```

A single part ID still works. The review screen (**Assignments…**) shows
the Percussion chair's parts with tick boxes, and, as now, saves only a
real override (a selection different from "everything").

### Booklets and reports

- The booklet appends each of the piece's percussion parts in turn.
- The contents page lists the piece once, now **with the booklet page it
  starts on** (every booklet, not just Percussion). The build report and
  consistency report list all its parts against the Percussion chair.
- A piece with no percussion parts is bracketed on the contents page, as
  any missing piece is now.

### Code that changes

Every consumer of a match assumes one part per chair per piece. A match
result gains a list of parts (one for ordinary chairs): `lib/matcher.py`,
`lib/models.py`, `lib/builder.py`, `lib/report.py`,
`lib/report_html.py`, `lib/assignment_editor.py`, `lib/validator.py`,
`lib/library.py` (loading `takes`), and the docs (Data Model, Setting Up
Ensembles, Assignment Editor, Booklet Builder).

## Effect on the library and bands

- Both bands: `drum_kit` and `auxiliary_percussion` chairs are replaced by
  `percussion`. Booklet files change accordingly (`percussion.pdf`).
- Assignments for `drum_kit` / `auxiliary_percussion` in four pieces
  (Going Quackers, Rock Around the Clock, Yellow Submarine, The Sound of
  Silence) no longer match a chair. The library check will flag them;
  removing them is part of the migration step (open question C).
- Before changing anything, snapshot what every chair gets in every
  piece; afterwards report each change (expected: Drum Kit and Aux
  booklets gone, Percussion gaining every percussion part, mallets and
  chimes now in the Percussion booklet).

## Settled

A. Mallets, bells and chimes: in the Percussion booklet (decision 5).
B. Keeping pieces apart: contents page numbers (decision 4). Considered and
   not chosen: a stamp on each part's first page; divider pages.
D. Copies: printed by the owner (decision 6).

## Open

C. **Existing pieces** (owner's question 4, after the rule settles):
   restore printed names where percussion parts were renamed while
   mapping, and remove the now-unneeded drum kit / aux assignments?

