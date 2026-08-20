# Contributing

## The rule the whole thing turns on

**Never state something the data does not support.**

That is not a style note, it is the product. A page that says a font draws a
character it does not, or prints a verdict beside a rendering it did not make,
is worse than a page that says nothing — because a reader cannot tell the
difference and will act on it.

In practice it means:

- "not measured yet" for a family whose file we never read, never zero coverage.
- "not read" where only a foundry's metadata exists, never "declares none".
- Every cap is disclosed: 24 faces of 37, 256 chart cells of 20,992, the first 96
  characters of a hex dump — and copy still hands over the whole value.
- Provenance carries the date the file was actually read, so a cached
  measurement cannot claim we opened a release we have not.
- A control the browser cannot honour does not ship. There is no mlym/mlm2
  switch because nothing in CSS selects an OpenType script tag, and no weight is
  offered that the family does not publish.

Issues that break this rule get the `honesty` label. Several bugs found this way
had passed every unit test.

## Running it

```sh
pip install -r requirements.txt
npm ci && npx playwright install chromium

python web/build/gen_index.py --limit 40   # data; drop --limit for all of it
python web/build/render.py                 # site/
npx playwright test                        # live tests, starts its own server
node web/tests/serve.mjs                   # or serve it yourself at :8787
```

The site is served under `/glyph-sleuth/`, never the root. Absolute URLs written
from `/` give an unstyled page and a wordmark pointing at the domain root —
everything internal goes through `render.link()`, and `SITE_BASE=""` builds for a
root domain. The test server deliberately serves under the prefix so this cannot
pass locally and fail in production.

## Tests, and which one to reach for

| Suite | Run | Covers |
| --- | --- | --- |
| Python | `python -m pytest web/build` | the generator and the renderer, against markup |
| Node | `npm run test:unit` · `npm run test:data` | `core.js`, and the served tables against the code that reads them |
| Browser | `npx playwright test` | what only a browser can answer |

**Run the browser suite before pushing anything that touches a page.** Every bug
in this project that reached a deploy was the same kind: a page that passed every
unit test and was wrong when a person looked at it. A nav item that 404s. A long
word painting over its neighbour. A face reported as not drawing a character it
draws. `document.fonts.check()` answering true for a family that does not exist.

Non-trivial logic leaves a runnable check behind, and the failing test comes
first. Prefer a test that kills a *class* of bug over one that pins a page: the
`/char/` fallback fix was correct and the lesson never left that function, so
three other page types stayed broken for weeks.

An assertion is only as good as its premise. Two of this project's tests were
written on premises that were simply false — "heavier draws wider" is not a law,
and metric-compatible families keep every weight the same width on purpose. If a
test has never been seen to fail, break the code deliberately and watch it fail
before trusting it.

## Build cost, measured

Kept so nobody re-derives it. Numbers from the CI run of 2026-08-18,
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

## The board

<https://github.com/users/beniza/projects/10>

Columns are **Status**. GitHub does not offer Milestone as a group-by, so the
release lives on the card and in the view filters instead.

| Status | Means |
| --- | --- |
| Todo | Staged for its milestone, not started |
| In Progress | Being worked on now |
| Blocked | Waiting on something outside this card. Say what, in a comment |
| In Review | Tests green and pushed, waiting on the deploy |
| Done | Deployed and verified live |

### Views

| View | Shows |
| --- | --- |
| **All work** | every open card, across every release |
| **v0.4.0** | `is:open milestone:"v0.4.0"` — the one to work in |
| **Inbox** | `is:open no:milestone` — where new issues land |
| **Backlog** | a flat table, for triage |

### The loop

Add an issue freely; it appears in **Inbox**. Give it a milestone to stage it.
Work the release in its own view, moving cards left to right. When the view is
empty, tag it.

**Labels** carry the kind: `bug`, `feature`, `test`, `docs`, `perf`, `a11y`,
`honesty`.

There are no task lists in the repo. `docs/DECISIONS.md` holds the standing
rules, `docs/BRIEF.md` the original brief; everything that is *work* is a card.

## Commits, releases and deploys

- **One feature per commit and per deploy.** A push costs about five minutes and
  each deploy is independently verifiable; batching concentrates risk into a diff
  nobody can bisect by eye.
- **Commit messages carry the why**, including what was wrong before. For several
  decisions in this repo the commit message is the only record.
- **Small releases, often.** An annotated tag, `vX.Y.Z`, headline `X.Y.Z: short
  summary` then prose. Do not hold work back to justify a bigger number.
- **Never re-run a failed deploy job.** It uploads a second artifact named
  `github-pages` and the next attempt dies on "Artifact count is 2". Push a fresh
  commit or use `workflow_dispatch`.

## Traps, each of which cost real time

- **Slugs must keep Unicode.** RIT's families name themselves in Malayalam;
  stripping to `[a-z0-9]` gave an empty slug, so those pages were written to
  `/font//index.html` and overwrote each other.
- **HarfBuzz does not read woff2**, which is what foundries serve. Handed
  compressed bytes it returns `.notdef` for everything and every family looks
  broken while being fine.
- **Google's metadata JSON has an anti-hijacking prefix** (`)]}'`). Drop the strip
  and every family fetch fails with "Expecting value: line 1".
- **`document.fonts.check()` cannot say no.** Chrome answers true for a family
  that does not exist. What is provable is whether our `@font-face` arrived.
- **Advance-width comparison cannot detect a fallback.** One glyph is one advance;
  two fonts for a script collide on round numbers, and a locally installed family
  is indistinguishable from a fallback by measurement.
- **Editing JS or CSS through a shell heredoc mangles `\n` escapes.** Use a file
  tool, or a patch script with a named `NEWLINE = chr(10)`.
- **`site/` is generated.** `core.js`, `copy.js`, `inspect.js`, `tryit.js` and
  `webfonts/` there are copies; they are gitignored.
- **The CI token is GitHub's.** It goes to GitHub hosts and nowhere else — it was
  once sent to gitlab.com with every RIT download, which answered 401.
- **Profile against a realistic corpus.** Seven local fonts said the build was
  I/O-bound; with 1,885 the real cost was `O(families × blocks × languages)`, and
  a language page took 18 seconds.

## Font files

We may read any font; we re-serve only what its own licence permits, and only
the foundry's own build. See **D2** in [`docs/DECISIONS.md`](docs/DECISIONS.md)
— it has been revised twice, and both revisions are kept, because both were
cases of a rule being stricter than anything required it.

Every standing rule lives in that file. Read it before changing what the build
publishes.
