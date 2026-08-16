# Addendum — desktop companion, data-production role

*Follow-up to `chats/chat1.md` (original brief) and the updated bundle
(`Glyph Sleuth.dc.html`, `README.md`, `PLAN.md`, `TODO.md`, `conventions.md`). Not ready to
build — sequenced after the web app's remaining features (Compare, Identify, the shaping
matrix) and the Phase 4 provenance decisions, because its output schema depends on data
shapes (`FAMILIES`, `FONT_DETAIL`, `SHAPING`) that are still settling.*

---

## 1 · What problem this solves

TODO.md's "what would fix the root cause" section says most of the site's numbers are
authored rather than computed, and that fixing this needs real font binaries parsed —
`cmap` for coverage, `GSUB`/`GPOS` for script tags and lookup counts, `silf` for Graphite,
`fvar` for axes — but flags a blocker: "the font files have to arrive in the project.
Cross-origin fetches are not available, so they need to be uploaded."

That blocker is real for the Claude Design prototype specifically — a browser sandbox with
no backend has no other door in. It is not a constraint on the shipped product, and it
should not become one: Glyph Sleuth's own architecture already rules out hosting or
transmitting font binaries anywhere (section 10 of the original brief; reaffirmed this
round when we ruled out self-mirroring for the CSS-snippet problem).

The desktop companion is how real numbers get produced without that rule ever being bent.
It runs on a contributor's own machine, against a font file they already legitimately have
— a foundry's release, a cloned repo, an installed font — parses it locally, and emits a
small derived-facts record. The font itself never leaves the machine it started on; only
the computed record travels.

## 2 · Scope

**Is:** a local tool that turns "I have a font" into a correctly computed, provenance-
complete submission for the web app's index. One job, done well.

**Is not:** a second way to browse Glyph Sleuth's content, a font editor, a font viewer
with feature parity to the web app, or anything that requires an account or a persistent
connection. It needs network access only to submit the final record (or none, if the
submission step is a manual PR, matching the web app's existing "indexing is a pull
request against a metadata file" contribution model).

## 3 · What it computes, per font file selected

| Fact | Source table | Feeds |
| --- | --- | --- |
| Codepoint coverage | `cmap` | `FAMILIES[].covers`, `FONT_DETAIL[].coverage` |
| Script tags declared | `GSUB`/`GPOS` script list | `FAMILIES[].tag`, `FONT_DETAIL[].tags`, `SHAPING[].tags` |
| Lookup counts per feature | `GSUB`/`GPOS` | `SHAPING[].gsubN/gposN/featN`, `SHAPE_BASE` |
| Axis ranges, if variable | `fvar` | `FONT_DETAIL[].axes` |
| Graphite presence | `silf` | `SHAPING[].graphite` (the field Feature 3 adds) |
| Shaping verdict per sequence | HarfBuzz, run locally | `FONT_DETAIL[].results`, feeds `font.evidence` |
| Shaping verdict, platform shaper | DirectWrite (Windows) / CoreText (macOS), run locally | `FONT_DETAIL[fontId].results[seqId].dw` / `.ct` (see `addendum-matrix-final.md`) |

The shaping step reuses the *exact same* `SEQUENCES` list already authored for the web app
— same codepoints, same `needs[]` features, same expected `out` — so the two products
share one definition of what "clean / caveat / fail" means. Neither product should carry
its own copy of that list once this is built; the web app's `SEQUENCES` becomes the shared
source, exported to or vendored into the companion.

Once the shaping-engine matrix is built, the companion is also the source of `dw` and `ct`
values: on Windows it additionally shapes the family's sequences through DirectWrite, on
macOS through CoreText, and includes whichever of those it could reach in the submitted
record. A contributor running it from one machine only fills in what that machine can
reach — the record just carries whichever engines were actually available, same
provenance discipline as everything else (checksum, companion version, timestamp) applied
per engine tested, not assumed for the ones that weren't.

## 4 · Output record — provenance, not just numbers

A record is only as trustworthy as its ability to be rerun by someone else. Every emitted
record carries:

- **A checksum of the font file** (sha256), so "covers 118/118" is a falsifiable, rerunnable
  claim, not an assertion — the same spirit as the `hb-shape` command lines already added
  to the evidence tables this round.
- **The companion app's version**, and **the pinned fontTools/HarfBuzz versions it used.**
  Two contributors on different HarfBuzz versions can get different shaping verdicts for
  the same font; the record has to say which build produced this one, the same way the
  site's footer already stamps "HarfBuzz 8.4.0 · 2026-07-14."
- **A computed-at timestamp.**

None of this is optional. An unstamped record is exactly the kind of unverifiable claim the
rest of the app is built to refuse.

## 5 · Submission flow

One JSON record (or a diff against an existing one) per font file, shaped to match the web
app's real data tables once those stabilize. Submission is a pull request against the same
metadata file the "Add a family" flow already describes — this *is* that flow, just
produced by a tool instead of typed by hand. This also gives the brief's "Arrival"
contributor journey ("a visible, dignified route from 'this is incomplete' to 'here is how
you fix it'") its actual mechanism, rather than leaving it as a promise.

## 6 · Why this stays a TODO, not a build item, yet

Two real blockers, not just priority:

- **Schema isn't settled.** The companion's export format has to match `FAMILIES`/
  `FONT_DETAIL`/`SHAPING` — and those are still changing (Feature 3 alone adds `graphite`
  to `SHAPING`). Building the exporter now risks reworking it once Compare, Identify and
  the matrix land.
- **It's a distributed, volunteer-driven data model, not a bulk import.** A responsive
  foundry (SMC, Google, SIL) could run it as part of their own release process and produce
  immediate high-value coverage; the long tail of families still depends on someone
  actually running the tool against them — the same shape of bottleneck as the per-script
  editorial research pipeline (see `addendum-community-issues.md`), just for numbers
  instead of prose.

Recommended order: finish the web app's remaining features and data shapes first, then
spec the companion's exporter against the settled schema, rather than the reverse.
