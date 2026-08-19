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

Live at <https://beniza.github.io/glyph-sleuth/> — 1,885 families indexed, 1,878
measured from their own released file, around 34,000 pages. `/regex/` and
`/identify/` are not built and are deliberately absent from the nav rather than
present as 404s.

Open work is on the [board](https://github.com/users/beniza/projects/10).
[`CONTRIBUTING.md`](CONTRIBUTING.md) says how to run it and how the work is
organised; [`docs/HANDOFF.md`](docs/HANDOFF.md) says what is being built and
why, and [`docs/PROGRESS.md`](docs/PROGRESS.md) tracks the phase plan.

## Two halves

| | Web | Desktop companion |
| --- | --- | --- |
| What | A static site: characters, fonts, scripts, languages and the evidence behind every verdict | A local tool a contributor runs against a font they already have |
| Where | `web/`, published from `site/` | `desktop/` |
| Emits | pages | a small stamped JSON record, as a pull request |

> **Fetch and parse. Serve only what the licence allows.** The build downloads a
> family's public release and reads its tables in memory. Where the licence in
> that same release permits redistribution, it also re-serves the foundry's own
> `woff2` build, unmodified — every face, converted and renamed not at all. We
> publish nothing we generated and nothing we cannot read a licence for, and a
> family we cannot draw says so rather than letting the browser substitute one.
> Specimens otherwise render from wherever the family is actually distributed.

Nothing you type ever leaves your browser. No uploads, no accounts, no server.

The desktop half is a companion, not a second front end: it measures the fonts
the build cannot reach — unreleased, in development, proprietary, or internal to
an organisation — on the machine that already has them.

## Scope

> If it answers a question, it's in. If it changes a file, it's out.

Read-only inspection is in scope. Anything that writes a font, a UFO or a PDF
belongs in `pysilfont` and `smith`, which already do it better and belong in a
build, not behind a GUI.

## Layout

| | |
| --- | --- |
| `site/` | what GitHub Pages serves. Generated; `/mockup/` is the committed prototype |
| `web/` | the site's source: logic, DOM, styles, build, tests |
| `desktop/` | the PySide6 companion |
| `shared/` | the Python Unicode and SLDR layer, used by both |
| `docs/` | the brief, the settled specs, the prototype bundle, the progress checklist |
| `.local/` | local scratch, gitignored |

## Licence

MIT.
