# Assignment Editor

## Purpose

The Assignment Editor provides a graphical interface for setting piece-level
part assignments without editing YAML directly.

Assignments are needed when a piece uses generic part labels (e.g. `Part 1 Bb`)
that do not map directly to ensemble instrument names.

---

## Usage

In the BandBook GUI, Booklet Builder tab:

1. Select an ensemble in the dropdown
2. Select a piece in the library browser
3. Click `Assignments…`

---

## Interface

The editor shows two columns:

- **Left** — ensemble parts (all parts from the selected ensemble)
- **Right** — a dropdown of available piece parts for each ensemble part

Select the appropriate piece part for each ensemble part. Choose `— none —`
to leave an ensemble part unassigned (it will fall through to direct matching
and fallbacks at build time).

Existing assignments are pre-populated. Parts with a direct match are also
pre-selected so you can see at a glance what already works.

**Clear All** resets all dropdowns to `— none —`.

**Save** writes the `assignments` block to the piece YAML.

---

## Storage

Assignments are stored in the piece YAML:

```yaml
assignments:
  trumpet_1: part_1_bb
  trumpet_2: part_2_bb
  alto_sax: part_1_eb
```

Assignments are piece-level and apply to all builds using that piece,
regardless of which ensemble is selected.

---

## Matching Priority

At build time, the builder checks in this order:

1. Explicit assignment (from piece YAML)
2. Direct match (ensemble part ID matches piece part ID)
3. Fallback (from ensemble definition)
4. Missing (warning, part omitted from booklet)
