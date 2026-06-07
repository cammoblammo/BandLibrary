# Add Part

## Purpose

`add_part.py` appends an additional part PDF to an existing imported piece.

This is useful when a piece is missing a part that needs to be added later —
for example, a separately scanned instrument part, or a part created after
the initial import.

---

## Usage

```
python3 tools/add_part.py <piece-slug> "<Part Label>" <part.pdf> [options]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `piece-slug` | Slug of the existing library piece to append to |
| `Part Label` | Human-readable label for the new part (e.g. `"Tenor Horn"`) |
| `part.pdf` | Source PDF to append |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--library <path>` | `library/` | Library root directory |
| `--aliases <path>` | `config/aliases.yaml` | Aliases file for part ID normalisation |

### Examples

```bash
# Add a tenor horn part to an existing piece
python3 tools/add_part.py hound-dog "Tenor Horn" tenor-horn.pdf

# Add a part to a piece in the test library
python3 tools/add_part.py hound-dog "Tenor Horn" tenor-horn.pdf --library test/
```

---

## What It Does

1. Locates the existing piece in the library
2. Reads the current PDF page count to determine where the new pages begin
3. Appends the new PDF's pages to the existing piece PDF
4. Calculates the page range automatically
5. Adds the new part stanza to the piece YAML
6. Removes the source PDF after a successful import

The source PDF is always appended at the end. Page order within the combined
PDF does not affect booklet building, since the builder selects pages by range.

---

## Part ID Normalisation

The part label is normalised to a canonical ID using the same rules as the importer:

1. Check `config/aliases.yaml` for an explicit mapping
2. If not found, slugify the label (lowercase, punctuation to underscores)

Examples:

| Label | Canonical ID |
|-------|-------------|
| Tenor Horn | `tenor_horn` |
| Bb Clarinet | `bb_clarinet` (if aliased) |
| Alto Sax 2 | `alto_sax_2` |

---

## Error Handling

The tool errors out if:

- the piece slug does not exist in the library
- the source PDF does not exist
- the part ID or label already exists in the piece

Duplicate parts are an error with no override flag. If a duplicate occurs,
check the piece YAML — if the part is genuinely different, add an alias to
give it a distinct canonical ID.

---

## Rollback

If anything fails after the operation has begun, both the piece PDF and
the piece YAML are restored to their original state from backups.
The source PDF is only removed after a fully successful import.

---

## Testing

Use `--library test/` to append parts to a test library without touching
the real library:

```bash
python3 tools/add_part.py hound-dog "Tenor Horn" tenor-horn.pdf --library test/
```