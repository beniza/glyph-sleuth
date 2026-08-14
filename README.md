# Glyph Sleuth

The window you keep open beside your editor to answer *which font has this, what
is this character, and what would break* — in seconds, without touching a file.

```
git clone https://github.com/beniza/glyph-sleuth
cd glyph-sleuth
pip install -r requirements.txt
python app.py
```

## Download

One file, nothing to install — [Windows](https://github.com/beniza/glyph-sleuth/releases/download/v0.1.0/glyph-sleuth-windows-x64.exe)
· [macOS (Apple silicon)](https://github.com/beniza/glyph-sleuth/releases/download/v0.1.0/glyph-sleuth-macos-arm64)
· [Linux](https://github.com/beniza/glyph-sleuth/releases/download/v0.1.0/glyph-sleuth-linux-x64)
· [all releases](https://github.com/beniza/glyph-sleuth/releases)

The builds are unsigned, so Windows SmartScreen and macOS Gatekeeper will warn
on first run; on macOS and Linux, `chmod +x` the file first.

## Scope

> **If it answers a question, it's in. If it changes a file, it's out.**

That decides every future feature. Read-only inspection is in scope; anything
that writes a font, a UFO, or a PDF belongs in `pysilfont` and `smith`, which
already do it better and belong in a build, not behind a GUI.

## What it does

One search field takes anything and works out what you meant, showing its
reading — and the other readings it rejected — under the box:

| You type | Read as |
|---|---|
| `✱` | the character |
| `U+2731`, `0x2731`, `✱`, `&#x2731;` | codepoint |
| `2731` | hex codepoint, with decimal offered as the alternative |
| `heavy asterisk` | Unicode name search |
| `\p{Script=Devanagari}` | property — every matching codepoint, fonts ranked by coverage |
| `U+2700..U+27BF` | codepoint range |
| `Quivira` | installed font |
| `Dingbats` | Unicode block |
| anything else | text, ranked by which fonts cover all of it |

**Search** lists the faces that map the character, each row drawn in the font it
names, with the same glyph shown side by side so you can see how differently
they draw it. The inspector adds encodings, every matching `\p{…}`, and the
characters that share its name — each with a live count of how many installed
faces have it.

**Convert** breaks text into codepoints and codepoints back into text, taking
any notation and mixing them freely. Invisible characters keep their row and get
a visible stand-in.

**Browse** walks a Unicode block drawn in a chosen face, greying what that face
can't draw.

**Language** is the one nothing else answers. Pick a language and it fetches SIL
SLDR exemplar characters and ranks your installed families by whether they can
actually set it — naming exactly which characters would drop to fallback.
Coverage counts a precomposed character as present when the face has the pieces
to build it.

On this machine, of 209 families: Hindi is covered by 2, Amharic by 1, Burmese
by 1. Coverage is a cliff, not a slope.

## Layout

| File | |
|---|---|
| `app.py` | the window. Inspector panes are HTML in a `QTextBrowser`, so links do the navigating |
| `index.py` | scans every installed face for its codepoint set; cached per file, so only fonts you changed get re-read |
| `chars.py` | codepoints, properties, name search, variants, query classification |
| `langs.py` | SIL langtags + SLDR exemplars, and the UnicodeSet expander |
| `ucd.py` | generated block ranges and property names — `python scripts/gen_ucd.py` to refresh |
| `store.py` | the disk cache |

Three dependencies: **PySide6** for the window and for rendering any installed
font, **fontTools** for reading `cmap` tables, **regex** for `\p{…}`.

Property matching asks the `regex` engine itself rather than a hand-kept list,
so an answer here is the answer a real regex would give — and every property
label shown is valid inside a `\p{…}` you can paste straight into code. The
tests assert that round trip.

## Data

- **langtags.json** — 9,600 tags, fetched once from `ldml.api.sil.org`
- **SLDR** — exemplar characters, fetched per language the first time you ask
- **UCD** — block ranges and property aliases, vendored in `ucd.py`

Everything is cached under your local app-data directory. Only the first look at
a given language needs the network; the rest works offline.

## Tests

```
python test_core.py    # parsing, properties, UnicodeSet, composition coverage
python test_app.py     # drives the real window offscreen
```

`test_app.py` builds the index and runs a query of every kind against the real
widgets. It waits on conditions rather than calling the app's own slots — faking
completion lets the queued signal arrive later and undo the next step, which is
exactly the bug it was written after.

## Known edges

- The UnicodeSet expander handles the shapes SLDR exemplars actually use —
  literals, ranges, sequences, escapes, nesting. Not set difference or
  intersection, which don't appear there. PyICU if that ever changes.
- `\p{…}` membership scans the whole codespace (~1M codepoints) on a worker
  thread; a second or two for a broad property.
- A cold index of ~400 faces takes about 25 s. After that it's ~2 s, and only
  changed files are re-read.
- Qt's font logging is off by default. Windows ships legacy `.fon` bitmap fonts
  DirectWrite can't open, and Qt logs a line every time a UI font lacks
  OpenType tables for a script and falls back — hundreds of lines here, none of
  them affecting what you see. `GLYPH_SLEUTH_FONT_LOG=1 python app.py` restores
  them if you're chasing a glyph that won't render.
