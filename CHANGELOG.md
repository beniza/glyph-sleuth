# Changelog

What changed in each release of Glyph Sleuth, newest first. The annotated
release tags carry the full notes, including what went wrong on the way; this is
the summary. Commit messages carry the reasons.

## Unreleased

### Added

- **A block in a family's coverage table leads to its glyphs.** Each block links
  to the glyphs page filtered to it, which has a block filter of its own. Each
  glyph now records every codepoint it draws, not only the first (space and
  no-break space are usually one glyph), so a block's glyphs add up to the
  coverage the family page gives. Where they cannot — Google's figure is for the
  whole family, the list for one file — the page says so.
- **A Try it link keeps how the text was set**, not only the text: `px` for the
  size, `weight`, `italic=1`, and `off=` for the features switched off — for
  example `?text=…&px=48&weight=700&off=akhn`. A setting the family does not
  offer is ignored.
- **A shortlist in Inspect, to choose a font and send the choice.** Set the
  text at a size, weight and italic; star the families you like; rank them by
  dragging or with ↑ ↓; copy a link. The recipient lands on that shortlist, in
  that order and setting, with every other family that has the text one click
  away and never removed. Each family is set in the nearest face it publishes,
  and says so where that is not what was asked — nothing is emboldened or
  slanted by the browser. Feature switches stay on each family's Try it, which
  every name links to with the same text and setting.

### Fixed

- **A mark in Inspect's codepoint list showed two dotted circles in Firefox.**
  The cell had no font of its own, so the circle and the mark fell back to
  different fonts, and the second font's shaper added a circle for a vowel sign
  with nothing before it. Each mark is now drawn by one family that has both.
  Firefox runs in the deploy's tests for this.
- **SMC's families were offered in one weight.** SMC hosts its own stylesheet,
  so no face list came with it: Manjari — Thin, Regular and Bold — had no weight
  control in Try it. The faces are now read from that stylesheet.

## 0.6.1 — 2026-10-18

Fixes: links that went nowhere, filters that showed nothing, a page that asked
one host for too much, and measurements that were dropped or passed off as fresh.

### Fixed

- **Inspect's link to r12a's String Analyser opened it empty.** It passed the
  text as `?text=`; the analyser reads `?chars=`, on `index.html`.
- **`/mockup/` says it is the old design prototype** (#11), with hand-written
  figures, so it is not read as the current site.
- **A script can be found by a language written in it** (#86). Filtering the
  scripts index for "Chinese" found nothing, because the rows named scripts;
  each row now names a few of its languages and matches all of them.
- **A character page asks a foundry for fewer files up front** (#93). It loaded
  24 faces eagerly — twelve stylesheets and a dozen woff2 files from one host for
  `/char/0D15/`, queued behind the browser's per-host limit. It loads 8, and every
  other family still has its tile, drawn as it is scrolled to.
- **A release out of reach keeps its last reading, and says so** (#6). A family
  whose release lookup failed — a moved URL, a host down — dropped to "not
  measured yet", and a reading kept after a failed download looked like one made
  today. The last good reading is kept in both cases, and the font page names the
  day the release could not be reached.
- **A glyphs page's facets list their glyphs.** "Encoded", "built by a rule" and
  "unreachable" showed nothing from the day they were added: the filter compared
  every facet with a font's verdict, which a glyph row does not have. Each
  facet's count is now the number of rows it shows, and a glyph a rule reads but
  none builds is no longer labelled "unreachable".

## 0.6.0 — 2026-10-18

The site says what it is for, measures Latin, and its verdicts stop overstating.

### Added

- **A home page that says what the site is for.** "Does your font draw your
  language correctly?", an input on the first screen, and three cases of the same
  text drawn differently — Vietnamese stacked accents, the Malayalam nta typed
  two ways, the Marathi eyelash ra. Every number and example in them is computed
  from the verdicts at build time, and each broken example is chosen to look
  broken in every browser, whether or not it applies the page's language.
- **Latin is measured.** Vietnamese ế and ệ and Yoruba ẹ́, judged by the ink:
  accents that collide, or that stand beside their letter, fail. About 765
  families are now opened and read, up from about 100.
- **A features index** at `/feature/` (#97), and feature examples drawn by real
  families with only that feature switched on or off, kept only where the build
  saw a difference (#98).
- **Scripts that fonts cover are listed** even when no indexed language uses
  them (#99): 84 scripts to 163, Odia, Ol Chiki and Meetei Mayek among them. Each
  carries its ISO 15924 name — "Oriya (Odia)", "Bengali (Bangla)" — and lists
  every language SIL's langtags writes in it.
- **More languages.** Those whose UDHR translation is not yet checked are indexed
  against SLDR's characters, with no sample text and a page saying why (#100);
  526 languages to 563. Every other language langtags records is findable in the
  languages index and leads to its script (#101).
- **Links into a page.** Every section heading has a fixed id and a "copy link"
  button; index filters and Try it's text are kept in the address; the site
  checker fails a link to a section that does not exist.
- **Inspect draws the text in every family that has every codepoint of it**, not
  eight families chosen for covering a whole block.
- **Every page says which build it is** — version, commit, build day and the day
  the fonts were read — in its footer and in `/version.json`.
- **Releases are published by a workflow** that refuses unless the tag, the
  version in `package.json`, this changelog and a green deploy all agree. 0.6.0
  is the first.

### Fixed

- **Shaping verdicts** (#96). The recommended nta was compared with itself and
  could never fail; Baloo Chettan 2, Rachana and Meera were called clean on a
  conjunct they never form. A conjunct is now checked against the same text with
  joining refused; a form the font cannot draw is no longer the yardstick; the
  expected form is shaped in the same language; and each verdict records the
  language it was shaped in, and its result without one.
- **A second number no longer changes what the first one means.** In Inspect and
  Try it, `2018` was U+2018 and `2018 2` was U+07E2 and U+0002: bare digits were
  hex alone and decimal in a list. They are hex in both now, with the decimal
  reading still offered; decimal has its own notation, `&#2018;`, which used to be
  read as plain text.
- **A family is judged on its own script.** Malini, a Malayalam family, was listed
  as one that "breaks" for lacking Devanagari.
- **Two spellings of one text** (ệ against e + dot below + circumflex) are no
  longer compared, which had given nearly every font without a composed ệ a
  caveat.
- **A slow foundry stylesheet** was reported as a face that did not load.
- **Bracketed UDHR names** such as "(Bataknese)" sort by their letters instead of
  opening every list of languages.
- **Malayalam** lives at `/lang/mal/`, not `/lang/mal_chillus/`.
- **The site checker** resolved absolute links under the real `site/` whatever it
  was given, so its own tests passed only where a local build had the page.

### Changed

- Each verdict now carries the language it was shaped in, and the cache re-reads
  any font measured by an older check.
- The deployed site grew from about 87 MB to about 106 MB compressed with Latin
  measured.

## 0.5.0 — 2026-08-21

The reported bugs, and the two more that fixing them uncovered.

- Inspect said how many families it was not showing, and linked the block page.
- Japanese and Korean got script pages: composite codes (`Jpan`, `Kore`) and
  variants (`Hans`, `Hant`) were dropped without a word. A drop report now names
  any code that resolves to nothing.
- The scripts cache keyed on its inputs alone served the answer from before the
  fix; the composite table is in the key now.
- `/script/Hani/` went from 2.5 MB to 59 KB, its charts bounded and disclosed.
- Charts and headline glyphs stopped being tofu where a covering family exists.
- Inline link lists became real lists.

## 0.4.3 — 2026-08-21

Every remaining cap, and a rule so the next one cannot be silent.

- A test fails on any literal slice in the renderer that is neither in `capped()`
  nor allowlisted with a reason.
- The block and script pages list every covering family; the caps that remain
  say what they leave out.

## 0.4.2 — 2026-08-20

- The language page shows every family that fits, not the first 36.

## 0.4.1 — 2026-08-20

Two releases of one family, and no more caps.

- A family released by both its foundry and Google keeps both, and the page shows
  where they differ.
- A character page carries a tile for every family that covers it, loading as
  they are scrolled to.

## 0.4.0 — 2026-08-20

The build refuses to overstate.

- `check_site.py` runs over the built site: every internal link resolves, and no
  page names a face it has no source for. It found three faults on its first run.
- The glyph inventory says when it stops short.
- A throttled download is retried; a 404 is an answer and is not.

## 0.3.0 — 2026-08-19

The site rebuilt, and the fonts actually drawn.

- The family index, and a page per family, character, block, script and language;
  Compare; Inspect; Try it.
- Foundry webfonts are served where their licence permits, so families with no
  stylesheet are drawn rather than shown in a fallback under their own name.

## 0.2.0 — 2026-08-15

- A licence per family, linked to its text.
- Five libre families with no Google Fonts entry.
- One Malayalam where there were two.

## 0.1.0 — 2026-08-14

- Release binaries for the desktop companion, built only when the tests pass.
