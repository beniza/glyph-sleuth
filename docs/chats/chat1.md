# Apply drawing

_Started 2026-08-16 05:49 UTC_

---

## User

<system-info comment="Only acknowledge these if relevant">
Project title is now "# Design brief — Glyph Sleuth web app????*A self-contained brief. Assume no prio"
The project currently has no files except possibly dotfiles — a `list_files` on the project root would return nothing else.
Current date is now August 16, 2026
</system-info>

<default aesthetic_system_instructions>
The user has not attached a design system. If they have ALSO not attached references or art direction, and the project is empty (the auto-managed _ds/ folder doesn't count), ask your opening questions with the ask_user tool. Whenever you ask opening questions in this project, include a design-system question in the form: the user's pick there sets the visual direction, so do NOT also ask about the visual aesthetic (no questions about vibe, colors or palette directions (including color-swatch svg-options questions), typography, mood, or art direction). Spend your other questions on everything else: audience, purpose, content, structure, scope, interactions, tone of copy. Exception: if the request already states the visual direction as a brand or concrete art direction, leave the design-system question out of your own questions (the app may still add one — it's skippable, and a skip doesn't change the stated direction) — but if they name a design system that isn't attached, keep the question: their pick there is what attaches it.

If the design-system question comes back unanswered — skipped without a pick (a "Not sure" / decide-for-me answer counts as a pick: it applies the effective default) — and no references or other art direction arrived either, THEN ask the visual-aesthetic questions before designing: a follow-up round (or one focused question) about vibe, colors, type, and mood is the right move once the design-system ask went unanswered. Do NOT just pick your own. Once you have a direction, use this guidance when creating designs:
- Choose a type pairing from web-safe set or Google Fonts. Helvetica is a good choice. Avoid hard-to-read or overly stylized fonts. Use 1-3 fonts only.
- Foreground and background: choose a color tone (warm, cool, neutral, something in-between). Use subtly-toned whites and blacks; avoid saturations above 0.02 for whites.
- Accents: choose 0-2 additional accent colors using oklch. All accents should share same chroma and lightness; vary hue.
- NEVER write out an SVG yourself that's more complicated than a square, circle, diamond, etc.
- For imagery, never hand-draw SVGs; use subtly-striped SVG placeholders instead with monospace explainers for what should be dropped there (e.g. “product shot”)

CRITICAL: ignore default aesthetic entirely if given other aesthetic instructions like reference images, design systems or guidance, or if there are user-authored files in the project already (the auto-managed _ds/ folder is not user-authored).
</default aesthetic_system_instructions>

<pasted_text name="Pasted text (329 lines)">
# Design brief — Glyph Sleuth web app

*A self-contained brief. Assume no prior context.*

---

## 1 · What you are designing

**Glyph Sleuth** is a read-only inspector for Unicode characters, fonts, scripts and
languages. It answers three questions in sequence:

1. **Identify** — what is this character?
2. **Cover** — which fonts contain it?
3. **Render** — will those fonts actually draw it correctly?

The third question is what distinguishes it. Most tools stop at coverage, and coverage
lies: a font can contain every codepoint in Malayalam and still set conjuncts wrongly,
misplace a chillu, or register itself under a script tag modern shapers no longer
prefer. Glyph Sleuth reports coverage, then reports whether the font's OpenType tables
declare the script, then reports whether shaping the language's exemplar characters
actually produced clean output. Three verdicts, not one.

It indexes roughly **1,885 freely licensed font families** from Google Fonts, SIL,
Swathanthra Malayalam Computing, Rachana and other libre foundries. It never edits,
generates or hosts fonts. It is a static site: no accounts, no server, nothing uploaded.

Design the **web app**. There is a desktop companion, but it is not your brief.

---

## 2 · Who it is for

Ranked. The ranking decides vocabulary and defaults.

1. **Script engineers** — people making a writing system work in software. They care
   about blocks, coverage cliffs, exemplar sets, OpenType feature tags, and whether a
   `\p{Script=Malayalam}` label is one a real regex engine would accept. They do not
   trust claims; they trust sources.
2. **Developers** — picking a font for a script, needing the licence, the download, the
   CSS, and a straight answer about what will break.
3. **Font designers** — auditing coverage of a face, or checking what the field already
   covers before starting one.
4. **Typesetters** — committing a whole publication to a family and needing confidence.
5. **Curious readers** — someone holding an unfamiliar character. Served, never
   optimised for.

Write for 1. The others follow. Never dumb the interface down for 5.

---

## 3 · Design philosophy

**Chrome stays small so the fonts are the only large voice.** This is the governing
rule. The subject matter is typefaces; every pixel of interface competing with a
specimen is a pixel working against the product. The chrome should speak in one quiet
voice so that specimens differ maximally against it.

**Facts, never taste.** The app never says a font is *better*. It reports coverage,
tags, shaping results, licences. Where judgement enters, it arrives as a sourced claim
("conjuncts render correctly — reported by a reader of this script"), never a star
rating.

**Every fact is an address.** The app is a graph of linked entities, not a set of modes.
A mode is a place you are in and must leave; an entity is a place you can arrive at from
anywhere and depart from in ten directions.

**Every verdict is interrogable.** A verdict you cannot open is an opinion. Any claim of
correctness expands to show which sequences were shaped and what came out.

**Provenance is visible.** Each page names where its facts came from and when: coverage
from cmap tables, exemplars from SLDR, verdicts from HarfBuzz on a stated date.

**Absence is content.** "No indexed font covers Tamil Supplement beyond this one" is a
real finding and deserves real presentation, not an empty state.

---

## 4 · Visual direction

A starting point, refine it if you can do better — but keep the governing rule.

**Palette.** A cool proof-sheet neutral, deliberately not warm cream. One signal blue
for links and passing verdicts. One red, reserved *solely* for "this breaks" and used at
most once per screen.

```
--ink    #16181D    text, primary bars
--paper  #E9EBE7    background (cool pale grey-green)
--card   #F5F6F3    panels, rows
--rule   #CBCFC8    hairlines
--proof  #1F4FD8    links, passing verdict
--fail   #A81E12    failure only — never decorative
--mute   #6E736C    secondary text
```

**Type.** Chrome in one superfamily across three roles, so it reads as a single quiet
voice: a condensed grotesque for labels and eyebrows (uppercase, letterspaced, small), a
regular sans for prose, a monospace for all data — codepoints, tags, ranges, counts.
IBM Plex Sans Condensed / Sans / Mono works well. **All codepoints, hex, script codes,
feature tags and counts must be monospaced.** This is not decoration; it is how the
audience reads.

Specimens are set in the actual fonts, loaded live, at large sizes. Let them dominate.

**Density.** Reference-tool density, not marketing density. Hairline rules, tight
vertical rhythm, minimal border-radius. Generous whitespace *around specimens only*.

**Motion.** Almost none. One restrained reveal on the coverage collapse is enough.
Respect `prefers-reduced-motion`.

**Avoid:** warm cream backgrounds with terracotta accents; near-black with acid-green;
generic card grids with drop shadows; numbered 01/02/03 markers; hero sections with a
big statistic and a gradient. None of these belong to this subject.

---

## 5 · Information architecture

Six entity kinds. Each is a page, each is a URL, each links to the others.

| Kind | URL | Example |
| --- | --- | --- |
| Character | `#/char/0D15` | ക MALAYALAM LETTER KA |
| Block | `#/block/malayalam` | U+0D00–0D7F |
| Script | `#/script/Mlym` | Malayalam |
| Language | `#/lang/ml` | Malayalam · `#/lang/jns` Jeseri |
| Font family | `#/font/manjari` | Manjari |
| Shaping feature | `#/feature/blwf` | Below-base forms |

Relations move along **two axes**, and the interface must make clear which is which:

- **Taxonomic — *is part of***: character → block → script
- **Functional — *is used by***: script → language → font → feature

**Relations carry a verb.** Never "Related: Manjari." Always **Set by** Manjari,
**Requires** blwf, **Confusable with** മ, **Triggers** below-base forms. The verb *is*
the information.

**Guard against link soup.** Every page shows at most **three primary relations**; the
rest fold behind a disclosure labelled with a count. A fully connected graph where
everything links to everything is unnavigable.

---

## 6 · Persistent components

**Omni-search bar.** One input, sticky at top, always available. It accepts a literal
character, a codepoint (`0D15`, `U+0D15`), a Unicode name or fragment, a script code
(`Mlym`), a font name, a language name or tag, an OpenType feature tag (`blwf`), or a
property expression (`\p{Script=Malayalam}`). It **shows how it read the query** —
"reads as: codepoint — U+0D15" — and shows rejected readings too. Results are grouped by
entity kind. This transparency is a feature, not a debug affordance.

**The trail.** A graph has no single parent, so a breadcrumb would be a lie. Show the
path the user actually took — Malayalam script → Malayalam block → ക → blwf — truncated,
and collapsing when they loop back.

**Provenance line.** Bottom of every page. Source and date, in monospace.

**Size control.** One slider drives every specimen on the page simultaneously. Specimens
must be comparable at identical size.

**Permalinks carry state.** Selected size, sample text, and compared fonts all encode in
the URL. Script engineers' real goal is often to *send someone proof*.

---

## 7 · Page specifications

### Script page — the flagship

The most important page in the app and the main arrival point from search engines.
Example: Malayalam.

- Head: eyebrow `SCRIPT · Mlym`, large name, native name below, then a fact row —
  blocks, assigned codepoints, languages, families indexed against.
- **Signature element: the collapse.** Three horizontal bars, each shorter than the
  last, showing how support falls away: *Covers the codepoints* 61 → *Declares the
  script* 34 → *Shapes it cleanly* 19. Ends with a plain sentence stating the
  consequence: "Forty-two families hold every character and still get it wrong." This is
  the product's whole thesis in one glance and should be the most memorable thing in the
  design.
- Blocks list, with coverage per block. Coverage cliffs — where one block has fifteen
  families and the adjacent supplement block has one — should be visible, not buried.
- Specimen list: each family set in its own face at shared size, with name, foundry,
  licence, download, CSS, and three status badges (Covers / script tag / Shapes). Failed
  or caveated entries carry a one-line explanation.
- A demonstration of failure: dotted circles (U+25CC with combining marks), rendered
  live, with an explanation that this is what a font produces when it cannot handle a
  sequence.
- Languages written in this script, as links.

### Character page

Giant glyph, name, codepoint, category, combining class. Related characters by verb:
part of *block*, written in *script*, set by *fonts*, forms conjuncts with *virama*,
confusable with *this other character*. Rendered across several faces at once so the
reader sees how differently it is drawn.

### Font family page

Specimen first and large. Coverage per script, script tags declared, shaping verdict per
language, weights and variable axes, licence, download, CSS snippet, fallback stack.
**"Why that verdict"** expands into the evidence: the sequences shaped, cluster counts,
which features applied, where a dotted circle appeared.

### Block page

Range, assigned versus reserved counts, the full character grid, which script it encodes,
best-covering families. The grid is a lot of glyphs — make it scannable and set in a
font that actually has them.

### Language page

Tag, family, region, exemplar set, default script, and which fonts fit *this language*
rather than merely the script. The distinction matters: Jeseri uses the Malayalam script
but its exemplar set includes characters Malayalam does not, so fonts that pass Malayalam
fail Jeseri. Show that.

### Shaping feature page

What `blwf` or `akhn` does, which scripts require it, which families implement it, which
characters trigger it. No comparable page exists on the web; treat it as reference
material.

### Home / search landing

Not a marketing page. A working front door: the omni-search, prominent, with worked
example queries that teach the syntax by demonstration. Plus entry points by script and
by language.

### Comparison view

Two or more fonts side by side at identical size, with a coverage diff — gained, lost,
moved — grouped by block so losses are loud. Reachable from any font page.

---

## 8 · User journeys

Design against these six. Each names where the current tool fails.

**Diagnosis (script engineer).** Someone reports that their Malayalam text renders
correctly in one application and breaks in another. The engineer needs to find what
differs between the fonts involved — both show full coverage, so the answer is in script
tags, features, or shaping. *The interface must let them get from a font to its
evidence in one or two steps, and compare two fonts' evidence directly.*

**Selection (developer).** Building a site that must show Malayalam alongside English.
Needs a family covering both, a licence they can ship, the CSS, the available weights,
and a sensible fallback chain. *Arrives from a search engine, not from the homepage —
the script page must be self-sufficient for a stranger.*

**Audit (font designer).** Extending a typeface into a new script; wants to see what the
libre field already covers and where it thins out, to decide whether the effort adds
anything. *Coverage cliffs are the finding. Make them impossible to miss.*

**Commitment (typesetter).** Setting a whole book in a language whose script is thinly
supported; needs confidence a family holds across headings, body, bold and italic before
committing. *Needs weights, a specimen with real page structure, and something printable
to take to a colleague who is not using the tool.*

**Identification (curious reader).** Encountered an unfamiliar character; wants to know
what it is and how to type it. *Can paste it, or has only a picture of it — design the
input affordances for both.*

**Arrival (contributor).** Notices their language community's fonts are missing and wants
to add them. *There must be a visible, dignified route from "this is incomplete" to
"here is how you fix it."*

---

## 9 · Copy rules

Sentence case. Active voice. Plain verbs. Name things as the reader recognises them, not
as the system builds them.

Verdicts are stated flatly and never apologise: "Registered under the legacy `mlym` tag.
Renders correctly in HarfBuzz, unpredictably in older stacks." Not "Unfortunately, this
font may have some issues."

Empty results are directions, not moods: "Nothing matches. Try a codepoint, a font name,
or a script code."

Never use marketing language. No "powerful", "seamless", "beautiful". The audience is
allergic to it.

---

## 10 · Constraints

- **Static site.** No backend, no accounts, no uploads. Everything the user types stays
  in the browser, and the interface should make that evident.
- **Read-only.** The app never edits or generates a font. Anything that writes a file is
  out of scope.
- **No hosted fonts that cannot be freely licensed.** Specimens draw from public CDNs or
  OFL faces only. This constraint is architectural, not incidental.
- **Mobile must genuinely work.** Specimens, the collapse, and the relation lists all
  need to hold up at 380px.
- **Accessibility floor:** visible keyboard focus, real headings, sufficient contrast on
  all text including the muted grey, reduced-motion respected.

---

## 11 · Sample content — use real data, not lorem

Malayalam words for specimens: **മലയാളം** (the language name), **സ്ത്ര** (a complex
conjunct), **ക്ക** (a doubled consonant conjunct), **ൻ** (a chillu letter).

Illustrative figures — plausible, not verified: Malayalam has 1 block, U+0D00–0D7F, 118
assigned codepoints, 17 languages. Of 1,885 indexed families, 61 cover it, 34 declare
`mlm2`, 19 shape it cleanly. Real font names in this space: Manjari, Gayathri, Chilanka
(all SMC), Noto Sans Malayalam, Noto Serif Malayalam, Anek Malayalam. Real OpenType
features: `akhn`, `blwf`, `pres`, `abvs`, `half`. Real languages using the Malayalam
script: Malayalam (ml), Jeseri (jns), Paniya (pcg), Ravula (yea).

---

## 12 · Deliverable

Priority order if you cannot do everything:

1. **Script page** — the flagship, the arrival point, and the home of the collapse.
2. **Font family page** — with the evidence expansion.
3. **Character page**.
4. **Home / search**, showing the omni-search reading its input.

Show the omni-search, the trail, the verb-carrying relations, provenance lines, and at
least one absence-as-content moment. Mobile and desktop.
</pasted_text>

<!-- The user explicitly selected the following skills for this project, as attachments to their message. These are not optional context — they define how you work. Use them. -->
<attached-skill name="Design Components">
This project uses Design Components: every design is a single streaming `Name.dc.html` file. The full authoring spec is in your system prompt under "Writing code — Design Components" — follow it. Author and edit `.dc.html` content with the `dc_write`, `dc_html_str_replace`, `dc_js_str_replace`, and `dc_set_props` tools (not `write_file`; `str_replace_edit` works but won't stream); template edits stream into the live preview as you type.
</attached-skill>


<system-reminder>Auto-injected reminder (ignore if not relevant): do not recreate copyrighted or branded UI unless the user's email domain matches that company. Create original designs instead.</system-reminder>

## Assistant

Brief is self-contained — building it.

_[tool: dc_write]_

_[tool: ready_for_verification]_

Built the four priority pages as one linked app: script page (Malayalam) with the collapse, font family page with the evidence expansion, character page, and home/search.

A few notes:
- The omni-search shows its readings including rejected ones; type into it from any page.
- Absence-as-content sits on the script page (Paniya and Ravula, with a route to contribute).
- The failing entry is Chilanka — one red per screen. Figures are illustrative, flagged in the provenance line.
- Not built: block, language, feature and comparison pages — they route to a stub. Say the word and I'll add them.

## User

Apply drawing

## Assistant

_[tool: read_file]_

Moving the eyebrow into the trail bar, right side.

_[tool: dc_html_str_replace]_

_[tool: dc_html_str_replace]_

_[tool: dc_js_str_replace]_

_[tool: dc_html_str_replace]_

_[tool: dc_html_str_replace]_

_[tool: ready_for_verification]_

The entity eyebrow now sits at the right end of the trail bar and updates per page (Script · Mlym, Font family · manjari, Character · U+0D15). Removed the duplicate eyebrows from the script, font and character page heads.

## User

Helpful if the total number fonts listed here. The chart below contains that info, so may be we can bring it over here.

## Assistant

_[tool: dc_js_str_replace]_

## User

Consumes too much space while providing too little useful info. concise this.

## Assistant

_[tool: dc_html_str_replace]_

Collapse is now three tight rows — label, bar with its note inline, count — about a third of the height, with the consequence sentence at reading size.

## User

Convert this into a single bar. total length is 61, 34 is shaded light indicating partially implemented and 19 in blue showing full support (use your design skills)

## Assistant

_[tool: dc_html_str_replace]_

_[tool: dc_js_str_replace]_

_[tool: dc_html_str_replace]_

One stacked bar of 61: 19 blue (shapes cleanly), 15 shaded (declares the script but fails shaping), 27 pale (coverage only), with an inline legend underneath.

## User

Apply drawing

## Assistant

_[tool: dc_html_str_replace]_

_[tool: dc_js_str_replace]_

_[tool: dc_js_str_replace]_

_[tool: dc_html_str_replace]_

_[tool: ready_for_verification]_

Filter chips now sit in the families header, left of the sample words: all 61 / shapes cleanly 19 / declares only 15 / covers only 27. Selecting one filters the specimen list. Legend items below the bar no longer wrap into each other.

## User

Found issues — fixing…

## Assistant

_[tool: dc_js_str_replace]_

_[tool: dc_js_str_replace]_

_[tool: dc_js_str_replace]_

_[tool: dc_html_str_replace]_

_[tool: ready_for_verification]_

Both fixed: the character page's "Set by" grid now uses the unfiltered list, and the buckets are relabelled to match the row badges — shape cleanly 19 / shape with caveats 15 / break 27.

## User

Remove it completely. Provide a write up about the script instead

## Assistant

_[tool: dc_html_str_replace]_

_[tool: ready_for_verification]_

Bar and legend removed. In their place, a two-column write-up on the script: abugida structure and conjuncts, the 1971 reform and chillu letters, the `mlm2`/`mlym` tag split, and the 19/15/27 verdict split pointing to the filters below.

## User

there are two prominent encoding issues in this script. 1. chillu: initially written as <base> <virama> <zwj>. Later chillu was encoded 0D7A-0D7F. The older form is still preserved for backward compatibility, but causes rendering issues.
2. encoding of ൻ്റ: This conjunct is handled differently by different fonts/shaping engines. 

You do a research and add another paragraph explaining challenges. This page would be an ideal place to mention it.

## Assistant

_[tool: dc_html_str_replace]_

_[tool: web_search]_

_[tool: ready_for_verification]_

Added "Two encoding problems most verdicts turn on" under the write-up, in two columns.

Sourced from the Unicode record: Unicode 5.1 introduced the atomic chillus at U+0D7A–0D7F, replacing sequences like NA, VIRAMA, ZWJ, and the ZWJ distinction is semantic in Malayalam — അവന്‍ and അവന്‌ are different words. For ṉṯa, the pre-5.1 representations ⟨na, virama, rra⟩ and ⟨na, virama, ZWJ, rra⟩ were already in use and all three remain widespread, and ⟨na, virama, ZWJ, rra⟩ collides with the legacy encoding of the side-by-side form ൻറ. na + virama + rra is what InScript and transliteration tools produce.

## User

here are a couple of ideal failure combinations:
1. Repham mark: Not all fonts render it correctly and often appear with a dotted circle
2. nta rendered with a na <virama> rra or chillu_n <virama> rra. No dotted circles, but conjunct nta is not formed.

## Assistant

_[tool: dc_html_str_replace]_

_[tool: dc_html_str_replace]_

_[tool: ready_for_verification]_

Replaced the generic dotted-circle sample with the two real cases: dot reph + ka as the loud failure, and both nta sequences as the quiet one where the conjunct simply doesn't form. Section is now "What failure looks like · loud and quiet".

## User

Found issues — fixing…

## Assistant

_[tool: dc_html_str_replace]_

_[tool: ready_for_verification]_

Each case now shows both outcomes side by side: dot reph shaped correctly next to the same sequence on a dotted circle, and the nta conjunct next to the separated ൻ റ fallback, each labelled.

## User

we can specify what non malayalm characters are present in the font (Basic Latin, Characters required for typesetting, such as various dashes, smart quotes etc). If this is a font contains multiple scripts, find a way to mention it without listing them all.

## Assistant

_[tool: dc_js_str_replace]_

_[tool: dc_html_str_replace]_

_[tool: ready_for_verification]_

Each specimen row now carries an "Also covers" line: Latin range, whether typographic punctuation is complete or what's missing, and additional scripts as a count rather than a list ("2 more scripts") — the count links naturally to the font page if you want it expandable there.

