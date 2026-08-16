# Compare — final settled spec

*Supersedes the open questions in README.md's "Feature 1 — Compare" section from the
updated bundle. The base spec (route, layout, the 14 rows, the differ/agree mechanic, the
honesty constraint against scoring) stands as written. This resolves everything that was
still open. No further design-tool round trip is planned — this is the spec to build
against.*

## Resolved

**Scope: single-script for now.** Compare operates within the script you arrived from
(Malayalam, currently) — no script parameter in the route yet. Rows 5–13 (coverage,
sequences, per-language fit) are understood to mean "within this script" implicitly.
Expanding to a script-scoped route (`#/compare/Mlym/manjari,gayathri`) is future work, not
in scope now — noted so the route isn't accidentally designed to preclude it later, but not
building it yet.

**Family picker: any two of the 1,885, not just the six detailed ones.** A row for which a
family has no computed data states that plainly — "not tested" or "no data yet," in Faint,
same convention the shaping matrix already uses for untested engines. This is not a
degraded mode to apologize for; it's the same honesty rule the whole app runs on.

**Two families, not "two or more."** Confirmed as an intentional descope from the original
brief's "two or more." A third column is out of scope; revisit only if a real need surfaces
later.

**Nested-row counting, resolved.** Two rows (6 "Coverage by block," 12 "Per-language fit")
each contain multiple sub-facts rather than one value per family. The top-level "N of 14
rows differ" count stays literal — a nested row counts as ONE differing row the moment any
sub-fact inside it differs, matching the visible 14-row list exactly. Independently, within
that row, only the sub-facts that actually differ get the blue-border/full-contrast
treatment — so the fine grain is still visible, it just doesn't inflate the headline
arithmetic into something that no longer matches what's on screen.

**Permalinks: all four state values encode in the URL**, not just the family pair. `a`, `b`,
`size` and `diffOnly` all round-trip through the hash (`replace`, not `push`, per the
existing spec, so the back button still leaves the page rather than stepping through every
slider tick). This closes the permalink gap flagged earlier on the font and script pages —
Compare should be the page where "send someone proof" actually works end to end.

**No guessed default pair.** Drop `manjari,gayathri` as a fallback entirely. Every entry
point supplies only what it actually knows and leaves the rest genuinely open:

- From a font page's "Compare with another family" link: the family you were viewing
  pre-fills the left picker; the right picker starts empty with a prompt — "Choose a family
  to compare against Manjari."
- From the nav bar or a cold `#/compare` with no params: both pickers start empty —
  "Choose two families to compare."

One rule for both cases, not a guessed default in one path and an honest empty state in the
other.

## Unchanged from the base spec

Route shape, the 14 rows and their order, the differ/agree visual treatment, the
differences-only toggle, and the constraint against computing a winner or aggregate score.
