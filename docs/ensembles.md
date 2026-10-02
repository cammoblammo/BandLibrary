# Setting Up Ensembles

An ensemble file lists a band's chairs and the rules for which part each
chair gets when a piece has no part of its own. There is no editing screen
for ensembles in the app; you change them in a text editor. This page shows
how.

The files:

| File | Contains |
|------|----------|
| `config/ensembles/<name>.yaml` | One band: its name and its chairs |
| `config/reading_groups.yaml` | Which written parts each kind of instrument can read, shared by every band |

For the full format, see **Data Model** in Help.

---

## How a chair is written

```yaml
  - id: tenor_sax
    label: Tenor Sax
    reads: [bb_treble]
    prefer: [flex 3, flex 4]
    compromise: [baritone_tc, euphonium_tc, bass_clarinet]
```

| Line | Meaning |
|------|---------|
| `id` | The chair's ID. Pieces with a part of the same ID give it to this chair directly. Also the booklet's file name (`tenor_sax.pdf`) |
| `label` | The name on the booklet cover and in reports |
| `reads` | The reading groups this player can read (see below) |
| `prefer` | Good substitutes, best first, used when the piece has no part for this chair |
| `compromise` | Readable but not ideal (range, style), used last. Builds flag them so you can check |

Entries in `prefer` and `compromise` are part IDs as pieces name them
(`alto_sax_1`, `baritone_tc`, …), or `flex N`:

- `flex 3` means part 3 of a flexible arrangement in any group the chair
  reads. For a B♭ chair that is `Part 3 in Bb` or `Part 3 in Bb TC`.
- `flex 5 c_bass` limits it to one group: here, `Part 5 in C BC`.

Lists are not followed as chains: `prefer: [trumpet_2]` means a piece's
Trumpet 2 part, not whatever the Trumpet 2 chair would get. List every
substitute you want, in order.

### A chair that gets every part: Percussion

```yaml
  - id: percussion
    label: Percussion
    reads: [percussion]
    takes: all
```

`takes: all` gives the chair **every** part of each piece that is in the
groups it reads, in the order they appear in the PDF. Both bands have one
Percussion chair like this: percussionists move between instruments, so
their booklet holds the kit, auxiliary, mallets and any other percussion
parts. Print a copy for each player.

A `takes: all` chair doesn't use `prefer` or `compromise`. To give it
something different in one piece, use the review screen (**Assignments…**),
which lets you tick the parts it should get.

Which parts count as percussion is the `percussion` reading group in
`config/reading_groups.yaml`. If a piece's percussion part isn't picked up
(for example a new name such as `Spoons`), add the name there.

Tuned percussion keeps the name it's printed with (`Bells`, `Glockenspiel`,
`Keyboard Percussion` …), because a piece can have more than one. Chairs
that double from it list every kind, in order of preference, e.g. Piano:
`prefer: [keyboard, mallets, keyboard_percussion, tuned_percussion, bells,
glockenspiel, xylophone, marimba, vibraphone, chimes]`.

### Reading groups

| Group | Covers |
|-------|--------|
| `bb_treble` | B♭ treble clef: clarinets, trumpets, tenor sax, bass clarinet, TC euphonium/baritone/trombone |
| `eb_treble` | E♭ treble clef: alto and baritone sax, alto clarinet, tenor horn |
| `c_treble` | C treble clef: flute, oboe, violin, guitar, piano, and tuned percussion (mallets, bells, glockenspiel, xylophone, marimba, vibraphone, keyboard/tuned percussion, chimes), which can double for these chairs through their `prefer` / `compromise` lists |
| `c_bass` | C bass clef: trombone, baritone, euphonium, tuba, bassoon, cello, bass guitar, piano |
| `f_treble` | F: French horn |
| `c_alto` | C alto clef: viola (no chair reads it yet) |
| `percussion` | Every percussion part: drum kit, snare and bass drum, timpani, auxiliary, mallets, bells, glockenspiel, chimes, `Percussion 1`… |

A chair can read more than one group: piano reads `c_treble` and `c_bass`.

---

## Example: adding a baritone sax chair

A baritone sax reads E♭ treble clef. It can also read bass-clef parts by
reading them as treble clef with a different key signature. That's not
ideal, but it's usually better than an alto sax or tenor horn part.

1. Open `config/ensembles/serscb.yaml` in a text editor.
2. Add this block among the other chairs. Where you put it is the order of
   rows in the review screen and reports:

   ```yaml
     - id: baritone_sax
       label: Baritone Sax
       reads: [eb_treble, c_bass]
       prefer: [flex 5 eb_treble, flex 4 eb_treble]
       compromise: [tuba, euphonium, baritone, trombone, flex 5 c_bass, flex 4 c_bass, tenor_horn, alto_sax_2]
   ```

   - Pieces with a baritone sax part give it directly (`id: baritone_sax`).
   - Flexible arrangements give part 5, or part 4, in E♭.
   - Otherwise it reads a bass-clef part, flagged as a compromise, and only
     as a last resort an E♭ tenor horn or alto sax part.

3. Save, then in BandBook choose **Tools → Check Library…** to confirm the
   ensemble loads and see how many pieces the new chair is covered for.
4. Use **Tools → Consistency Report…** or **Assignments…** on a few pieces
   to check the parts it gets, then build as usual.

The next build creates `baritone_sax.pdf`. To remove a chair, delete its
block.

---

## Common changes

### A chair gets the wrong substitute in many pieces

Reorder its `prefer` list, or move an entry between `prefer` and
`compromise`. Check the result with the Consistency Report. For a single
piece, use an assignment instead.

### A chair gets nothing in some pieces

Look at the piece's parts in the Library list and add a suitable part ID, or
a `flex` entry, to the chair's `prefer` or `compromise` list.

### A new instrument name appears in pieces

If a new kind of part (say `soprano_cornet`) should be readable by existing
chairs, add it to the right group's `parts` in `config/reading_groups.yaml`,
then add it to those chairs' lists. Check Library reports an error if a
chair lists a part outside the groups it reads.

### Adding a new ensemble

Copy an existing file in `config/ensembles/`, give it a new file name, and
change `id`, `name` and `band` at the top:

```yaml
schema_version: 2

ensemble:
  id: jazz
  name: JAZZ
  band: South-East Sounds Jazz Band
```

Then edit the chairs. Restart BandBook for a new file to appear in the
Ensemble list. Changes to existing files are picked up at the next Dry Run,
Build or review.

### Renaming a chair

The chair ID is also the booklet file name and the key for its assignments.
If you change an ID, assignments made under the old ID no longer apply. The
Consistency Report lists them as assignments for an unknown chair.

---

## Writing YAML safely

- Indent with spaces, never tabs, and keep each chair's lines aligned.
- Lists go in square brackets with commas: `[flex 3, flex 4]`.
- If a file has a mistake, **Check Library…** and the Booklet Builder show
  an error naming the file and the chair.
- The files are in git, so you can always see or undo what changed.
