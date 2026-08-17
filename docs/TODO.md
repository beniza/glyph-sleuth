# TODO

Everything identified and not yet done. `PROGRESS.md` tracks the phase plan;
this is the list of *known problems and deferred ideas*, including the ones
found by building something else. Ordered by what hurts most.

Each item says what is wrong and why it matters, so a future session can
judge it rather than re-derive it. The scope rule still decides: **if it
answers a question, it's in; if it changes a file, it's out.**

---

## 1 · Live bugs — links that go nowhere

The site links to ten routes that 404 today. Every one is a real dead end a
reader will hit, and several are in the nav on every page.

- [ ] `/scripts/`, `/languages/` — in the nav on every page
- [ ] `/inspect/`, `/regex/`, `/identify/` — in the nav on every page, and
      home's three entry questions point at `/inspect/` and `/identify/`
- [ ] `/script/<code>/`, `/lang/<id>/` — home's index section links these
- [ ] `/feature/<tag>/` — the font page's Implements chips, every lookups-page
      feature heading, and every trace step links here. This is the most-linked
      missing page on the site
- [ ] `/char/<hex>/` — every encoded glyph on a glyphs page links here
- [ ] `/block/<slug>/` — the font page's dominant-block fact links here

**Until they exist, the honest options are to build them or stop emitting the
links.** Emitting a link that 404s is the interface making a promise the site
does not keep, which is the failure mode this project is otherwise careful
about. Build order that clears the most dead links per page: feature → char →
block → script → lang, then the three tool pages.

## 2 · Silent truncation and unpinned inputs

Both are cases where the site could be quietly wrong rather than visibly
incomplete, which is worse.

- [ ] **Glyph inventory caps at 4,000 glyphs and says nothing.** A CJK face has
      tens of thousands. The page must state what it dropped, or a reader will
      read the list as complete. Every other cap on the site is disclosed
- [ ] **Releases are not pinned.** The font policy promises "pin releases and
      degrade gracefully: a moved URL keeps the last good record and marks it
      stale." Neither half exists — a moved URL currently just becomes a stub
      with a printed warning, and the previous good measurement is lost
- [ ] **Nothing is cached between builds.** Every run re-downloads every
      release, which is rude to small foundries and is most of the 10-minute
      build. An HTTP cache keyed on the release tag would remove nearly all of it

## 3 · Claims we cannot fully stand behind yet

- [ ] **The `out` comparison can produce a false caveat.** Two different glyph
      ids can draw the same shape, so a differing glyph run is not proof of a
      fault. The note says so, but the verdict still reads "caveat". A stronger
      check would compare advance widths and mark positions, or rasterise both
      runs and compare ink
- [ ] **`dw` and `ct` are empty everywhere.** GitHub Actions has Windows and
      macOS runners, so these can be filled from CI rather than waiting for the
      desktop companion. Until then every matrix has two "not tested" columns
- [ ] **Graphite is detected, never run.** `silf` presence gives "not
      applicable" honestly, but a font that *has* Graphite tables gets no
      verdict. SIL's own families are the ones that carry them
- [ ] **Most Google families have no tags or lookups.** Only families reaching a
      script we have sequences for get their file opened, so ~1,840 families
      show "not read" for tier 2. Widening the gate is a cost/coverage
      trade-off, not a bug — but it should be a decision, not an accident
- [ ] **Foundry licences are unread.** The release ships `OFL.txt`; we show an em
      dash. Reading it is a few lines and removes a visible blank

## 4 · Depth that only exists for two scripts

- [ ] Sequences exist for Malayalam and Devanagari only. Adding a script is a
      `sequences.json` entry plus a line in `SHAPED_SCRIPTS` — the next most
      useful are Arabic (nine blocks, positional forms), Tamil, Bengali,
      Sinhala, Khmer, Myanmar
- [ ] Devanagari's seven sequences are a first pass and want review by someone
      who reads the script. My i-matra entry was in visual order and the shaper
      correctly rejected it; there may be more of that
- [ ] No sequence covers a *language-specific* difference within one script yet,
      beyond the Marathi eyelash ra. That is where fonts most often fail

## 5 · Compare, the rest of the settled spec

The lookup-level diff is done. `addenda/addendum-compare-final.md` asks for
more:

- [ ] Coverage by block, as nested rows counting as one row toward the headline
- [ ] Per-language fit rows
- [ ] Specimen row, both families at one shared size
- [ ] The `hb-shape` line per family per sequence
- [ ] Source repository row
- [ ] `diffOnly` toggle and `size` in the URL — currently only `a` and `b` are

## 6 · Trace, next steps

- [ ] GPOS steps are invisible. The trace shows glyph-run changes, so mark
      attachment and kerning — which change positions, not glyphs — never
      appear. A position column would show them
- [ ] No way to trace *arbitrary* text, only the authored sequences. A "trace
      this" field on the font page would make it a tool rather than a report

## 7 · Home, still unfinished

- [ ] The worked verdict section — one sequence, three families, from real data.
      It was deferred until font pages existed. They exist now
- [ ] The query examples that fill the search field. Waiting on Inspect
- [ ] There is no search field in the masthead at all yet, which the prototype
      has on every page

## 8 · Presentation and platform

- [ ] **No mobile verification.** The brief requires 380px to work. Nothing has
      been checked at that width, and the evidence matrix is the obvious risk
- [ ] **No accessibility pass.** Focus styles and one h1 per page are in;
      unaudited are table captions, the facet buttons' pressed state, the size
      slider's announced value, and colour contrast on `--faint` text
- [ ] **1,885 rows ship in one page** on `/fonts/`. No show-more, no
      pagination. Fine on a desktop, unmeasured on a phone
- [ ] **Print stylesheet is three rules.** The archive TODO wanted a real
      specimen sheet you could save as PDF
- [ ] **No sitemap.xml and no robots.txt.** Generating static HTML for search
      engines and then not listing the pages is half the job
- [ ] The mockup at `/mockup/` is the old prototype and will drift further from
      the real site with every change. Worth a note on it saying so

## 9 · Carried from the archive backlog

- [ ] Alt+X to swap codepoint and character
- [ ] Click-to-copy a glyph, and a tray that collects a set
- [ ] Markdown preview editor for the specimen

## 10 · Later phases, unchanged

- [ ] Identify — draw or drop, shape matching in the browser
- [ ] The shaping-engine matrix's remaining work is (3) above
- [ ] Desktop companion (PySide6), for fonts CI cannot reach
- [ ] Provenance and version history: SLDR revisions and validity levels,
      per-release coverage and verdicts. Google's Manjari is v14 with 44 GSUB
      lookups where SMC's own release is v2.200 with 48 — that difference is
      what this phase exists to explain

---

## Not doing, and why

- **Hosting font files.** Settled: fetch and parse, never host.
- **Publishing glyph outlines as SVG.** It would let unencoded glyphs be drawn
  without a webfont, but shipping the outlines of every glyph is redistributing
  the font in another format. The current approach — letting the browser shape
  the input — shows the same glyph and hosts nothing.
- **A score, or a ranking, in Compare.** Two families with identical rows still
  differ in ways the table cannot see.
