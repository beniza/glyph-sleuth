# Glyph Sleuth

A read-only inspector for Unicode characters, fonts, scripts and languages, for
script engineers first.

Its argument in one sentence: **coverage says a font contains a character; it
does not say the font will draw it correctly.** So every claim carries its
evidence, in three tiers — does the font *cover* the codepoints, does it
*declare* the right OpenType script tag, does it *shape* the script's exemplar
sequences cleanly.

Malayalam is the flagship script, not the only one.

## Status

Being rebuilt, web first. What is live today is the **design mockup** — the
prototype the implementation is being built against, served from `site/`.

Start at [`docs/PROGRESS.md`](docs/PROGRESS.md) for where the work stands, and
[`docs/HANDOFF.md`](docs/HANDOFF.md) for what is being built and why.

## Two halves

| | Web | Desktop companion |
| --- | --- | --- |
| What | A static site: characters, fonts, scripts, languages and the evidence behind every verdict | A local tool a contributor runs against a font they already have |
| Where | `web/`, published from `site/` | `desktop/` |
| Emits | pages | a small stamped JSON record, as a pull request |

The desktop half is a companion, not a second front end. It exists because the
facts that need a font file open — OpenType tags, lookup counts, shaping
verdicts — have to be computed somewhere, and it is not going to be here:

> **No font binary is ever fetched, mirrored or hosted by Glyph Sleuth's own
> infrastructure**, not even transiently in a build step.

Specimens render from wherever the family is actually distributed. Real computed
numbers come from a contributor's own machine, or they do not exist yet and the
page says so.

## Scope

> If it answers a question, it's in. If it changes a file, it's out.

Read-only inspection is in scope. Anything that writes a font, a UFO or a PDF
belongs in `pysilfont` and `smith`, which already do it better and belong in a
build, not behind a GUI.

## Layout

| | |
| --- | --- |
| `site/` | what GitHub Pages serves. Currently the mockup |
| `web/` | the site's source: logic, DOM, styles, build, tests |
| `desktop/` | the PySide6 companion |
| `shared/` | the Python Unicode and SLDR layer, used by both |
| `docs/` | the brief, the settled specs, the prototype bundle, the progress checklist |
| `.local/` | local scratch, gitignored |

## Licence

MIT.
