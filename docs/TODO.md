# TODO

**Open work lives on the board**, not here:
<https://github.com/users/beniza/projects/10>

Every item that was §1-§10 of this file is now an issue carrying its own
reasoning, staged into a milestone. Columns on the board are the milestone;
`Someday` is real-but-not-scheduled, and no milestone is the inbox.

Two backlogs drift apart, so there is one. What stays here is the material that
is *not* a task and would otherwise be re-derived: what the build costs, and
what we decided not to do.

- Add an issue freely; it lands in the inbox.
- Stage it by dragging it into a release.
- Work the release, then tag it. Small releases, often.

`PROGRESS.md` still tracks the phase plan and what has shipped.

---

## Live testing

`npx playwright test` runs Chromium against the built site, served under
`/glyph-sleuth/` the way Pages serves it — from the root instead, every absolute
URL would resolve by accident and hide the class of bug that shipped once.

It exists because every bug in this project that reached a deploy was the same
kind: a page that passed every unit test and was wrong when a person looked at
it. A nav item that 404s. A long word painting over its neighbour. A face
reported as not drawing a character it draws. `document.fonts.check()` answering
true for a family that does not exist.

Deliberately not a screenshot suite — those flake and nobody trusts them. It
asserts the things that actually went wrong: every nav link resolves, the Tools
disclosure opens by click *and* by keyboard, nothing overflows at 380px, no
drawing spills out of its own box, the fallback marking neither cries wolf nor
stays silent, and the pages still work with JavaScript switched off.

CI runs it after the build and before the deploy, and uploads the report on
failure.

- [ ] It covers five pages at 380px and one flow through Inspect. Worth widening
      as pages change, but keep it cheap: it is a gate, not a suite.

## Build cost, measured

Kept here so nobody re-derives it. Numbers from the CI run of 2026-08-18,
1,885 families and ~34,000 pages:

| step | before | after |
| --- | --- | --- |
| `gen_index.py` | 7m54s | **0m20s** warm, 7m cold |
| `render.py` | 14m29s | **2m48s** |
| upload artifact | 6s | 5s |
| deploy | 16s | 11s |
| **total** | **25m** | **3m46s** |

Three causes, and only the first was the one I expected:

1. **Writing pages** — 19ms of disk wait each, 33,000 of them. Sixteen threads.
2. **Block coverage recomputed per call** — the real render cost, and invisible
   in a seven-font local set. `made_for` asked `dominant_block`, which walked all
   327 blocks, once per fitting family per language, from three separate places:
   **18 seconds per language page**, 526 pages, 157 minutes projected. Computed
   once per family by bisection it is 0.10s a page.
3. **527 UDHR and SLDR fetches** — five and a half minutes of the generator, now
   cached per language, with the script scan and the name table keyed on the
   Unicode version.

The lesson worth keeping: profile against a realistic corpus. Every local
measurement said the build was I/O-bound, because seven fonts never exercised
the O(families × blocks × languages) path that dominated it.

## Not doing, and why

- **Hosting a font we have no licence to.** The rule was once "never host",
  and it was revisited on 2026-08-18 — see `BUILD-PLAN.md`. What stands is
  narrower: we serve the foundry's own build, unmodified, only where a licence
  in the same release permits it, and we convert nothing. A release we cannot
  read a licence for is measured and never re-served.
- **Publishing glyph outlines as SVG.** It would let unencoded glyphs be drawn
  without a webfont, but shipping the outlines of every glyph is redistributing
  the font in another format. The current approach — letting the browser shape
  the input — shows the same glyph and hosts nothing.
- **A score, or a ranking, in Compare.** Two families with identical rows still
  differ in ways the table cannot see.
- **A database with dynamic page generation.** Reconsidered on 2026-08-18, when
  the project had grown to ~34,000 pages, and declined on the numbers.

  The fear is the page count; the measurements say the page count is free.
  Uploading the 33,000-file artifact takes 6 seconds and the deploy 11. Every
  minute of the build was spent *deriving* facts from font files — which a server
  would still have to do, either per request or into a cache that then needs
  invalidating. A database moves that work; it does not remove it.

  What it would cost is specific: GitHub Pages, and with it the brief's "no
  backend, no accounts, no uploads". A server means logs, addresses, uptime, and
  somewhere visitor input could be collected. "Nothing you type leaves the
  browser" is currently structural — there is no server to send it to — and it
  would become a policy claim instead.

  What it would buy is narrower than it looks, and available without a server:
  incremental builds (regenerate only what changed) can use SQLite as a
  build-time store while still emitting static files, and genuine client-side
  querying over the whole corpus can serve a SQLite file over range requests
  (`sql.js` / `sqlite-httpvfs`, the Datasette-Lite pattern) from the same static
  hosting.

  **Revisit when there is per-user state** — accounts, saved comparisons, a
  contribution review queue. Wanting richer queries is not the trigger; wanting
  to remember who is asking is.
