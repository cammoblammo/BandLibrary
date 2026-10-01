# Consistency Report

## Purpose

The consistency report shows how every chair in each ensemble gets its music
across the whole library, and flags where ensembles, part names and
assignments don't line up. It changes nothing.

Run it after editing an ensemble or `config/reading_groups.yaml`, or after
importing several pieces.

---

## In the app

Choose **Tools → Consistency Report…**. BandBook builds the report for every
ensemble, saves it as `output/consistency-report.html` and opens it in your
web browser. The status bar shows how many warnings it found.

In the Booklet Builder's test mode it reports on the test library and saves
to `test-output/`.

---

## Command line

```
python3 tools/consistency_report.py [--ensemble FILE ...] [--html FILE]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--library <path>` | `library/` | Library directory |
| `--ensemble <path>` | every file in `config/ensembles/` | Ensemble to include (repeatable) |
| `--html <path>` | none | Also write an HTML page with a chair-by-piece grid |
| `--fragment` | off | Write the HTML without the page wrapper |

---

## What it reports

A summary for each ensemble counts how chairs are matched across all pieces:
direct, fallback, compromise, assigned and missing.

Warnings:

| Finding | Meaning |
|---------|---------|
| Missing although a matching part exists | A chair gets nothing although the piece has, e.g., `flute` for a `flute_1` chair |
| Missing with no fallback | A chair with no substitutes gets nothing in some pieces |
| Possible duplicate part name | Two part IDs in the library probably mean the same part |
| Chair lists a part it can't read | A `prefer`/`compromise` entry is outside the chair's reading groups |
| Assignment outside what the chair reads | A piece assigns a chair a part from another transposition or clef |
| Same chair, different name | One ensemble has `flute`, another `flute_1`: their assignments don't carry over |
| Assignment for unknown chair | An assignment names a chair no ensemble has |

Information:

| Finding | Meaning |
|---------|---------|
| Compromise in use | Which chairs read compromise parts, and in which pieces |
| Redundant assignment | An assignment that matches what the rules already choose |
| Assignment overrides a direct match | A piece gives a chair something other than its own part |
| Part never used | A part no chair reads, in two or more pieces |
| Same chair, different fallbacks | A chair ID with different lists in different ensembles |
| Substitute not in any piece yet | A `prefer`/`compromise` entry no piece has (check the spelling) |

The HTML page adds a grid for each ensemble: one row per chair, one column
per piece, with each cell showing what the chair reads and why.
