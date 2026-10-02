# Data Model

## Overview

BandLibrary uses three types of YAML file:

- **Piece YAML** — metadata for a single imported piece
- **Ensemble YAML** — definition of an ensemble and its chairs
- **Reading groups** — which written parts each kind of chair can read,
  shared by every ensemble

These are kept strictly separate. Piece data describes what parts exist.
Ensemble data describes what parts are needed. The builder is the only
component that reads both.

---

## Piece YAML

Location: `library/<slug>/<slug>.yaml`

### Minimal example

```yaml
schema_version: 1

piece:
  id: hound-dog
  title: Hound Dog
  source_pdf: hound-dog.pdf
  status: manual

parts:
  - id: trumpet_1
    label: Trumpet 1
    pages: [12, 12]

  - id: trumpet_2
    label: Trumpet 2
    pages: [13, 14]

  - id: trombone
    label: Trombone
    pages: [5, 5]
```

### With assignments

```yaml
schema_version: 1

piece:
  id: cast-in-blues
  title: Cast in Blues
  source_pdf: cast-in-blues.pdf
  status: manual

parts:
  - id: part_1_bb
    label: Part 1 Bb
    pages: [3, 4]

  - id: part_2_bb
    label: Part 2 Bb
    pages: [5, 6]

  - id: part_1_eb
    label: Part 1 Eb
    pages: [7, 8]

assignments:
  trumpet_1: part_1_bb
  trumpet_2: part_2_bb
  trumpet_3: part_2_bb
  alto_sax: part_1_eb
```

### Field reference

#### piece

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Slugified piece identifier, matches directory name |
| `title` | string | Human-readable title |
| `source_pdf` | string | Filename of the source PDF within the piece directory |
| `status` | string | Always `manual` for pieces imported via the manual workflow |

#### parts (list)

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Normalised part identifier (used for matching) |
| `label` | string | Original label from the manual file |
| `pages` | [int, int] | Start and end page numbers (1-based, inclusive) |

#### assignments (optional mapping)

Maps ensemble part IDs to piece part IDs for pieces with non-standard part labels.
The builder checks assignments before attempting direct matching or fallbacks.

A value is one part ID, or a **list** of part IDs for a `takes: all` chair
(the Percussion chair), in booklet order:

```yaml
assignments:
  percussion: [percussion_2, bells]
```

---

## Ensemble YAML

Location: `config/ensembles/<name>.yaml`

An ensemble is a list of chairs. Each chair says which reading groups it can
play, which substitutes suit it when a piece has no part for it, and which
substitutes are only a compromise.

### Example

```yaml
schema_version: 2

ensemble:
  id: serscb
  name: SERSCB
  band: South East Regional Schools Concert Band

parts:
  - id: clarinet_3
    label: Clarinet 3
    reads: [bb_treble]
    prefer: [clarinet_2, clarinet_1, flex 2]

  - id: tenor_sax
    label: Tenor Sax
    reads: [bb_treble]
    prefer: [flex 3, flex 4]
    compromise: [baritone_tc, euphonium_tc, trombone_tc, bass_clarinet]
```

### Field reference

#### parts (list)

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Chair identifier; also the booklet filename |
| `label` | string | Human-readable label used in reports and on the cover page |
| `reads` | [string, ...] | Reading groups this chair can play (see below) |
| `prefer` | [string, ...] | Good substitutes, best first |
| `compromise` | [string, ...] | Readable but not ideal (e.g. range); used last and flagged |
| `takes` | `one` or `all` | `one` (default): one part per piece. `all`: every part of the piece in the `reads` groups, in PDF order (the Percussion chair). An `all` chair needs `reads` and has no `prefer` / `compromise` |

Entries in `prefer` and `compromise` are **piece part IDs** (what a piece
calls its parts), or `flex N`:

- `flex 3` means part 3 of a flexible arrangement, in every reading group the
  chair reads, in `reads` order. For a chair that reads `bb_treble`, that is
  `part_3_in_bb` or `part_3_in_bb_tc`.
- `flex 3 c_bass` limits it to one group.

Substitutes are not followed as a chain: `prefer: [clarinet_2]` matches a
piece part called `clarinet_2`, not whatever the Clarinet 2 chair would get.
List every substitute you want, in order.

#### Older format

Schema 1 files use a single `fallback` list instead of `prefer`/`compromise`.
They still load, with `fallback` treated as `prefer`.

### Matching order

For each chair and each piece, the builder takes the first of:

1. the piece's **assignment** for this chair, if any (one part, or a list)
2. for a `takes: all` chair: **every** part it reads (**all**), or nothing
   (**missing**); the steps below don't apply to it
3. a **direct** match: a piece part with the same ID as the chair
4. the first `prefer` entry the piece has (**fallback**)
5. the first `compromise` entry the piece has (**compromise**, noted in the build report)
6. nothing (**missing**)

---

## Reading Groups

Location: `config/reading_groups.yaml`

A reading group is a set of written parts with the same transposition and
clef. Reading a group means the notes make sense to the player; whether the
range suits is decided by each chair's `prefer` and `compromise` order.

```yaml
schema_version: 1

groups:
  bb_treble:
    label: B♭ treble clef
    parts: [clarinet_*, trumpet_*, tenor_sax, bass_clarinet, euphonium_tc]
    flex: ["part_{n}_in_bb", "part_{n}_in_bb_tc"]
```

| Field | Description |
|-------|-------------|
| `label` | Human-readable name |
| `parts` | Part IDs in this group; `*` matches anything |
| `flex` | How flexible-arrangement parts are named in this group; `{n}` is the part number |

The validator reports an error when a chair lists a substitute outside the
groups it reads. Chairs without `reads` are not checked.

---

## Aliases File

Location: `config/aliases.yaml`

Maps variant instrument names to canonical part IDs.
Used by the importer when normalising part labels from manual files.
Also used by the manual editor for autocomplete.

### Example

```yaml
schema_version: 1

aliases:
  "Electric guitar": guitar
  "Alto sax 1": alto_sax_1
  "Bb Clarinet": bb_clarinet
  "Clarinet in Bb": bb_clarinet
  "Drum Kit": drum_kit
  "Drumset": drum_kit
  "French Horn": horn
```

Alias keys are matched case-insensitively with punctuation and spacing normalised,
so `"Bb Clarinet"`, `"BB CLARINET"`, and `"bb-clarinet"` all resolve to the same entry.

---

## Slugification

Directory names, filenames, and part IDs are all slugified:

- Unicode normalised to ASCII
- Lowercased
- Non-alphanumeric characters replaced with hyphens (directories/filenames)
  or underscores (part IDs)
- Consecutive separators collapsed
- Leading and trailing separators removed

Examples:

| Input | Slug (filename) | ID (part) |
|-------|----------------|-----------|
| Hound Dog | hound-dog | hound_dog |
| Trumpet 1 | trumpet-1 | trumpet_1 |
| Alto Sax 1 | alto-sax-1 | alto_sax_1 |
| Bb Clarinet | bb-clarinet | bb_clarinet |
