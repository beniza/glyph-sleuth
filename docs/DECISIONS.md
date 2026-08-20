# Decisions

Standing rules, and why they stand. Not a task list — the board holds open work.

A decision here governs code that has not been written yet, so it lives with the
code rather than in an issue: it must be readable before someone edits
`gen_index.py`, it must version in the same commit as the behaviour it describes,
and it must load into the context of whoever — or whatever — is working.

**Revisions are kept, not overwritten.** Two of these have been revised, and in
both cases the original reasoning is why the revision could be judged rather than
re-argued from nothing. Add to an entry; do not rewrite its history.

Each entry: the rule, the date it was settled, what it costs, and what would
make it wrong.

---

## D1 · Scope: if it answers a question, it is in

**Settled** at the outset, carried from the archive, restated verbatim because
it has decided every feature since:

> If it answers a question, it's in. If it changes a file, it's out.

Read-only inspection is in scope. Anything that writes a font, a UFO or a PDF
belongs in `pysilfont` and `smith`, which already do it better and belong in a
build, not behind a GUI.

**What would make it wrong:** nothing yet proposed. It is the reason this project
is finishable.

---

## D2 · The font-file policy: fetch and parse, serve only what the licence allows

**Settled** 2026-08-16. **Revised** 2026-08-18. Both revisions kept below,
because both were cases of a rule being stricter than anything required it, and
the second cost real correctness before it was caught.

**Fetch and parse. Serve only what the licence allows.**

`BRIEF.md` §4 said no font binary may be *fetched* "even transiently in a
build pipeline". That is stricter than the brief it consolidates: `chat1.md` §10
forbids **hosting** ("no hosted fonts that cannot be freely licensed... never
edits, generates or hosts fonts") and forbids uploading what the visitor types,
but says nothing about a build step reading a public font. The stricter reading
came from a Claude Design sandbox limitation that
`addenda/addendum-desktop-companion.md` §1 itself calls "not a constraint on the
shipped product".

Built strictly, Manjari, Gayathri, Meera and RIT Rachana — the faces the whole
prototype is designed around — would read *not measured yet* indefinitely, and
tiers 2 and 3 would be unevidenced for every family including Google's, since
Google's metadata carries coverage and nothing else. The load-bearing
distinction is redistribution, not reading. So:

- CI may download a publicly released OFL/GPL+FE font, parse `cmap`, `GSUB`,
  `GPOS`, `fvar` and `silf` in memory, run HarfBuzz against it, and discard the
  binary. Redistribution carries the legal weight, and none happens.
- **Serve only what its own licence permits, and only the foundry's own build.**
  Revisited on 2026-08-18, and this is the second correction in this section.
  "Never serve a font file" was, again, stricter than any brief required, and it
  cost exactly the families the site is for: RIT publishes its Malayalam faces as
  a GitLab job artifact and SIL as a tarball, neither behind a stylesheet, so no
  browser could reach them. Every page that named one — the specimen, the
  evidence matrix, the glyph grid, the lookup rules — drew it in whatever the
  browser fell back to, under a verdict of its own. The page was asserting a
  drawing it had not made, which is the one thing this site may never do.

  Both foundries ship a `woff2` build and their licence in the same archive. So
  `gen_index` reads the licence out of the release, and where it is one that
  permits redistribution (`REDISTRIBUTABLE`) it writes that foundry's own files,
  byte for byte, to `web/webfonts/` — every face of the family, not only the
  regular, so the weight and italic controls can offer faces that exist. Which
  face is which comes from each file's own `OS/2`, and which files belong to the
  family comes from each file's own name table; neither is guessed from a
  filename. Coverage, script tags and shaping stay the regular's, because those
  are what the family page reports. We convert nothing and rename nothing: a
  release with no `woff2` gets no webfont, because a file we generated is not
  the file the foundry released. The gate denies by default — an unreadable
  licence means no webfont — and `test_gen.py` asserts there is exactly one
  writer and one directory.

  Specimens otherwise render from Google's CDN or the foundry's own stylesheet.
  Where none of the three applies, **the page says so and draws nothing** — see
  `can_draw()` and `why_not_drawn()` in `render.py`.
- **Never commit a binary.** Downloads are CI-only, cached, gitignored.
- **Provenance on every computed fact** — source URL, release tag, checksum,
  date.
- **Pin releases and degrade gracefully.** A moved URL keeps the last good
  record and marks it stale; it never fails the build or drops a family in
  silence.

The visitor-facing promise is unchanged: nothing typed leaves the browser, no
uploads, no accounts.

GitHub Actions has Windows and macOS runners, so DirectWrite and CoreText
verdicts can come from CI too. That does not make the companion pointless — it
re-points it at the case CI genuinely cannot reach, which is also the higher-
value one for this audience: fonts that are not publicly downloadable at all
(unreleased, in development, proprietary, SIL-internal).

---
---

## D3 · Method: test-driven, and the browser is the gate

**Settled** at the outset.

Every non-trivial unit gets its failing test first. The tests gate the deploy —
a red suite must not reach the site.

Added 2026-08-18, after four browser-only bugs reached production: the Playwright
suite is not optional. Every bug in this project that reached a deploy was the
same kind — a page that passed every unit test and was wrong when a person looked
at it. Unit tests cannot see a nav item that 404s, a long word painting over its
neighbour, or a face reported as not drawing a character it draws.

Two corollaries learned the hard way, both recorded in `CONTRIBUTING.md`:

- Prefer a test that kills a **class** of bug over one that pins a page.
- An assertion is only as good as its premise. If a test has never been seen to
  fail, break the code deliberately and watch it fail before trusting it.

**What would make it wrong:** nothing. The suite is a gate, not a suite — keep it
cheap, and it stays worth having.

---

## D4 · Static, not a database

**Settled** 2026-08-18, reconsidered at ~34,000 pages and declined on
measurements rather than on principle.

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

---

## D5 · Not doing, and why

Each of these was proposed and declined. They are here so the next person to
propose one starts from the reasoning rather than from scratch — and so that
if the reasoning stops holding, that is visible.

- **Publishing glyph outlines as SVG.** It would let unencoded glyphs be drawn
  without a webfont, but shipping the outlines of every glyph is redistributing
  the font in another format. The current approach — letting the browser shape
  the input — shows the same glyph and hosts nothing.

- **A score, or a ranking, in Compare.** Two families with identical rows still
  differ in ways the table cannot see.
