# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A static site that answers, for a Unicode character or a shaped sequence, which
fonts can actually draw it — and shows the evidence for every claim. Its
argument: **coverage says a font contains a character; it does not say the font
will draw it correctly.** Malayalam is the flagship script.

Live at <https://beniza.github.io/glyph-sleuth/>, built by CI from `main`.

## The rule that governs every change

**Never state something the data does not support.** This is the product, not a
style preference. A page that prints a verdict beside a rendering it did not
make is worse than a page that says nothing, because a reader cannot tell.

Concretely: "not measured yet" for a family whose file was never read, never
zero coverage. "not read" where only metadata exists, never "declares none".
Every cap disclosed. A control the browser cannot honour does not ship. Full
text and the failure history in `CONTRIBUTING.md`; issues that break it carry
the `honesty` label.

## Commands

```sh
pip install -r requirements.txt
npm ci && npx playwright install chromium

python web/build/gen_index.py --limit 40   # fetch + measure -> web/data/, web/webfonts/
python web/build/render.py                 # web/data/ -> site/
node web/tests/serve.mjs                   # serve site/ at :8787 under /glyph-sleuth/
```

`gen_index.py` takes `--limit N` (families and languages) and `--google-only`
(skip foundry listings). A full run is minutes cold, ~20s warm; always use
`--limit` when iterating. `web/data/cache/` makes it warm and is keyed on the
exact file URL a measurement came from.

### Tests

```sh
python -m pytest web/build                          # generator + renderer
python -m pytest web/build/test_render.py -k slug   # one test by name
python web/build/test_gen.py                        # same file as a plain script (CI does this)
python shared/test_core.py                          # the shared Python layer
npm run test:unit                                   # core.js
npm run test:data                                   # served tables vs the code reading them
npx playwright test                                 # browser, starts its own server
npx playwright test -g "loads the face"             # one browser test by name
```

Python test files are dual-mode: `pytest` collects them, and `__main__` runs
them as plain scripts, which is how CI invokes them. **A test using a pytest
fixture argument breaks the script path** — swap globals manually with
try/finally instead.

**Run `npx playwright test` before pushing anything that touches a page.** Every
bug in this project that reached a deploy was one the unit tests could not see.

## Architecture

A two-stage build. Nothing is assembled in the browser that could be in the
markup, so every fact survives JavaScript being off.

```
foundry releases, Google metadata, UDHR, SLDR, UCD
        |  gen_index.py   fetch, parse fonts in memory, shape with HarfBuzz
        v
web/data/*.json          fonts, blocks, scripts, languages, props, names
web/webfonts/**          foundry woff2 we are licensed to re-serve
        |  render.py      one function per page kind
        v
site/                    ~34,000 static pages + copied JS/CSS/webfonts
```

**`web/build/gen_index.py`** — the only thing that touches the network or reads
a font. Downloads a release, parses `cmap`/`GSUB`/`GPOS`/`fvar`/`silf` with
fontTools, runs HarfBuzz over authored sequences, writes JSON. `SOURCES` is a
declarative list of foundries (four host kinds: `github`, `github-repos`,
`gitlab`, `css`) — adding a foundry is one entry.

**`web/build/render.py`** — pure `web/data/` in, `site/` out. No network. One
`*_page()` function per page kind; `BASE` (env `SITE_BASE`, default
`/glyph-sleuth`) prefixes every internal URL via `link()`.

**`shared/`** — the Python Unicode and SLDR layer, added to `sys.path` by the
generator, which imports `langs` and `ucd` directly; `chars` and `store` (a
pickle cache) sit behind them. `ucd.py` is generated from the UCD; do not
hand-edit.

**`web/core.js`** — DOM-free logic: coverage bisection, `parse()` for any
codepoint notation, ranking. Imported by `app.js`, `inspect.js`, `tryit.js` and
both Node test suites, so the browser and the tests agree on what a string
means. `render.py` mirrors some of it in Python — `use_it()` and `useIt()` are a
deliberate pair; change both.

Page scripts: `app.js` loads on every page and dynamically imports the rest;
`copy.js` (all `.copy` buttons), `inspect.js` (`/inspect/` only), `tryit.js`
(family pages only).

### The three tiers

The core model, and it is spread across generator and renderer:

1. **Coverage** — does `cmap` contain the codepoints. Google publishes this as
   metadata, so ~1,900 families get it cheaply.
2. **Declared tags** — which OpenType script tag `GSUB`/`GPOS` declares. Needs
   the file itself. A face can cover every codepoint of a script and still
   declare only the old tag, which is exactly the failure the site exists to
   show.
3. **Shaping** — HarfBuzz over authored sequences in `web/content/sequences.json`,
   per script in `SHAPED_SCRIPTS`. Only Malayalam and Devanagari have sequences.

A family with tier 1 only is `"tier": "stub"` and its page says *not measured
yet*. Never substitute zero for unknown.

### Generated, not source

`site/` (except `site/mockup/`), `web/data/` and `web/webfonts/` are gitignored
build output. `site/core.js`, `copy.js`, `inspect.js`, `tryit.js` and
`site/webfonts/` are **copies** — edit the originals in `web/`.

`site/mockup/` is committed on purpose: the design prototype the build is
checked against, not output.

## Fonts: what may be published

`docs/DECISIONS.md` **D2**, revised twice. Read it before changing what the
build emits. In short: read any font; re-serve only the foundry's own `woff2`,
byte for byte, and only when a licence in the same release permits it. Convert
nothing, rename nothing. `test_gen.py` asserts exactly one binary writer and one
output directory. Where a face cannot be loaded, the page says which of the two
reasons and **draws nothing**.

## Where things are written down

| | |
| --- | --- |
| [the board](https://github.com/users/beniza/projects/10) | every open item. There are no task lists in the repo |
| `CONTRIBUTING.md` | commands, test strategy, commit and release conventions, measured build cost, the trap list |
| `docs/DECISIONS.md` | standing rules and why they stand; revisions kept, not overwritten |
| `docs/BRIEF.md` | the original brief. Archival — describes a plan, not the built site |

## Traps worth knowing before you start

Full list in `CONTRIBUTING.md`. The ones that cost the most time:

- **The site is served from `/glyph-sleuth/`, never the root.** Absolute URLs
  written from `/` give an unstyled page. Everything internal goes through
  `render.link()`. The test server serves under the prefix deliberately, so this
  cannot pass locally and fail in production.
- **Slugs keep Unicode.** RIT families name themselves in Malayalam; stripping
  to ASCII gave empty slugs that overwrote each other.
- **HarfBuzz cannot read woff2**, which is what foundries serve. It returns
  `.notdef` for everything and the family looks broken while being fine.
- **`document.fonts.check()` cannot say no** — Chrome answers true for families
  that do not exist. What is provable is whether our `@font-face` arrived.
- **Editing JS or CSS through a shell heredoc mangles escapes.** Use the file
  tools, or a patch script with a named `NEWLINE = chr(10)`.
- **Never re-run a failed deploy job.** It uploads a second `github-pages`
  artifact and the next attempt dies on "Artifact count is 2". Push a commit or
  use `workflow_dispatch`.

## Conventions

- One feature per commit and per deploy; commit messages carry the *why*,
  including what was wrong before.
- Small releases, often. Annotated tags `vX.Y.Z`, headline then prose, marked
  pre-release until v1.0.
- Prefer a test that kills a *class* of bug over one that pins a page.
- An assertion is only as good as its premise. If a test has never been seen to
  fail, break the code deliberately and watch it fail.
