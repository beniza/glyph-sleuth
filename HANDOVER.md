# Handover

Where the project stands, and the things that would cost the next session an
hour to rediscover. Read `README.md` first for what the tool *is*; this is what
you need to work on it.

## State

Two halves of one tool, both shipped and live:

| | Desktop | Web |
|---|---|---|
| Entry point | `app.py` (PySide6) | <https://beniza.github.io/glyph-sleuth/> |
| Ships as | binaries on the [v0.2.0 release](https://github.com/beniza/glyph-sleuth/releases/tag/v0.2.0) | GitHub Pages, rebuilt on push and monthly |
| Answers | which of **my** fonts set this | which **freely available** font sets this |

Version lives in one file, `VERSION` (currently `0.2.0`), read by the desktop
title bar, the web masthead, and bundled into the frozen binary by PyInstaller.
Bumping it means editing that file and tagging `vX.Y.Z`.

## The web app in five minutes

```
python scripts/gen_web_index.py --limit 60   # build a slice of the data (~3 min)
python -m http.server -d web 8765            # serve it
node web/test-core.mjs                       # 16 tests, the deploy gate
```

`web/data/` and `web/fonts/` are **derived and gitignored** — CI rebuilds them.
Without running the generator the page loads to an error message, which is
correct behaviour, not a bug.

- `web/core.js` — all logic, no DOM. The port of `chars.py`, plus coverage,
  scripts, licences and link builders. **Anything testable belongs here**;
  `web/test-core.mjs` is the only test file and it gates the deploy.
- `web/app.js` — the five modes and all DOM work.
- `web/style.css` — the specimen sheet. One rule decides layout arguments: the
  fonts are the only large voice on the page; chrome stays small and quiet.
- `scripts/gen_web_index.py` — builds every data file.

## Things that will bite you

**Google publishes font coverage as JSON.** `fonts.google.com/metadata/fonts/<Family>`
returns a `coverage` map of codepoint ranges, so all 1,832 Google families cost
small JSON fetches and **zero font downloads**. Don't "fix" this by downloading
fonts. (It also carries `license`, which is where the licence tags come from.)

**Only non-Google faces are hosted.** SIL, SMC, RIT and the libre classics are
downloaded, read with fontTools, re-emitted as woff2 into `web/fonts/`, and
served by us — legal because they are OFL or GPL+FE. Google's are served from
Google's CDN. **Never host a face we can't redistribute**; that constraint shaped
the whole design.

**Adding a foundry is one entry** in `SOURCES` in `scripts/gen_web_index.py`.
Four host kinds are supported: `github` (an org's repos), `github-repos` (an
explicit list), `gitlab` (a group), and `css` (a stylesheet listing woff2s —
SMC's own site, which is more complete than their GitLab releases).

**Deliberately not indexed:** Last Resort (a glyph for every codepoint in
Unicode, all placeholder boxes — it would top every answer while answering
nothing), STIX (Google carries STIX Two), Liberation (publishes no built
binaries), Source Han (an 80 MB `.ttc` that Noto already covers).

**Duplicate detection is deliberately narrow.** `same_family` merges only on a
known suffix (`Charis` / `Charis SIL`). It must not merge on any shared prefix:
`Meera` (Malayalam) and `Meera Inimai` (Tamil) are different fonts, and hiding
one behind the other is a wrong answer.

**A woff2 filename can collide** when two faces in one release share a family
name. Files are pruned against the finished index (`prune_fonts`), never deleted
when a duplicate is dropped — that bug shipped once and 404'd three fonts.

**A script is not a block.** Devanagari spans three blocks, Tamil two, Arabic
nine. `scripts.json` carries the ranges per block so the client can measure any
font against any block. This is the whole point of the Language & script view:
of 1,885 families, 15 cover the main Tamil block and **one** covers Tamil
Supplement.

**A language is not a script.** `ml` is Malayalam in `Mlym`, `Arab`
(Arabi-Malayalam) and `Brai`. langtags marks the default by giving the bare tag
its script — rely on that for ordering, never on alphabetical.

**The browse QA daemon caches assets.** When a CSS or JS change appears not to
take effect in headless checks, `browse stop` and re-run. A `?v=` on the page URL
does not bust cached `app.js`.

## CI

- `.github/workflows/pages.yml` — rebuilds the index and deploys the site, on
  push to `web/**` or the generator, monthly on the 1st, or by hand. Gated on
  `node web/test-core.mjs`. A full build is ~8 minutes; `GITHUB_TOKEN` is passed
  so the GitHub API isn't rate-limited (60/hr unauthenticated will fail).
- `.github/workflows/release.yml` — on a `v*` tag, builds PyInstaller binaries
  for Windows, macOS and Linux, gated on `test_core.py` **and** `test_app.py`,
  then creates the release. Releases are marked `--prerelease` until 1.0.
- README download links are pinned to a tag (`v0.2.0`) because
  `/releases/latest/download/` **404s while the newest release is a
  pre-release**. Update them when tagging, or switch to `/latest/` at 1.0.

## Conventions worth keeping

- Comments say *why*, never *what*. Several exist only to stop a future reader
  "fixing" a deliberate choice — leave those in place.
- British spelling in prose and identifiers (`licence`, `colour`).
- Tests assert the non-obvious: composition-aware coverage, the DejaVu case in
  `dominantBlock`, why a prefix match is not a family match.
- Every commit message explains the reasoning, not just the change.

## Next

`TODO.md` holds the backlog: a font index, a Markdown editor for Preview, PDF
export, copy-glyph and a collection tray, and Alt+X to swap codepoint and
character. The PDF item has the cheapest first step (`@media print`), and the
Alt+X item is the smallest whole feature.
