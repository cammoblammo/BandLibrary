# Assignment Editor

## Purpose

The Assignment Editor is a review screen for one piece and one ensemble.
It shows the part every chair will read, and why, and lets you override
any chair for that piece.

Most chairs need nothing: the ensemble's `prefer` and `compromise` lists
(see `data-model.md`) choose a part automatically. Use the editor to check
the result and to make piece-specific choices.

---

## Usage

In the BandBook GUI, Booklet Builder tab:

1. Select an ensemble in the dropdown
2. Select a piece in the library browser
3. Click `Assignments…`

---

## Interface

Each row is a chair in the selected ensemble:

| Column | Shows |
|--------|-------|
| Chair | The chair's name. Hover for what it reads, prefers and accepts as a compromise |
| Gets | The part the chair will read. `Automatic — …` means no assignment |
| View | Opens the pages the chair will read in a separate window |
| Why | A badge and a short explanation |

The badges:

| Badge | Meaning |
|-------|---------|
| Direct | The piece has this chair's own part |
| Fallback | A preferred substitute; the note names the entry that matched (e.g. `Preferred: flex 4`) |
| Compromise | Only a compromise is available; check it suits the player |
| Assigned | You have chosen a part for this piece; the note says what automatic would give |
| Missing | Nothing in the piece matches; the chair's booklet will skip this piece |

The summary at the top counts each kind. Tick **Only chairs that need a look**
to hide Direct and Fallback rows and see just compromises, assignments and gaps.

**View** always shows the part currently selected in that row, so you can
try a different dropdown choice and view it before saving. Preview windows
stay open alongside the review screen; use Page Up/Page Down to turn pages
and Escape to close.

If you assign a part outside the reading groups the chair reads, the note
shows a ⚠ warning. The assignment is still allowed.

**Reset All to Automatic** sets every row back to `Automatic`.

**Save** writes the assignments to the piece YAML.

---

## What gets saved

Only real overrides are stored:

- Choosing the same part automatic already gives (Direct or Fallback) stores nothing.
- Choosing the same part when automatic is a **Compromise** stores it. This
  records that you have checked it, and the build no longer flags it.
- Choosing any other part stores it as an assignment.

Assignments for chairs that are not in the selected ensemble (for example,
another band's chairs) are kept unchanged.

---

## Storage

Assignments are stored in the piece YAML:

```yaml
assignments:
  tenor_sax: part_4_in_bb_tc
  drum_kit: auxiliary_percussion
```

Assignments are keyed by chair ID. A chair ID used by more than one
ensemble shares its assignment across them.

---

## Matching Priority

At build time, the builder checks in this order:

1. Assignment (from piece YAML)
2. Direct match (chair ID matches a piece part ID)
3. Preferred substitutes (`prefer`, in order)
4. Compromises (`compromise`, in order; noted in the build report)
5. Missing (warning; the piece is left out of that chair's booklet)
