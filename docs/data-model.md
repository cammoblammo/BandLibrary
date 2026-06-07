# Data Model

## Overview

BandLibrary uses two types of YAML file:

- **Piece YAML** — metadata for a single imported piece
- **Ensemble YAML** — definition of an ensemble and its instrumentation

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

---

## Ensemble YAML

Location: `config/ensembles/<name>.yaml`

### Example

```yaml
parts:
  - id: flute
    label: Flute

  - id: clarinet_1
    label: Clarinet 1

  - id: clarinet_2
    label: Clarinet 2
    fallback: [clarinet_1]

  - id: trumpet_1
    label: Trumpet 1

  - id: trumpet_2
    label: Trumpet 2
    fallback: [trumpet_1]

  - id: trumpet_3
    label: Trumpet 3
    fallback: [trumpet_2, trumpet_1]

  - id: trombone
    label: Trombone

  - id: drum_kit
    label: Drum Kit
```

### Field reference

#### parts (list)

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Ensemble part identifier |
| `label` | string | Human-readable label used in reports and output filenames |
| `fallback` | [string, ...] | Optional list of alternative part IDs to try if no direct match |

Fallback entries may refer to other ensemble part IDs or piece part IDs directly.

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
