# Glyph Sleuth — build plan

*What we are building and in what order. `PROGRESS.md` tracks how far along it
is; this explains the reasoning behind the sequence. Where this and `HANDOFF.md`
disagree, this document is the later decision.*

## Context

The rebuild starts from a design prototype (`docs/prototype/`), five settled
feature addenda, a consolidating `HANDOFF.md`, and an archived first attempt on
`archive/pre-rebuild` that was desktop-first and shipped working code for both
halves.

The rebuild inverts that: **web first, desktop as a companion**. The web app is
a static site that never hosts a font binary. The companion is a local tool a
contributor runs against a font they already have; it emits a small stamped JSON
record as a pull request.

This plan salvages what the archive proved works, drops what the new scope
excludes, and sequences the build. The scope rule from the archive still decides
every future feature and is worth restating verbatim: **if it answers a question,
it's in; if it changes a file, it's out.**

**Method: test-driven.** Every non-trivial unit gets its failing test first —
`web/tests/test-core.mjs` for JS, plain-assert suites for the Python generator
and the companion. Red, green, refactor. The tests gate the deploy.

---

## Repository layout

```
.gitignore
.local/                 scratch, gitignored — never committed
docs/
  HANDOFF.md            the consolidating brief
  BUILD-PLAN.md         this document
  PROGRESS.md           the resumable checklist
  addenda/              the five settled feature specs
  chats/                original design transcript
  prototype/            the v2 spec bundle: README, PLAN, TODO, conventions, screenshots
  prototype-v1/         superseded first prototype, history only
site/                   the GitHub Pages publish directory
web/                    everything web: core.js, app.js, style.css, templates, build, tests
desktop/                the PySide6 companion
shared/                 Python Unicode + SLDR layer, used by both generator and companion
```

`web/` and `desktop/` never import each other. Their only contract is the JSON
record the companion exports and the generator consumes.

### The mockup, served now

`site/index.html` is the prototype `Glyph Sleuth.dc.html` with its `support.js`
beside it, published to GitHub Pages so the design is visible and linkable while
the real site is built. `docs/prototype/` keeps the spec markdown and screenshots
and points at `site/` rather than holding a second copy of the HTML — one file,
no drift.

When Phase 1 produces a real generated home page it takes `site/index.html`, and
the mockup moves to `site/mockup/` rather than being deleted; it stays the visual
reference the build is checked against.

---

## Settled architecture

**Static HTML, generated.** Pages are rendered to real HTML files at build time
so search engines can read them — not assembled in the browser from JSON. JS is
progressive enhancement on top of served markup, never the thing that produces
it.

This changes the prototype's routes: hash routes (`#/font/manjari`) become real
paths (`/font/manjari/`). Keep the URL *shapes* so the prototype's inter-page
links survive the translation.

**Three page classes, three treatments:**

| Class | Pages | Treatment |
| --- | --- | --- |
| Entity | script, font, font/shaping, char, block, lang, feature | Fully generated HTML, one file each |
| Index | `/scripts`, `/languages`, `/fonts` | Full list in HTML; JS adds filter/sort/show-more over the served rows |
| Tool | inspect, regex, identify, compare | One generated shell each + JS; inherently input-driven |

`/inspect/<text>` is the exception in its class — generate nothing, but keep the
URL readable and let JS render from the path segment.

**Stack:** HTML + CSS + vanilla JS, no framework, no bundler. Python renders the
pages. Keep the archive's split, which held up well:

- `core.js` — all logic, no DOM. Testable.
- `app.js` — all DOM, per-page enhancement.
- `style.css` — the specimen sheet.
- `web/tests/test-core.mjs` — the JS test file, and the deploy gate.

`.github/workflows/pages.yml` runs the generator, runs both test suites, and
publishes `site/`. Until Phase 1 lands it publishes the mockup unchanged.

**Data pipeline stays a build-time script** (`web/build/gen_index.py`, ported
from the archive's `gen_web_index.py`). Google publishes each family's coverage
as codepoint ranges at `fonts.google.com/metadata/fonts/<Family>`, so ~1,900
families are measured for the cost of small JSON fetches alone. Everything
deeper — OpenType script tags, lookup counts, axes, Graphite, shaping verdicts —
comes from parsing the release, per the policy below.

## The font-file policy

**Fetch and parse. Never host.**

`HANDOFF.md` §4 said no font binary may be *fetched* "even transiently in a
build pipeline". That is stricter than the brief it consolidates: `chat1.md` §10
forbids **hosting** ("no hosted fonts that cannot be freely licensed... never
edits, generates or hosts fonts") and forbids uploading what the visitor types,
but says nothing about a build step reading a public font. The stricter reading
came from a Claude Design sandbox limitation that
`addenda/addendum-desktop-companion.md` §1 itself calls "not a constraint on the
shipped product".

Built strictly, Manjari, Gayathri, Meera and RIT Rachana — the faces the whole
prototype is designed around — would read *not measured yet* indefinitely, and
tiers 2 and 3 would be unevidenced for every family including Google's, since
Google's metadata carries coverage and nothing else. The load-bearing
distinction is redistribution, not reading. So:

- CI may download a publicly released OFL/GPL+FE font, parse `cmap`, `GSUB`,
  `GPOS`, `fvar` and `silf` in memory, run HarfBuzz against it, and discard the
  binary. Redistribution carries the legal weight, and none happens.
- **Never host, mirror or serve a font file.** Specimens render from Google's
  CDN or the foundry's own stylesheet. Absolute, and the tests assert it.
- **Never commit a binary.** Downloads are CI-only, cached, gitignored.
- **Provenance on every computed fact** — source URL, release tag, checksum,
  date.
- **Pin releases and degrade gracefully.** A moved URL keeps the last good
  record and marks it stale; it never fails the build or drops a family in
  silence.

The visitor-facing promise is unchanged: nothing typed leaves the browser, no
uploads, no accounts.

GitHub Actions has Windows and macOS runners, so DirectWrite and CoreText
verdicts can come from CI too. That does not make the companion pointless — it
re-points it at the case CI genuinely cannot reach, which is also the higher-
value one for this audience: fonts that are not publicly downloadable at all
(unreleased, in development, proprietary, SIL-internal).

---

## Phase 1 — Generator and the ten built pages

Ported from `archive/pre-rebuild`:

- `web/build/gen_index.py` ← `scripts/gen_web_index.py`. Google metadata
  coverage, `SOURCES` (four host kinds), UDHR sample text, `script_index` /
  `script_blocks`, `scripts_for`, `disambiguate`, `write_blocks`, `write_names`.
- `web/core.js` ← the archive's `web/core.js`. Directly reusable: `covers`,
  `countIn`, `missingFrom`, `rankFonts`, `dominantBlock`, `scriptCoverage`,
  `blockOf`, `parse`, `hex`, `encodings`, `normalizationVariants`,
  `matchesProperty`, `validProperty`, `standin`.
- `shared/` ← `ucd.py`, `chars.py`, `langs.py`, `store.py` as-is; the Unicode
  and SLDR layer, scope-neutral.

Non-obvious rules to carry across, each of which cost real debugging once:

- `same_family` merges only on a **known suffix** (`Charis` / `Charis SIL`),
  never a shared prefix — `Meera` and `Meera Inimai` are different fonts.
- The exclusion list stays, with its reasons in comments: Last Resort (a
  placeholder box for every codepoint — would top every answer while answering
  nothing), STIX, Liberation, Source Han.
- Google's metadata JSON arrives behind an anti-hijacking guard, `)]}'`. Drop
  the strip and every family fetch fails with "Expecting value: line 1".
- Coverage is **composition-aware**: a precomposed character counts as present
  when the face has the pieces.
- Script ordering comes from langtags' default marking (the bare tag carries its
  script), never alphabetical — that bug opened Malayalam on Arabic.
- `\p{…}` membership asks the regex engine itself, so every property label shown
  is paste-able into real code. The test asserts the round trip.
- `MLYM_NAMES` stays 128 long, built by explicit range assignment.
- `cpMeta` tests `reserved` **first**, so unassigned points never classify as
  marks.

### Phase 1a — restore measurement under the corrected policy

The data layer landed while the strict no-fetch rule was still in force, so the
measuring half needs putting back:

- Re-add the archive's release-reading path — `archive()`, `extract_fonts`,
  `pick_faces` — but **parsing only**: `cmap` for coverage, `GSUB`/`GPOS` for
  script tags and lookup counts, `fvar` for axes, `silf` for Graphite. No woff2
  is emitted, no `OUT_FONTS`, no `prune_fonts`; the binary is discarded after
  parsing. `fontTools` returns as a dependency.
- Add HarfBuzz shaping in CI (`uharfbuzz`) against the shared `SEQUENCES` list,
  filling the `hb` column for real. Windows and macOS runners fill `dw` and `ct`
  later; the matrix's three treatments already cover what is still untested.
- Every record carries provenance: source URL, release tag, file checksum, date.
- `tier` becomes real: `measured` where we computed it, `stub` where the family
  is indexed but nothing has been read yet.
- **Rewrite `test_no_font_is_ever_downloaded`.** It asserts the strict rule by
  banning `fontTools`, `woff2` and `zipfile` from the generator source. It must
  instead assert what actually matters, and take the matching name —
  `test_no_font_is_ever_served`: no font file in the site output, no binary
  committed, no page or snippet pointing at a font URL of ours.

Then render the ten page types faithfully from `docs/prototype/`, fixing the
known gaps in `HANDOFF.md` §6 as we go:

- CSS "Use it" snippet: Google → foundry's own hosted CSS → honest "not served
  from a public CDN, download and self-host" with a `@font-face` template. Never
  fabricate a working `@import`. *(Done in `core.js` as `useIt()`.)*
- Wire home's "Only have a picture of it" to `/identify/`.
- Encode size-slider and sample-word state in the URL, as Compare does.
- Do not port `collapseData` — dead code for a bar that was removed.
- Replace the prototype's authored placeholders with computed values and delete
  the placeholders: the 1,885 total, the 61/34/19 counts, script-index family
  counts, `INDEX_FONTS` verdicts.

Design tokens, type scale and copy are final — take them from the prototype
exactly.

## Phase 2 — Compare, Identify, shaping matrix

Per the settled specs, with `HANDOFF.md` winning over the bundle README where
they disagree:

- **Compare** — 14 rows, agree/differ computed per row, no score, no guessed
  default pair (the README's `manjari,gayathri` default is overridden). All four
  state values in the URL.
- **Identify** — atlas built only after `document.fonts.load('256px Manjari')`
  and `fonts.ready`; 256px render → ink-bbox crop → 24×24 binary;
  `IoU − 0.15 × centroidDistance`. Marks get a U+25CC base and the page says so.
  Never a single "detected" answer.
- **Matrix** — `{hb, dw, ct, gr}` with three distinct treatments (verdict /
  literal `not tested` / `not applicable`), `graphite` on `SHAPING` entries
  driving the `gr` column, and the required legend. The engine strip goes in the
  filter-chips row — the collapse bar no longer exists.

## Phase 3 — Salvaged TODOs

All four archive backlog items, in ascending cost:

1. **Alt+X** — swap codepoint and character in the search field and Inspect.
   `core.parse` and `core.hex` already do the work; this is a `keydown` handler.
   Additive only, never the sole route — Alt+X is not reserved on all platforms
   and screen readers may claim it.
2. **Print stylesheet** — `@media print`: hide chrome, keep specimens and
   evidence tables, force light colours, break cleanly. The browser's own Save
   as PDF does the rest. No font embedding, so no licensing question.
3. **Copy glyph + tray** — click-to-copy on block-chart cells and specimen
   tiles, plus a tray that collects a set and feeds it to Inspect as the sample
   text. Copy must be a second explicit affordance so clicking still navigates.
4. **Markdown preview editor** — a plain textarea rendered as Markdown into the
   specimen, so a family can be judged across headings, weights and sizes rather
   than one size in one style. Needs per-family weight data, which the index now
   records as `faces` from Google's metadata.

## Phase 4 — Desktop companion (PySide6)

Only once the web data shapes are locked. Reuses the archive's desktop patterns
(`app.py`'s window, `index.py`'s per-file cached cmap scan, fontTools) and
shares the parsing and shaping code with the generator rather than
reimplementing it — one definition of what "clean / caveat / fail" means.

Its purpose narrows now CI can measure anything public: the companion is for
fonts CI **cannot** reach — unreleased, in development, proprietary, or
SIL-internal. A contributor points it at a font they already legitimately have
and it exports a checksum- and version-stamped JSON record for the "Add a
family" pull-request flow. Never the font itself. That is the more valuable tool
for this audience anyway.

One testing lesson to carry: `test_app.py` waits on conditions rather than
calling the app's own slots. Faking completion lets the queued signal arrive
later and undo the next step — that is the bug it was written after.

## Phase 5 — Provenance and version history

Blocked on data decisions, not code. Cite SLDR file and revision, carry the
validity level (approved / contributed / provisional / unconfirmed), restructure
display groups into the real named sets (main, auxiliary, index, punctuation,
numbers) and state which the fit verdict was computed over. Release lists are
cheap (tags, `FONTLOG.md`); per-release verdicts are expensive, so show verdicts
only for releases actually tested and mark the rest untested.

---

## Conventions

Carried from the archive, all of them deliberate:

- Comments say *why*, never *what*. Several exist only to stop a future reader
  "fixing" a deliberate choice.
- British spelling in prose and identifiers (`licence`, `colour`).
- Tests assert the non-obvious, not the trivial.
- Every commit message explains the reasoning.
- Voice: matter-of-fact. Never claim something the page cannot show.
- Derived data is gitignored and rebuilt by CI. Without the generator the site
  shows an error — correct behaviour, not a bug.

## Verification

- `node web/tests/test-core.mjs` — the deploy gate. Asserts the salvaged
  non-obvious rules explicitly: composition-aware coverage, the DejaVu case in
  `dominantBlock`, why a prefix match is not a family match, the `\p{…}` round
  trip.
- `python shared/test_core.py` and `python web/build/test_gen.py`.
- `python web/build/gen_index.py --limit 60`, then serve the output directory —
  confirm generated pages are real HTML with content in the served source (view
  source, not devtools), and that every page works with JS disabled except the
  four tool pages.
- Spot-check the claims the site makes: Malayalam offers `Mlym, Arab, Brai` and
  opens on Malayalam; Hindi opens on Devanagari; the Tamil Supplement coverage
  number is computed, not authored.
- Confirm no font binary is **served or committed**: the site output tree
  contains no font files, `git status` is clean of binaries after a build, and
  no "Use it" snippet or specimen points at a URL of ours. Fetching and parsing
  in CI is expected and fine.
- Confirm every computed number carries its provenance, and that a family whose
  release URL has moved shows as stale rather than vanishing or failing the
  build.
- Compare against `docs/prototype/screenshots/` for visual fidelity.