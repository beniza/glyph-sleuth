# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Read `CONTRIBUTING.md` first.** It holds the commands, the test strategy, the
commit and release conventions, and the trap list. This file covers only what it
does not: how the pieces fit together.

Two rules matter enough to state twice, because breaking either wastes a deploy:

- **Never state something the data does not support.** This is the product, not
  a style preference. `CONTRIBUTING.md` has the concrete forms and the failure
  history.
- **Run `npx playwright test` before pushing anything that touches a page.**

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

**`web/build/gen_index.py`** — the only thing that touches the network or reads a
font. `SOURCES` is a declarative list of foundries (host kinds `github`,
`github-repos`, `gitlab`, `css`); adding one is a single entry. Takes
`--limit N` and `--google-only`; always use `--limit` when iterating. Its cache
under `web/data/cache/` is keyed on the exact file URL a measurement came from.

**`web/build/render.py`** — pure `web/data/` in, `site/` out, no network. One
`*_page()` function per page kind. `BASE` (env `SITE_BASE`) prefixes every
internal URL via `link()`.

**`shared/`** — the Python Unicode and SLDR layer, added to `sys.path` by the
generator, which imports `langs` and `ucd`; `chars` and `store` sit behind them.
`ucd.py` is generated from the UCD — do not hand-edit.

**`web/core.js`** — DOM-free logic: coverage bisection, `parse()` for any
codepoint notation, ranking. Imported by `app.js`, `inspect.js`, `tryit.js` and
both Node suites, so the browser and the tests agree on what a string means.
`render.py` mirrors part of it in Python: `use_it()` and `useIt()` are a
deliberate pair — change both.

`app.js` loads everywhere and dynamically imports the rest: `copy.js` (all
`.copy` buttons), `inspect.js` (`/inspect/`), `tryit.js` (family pages).

## The three tiers

The core model, spread across generator and renderer:

1. **Coverage** — does `cmap` contain the codepoints. Google publishes this as
   metadata, so ~1,900 families get it cheaply.
2. **Declared tags** — which OpenType script tag `GSUB`/`GPOS` declares. Needs
   the file. A face can cover every codepoint of a script and still declare only
   the old tag, which is exactly the failure this site exists to show.
3. **Shaping** — HarfBuzz over authored sequences in `web/content/sequences.json`,
   per script in `SHAPED_SCRIPTS`. Malayalam and Devanagari only.

A family with tier 1 alone is `"tier": "stub"` and its page says *not measured
yet*. Never substitute zero for unknown.

## Generated, not source

`site/` (except `site/mockup/`), `web/data/` and `web/webfonts/` are gitignored
build output. `site/core.js`, `copy.js`, `inspect.js`, `tryit.js` and
`site/webfonts/` are **copies** — edit the originals in `web/`.

`site/mockup/` is committed on purpose: the design prototype the build is
checked against.

## Running one test

`CONTRIBUTING.md` lists the suites. To narrow:

```sh
python -m pytest web/build/test_render.py -k slug
npx playwright test -g "loads the face"
```

Python test files are dual-mode — `pytest` collects them, and `__main__` runs
them as plain scripts, which is how CI invokes them. **A pytest fixture argument
breaks the script path**; swap globals manually with try/finally instead.

## Where things are written down

| | |
| --- | --- |
| [the board](https://github.com/users/beniza/projects/10) | every open item. There are no task lists in the repo |
| `CONTRIBUTING.md` | commands, tests, conventions, build cost, traps |
| `docs/DECISIONS.md` | standing rules and why. **D2 governs what the build may publish** |
| `docs/BRIEF.md` | the original brief. Archival — a plan, not the built site |
