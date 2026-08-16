# Implementation plan

## First, the two you asked about

### Exemplar provenance

An exemplar set is the list of characters a language actually writes with, published per language in
CLDR and, for the long tail of languages, in SIL's SLDR. It is not one list. The data defines named
sets — **main**, **auxiliary**, **index**, **punctuation**, **numbers** — and they answer different
questions. Main is what ordinary text needs. Auxiliary is what appears in loanwords, dialect
spellings and older orthographies. Index is the set a sorted list is bucketed by. Punctuation is the
marks the orthography uses, which is where the shared Indic danda enters and where a Script-only
regex quietly fails.

What the app shows now is not that. The groups on each language page — Vowels, Consonants, Chillus,
Signs — are linguistic groupings written for display. They are reasonable, but they are ours, not
the data's, and they cannot be checked against a source.

Provenance means three additions:

1. **Cite the file and its revision.** `ml.xml`, SLDR, with the commit or release date the set was
   read from. A verdict computed against a set that has since changed is a verdict about the past.
2. **Carry the validity level.** SLDR marks data as approved, contributed, provisional or
   unconfirmed. A language whose exemplar set is unconfirmed cannot produce a trustworthy verdict,
   and saying so is more useful than a number.
3. **Restructure the groups to the real named sets**, and state which ones the fit verdict was
   computed over. Most disagreements about whether a font "fits Malayalam" are really disagreements
   about whether auxiliary and punctuation were included.

The payoff is that "19 families fit" becomes a reproducible claim: this set, this revision, these
named subsets, this shaper.

### Version history

Every verdict on the site is about a specific build of a font, but the site presents verdicts as
properties of families. Those are different things. Chilanka covering 112 of 118 codepoints is not a
fact about Chilanka; it is a fact about a release that predates six assignments.

A version history is, per family, the release list with a date, and for each release: coverage, the
lookups present, and the verdict — plus one line on what changed. It answers the three questions an
engineer actually has:

- Was this fixed? (and if so, in which release)
- Which release should I pin?
- Did anything regress between the release I shipped and the current one?

Two things make it cheap or expensive. The release list is cheap: the repositories carry tags and
release notes, and the SMC families have a `FONTLOG.md` written for exactly this purpose. The
per-release verdict is expensive, because it means shaping every release, not just the current one.
The honest middle is a real release list with real coverage and dates, the verdict shown only for
releases actually tested, and the rest left explicitly untested.

---

## Build order

### Phase 1 — Compare

Route `#/compare/<a>,<b>`, already linked from every font page.

Two families side by side, with the comparison doing the work rather than two columns of facts:
rows where the families differ are set in full contrast, rows where they agree are muted, so the
differences are what the eye lands on.

Rows: specimen at a shared size, coverage by block, script tags declared, features implemented
(present in one and absent in the other called out), GSUB/GPOS lookup counts, per-language fit, the
same sequences shaped by both with each verdict, licence, foundry, source repository, and the
`hb-shape` line for each sequence against each font.

Controls: two pickers over the six detailed families, and a swap. All data exists — `FAMILIES`,
`FONT_DETAIL`, `SHAPING`, `SEQUENCES`. No new authoring.

### Phase 2 — Identify: draw or drop

Route `#/identify`. This replaces the unbuilt promise on the home page with something real.

- A square canvas the user draws on with the mouse or a finger, plus clear and undo.
- The same canvas accepts a dropped or pasted image, scaled to fit, thresholded to an ink mask.
- On the other side, a ranked list of candidate characters with a similarity score.

How the matching works, and what it honestly is: after the webfont loads, each assigned codepoint in
the block is rendered offscreen at a large size in one reference face, cropped to its ink bounding
box, and resampled to a small binary grid — a shape signature. The user's drawing goes through the
same pipeline, and candidates are ranked by overlap between signatures with a penalty for centroid
displacement.

That is shape similarity computed in the browser against real glyph outlines. It is not handwriting
recognition and it will not be reliable on a rough sketch, and the page will say exactly that. Each
candidate links to its character page and to Inspect.

The one technical dependency is waiting on `document.fonts.load` before building the atlas, so the
signatures come from the real face rather than a fallback.

### Phase 3 — Engine matrix

Widen every verdict from one shaper to four: HarfBuzz, DirectWrite, CoreText, Graphite.

Structurally this is a per-font, per-sequence record of four values instead of one. The HarfBuzz
column is what the site already has. The other three are unknown, and they will render as **not
tested** in grey rather than being invented — a browser cannot reach DirectWrite or CoreText, and
Graphite reads *not applicable* for a font with no `silf` table, which is all six indexed families.

That sounds like an empty feature. It is the opposite: the matrix makes visible that "Anek shapes
cleanly" currently means "one shaper on one machine agreed", which is the caveat the site states in
prose and cannot yet show. Filling the columns later is a data problem, not a rebuild.

Rendered as four columns in the font page evidence table, and as a compact strip on the script page
where the collapse bar already lives.

### Phase 4 — Provenance and history

Needs decisions from you: which SLDR revisions to cite, whether to show validity levels, and how far
back the release lists should go.
