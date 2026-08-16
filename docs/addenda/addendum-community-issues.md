# Addendum — grounded scope + community issue reporting

*Follow-up to the "Glyph Sleuth web app" brief in `chats/chat1.md`. Written after evaluating
the built prototype (`project/Glyph Sleuth.dc.html`) and researching whether the
Malayalam page's depth of per-script research is viable across all scripts.*

---

## 1 · Scope philosophy — grounded, not exhaustive

Drop the assumption that a script needs its pitfalls fully documented before it ships. Three
honest tiers, stated as such on the page itself (never disguised):

- **Tier A — grounded.** A script with sourced, verified encoding pitfalls and shaping
  verdicts, written the way the Malayalam page's chillu and ṉṯa sections were: someone
  flags a real issue, a research pass sources and verifies it against primary records
  (Unicode L2 documents, OpenType registries, HarfBuzz output on a stated date). Realistically
  ~20–40 scripts start here — the ones with an active public encoding history (major Indic
  scripts, the Arabic-family scripts, Thai/Lao/Khmer/Myanmar, Tibetan, Mongolian, N'Ko).
- **Tier B — measured.** Coverage (tier 1) and script-tag declaration (tier 2) are fully
  automatable today from font binaries — this is a build step, not research, for any script
  in the corpus. Shaping (tier 3) runs the mechanical checks only (dotted-circle detection,
  cluster-count sanity) with no editorial pitfalls write-up yet. Say so on the page: "No
  known encoding pitfalls documented for this script yet" is itself a real, provenance-bearing
  fact — same principle as the brief's existing "absence is content" rule.
- **Tier C — stub.** Script is recognized (ISO 15924 code, block, assigned codepoints) but
  has no meaningfully-sized libre font ecosystem to audit yet. Just the facts row and a route
  to contribute.

A script's tier is itself a fact the page states plainly, in the same monospace/provenance
voice as everything else — never softened, never apologised for.

## 2 · New component — "Report an issue"

A sibling to the existing "Add a family" contribute flow (already in the brief, section 7's
absence-as-content block: *"Add a family for one of these languages"*), reachable from the
same places:

- On a **script page**, next to the pitfalls write-up (or in its place, on a Tier B/C page
  that has none yet): *"Know an encoding or shaping problem with this script? Report it."*
- On a **font family page**, next to a specific verdict: *"This verdict looks wrong? Report
  what you're seeing."*
- On a **character page**, for a specific codepoint or sequence.

Fields, deliberately minimal (this is a static site — the form target is out of scope here,
just the shape of what's captured): script or font context (pre-filled from the page),
the codepoint sequence involved, a plain-language description of what goes wrong, and an
optional contact/attribution. No screenshot upload, no account — matches the "read-only,
nothing leaves the browser except what you explicitly submit" posture already in the brief's
constraints section.

## 3 · Provenance must separate the two kinds of fact

This is the one place the design has to be disciplined, because it's exactly the audience
(section 2's "they do not trust claims; they trust sources") that would notice the difference
being blurred:

| | Grounded (Tier A) | Submitted (unverified) |
|---|---|---|
| Voice | states the fact directly | attributes it: *"Reported by a reader of this script"* |
| Provenance line | names the source and date — Unicode L2 doc, HarfBuzz run | names the report and its status — *"submitted 2026-08, unverified"* |
| Visual weight | full write-up prose, same as any other verified section | set apart — a bordered aside, not blended into the main write-up |

This is not a new idea for the brief — section 3 already draws this exact line for judgment
calls ("conjuncts render correctly — reported by a reader of this script"). This addendum
just extends it to cover crowd-sourced problem reports, not only crowd-sourced confirmations.

## 4 · The promotion path

A submitted report isn't the end state — it's an input to the same research process that
produced the Malayalam write-up in the first place. Periodically (per script, as reports
accumulate, or on a standing cadence), a research pass attempts to verify a submitted claim
against primary sources and either:

- **promotes** it — becomes a grounded paragraph with citations, the script's tier can move
  from B/C toward A, or
- **can't confirm it** — stays labeled as an unverified report, visibly, rather than being
  silently dropped or silently upgraded.

This is literally a repeatable version of what happened in this project's own design
session — a human flagged chillu and ṉṯa, a research pass then sourced and verified them.
Community reports are just a second channel feeding the same pipeline.

## 5 · Prior art update — ScriptSource is retiring

Confirmed directly (not in the original research pass, which only flagged this as needing
confirmation): **ScriptSource is being retired and closes at the end of September** 2026.
Its replacement is **[Writing Systems Technical Resources](https://writingsystems.info/)**,
whose own [migration notes](https://writingsystems.info/support/migrating-from-scriptsource/)
say the move is explicitly to favour **openly-licensed content** and a leaner, more
maintainable stack — content that was outdated, no longer relevant, or not openly licensed
was left behind rather than carried forward as-is.

Two things worth taking from that, concretely:

- **License discipline matters for Tier A write-ups**, the same way it clearly mattered to
  SIL's own migration. Any fact sourced from a third party (a forum post, an L2 document, a
  blog) should be verifiable and attributable, not just true — the same standard the
  migration applied to its own content.
- **A structural choice worth noting, not necessarily copying**: writingsystems.info
  reportedly dropped individual per-language pages in favour of a search-first index, which
  cuts directly against this brief's core "every entity is an address" philosophy (section 3).
  That's presumably a maintenance-burden trade-off on their end, not a verdict that
  per-entity pages are wrong — but it's a real data point that the entity-graph model has a
  cost at scale, from a project that apparently decided it wasn't worth paying. Worth keeping
  in mind if Glyph Sleuth's own maintenance burden becomes a live question later, rather than
  dismissing it as irrelevant precedent.

---

**Net effect on the brief's section 12 deliverable priorities:** unchanged for the prototype.
This addendum is about the content-scaling and contribution model behind the script page,
not a new page kind to build next — the one page-level addition worth prioritizing whenever
scope allows is the "Report an issue" affordance on the script page, since it's what turns a
Tier B/C script into a live candidate for Tier A over time.
