# Glyph Sleuth — open items

From the script-engineer review. Grouped by what it costs to do honestly.

## Cheap and purely mechanical

1. **`v` flag correction.** The four-engine table says JavaScript cannot intersect sets. ES2024's
   `v` flag can: `[\p{scx=Mlym}&&\p{Nd}]`. The Malayalam-digits recipe's rationale rests on the
   wrong claim. Fix the row, add the `v`-flag form, note the browser floor.
   *Data needed: none. Effort: minutes.*

2. **`hb-shape` command lines in the evidence tables.** Generated from data already present —
   family file name plus the sequence's codepoints and features. Claims nothing about output;
   hands the reader a line they can run. Retires "take the verdict on faith" for the cheapest
   possible price.
   *Data needed: none. Effort: small.*

3. **Prev/next codepoint navigation.** `charRecord` already renders any point in the block, so this
   is two links and a boundary check. Should say when the neighbour is reserved.
   *Effort: small.*

4. **Inspect permalink.** Update the hash with `history.replaceState` on a debounce so an inspection
   can be shared without flooding history.
   *Effort: small, needs care not to fight the hashchange handler.*

5. **Keyboard layout links.** One external link per input table, pointing at the Keyman layout that
   produces these sequences.
   *Effort: minutes. Needs the right URLs.*

## Medium, and mostly authoring rather than engineering

6. **Compare view.** Everything it needs already exists: `FAMILIES`, `FONT_DETAIL`, `SHAPING`,
   `SEQUENCES`. Two families side by side — coverage by block, script tags, per-language verdicts,
   the same sequences shaped by both, lookup counts. The route is already linked from every font
   page, so the choice is build it or remove the link.
   *Effort: one build pass.*

7. **Exemplar provenance.** Add the SLDR revision and a link per language, and restructure the
   character groups to CLDR's actual named sets (main, auxiliary, index, punctuation, numbers)
   instead of the ad hoc groupings now in place.
   *Data needed: real SLDR revisions. Effort: small once the data is in hand.*

8. **Per-release version history.** A short changelog per family with the verdict at each release,
   which is what makes "was this fixed in 2.100?" answerable. Chilanka's gap is already described as
   a release artifact; this is what would show it.
   *Data needed: real release lists. Effort: medium.*

9. **Graphite presence.** Scoped to "does this family carry `silf` tables, and if so are its rules
   equivalent to the OpenType ones" — a row per font, not a rule browser. Real answer for the six
   indexed families (none of them ship Graphite; SIL's own fonts do, and none are indexed yet).
   *Effort: small if scoped. Large if it means showing Graphite rules.*

## The expensive one, and the thing that would retire several others

10. **Shaping-engine matrix.** HarfBuzz, DirectWrite, CoreText, Graphite per sequence per family.
    No technical difficulty — it is four columns instead of one — but it multiplies the app's
    authored data fourfold, and authored data is exactly what its credibility rests on. Filling
    three new columns by invention would be worse than leaving them empty.

    Recommended shape: build the matrix structure, populate the HarfBuzz column from what is
    already there, and mark the other three "not tested" until real results exist. The gap becomes
    visible instead of implied.

## What would fix the root cause

Items 2, 6, 9, 10 and the shaping tables all trace back to one thing: the app's font data is
authored rather than read. That is fixable. Given the actual font binaries in the project, a parser
can compute, for real:

- coverage, from `cmap`
- script and language tags, from `GSUB`/`GPOS` script lists
- lookup counts and types per feature
- Graphite presence, from `silf`
- axis ranges, from `fvar`

Shaping verdicts still need a shaper, which a browser cannot provide for an arbitrary font — but
everything above is a table read, and it would make most of the numbers on the font, block and
script pages computed rather than asserted.

*Blocker: the font files have to arrive in the project. Cross-origin fetches are not available, so
they need to be uploaded.*
