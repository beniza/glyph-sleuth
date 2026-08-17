# Progress

The resumable checklist. `HANDOFF.md` says what we're building and why,
`BUILD-PLAN.md` says in what order and on what reasoning; this says how far we've
got. Tick items as they land, and keep the notes under a phase
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
- [x] Pages live at <https://beniza.github.io/glyph-sleuth/> (was already set to
      build from Actions, so `pages.yml` just took over)

## Phase 1 — Generator and the ten built pages

Ported from `archive/pre-rebuild`, with the font-hosting path removed.

- [x] `shared/` — `ucd.py`, `chars.py`, `langs.py`, `store.py` as-is (7 tests)
- [x] `web/build/gen_index.py` ← `scripts/gen_web_index.py`, minus the whole
      font-downloading half (9 tests). Non-Google foundries are indexed as
      `tier: "stub"` with no ranges until the companion measures them
- [x] `web/core.js` ← the archive's, logic only, no DOM (17 tests), with
      `useIt()` replacing `embed()` and one further-reading link per page

### Phase 1a — restore measurement under the corrected font policy

The data layer above landed while `HANDOFF.md` §4's stricter "never fetch a font
even in CI" rule was still in force. That rule turned out to be stricter than the
brief it consolidates, and it would have left the flagship Malayalam faces
permanently unmeasured and tiers 2–3 unevidenced for every family. Corrected to
**fetch and parse, never host** — see `BUILD-PLAN.md`.

- [x] Restore the release-reading path in `gen_index.py`, parsing only: `cmap`
      for coverage, `GSUB`/`GPOS` for tags and lookup counts, `fvar` for axes,
      `silf` for Graphite. Nothing written, binary discarded after parsing
- [x] Provenance on every computed fact: file, release/stylesheet, checksum, date
- [x] A family whose release cannot be read degrades to a stub with a printed
      reason, rather than failing the build or vanishing
- [x] `test_no_font_is_ever_downloaded` → `test_no_font_is_ever_served`
- [x] HarfBuzz in CI (`uharfbuzz`) against the authored sequence list, now
      `web/content/sequences.json` and shared with the companion
- [x] Shape Google's families too — its metadata stops at coverage, and Google
      carries the flagship Malayalam faces, so those pages had no tags and no
      verdicts. Only families reaching a script we have sequences for get
      opened, which is tens of files rather than 1,900
- [x] Correct the same drift in `HANDOFF.md` §4 and `README.md`

### Phase 1b — the pages

- [x] Static HTML rendering (`web/build/render.py`, 6 tests): page shell,
      real paths instead of hash routes, `web/style.css` from the prototype's
      final tokens. CI runs generator → renderer → deploy, tests gating
- [x] The mockup moves to `/mockup/`; `/` is now a generated page
- [x] Home — the claim, what is indexed vs what is measured, the three entry
      questions, index links. Still to add once their pages exist: the worked
      verdict, and the query examples that fill the search field
- [ ] Script page — engine strip in the filter-chips row, no collapse bar
- [x] Font family page — laid out as the prototype does it: name and size
      control, byline, specimen, linked facts strip, then three columns —
      coverage and Declares, the evidence matrix, Use it / Implements / weights
- [ ] "The face" prose section — the prototype carries an authored paragraph
      per family; we have none, so the section is omitted rather than faked
- [ ] Licence for foundry families: the release carries OFL.txt but we do not
      read it yet, so those pages show an em dash
- [x] Lookups page (`/font/<id>/lookups/`) — every lookup a feature runs, its
      type, rule count and sample rules, shown in the script with the glyph
      names beside them. Renamed from "shaping": shaping is the engine's job and
      a script engineer cannot change it; lookups are what they write
- [x] Glyphs page (`/font/<id>/glyphs/`) — every glyph, encoded or built by a
      rule, which features produce and consume it, and which are reachable by
      nothing at all
- [x] Devanagari as a second shaped script; expected output now verified by
      shaping the expected form and comparing glyph runs
- [ ] GPOS anchor diagrams on the shaping page — the prototype draws mark
      attachment; we currently report attachment counts only
- [ ] Font shaping tables
- [ ] Character page
- [ ] Block page
- [ ] Language page
- [ ] Feature page
- [ ] Inspect
- [ ] Regex
- [x] Index page `/fonts/` — every family in the markup; filter by name, by
      declared OpenType script tag, by Unicode block covered; facets for
      measured/unmeasured and shaping; sort by name, verdict or coverage
- [x] No script is the site's default lens — the font page measures each face
      against its own dominant block, and the specimen is set in that script
- [ ] Index pages: `/scripts/`, `/languages/`

Known gaps to fix while building (`HANDOFF.md` §6), not new design work:

- [x] CSS snippet: Google → foundry's own CSS → honest self-host state
- [ ] Home's "Only have a picture of it" links to `/identify/`
- [ ] Size slider and sample-word state encode into the URL
- [ ] `collapseData` not ported — dead code
- [ ] Authored placeholders replaced with computed values and deleted

## Phase 2 — Compare, Identify, shaping matrix

- [x] Compare, at lookup level — features declared, rules and lookups per
      feature, and per-sequence verdicts. A shell plus one small JSON per
      family, because 1,878 measured families are 1.7 million pairs
- [x] Trace — every step where a lookup changed the glyph run, folded into the
      evidence row. A verdict is a claim; the trace is the demonstration
- [ ] Compare — the remaining rows from the settled spec (coverage by block,
      per-language fit, specimen at a shared size)
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

- **Fetch and parse, never host.** CI may download a public OFL/GPL+FE release,
  parse it in memory and discard it. It may never host, mirror, serve or commit
  a font file, and no page or snippet may point at a font URL of ours.
- Nothing the visitor types leaves the browser. No uploads, no accounts.
- Never claim something the page cannot show.
- `same_family` merges on a known suffix only, never a shared prefix.
- Coverage is composition-aware.
- Script order comes from langtags' default marking, never alphabetical.
- `MLYM_NAMES` is 128 long, built by explicit range assignment.
- `cpMeta` tests `reserved` first.
- Comments say why, never what. British spelling in prose and identifiers.
