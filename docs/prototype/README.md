# Handoff: Glyph Sleuth — Compare, Identify, and the shaping-engine matrix

## Overview

Glyph Sleuth is a Unicode character and font inspector for script engineers, font designers and
developers. Its argument is one sentence: **coverage says a font contains the character, it does not
say the font will draw it correctly** — so every claim the app makes carries the evidence behind it.

The existing prototype covers ten page types (listed under **Existing pages**). This handoff
specifies **three unbuilt features**, in priority order:

1. **Compare** — two font families side by side, differences emphasised.
2. **Identify** — draw a character or drop an image of one, get ranked candidates by real shape
   similarity computed in the browser.
3. **Shaping-engine matrix** — widen every verdict from one shaper to four.

A fourth item (exemplar provenance and per-release version history) is specified as background in
`PLAN.md` but is **not ready to build** — it needs data decisions from the product owner first.

## About the design files

The files in this bundle are **design references created in HTML**. They are prototypes showing
intended look and behaviour, not production code to copy. `Glyph Sleuth.dc.html` is a single-file
prototype using a small in-house template runtime (`support.js`); do not port that runtime.

The task is to **recreate these designs in the target codebase's existing environment** — React, Vue,
Svelte, SwiftUI, whatever is already there — using its established patterns, router and component
library. If no environment exists yet, choose one appropriate to the project and implement there.

Read the prototype for exact type scale, spacing, colour and copy. Read this README for behaviour,
data shapes and the reasoning behind each decision.

## Fidelity

**High fidelity.** Colours, typography, spacing and copy are final. Recreate the UI faithfully using
the codebase's own primitives. The one thing that is deliberately provisional is *data*: several
numbers in the prototype are authored placeholders, and the README marks which.

## Design tokens

### Colour

| Token | Hex | Use |
| --- | --- | --- |
| Bone | `#E9EBE7` | Page background |
| Panel | `#F5F6F3` | Inset panels, inputs, specimen wells |
| Rule | `#CBCFC8` | Every hairline border and divider |
| Ink | `#16181D` | Primary text, active chip fill |
| Muted | `#6E736C` | Secondary text, labels, data |
| Faint | `#9AA096` | Disabled and unlinked entities |
| Proof blue | `#1F4FD8` | Links, passing verdicts, active accents |
| Alarm red | `#A81E12` | Failing verdicts, caveats, warnings |
| Caveat grey-violet | `#B9C0D8` | The middle band of the collapse bar |
| Hatch | `#DCDFD8` | Reserved codepoint hatching (135° 4px stripes) |

Tints in use: `rgba(31,79,216,.06–.16)` for passing panels and match highlights,
`rgba(168,30,18,.07)` for failing badges.

### Type

- **Body** — IBM Plex Sans. 15–16.5px, line-height 1.6, `text-wrap: pretty`, max-width 62–70ch.
- **Eyebrows and section heads** — IBM Plex Sans Condensed 600, 10.5–11px, uppercase,
  letter-spacing .13–.16em, muted.
- **Data** — IBM Plex Mono, 10.5–13px. All codepoints, counts, tags, offsets, commands.
- **Page titles** — 40px, weight 500, letter-spacing −.02em. Home's claim line is 35px/1.22/−.018em.
- **Facts strip** — mono value 15–17px above a 10.5px uppercase condensed label.
- **Malayalam specimens** — Manjari (reference face), Gayathri, Chilanka, Noto Sans Malayalam,
  Noto Serif Malayalam, Anek Malayalam. Loaded from Google Fonts.

### Geometry

- Border radius: **2px** on inputs, buttons and chips. **0 everywhere else.** No rounded cards.
- Borders: 1px `#CBCFC8`. Section heads sit above a 1px `#16181D` rule; row dividers use Rule.
- No shadows, except `box-shadow: 0 2px 0 #1F4FD8` under a regex match highlight.
- Content column: `max-width: 1180px`, `padding: 0 20px`.
- Section rhythm: 34px top padding for page sections, 44–56px between major home sections.
- Multi-column sections: `repeat(auto-fit, minmax(300px, 1fr))` with `gap: 30px 44px`.
  **Always set a row gap** — wrapped columns collide without one.

### Voice

Matter-of-fact, no marketing register. Never claim something the page cannot show — several rounds of
review on this prototype were spent removing exactly that. Where a demonstration is impossible
(browsers apply Indic mark attachment even with `mark`/`mkmk` disabled), the page says so plainly
instead of faking a comparison. Preserve this. It is the product's credibility.

---

## Existing pages, for context

All routes are hash-based: `#/<kind>/<id>`.

| Route | What it is |
| --- | --- |
| `#/` | Home: claim, three entry questions, query examples, a worked verdict, full index |
| `#/script/Mlym` | Script page: collapse bar, filterable specimen list, languages, features |
| `#/font/<id>` | Font family: coverage by block, script tags, per-language verdicts, evidence table, CSS, weights |
| `#/font/<id>/shaping` | GSUB/GPOS lookup tables with anchor diagrams |
| `#/char/<hex>` | Character: properties, sequences, relations, similar characters, specimen grid |
| `#/block/malayalam` | 8×16 code chart, version history of the block, coverage |
| `#/lang/<tag>` | Language: exemplar set, deciding sequences, families that fit |
| `#/feature/<tag>` | OpenType feature: pipeline position, examples, implementers |
| `#/inspect/<text>` | Text inspector: clusters, codepoints, normalisation, encodings |
| `#/regex` | Property reference, four-engine syntax comparison, live tester, recipes |
| `#/languages` `#/scripts` `#/fonts` | Index pages with filter, sort, search, show-more |

Persistent nav sits above the trail: Home · Scripts · Languages · Fonts · Inspect · Regex.
**Add Identify and Compare to it.**

### Data shapes already in the prototype

Ported as-is, these are your inputs. All live in `Glyph Sleuth.dc.html`.

- `FAMILIES` — `{id, name, face, foundry, licence, covers, tag, shapes: 'clean'|'caveat'|'fail', note, also}`
- `FONT_DETAIL[id]` — `{designer, about, source, coverage[], features[], tags[], weights[], axes?, results{}, typography, byline}`
- `SHAPING[id]` — `{version, tags, gsubN, gposN, featN, drop?[], warn?}`
- `SHAPE_BASE` — `{gsub[{feat, type, flag, n, note, rules[{in, out}]}], gpos[{feat, type, n, note, samples[]}]}`
- `SEQUENCES` — `{id, codes, needs[], langs, out}`
- `LANG_DETAIL[tag]`, `CHARS[hex]`, `BLOCK`, `FEATURE_DETAIL[tag]`, `SOURCE_REPO[id]`
- `MLYM_NAMES` — 128-slot array of real Unicode names for U+0D00–0D7F, empty at the ten reserved
  points. Built by explicit range assignment, **not** a positional string — an earlier positional
  version silently shifted 40 names by one. Keep the assertion that its length is 128.
- Helpers: `cpMeta(cp)`, `cpName(cp)`, `clusterFeatures(cps)`, `segmentClusters(text)`,
  `charRecord(hex)`, `isMlymCons`, `isMlymMark`, `isCombiningCp`

`cpMeta` returns `{hex, key, name, cat, script, block, combining, invisible, reserved, glyphText,
token}`. It tests `reserved` **first**, so unassigned points are never classified as marks. Preserve
that ordering.

---

# Feature 1 — Compare

**Route:** `#/compare/<idA>,<idB>` — already linked from every font page's "Use it" block, currently
landing on a placeholder. Default to `manjari,gayathri` when params are missing or unknown.

## Purpose

An engineer choosing between two families, or diagnosing why text renders differently on two
machines, needs the differences surfaced — not two columns of facts to read in parallel.

## Layout

Page title `Compare`, then two family pickers side by side (`<select>` or a chip row over the six
families in `FAMILIES`) with a **swap** button between them. Below, a two-column comparison table:
row label in a left gutter (`minmax(140px, 0.8fr)`), then one column per family
(`minmax(200px, 1fr)` each).

**The comparison mechanic, and the point of the feature:** every row computes whether the two values
agree.

- **Differ** → values in Ink at full contrast; row label gets a 2px left border in Proof blue and the
  row background lifts to Panel.
- **Agree** → values in Muted; no accent.

A count at the top reads e.g. `7 of 14 rows differ`, with a toggle: **all rows / differences only**.

## Rows, in order

1. **Specimen** — `മലയാളം സ്ത്രീ ൻ്റ` in each family at a shared size (one slider, 24–132px,
   default 64). Never counts as differing.
2. **Foundry**, 3. **Licence**, 4. **Latest release** (`SHAPING[id].version`)
5. **Malayalam coverage** — `f.covers` (e.g. `118/118`). Differing → the lower value in Alarm red.
6. **Coverage by block** — nested rows from `FONT_DETAIL[id].coverage`, aligned by block label.
7. **Script tags declared** — `SHAPING[id].tags`. Tags present in one and absent in the other get a
   red strike or an `absent` marker. This row is where the Anek `mlm2`-only problem becomes obvious.
8. **GSUB lookups**, 9. **GPOS lookups**, 10. **Features** — the three counts from `SHAPING`.
11. **Features implemented** — union of `SHAPE_BASE.gsub[].feat` plus GPOS features, one line each,
    marked present/absent per family using `SHAPING[id].drop`. Absent in one only → row differs.
12. **Per-language fit** — from `FONT_DETAIL[id].verdicts`, one sub-row per language.
13. **Sequences** — for each of `SEQUENCES`, the sequence rendered in both families with each
    verdict beneath, plus the `hb-shape` line for each family. Reuse the existing generator:
    `hb-shape --font-file=<Name>-Regular.ttf --unicodes=<comma-separated> --features=<applied> --script=Mlym --language=<lang>`
14. **Source repository** — from `SOURCE_REPO[id]`, external, `target="_blank" rel="noopener"`.

Each family column header links to that family's page and to its shaping tables.

## State

`{ a: string, b: string, size: number, diffOnly: boolean }`. `a` and `b` are the route params and
should update the URL when changed (replace, not push, so the back button still leaves the page).

## Honesty constraint

Do **not** compute a winner or a score. Two families with identical verdicts differ in ways this
table cannot see; presenting a total would assert more than the data supports.

---

# Feature 2 — Identify: draw or drop

**Route:** `#/identify`. Replaces the unbuilt "Only have a picture of it" promise on home, which
should become a link here.

## Purpose

Someone has a character they cannot type: on a sign, in a scanned document, in a bug report
screenshot. They need to get from a shape to a codepoint.

## Layout

Two columns, `minmax(320px, 1fr)` each, 44px gap.

**Left — the input surface.** A square canvas, 320×320 CSS px (back it at `devicePixelRatio` for
crisp strokes), 1px Rule border, Panel background.

- Draw with mouse, pen or touch via pointer events. Stroke: round cap and join, Ink, width ~14px at
  320px. Coalesced pointer events if available.
- Accepts a **dropped image file**, a **pasted image** from the clipboard, and a file picker for
  keyboard users. The drop target is the whole canvas; on drag-over, the border goes Proof blue and a
  Panel-tinted overlay reads `drop an image of the character`.
- A dropped image is drawn scaled to fit with ~8% padding, then thresholded to an ink mask
  (luminance < 0.6 counts as ink; auto-invert if more than half the pixels are ink, so light-on-dark
  photographs work).
- Controls beneath: **clear**, **undo** (keep a stack of strokes, not pixels), and a size control for
  the brush. Mono 12px buttons, 2px radius, Rule border.

**Right — candidates.** A ranked list, top 12, appearing as soon as the canvas has ink and updating
on a ~150ms debounce after each stroke ends.

Each candidate row: the glyph at 44px in the reference face, its `U+XXXX` and name in mono, a
similarity bar (Proof blue fill on a Panel track, labelled with a percentage), and links to its
character page and to `#/inspect/<char>`.

## How matching works

Build a **glyph signature atlas** once per session, after the webfont is confirmed loaded:

1. `await document.fonts.load('256px Manjari')`, then `await document.fonts.ready`. Building the
   atlas before this yields signatures for a fallback face and the results are silently wrong.
2. For each assigned codepoint in U+0D00–0D7F (skip the ten where `MLYM_NAMES` is empty), render the
   character at 256px into an offscreen canvas. Prefix combining marks with U+25CC so they have a
   base, and record that the signature includes the dotted circle.
3. Crop to the ink bounding box, then resample to a **24×24** binary grid at a ~0.5 ink threshold.
   Store the grid, its ink count and its centroid.

Score a query the same way, then rank by:

```
score = intersectionOverUnion(query, candidate) − 0.15 × centroidDistance
```

Both grids normalised to their bounding boxes first, so size and position don't matter but aspect
ratio and stroke distribution do. Clamp to `[0, 1]`.

Atlas build is ~118 renders; do it in an idle callback or a worker and show a `building the glyph
atlas` line in the candidate column while it runs. Cache in memory for the session.

## Honesty constraint — non-negotiable

A caption under the candidates must say, in the app's own register, that this is **shape similarity
computed in the browser against real glyph outlines, ranked — not handwriting recognition**, that a
rough sketch will rank poorly, and that combining marks are matched with their dotted circle
included. Never present a single "detected" answer, never hide the score, and never round a low
score up to sound confident.

Also state which face the atlas was built from, since the ranking is only as representative as that
face. Offer the six families as atlas sources if it is cheap; otherwise name Manjari as the
reference.

## State

`{ strokes: Stroke[], imageMask: ImageData | null, brush: number, atlasReady: boolean, candidates: Candidate[] }`

Canvas pixels are not React state. Keep strokes in a ref, redraw imperatively, and lift only
`candidates` and `atlasReady` into render state.

## Accessibility

Drawing is inherently pointer-only, so the file picker and paste paths are the accessible route, not
a nicety. The canvas needs an `aria-label` and the candidate list must be reachable and readable
without ever touching the canvas.

---

# Feature 3 — Shaping-engine matrix

## Purpose

Today every verdict means "HarfBuzz agreed". A font that passes HarfBuzz and fails DirectWrite is
the ordinary case, and which engine broke tells you whose bug it is. The site states this caveat in
prose (`Anek Malayalam` reads *clean in HarfBuzz only*) but cannot show it.

## Data change

Widen the per-sequence result from one value to four:

```js
// FONT_DETAIL[fontId].results[sequenceId]
{
  hb: { verdict: 'clean' | 'fail' | 'caveat', out: 'ൻ്റ', note: '…' },
  dw: null,   // DirectWrite — not tested
  ct: null,   // CoreText — not tested
  gr: 'n/a'   // Graphite — no silf table in this family
}
```

Three states, three treatments:

- **A verdict** — rendered as now, coloured Proof blue / Muted / Alarm red.
- **`null`** — the literal words `not tested` in Faint. Not a dash, not a blank, not an assumption.
- **`'n/a'`** — `not applicable` in Faint, for Graphite where the font carries no `silf` table.

Add `graphite: false` to each entry in `SHAPING` (none of the six indexed families ship Graphite
tables; SIL's own families do, and none are indexed yet). Drive the `gr` column from it rather than
hardcoding per row.

## Rendering

**Font page evidence table** — the existing two-column row becomes: sequence and features on the
left, then four narrow verdict columns headed `HarfBuzz` / `DirectWrite` / `CoreText` / `Graphite`,
with the shaped output shown under the HarfBuzz column since that is the only one whose output is
known. Keep the `hb-shape` line spanning the full row width.

**Script page** — a compact strip beside the collapse bar: four engine labels with the count of
families tested under each (`61 / 0 / 0 / 0`), which makes the coverage of the *testing* legible at a
glance.

**Legend, required.** One line under the matrix: browsers cannot reach DirectWrite or CoreText, so
those columns are populated from external test runs and are empty until such a run exists. This
prevents the empty columns reading as a rendering bug.

## Why an almost-empty feature is worth building

The matrix makes the shape of the current evidence visible: one engine, one platform, one date.
Filling the other columns later is a data-import problem against a structure that already exists,
not a rebuild. Do not populate `dw`, `ct` or `gr` with guesses to make the table look complete —
that would invert the product's entire premise.

---

## Interactions and behaviour common to all three

- **Routing** — hash-based in the prototype. Use the codebase's router; keep the URL shapes so links
  between pages survive.
- **Trail** — the persistent nav plus a breadcrumb trail of visited entities, deduplicated when you
  revisit (revisiting an earlier entity truncates the trail back to it rather than appending).
  Compare and Identify both need trail labels.
- **Transitions** — the only animation in the app is `bargrow`, a 0.5s ease-out `scaleX` on bar
  fills, with `prefers-reduced-motion` honoured. Add nothing.
- **Empty and error states** — every list in the app has one, written as a sentence that says what to
  do next. Match that: the candidate column before any ink, the compare table with `differences only`
  and no differences, a regex that will not compile.
- **Responsive** — single fluid column set with `auto-fit` grids; no breakpoint logic. Comparison
  columns stack on narrow viewports, and the compare row labels must stay attached to their values
  when they do.

## State management summary

| Feature | State |
| --- | --- |
| Compare | `{a, b, size, diffOnly}`, `a`/`b` mirrored to the URL |
| Identify | strokes and pixels in refs; `{candidates, atlasReady, brush}` in render state; atlas cached per session |
| Matrix | none — derived from `FONT_DETAIL[].results` and `SHAPING[].graphite` |

## Assets

No images, no icon set. Every glyph on every page is live text in a webfont. Arrows are the literal
characters `←` `→` `↗`; the dotted circle is U+25CC; the external-link mark is `↗` followed by the
words `— external`.

Webfonts, all from Google Fonts: IBM Plex Sans, IBM Plex Sans Condensed, IBM Plex Mono, Manjari,
Gayathri, Chilanka, Noto Sans Malayalam, Noto Serif Malayalam, Anek Malayalam, Baloo Chettan 2.

## A data caveat to carry forward

Some numbers in the prototype are authored placeholders, not measurements: the 1,885-family index
total, the 61/34/19 collapse counts, the `SHAPE_BASE` lookup structure and GPOS anchor offsets, the
script-index family counts, and the verdicts for the ten families in `INDEX_FONTS` without pages.
Real values need font binaries parsed — `cmap` for coverage, `GSUB`/`GPOS` script lists for tags,
lookup counts per feature, `silf` for Graphite, `fvar` for axes. That parse is straightforward given
the files; only shaping verdicts genuinely need a shaper. If you implement against real fonts, prefer
computed values and delete the placeholders rather than keeping both.

## Files in this bundle

- `Glyph Sleuth.dc.html` — the full prototype, all ten page types and all data
- `support.js` — the prototype's template runtime. **Reference only; do not port.**
- `PLAN.md` — the build plan, plus the reasoning on exemplar provenance and version history
- `TODO.md` — the full open-items list with effort estimates
- `conventions.md` — project conventions, including the one-external-link-per-page rule
- `screenshots/` — one capture per existing page type, at ~900px viewport width:

  | File | Page | What it shows |
  | --- | --- | --- |
  | `01-home.png` | `#/` | Hero claim, the three entry questions, query examples |
  | `02-script-malayalam.png` | `#/script/Mlym` | Collapse bar, filter chips, linked facts strip |
  | `03-font-manjari.png` | `#/font/manjari` | Facts strip, specimen, the face write-up |
  | `04-font-manjari-shaping.png` | `#/font/manjari/shaping` | GSUB lookup rows, GPOS anchor diagram |
  | `05-char-0D7B-chillu-n.png` | `#/char/0D7B` | Prev/next nav, properties, sequences, similar characters |
  | `06-block-malayalam.png` | `#/block/malayalam` | The 8×16 chart with hatched reserved cells |
  | `07-lang-pcg-paniya.png` | `#/lang/pcg` | Exemplar tiles and the nothing-fits empty state |
  | `08-feature-pres.png` | `#/feature/pres` | Pipeline strip, ZWNJ example pairs |
  | `09-inspect.png` | `#/inspect/മലയാളം` | Cluster breakdown and the selected-codepoint panel |
  | `10-regex.png` | `#/regex` | Live tester with a match, recipes, four-engine table |
  | `11-index-fonts.png` | `#/fonts` | Index pattern: search, facet chips, sort, show-more |

  Captures are viewport-height, so long pages are cut off below the fold — open the prototype for
  anything the crop hides. There is no screenshot for Compare, Identify or the matrix; those are the
  three features being specified here.
