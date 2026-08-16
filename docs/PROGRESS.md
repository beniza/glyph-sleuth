# Progress

The resumable checklist. `HANDOFF.md` says what we're building and why; this says
how far we've got. Tick items as they land, and keep the notes under a phase
current — an interrupted session should be able to start here and nowhere else.

Method is test-driven throughout: the failing test comes first, for every
non-trivial unit. `web/tests/test-core.mjs` gates the deploy; `pytest` covers the
generator and the companion.

Scope rule, which decides every item that gets proposed later: **if it answers a
question, it's in; if it changes a file, it's out.**

## Phase 0 — Layout and the served mockup

- [x] Reorganise the repo: `docs/`, `site/`, `.local/` (gitignored)
- [x] `.gitignore` — `.local/`, derived data, the usual noise
- [x] Prototype HTML becomes `site/index.html`, served as the mockup
- [x] `docs/PROGRESS.md` — this file
- [x] Fix `HANDOFF.md` §8 manifest: it pointed at `project/`, not the real paths
- [x] `.github/workflows/pages.yml` — publish `site/`
- [x] `README.md` + `LICENSE` (MIT, carried from the archive branch)
- [ ] Enable Pages in the repo settings (Source: GitHub Actions) — manual step

## Phase 1 — Generator and the ten built pages

Ported from `archive/pre-rebuild`, with the font-hosting path removed.

- [ ] `shared/` — `ucd.py`, `chars.py`, `langs.py`, `store.py` as-is
- [ ] `web/build/gen_index.py` ← `scripts/gen_web_index.py`, minus `OUT_FONTS`,
      `build_face`, `extract_fonts`, `prune_fonts`
- [ ] `web/core.js` ← `web/core.js`, logic only, no DOM
- [ ] Static HTML rendering: entity pages generated, index pages served whole
      with JS filtering on top, tool pages as shells
- [ ] Home
- [ ] Script page — engine strip in the filter-chips row, no collapse bar
- [ ] Font family page — real CSS "Use it" fallback chain
- [ ] Font shaping tables
- [ ] Character page
- [ ] Block page
- [ ] Language page
- [ ] Feature page
- [ ] Inspect
- [ ] Regex
- [ ] Index pages: `/scripts`, `/languages`, `/fonts`

Known gaps to fix while building (`HANDOFF.md` §6), not new design work:

- [ ] CSS snippet: Google `@import` → foundry's own CSS → honest self-host state
- [ ] Home's "Only have a picture of it" links to `/identify/`
- [ ] Size slider and sample-word state encode into the URL
- [ ] `collapseData` not ported — dead code
- [ ] Authored placeholders replaced with computed values and deleted

## Phase 2 — Compare, Identify, shaping matrix

- [ ] Compare — 14 rows, agree/differ per row, no score, no guessed default pair
- [ ] Identify — atlas after `document.fonts.ready`, 24×24 signatures,
      `IoU − 0.15 × centroidDistance`, honest weak-result state
- [ ] Shaping matrix — `{hb, dw, ct, gr}`, three treatments, required legend

## Phase 3 — Salvaged from the archive backlog

- [ ] Alt+X — swap codepoint and character; additive, never the only route
- [ ] Print stylesheet — `@media print`, browser's own Save as PDF
- [ ] Copy glyph + collection tray, feeding Inspect
- [ ] Markdown preview editor — needs per-family weights recorded in Phase 1

## Phase 4 — Desktop companion (PySide6)

Blocked until the web data shapes are locked.

- [ ] `desktop/` — parse `cmap`/`GSUB`/`GPOS`/`fvar`/`silf` locally
- [ ] Run HarfBuzz locally; DirectWrite on Windows, CoreText on macOS
- [ ] Export a checksum- and version-stamped JSON record — never the font
- [ ] Contribution flow: the record becomes a pull request

## Phase 5 — Provenance and version history

Blocked on data decisions, not code.

- [ ] Cite SLDR file and revision; pin, re-verify periodically
- [ ] Carry the validity level; show "not tested" rather than a computed guess
- [ ] Restructure exemplar groups into the real named sets
- [ ] Per-family release history, verdicts only where actually tested

## Constraints that do not move

- No font binary is ever fetched, mirrored or hosted by our infrastructure —
  not even transiently in a build step. Google's coverage metadata is JSON, not
  a binary, and is fine.
- Never claim something the page cannot show.
- `same_family` merges on a known suffix only, never a shared prefix.
- Coverage is composition-aware.
- Script order comes from langtags' default marking, never alphabetical.
- `MLYM_NAMES` is 128 long, built by explicit range assignment.
- `cpMeta` tests `reserved` first.
- Comments say why, never what. British spelling in prose and identifiers.
