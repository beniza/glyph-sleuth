# TODO

Backlog for Glyph Sleuth, newest ideas at the top. Everything here is a *want*,
not a commitment — the scope rule in the README still decides: **if it answers a
question, it's in; if it changes a file, it's out.** Every item below answers a
question or hands you something to take away, so all of them pass.

## Open

### 1. A font index

A page listing every indexed family, browsable rather than searched — the thing
you land on when you don't yet know what you're looking for. Sort by name, by
foundry, by coverage; filter by script. Today the only ways in are a search box
and the Browse block grid, so a family with an unfamiliar name is unreachable
unless you already know it.

*Where:* a sixth mode in `web/app.js` beside Search/Preview/Browse. The data is
already loaded (`core.data.fonts`); this is a table plus filters, not a new index.

*Open question:* one row per family with a specimen, or the tile wall used for
single characters? Depends whether the sample text is fixed or per-script.

### 2. Rich text / Markdown editor for the preview

Preview takes a plain textarea. A small editor would let you set a real page —
headings, bold, a list — and see whether a family holds up across weights and
sizes, not just at one size in one style. Markdown is the lighter of the two:
no toolbar, no formatting model to fight, and it degrades to what we have now.

*Where:* `#preview-text` in `web/index.html`, rendered into the specimen entries.

*Careful:* bold and italic mean loading more than the regular face — the index
records one face per family today, so the ranking would need to know which
weights a family actually has. Google's metadata has `fonts` per family (weights
and styles); the foundry path would need it read from the release.

### 3. Download the specimen sheet as PDF

A specimen sheet is a thing you print or send. `window.print()` with a print
stylesheet gets 90% of it for almost no code, and the browser's own "Save as
PDF" does the rest. A generated PDF (pdf-lib and friends) would embed the fonts
properly but is a much bigger build and re-raises the licensing question we
avoided by never hosting fonts we can't redistribute.

*Start with:* `@media print` in `web/style.css` — hide the chrome, keep the
entries, force light colours, and let each specimen break cleanly.

### 4. Copy glyphs: click to copy, or collect a set

Click a glyph in the Browse grid or the tile wall to copy it. Shift-click (or a
tray) to collect several and copy them together — the workflow when you are
assembling an orthography's characters to test a font against.

*Where:* `.cell` in Browse and `.tile` in the glyph wall already have click
handlers (they run a search). Copy needs to be a second, explicit action —
probably a small "copy" affordance on hover so clicking still navigates.

*Nice with it:* a persistent tray that feeds straight into Preview as the sample
text, which closes the loop between "these are my characters" and "which fonts
set them".

### 5. Alt+X to swap codepoint and character

Word's trick: type `0D15`, press Alt+X, get ക; put the caret after ക, press
Alt+X, get `0D15`. In the search box this is faster than either notation on its
own, and it is muscle memory for anyone who has typed Unicode in Word.

*Where:* a `keydown` handler on `#omni` in `web/app.js`. The parsing is already
done — `core.parse` reads every codepoint notation, and `core.hex` writes one.

*Careful:* Alt+X is not reserved on all platforms and screen readers may claim
it; make it additive, never the only way to convert (Convert mode stays).

## Done

### Language & script opens on the default script — shipped

`Language & script` opened Malayalam on **Arabic**, because the scripts sorted
alphabetically. SIL langtags marks the default by giving the bare tag its script
(`ml` is `Mlym`; `ml-Arab` is the other way Malayalam is written), so that one
now leads and the rest follow.

Verified live: Malayalam offers `Mlym, Arab, Brai` and opens on Malayalam; Hindi
offers `Deva, Brai, Latn, Mahj, Modi, Newa` and opens on Devanagari.
Commit `4c6d018`.
