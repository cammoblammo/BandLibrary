"""
Read page text as a part name.

parse_name("Clarinet in B♭ 1", aliases) gives the label "Clarinet 1", the
part ID the aliases resolve it to, and notes for anything the reader should
check. Clefs are never guessed: "Part 4 in C" stays as printed and is
flagged, because bare C parts belong to no reading group.
"""

from __future__ import annotations

import re
import unicodedata

from ..aliases import normalise_part_id
from ..utils import canonicalise_alias_key
from .pages import NameMatch

# Words a part name is made of. A name starts with one of these (or a key
# such as "Bb", or "Part") and contains nothing else but keys, numbers,
# clef marks and joining words.
INSTRUMENT_WORDS = {
    "flute", "flutes", "piccolo", "oboe", "oboes", "cor", "anglais", "english",
    "clarinet", "clarinets", "bassoon", "bassoons", "contrabassoon",
    "saxophone", "saxophones", "sax", "alto", "tenor", "baritone", "bari",
    "soprano", "bass", "contrabass", "horn", "horns", "french", "trumpet",
    "trumpets", "cornet", "cornets", "flugelhorn", "trombone", "trombones",
    "euphonium", "euphoniums", "tuba", "tubas", "sousaphone", "guitar",
    "electric", "acoustic", "piano", "keyboard", "keyboards", "keys",
    "synth", "synthesizer", "organ", "violin", "violins", "viola", "violas",
    "cello", "cellos", "violoncello", "double", "drum", "drums", "kit",
    "drumkit", "snare", "cymbal", "cymbals", "percussion", "aux",
    "auxiliary", "mallets", "mallet", "glockenspiel", "glock", "xylophone",
    "marimba", "vibraphone", "vibes", "timpani", "tambourine", "chimes",
    "bells", "claves", "woodblock", "triangle", "cowbell", "shaker",
    "recorder", "recorders", "beginners", "beginner", "ukulele", "harp",
    "voice", "vocals", "strings", "maracas", "bongos", "congas", "guiro",
    "cabasa", "timbales", "agogo", "vibraslap", "gong", "toms", "hi-hat",
}

# Score abbreviations: only used to recognise score pages
ABBREVIATIONS = {
    "fl", "picc", "ob", "cl", "clar", "bcl", "bsn", "sax", "asx", "tsx",
    "hn", "hns", "tpt", "tpts", "trp", "tbn", "tbns", "trb", "euph", "bar",
    "tba", "perc", "dr", "drs", "drms", "glock", "xyl", "timp", "vln", "vn",
    "vla", "vc", "vcl", "db", "pno", "gtr", "kbd", "bs",
}
VOICE_PREFIXES = {"a", "t", "b", "s", "bb", "eb"}

KEYS = {k for n in "abcdefg" for k in (n, n + "b", n + "#")}
JOINERS = {"in", "or", "and", "set", "tc", "bc", "treble", "clef", "solo",
           "i", "ii", "iii", "iv", "part", "1st", "2nd", "3rd", "4th"}
SCORE_MARKERS = {"score", "full score", "conductor", "conductor score",
                 "conductors score", "condensed score"}

# Transpositions that go without saying: "Trumpet in B♭" is a trumpet part.
# "Horn in F" also becomes "French Horn".
STANDARD_KEYS = [
    ("bass clarinet", "Bb"), ("clarinet", "Bb"), ("trumpet", "Bb"),
    ("cornet", "Bb"), ("flugelhorn", "Bb"), ("tenor horn", "Eb"),
    ("soprano saxophone", "Bb"), ("soprano sax", "Bb"),
    ("tenor saxophone", "Bb"), ("tenor sax", "Bb"),
    ("alto saxophone", "Eb"), ("alto sax", "Eb"),
    ("baritone saxophone", "Eb"), ("baritone sax", "Eb"),
    ("alto clarinet", "Eb"),
]
ORDINALS = {"1st": "1", "2nd": "2", "3rd": "3", "4th": "4"}

MAX_WORDS = 7
MAX_LENGTH = 40

FLEX_RE = re.compile(
    r"part\s*(\d+[a-z]?)\s*(?:in\s+)?([A-G][b#]?)(?:\s+(TC|BC))?", re.I)


def _tokens(text: str) -> list[str]:
    text = text.lower().replace("♭", "b").replace("♯", "#")
    return re.findall(r"[a-z0-9#]+", text)


def normalise(text: str) -> tuple[str, list[str]]:
    """Tidy printed text: accidentals, clef words, spacing. Returns notes."""
    notes = []
    s = unicodedata.normalize("NFC", text)
    s = s.replace("♭", "b").replace("♯", "#")
    s = " ".join(s.split()).strip(" .,:;-–—")
    # OCR misreadings: a flat read as ">", "1st" read as "tst" / "4st",
    # and a key run into the next word ("EbALTO")
    s = re.sub(r"\b([BE])>", r"\1b", s)
    s = re.sub(r"^[t4lI|]st\b", "1st", s)
    s = re.sub(r"\b([BE][b])(?=[A-Z]{3})", r"\1 ", s)
    # A flat drawn as a separate glyph: "B b" -> "Bb"
    s = re.sub(r"\b([A-G])\s+([b#])(?=\s|$|\d)", r"\1\2", s)
    # Accidentals drawn in a music font can vanish from the text layer.
    # Band instruments are never in B or E natural.
    m = re.search(r"\bin ([BE])\b(?![b#])", s)
    if m:
        s = s[:m.end(1)] + "b" + s[m.end(1):]
        notes.append(f'read "in {m.group(1)}" as "in {m.group(1)}b" '
                     "(the flat is missing from the PDF text)")
    s = re.sub(r"\(?\s*treble\s+clef\s*\)?", "TC", s, flags=re.I)
    s = re.sub(r"\(?\s*bass\s+clef\s*\)?", "BC", s, flags=re.I)
    s = re.sub(r"\bT\.\s?C\.?(?=\s|$)", "TC", s)
    s = re.sub(r"\bB\.\s?C\.?(?=\s|$)", "BC", s)
    s = " ".join(s.split())
    # Capitals (common on scans) become "Alto Saxophone"; keys and clefs stay
    s = re.sub(r"\b[A-Z]{3,}\b", lambda m: m.group(0).capitalize(), s)
    s = " ".join(_split_run_together(w) for w in s.split())
    # "2nd Bb Clarinet" -> "Bb Clarinet 2"
    m = re.match(r"(1st|2nd|3rd|4th)\s+(.+)", s, re.I)
    if m:
        s = f"{m.group(2)} {ORDINALS[m.group(1).lower()]}"
    return s, notes


def _split_run_together(word: str) -> str:
    """OCR can drop a space: "AltoSaxophone" -> "Alto Saxophone", "Hornin" -> "Horn in"."""
    low = word.lower()
    known = INSTRUMENT_WORDS | {"in"}
    if low in known or not low.isalpha():
        return word
    for i in range(2, len(low) - 1):
        if low[:i] in INSTRUMENT_WORDS and low[i:] in known:
            return f"{word[:i]} {word[i:]}"
    return word


def is_score_marker(text: str) -> bool:
    return canonicalise_alias_key(text) in SCORE_MARKERS


def looks_instrumental(text: str) -> bool:
    """Loose test, used to count staff names on score pages."""
    toks = _tokens(text)
    if not toks or len(toks) > MAX_WORDS or text.lstrip().startswith("("):
        return False
    if toks[0] == "part" and len(toks) > 1 and toks[1][:1].isdigit():
        return True
    if toks[0] in INSTRUMENT_WORDS:
        return True
    if toks[0] in ABBREVIATIONS and (len(toks[0]) > 1 or len(toks) > 1):
        return True
    return (len(toks) > 1 and toks[0] in VOICE_PREFIXES
            and (toks[1] in ABBREVIATIONS or toks[1] in INSTRUMENT_WORDS))


def _is_name(tokens: list[str]) -> bool:
    if not tokens or len(tokens) > MAX_WORDS:
        return False
    first = tokens[0]
    if first not in INSTRUMENT_WORDS and first not in KEYS \
            and first not in {"1st", "2nd", "3rd", "4th"}:
        return False
    if not any(t in INSTRUMENT_WORDS for t in tokens):
        return False
    return all(t in INSTRUMENT_WORDS or t in KEYS or t in JOINERS
               or re.fullmatch(r"\d+[a-z]?", t) for t in tokens)


def _drop_standard_key(s: str) -> str:
    """ "Trumpet in Bb 1" or "Bb Trumpet 1" -> "Trumpet 1"; "F Horn" -> "French Horn" """
    m = re.match(r"(?:horn in F|F horn)\b\s*", s, re.I)
    if m:
        return ("French Horn " + s[m.end():]).strip()
    for instrument, key in STANDARD_KEYS:
        m = re.match(rf"({instrument})\s+in\s+{key}\b\s*", s, re.I) \
            or re.match(rf"{key}\s+({instrument})\b\s*", s, re.I)
        if m:
            rest = s[m.end():]
            joiner = "" if rest.startswith("/") else " "
            return (m.group(1) + joiner + rest).strip()
    return s


def parse_name(text: str, aliases: dict[str, str]) -> NameMatch | None:
    """Read text as a part name, or return None if it isn't one."""
    match = _parse_name(text, aliases)
    if match is None and "," in text:
        # A running header: "Part 5 in C, Trombone/Baritone"
        name, rest = text.split(",", 1)
        match = _parse_name(name, aliases)
        if match and rest.strip():
            match.printed_for = rest.strip()
    return match


def _parse_name(text: str, aliases: dict[str, str]) -> NameMatch | None:
    if len(text) > MAX_LENGTH * 2:
        return None
    s, notes = normalise(text)
    if not s or len(s) > MAX_LENGTH or s.startswith("("):
        return None

    m = FLEX_RE.fullmatch(s)
    if m:
        number, key, clef = m.group(1), m.group(2), m.group(3)
        key = key[0].upper() + key[1:].lower()
        label = f"Part {number.lower()} in {key}" + (f" {clef.upper()}" if clef else "")
        if key == "C" and not clef:
            notes.append("clef not printed: add TC or BC")
        return NameMatch(label, normalise_part_id(label, aliases), True, notes)

    if canonicalise_alias_key(s) in aliases:
        simple = _drop_standard_key(s)
        label = simple if canonicalise_alias_key(simple) in aliases else s
        return NameMatch(label, normalise_part_id(label, aliases), True, notes)

    if not _is_name(_tokens(s)):
        return None

    label = _drop_standard_key(s)
    for candidate in (label, s):
        if canonicalise_alias_key(candidate) in aliases:
            return NameMatch(candidate, normalise_part_id(candidate, aliases),
                             True, notes)
    return NameMatch(label, normalise_part_id(label, aliases), False, notes)
