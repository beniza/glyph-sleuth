# Glyph Sleuth — implementation handoff

*Consolidated brief for whoever (or whichever session) implements this. Read this document
top to bottom before opening any other file — it tells you what's here, what's settled, and
what's still genuinely open. Where this document and an individual addendum disagree, this
document wins; it's the final consolidation.*

---

## 1 · What this is

**Glyph Sleuth** is a read-only inspector for Unicode characters, fonts, scripts and
languages, for script engineers first (developers, font designers, typesetters, and curious
readers, in that priority order — see `chats/chat1.md` for the full original brief). Its
argument in one sentence: **coverage says a font contains a character; it does not say the
font will draw it correctly.** Every claim the app makes carries the evidence behind it —
three tiers, not one: does the font *cover* the codepoints, does it *declare* the right
OpenType script tag, does it *shape* the script's exemplar sequences cleanly.

It is a **static site** — no accounts, no server, nothing uploaded, and (settled this
round) **it never hosts or serves font binaries itself.** Visitors' browsers load fonts
from wherever the family is actually distributed (Google Fonts, a foundry's own CDN); real
computed facts (coverage, tags, shaping verdicts) come from a separate desktop companion
tool, not from Glyph Sleuth's own infrastructure touching font files. See §4.

**Malayalam is the flagship script, not the only one.** It's built to full depth because
the brief was written against it; the architecture (tiered scope, the contribution
pipeline, the desktop companion) is explicitly designed to extend to other scripts over
time. Several features below are deliberately scoped to "this script only, for now" — that
is a sequencing decision for those specific features, not a statement that the product ends
at Malayalam.

## 2 · Current state — what's built, where to look

The **prototype is the visual source of truth.** It's a Claude Design export (`.dc.html`,
a single-file template format — do not port its runtime, `support.js`; recreate the visual
design faithfully in whatever the target codebase actually uses). Colours, typography,
spacing and copy in it are final; only some of its *data* is an authored placeholder
(flagged below).

There are **two versions of the prototype in this repo** — use the newer one:

- `docs/prototype-v1/` — **superseded.** The original
  4-page build (Home, Script, Font, Character). Keep for history only.
- `site/index.html` (+ `site/support.js`), specced by `docs/prototype/` — **current.** Ten built
  page types: Home, Script, Font family, Font shaping tables (`/font/<id>/shaping`),
  Character, Block, Language, Feature, Inspect (`/inspect/<text>`), Regex. Plus index pages
  (`/scripts`, `/languages`, `/fonts`). This bundle's own `README.md`, `PLAN.md`, `TODO.md`
  and `conventions.md` are still authoritative for anything this document doesn't override
  — carry all of it (including `screenshots/`) into the implementation, not just the
  `.dc.html`.

Three features were specified in that bundle but **not yet built** in the prototype:
Compare, Identify, and the shaping-engine matrix. All three are now fully settled — see §3.

## 3 · Settled feature specs

Each of these was an open design conversation this round; each is now closed. Full detail
in the named file — read the base spec in the bundle's `README.md` first, then the
addendum for what was resolved on top of it.

- **Compare** (`addendum-compare-final.md`) — two families side by side, differences
  emphasized, never a score. Single-script for now. Any two of the indexed families are
  comparable; missing data states so plainly rather than being hidden. Nested rows (coverage
  by block, per-language fit) count as one row each toward the headline "N of 14 differ,"
  with sub-fact highlighting still visible inside them. All four state values (`a`, `b`,
  `size`, `diffOnly`) encode in the URL. No guessed default family pair anywhere — every
  entry point pre-fills only what it actually knows and leaves the rest an open picker with
  a plain prompt.

- **Identify** (`addendum-identify-final.md`) — draw-or-drop shape matching against real
  glyph outlines, explicitly *not* handwriting recognition, and the page says so. Web app
  scope follows the active script and uses one fixed reference face (Manjari) for now; the
  desktop companion is where cross-script and multi-face matching eventually belongs, not
  the web app. Weak results get their own honest state ("No strong matches...") rather than
  a silently padded ranked list. Explicit copy reassures that a dropped image never leaves
  the device.

- **Shaping-engine matrix** (`addendum-matrix-final.md`) — widens every verdict from
  HarfBuzz-only to `{hb, dw, ct, gr}`. DirectWrite/CoreText verdicts come from the desktop
  companion (run on Windows/macOS respectively), not a separate process. The per-script
  engine-coverage strip lives in the filter-chips row (the script page's old "collapse bar"
  no longer exists — it was removed earlier in the design and its leftover `collapseData`
  is dead code to delete). Site-wide badges stay HarfBuzz-defined for now; the matrix is an
  added transparency layer, not a change to what "clean/caveat/fail" means, until real
  cross-engine data is common enough to revisit that.

- **Phase 4 — exemplar provenance & version history** (`PLAN.md` in the bundle, decisions
  below) — pin an SLDR revision and re-verify it periodically rather than always tracking
  latest. Show "not tested" plainly wherever SLDR marks a set unconfirmed, rather than
  computing a verdict against untrustworthy data. Per-family version history goes back
  through all releases if that's cheap to produce; falls back to a defined baseline cutoff
  only if it isn't.

## 4 · Desktop companion — spec drafted, deliberately not built yet

Full spec in `addendum-desktop-companion.md`. It's a **local tool**, not a second web
front-end: a contributor points it at a font file they already legitimately have, it parses
`cmap`/`GSUB`/`GPOS`/`fvar`/`silf` locally and runs HarfBuzz (plus DirectWrite on Windows,
CoreText on macOS) locally, and emits a small, checksum-and-version-stamped JSON record —
never the font itself — as a contribution against the same metadata-file pull-request flow
the web app's "Add a family" already describes.

**Why it's a TODO, not a build item:** its export schema has to match the web app's real
data shapes (`FAMILIES`/`FONT_DETAIL`/`SHAPING`), which were still moving as of this
handoff (the matrix alone adds a `graphite` field). Build the web app's remaining pieces
first; spec the companion's exporter against the settled schema once it exists, not before.

This is also the resolution to a constraint that must not be relaxed during implementation:
**no font binary should ever be fetched, mirrored, or hosted by Glyph Sleuth's own
infrastructure**, even transiently in a build pipeline. Real computed numbers come from the
companion running on a contributor's own machine, or they don't exist yet and the page says
so — never from Glyph Sleuth reaching out to fetch a font itself.

## 5 · Scope and content-growth philosophy

Full detail in `addendum-community-issues.md`. The short version: don't wait for every
script (or every pitfall for a given script) to be fully documented before shipping it.
Three honest tiers, stated as a fact on the page itself — **grounded** (sourced, verified
pitfalls and shaping verdicts, Malayalam's chillu/ṉṯa write-ups being the model), **measured**
(automatable tiers 1–2, mechanical-only tier 3, no editorial pitfalls yet — say so), and
**stub** (recognized, indexed, nothing more yet). A "Report an issue" affordance (sibling to
the existing "Add a family" contribute flow) lets community reports feed the same
research-verification pipeline that produced the grounded content, with unverified
submissions visually and textually distinct from sourced facts — never blended in as
equals.

Also folded in here: **ScriptSource is retiring** (closes end of September 2026); its
successor, **Writing Systems Technical Resources** (writingsystems.info), is already
`conventions.md`'s second-priority external-reading source, after r12a.io and before
Wikipedia, per the one-external-link-per-page rule already in that file. Nothing further to
decide there.

## 6 · Known implementation gaps to fix while building (not new design decisions)

These were flagged during review and don't need further design conversation — just don't
lose them in the handoff:

- The font page's CSS "Use it" snippet currently always assumes a Google Fonts `@import`.
  Per the settled decision, implement the priority fallback instead: Google Fonts (if
  actually distributed there) → the foundry's own hosted webfont CSS (e.g. SMC's
  `smc.org.in/fonts/manjari.css`) → a CDN mirror of the source repo's built binaries, if one
  genuinely exists → an honest "not served from a public CDN — download and self-host"
  state with a `@font-face` template. Never fabricate a working `@import` for a family that
  doesn't have one.
- The home page's "Only have a picture of it" text is still an inert promise, not a link —
  it should point to `#/identify` once that page exists.
- General script/font page permalinks (the size slider, sample-word selection) still don't
  encode into the URL, unlike Compare's now-settled all-four-state-in-URL rule. Worth
  extending the same treatment there rather than leaving Compare as the only page where
  "send someone proof" actually works.
- `collapseData` in the prototype's script-page logic is dead code (defined, never
  rendered) — the visual "collapse" bar it was for was removed earlier in the design.
  Don't port it.
- One question from the original font-page review was never explicitly re-settled after the
  updated bundle arrived: whether the font page's "Declares"/"Implements" sections should
  adopt the verb-first relation styling used on the character and script pages, or keep
  their own font-specific grouping. The bundle shipped without changing this, which reads as
  an implicit "keep as is" — flagging so it's a conscious choice if revisited, not an
  oversight.

## 7 · Build order

1. Recreate the ten already-built page types faithfully from the current `.dc.html` bundle,
   fixing the known gaps in §6 as you go (don't carry forward the dead code or the
   contextually-wrong hardcoded links).
2. Build Compare, Identify, and the shaping matrix against their final specs (§3).
3. Desktop companion — only once the above data shapes are locked in (§4).
4. Phase 4 provenance/version-history work, whenever real SLDR revisions and release lists
   are in hand.

## 8 · File manifest

| File | What it is |
| --- | --- |
| `docs/chats/chat1.md` | Original design brief + full iteration transcript with the design assistant |
| `docs/prototype-v1/` | Superseded first prototype — history only |
| `docs/prototype/` | Current prototype's spec docs: `README.md`, `PLAN.md`, `TODO.md`, `conventions.md`, `screenshots/` — carry all of it |
| `site/index.html`, `site/support.js` | The current prototype itself, served as the mockup |
| `docs/addenda/addendum-community-issues.md` | Scope tiering + community issue reporting + ScriptSource/writingsystems.info |
| `docs/addenda/addendum-desktop-companion.md` | Desktop companion spec, including the matrix's DW/CT extension |
| `docs/addenda/addendum-compare-final.md` | Compare — final settled spec |
| `docs/addenda/addendum-identify-final.md` | Identify — final settled spec |
| `docs/addenda/addendum-matrix-final.md` | Shaping-engine matrix — final settled spec |
| `docs/HANDOFF.md` | This document |
| `docs/PROGRESS.md` | The resumable build checklist — start here to pick the work back up |
