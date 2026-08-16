# Shaping-engine matrix — final settled spec

*Supersedes the open questions in README.md's "Feature 3 — Shaping-engine matrix" section.
The base spec (per-sequence `{hb, dw, ct, gr}` shape, the three verdict/not-tested/not-
applicable treatments, the font-page four-column evidence table, the required legend, and
the hard rule against inventing `dw`/`ct`/`gr` values) stands as written. This resolves
everything that was still open.*

## Resolved

**DirectWrite and CoreText verdicts come from the desktop companion, not a separate
mechanism.** When the companion runs on Windows, it also shapes the family's sequences
through DirectWrite; on macOS, through CoreText — emitting those verdicts into the same
submitted record as the cmap/GSUB/GPOS/`fvar`/`silf` facts (see
`addendum-desktop-companion.md`, which this extends). One contribution pipeline produces
every fact on the site, rather than a second, undefined "external test run" process. A
contributor running the companion on Windows fills in `dw` for whatever they test; a
contributor on macOS fills in `ct`; nobody running it fills in both from one machine, and
that's fine — the record just carries whichever engines were actually reachable from
wherever it ran, stamped with the same checksum/version/timestamp provenance as everything
else the companion produces.

**The compact per-script strip lives in the filter-chips row**, not "beside the collapse
bar" — that bar was removed earlier in the design and doesn't exist in the current build
(its data, `collapseData`, is defined but never rendered — dead code to clean up whenever
this is implemented). The filter-chips row already shows at-a-glance counts ("all 61 /
shapes cleanly 19 / declares only 15 / covers only 27"); the engine-tested strip (`61 / 0 /
0 / 0`) sits there as a sibling to it, not as a floating element referencing UI that isn't
there.

**The site's primary verdict stays HarfBuzz-defined for now.** Family badges, filter
counts, and the font page's headline "shapes: clean/caveat/fail" continue to mean
"HarfBuzz says so," unchanged, even once DirectWrite/CoreText data starts arriving. The
matrix is an added transparency layer on top of that, not a change to what the primary
classification means. Revisit only once real cross-engine data exists in enough volume that
a font disagreeing across engines is a common rather than hypothetical case.

## Unchanged from the base spec

The `{hb, dw, ct, gr}` per-sequence shape, the three-treatment rendering rule (verdict /
"not tested" in Faint / "not applicable" in Faint), the four-column font-page evidence
table with shaped output shown only under HarfBuzz, the required legend explaining why
DW/CT are empty, and the non-negotiable rule against populating any of the three new
columns with invented values.

---

With this, all three previously-unbuilt features from the updated bundle (Compare,
Identify, the matrix) and the Phase 4 provenance/version-history decisions are settled.
Nothing from the bundle remains open except the desktop companion itself, which stays a
TODO by design until the web app's data shapes are locked in by building the above.
