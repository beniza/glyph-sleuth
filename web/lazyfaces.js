// Faces for tiles the reader has actually scrolled to.
//
// A character page can be covered by nine hundred families. Every tile is in the
// markup — it is a few hundred bytes — but nine hundred webfonts is ninety
// megabytes, so the faces arrive as they are needed.
//
// The ordering here is the whole point, and it is a safety property rather than a
// performance one. A tile without its face has not been drawn by the family it
// names, so it must not carry `data-face` yet: the fallback marking in app.js
// would mark all of them as failed on load, and a page crying wolf about eight
// hundred families is worse than a page showing twenty-four. So each tile keeps
// `data-family` plus what a face needs, and only becomes a `data-face` claim once
// the face is really there.
//
// With JavaScript off none of this runs and none of it is missed: the first
// DRAWN_LIMIT tiles have their faces in the markup, and the rest are a list of
// family names, each a link to a page that draws it.

// Any panel that asked for its faces later — the character grid's tiles, the
// language page's cards, and Inspect's tiles, which it builds after the page
// has loaded and so hands over itself. Asked-for families are remembered across
// calls: Inspect redraws on every keystroke and must not fetch a face twice.
const head = document.head;
// family -> settles once its stylesheet has arrived or failed. Not a Set: a
// family asked for by an earlier redraw may still be on its way, and a tile
// waiting on it must wait too.
const asked = new Map();

/** Append a stylesheet and settle when it has loaded or failed. */
const sheet = (href) => new Promise((settle) => {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = href;
  link.onload = link.onerror = () => settle();
  head.append(link);
});

// Google takes every family in one request, which is the difference between
// forty stylesheets and two. Batched, not one-per-tile.
const BATCH = 20;

/** Load faces for `tiles` as they are scrolled to, and keep `note` honest about
 *  how many have been drawn. Returns a function that stops watching. */
export function watch(tiles, note) {
  const pending = [...tiles];
  if (!pending.length) return () => {};

  const load = (tiles) => {
    const google = [];
    const waits = [];
    for (const tile of tiles) {
      const family = tile.dataset.family;
      if (!family) continue;
      if (asked.has(family)) {
        waits.push(asked.get(family));
        continue;
      }
      const css = tile.dataset.css;
      if (css && css.includes("fonts.googleapis.com")) {
        google.push(family);
      } else if (css) {
        asked.set(family, sheet(css));
      } else if (tile.dataset.rule) {
        const style = document.createElement("style");
        style.textContent = tile.dataset.rule;
        head.append(style);
        asked.set(family, Promise.resolve());
      }
      if (asked.has(family)) waits.push(asked.get(family));
    }

    for (let at = 0; at < google.length; at += BATCH) {
      const batch = google.slice(at, at + BATCH);
      const query = batch.map((f) => `family=${f.replace(/ /g, "+")}`).join("&");
      const arrived = sheet(`https://fonts.googleapis.com/css2?${query}&display=swap`);
      for (const family of batch) asked.set(family, arrived);
      waits.push(arrived);
    }

    // The claim is made only now, and only after the face has had its chance to
    // arrive — and then it is checked, here, because app.js runs its check once
    // on load and these tiles did not exist as claims at that point. Promoting
    // them without checking left a lazily-loaded face that failed to arrive
    // silently presented as a drawing, which is the exact bug the eager path has
    // a test for.
    //
    // Waiting on the stylesheets first is not optional. `document.fonts.ready`
    // knows nothing of a <link> still in flight, so it settled at once, the
    // check found no @font-face for the family, and every lazily-loaded foundry
    // family — all of SMC's — was marked as not drawing a text it drew.
    Promise.all(waits).then(() => document.fonts.ready).then(async () => {
      const promoted = [];
      for (const tile of tiles) {
        if (!tile.dataset.family) continue;
        tile.dataset.face = tile.dataset.family;
        delete tile.dataset.family;
        tile.classList.remove("waiting");
        promoted.push(tile);
        counted();
      }
      if (!promoted.length) return;
      const { markMissing, noteFallbacks } = await import("./facecheck.js");
      if (await markMissing(promoted)) noteFallbacks();
    });
  };

  const total = pending.length;
  let done = 0;
  const counted = () => {
    done += 1;
    // The page said "showing 24 of 912" before. While loading it says how many
    // have actually been drawn, because a tile in the page font is not a drawing
    // of this family and the count must not pretend it is.
    if (!note) return;
    if (done >= total) note.textContent = note.dataset.drawnNote || "";
    else note.textContent = `Drawing ${done + total - pending.length} of ${total} more `
      + "families as you scroll — each one is a webfont, so they arrive when you reach them.";
  };

  for (const tile of pending) tile.classList.add("waiting");

  // rootMargin so a face is asked for slightly before it is looked at.
  const watcher = new IntersectionObserver((entries) => {
    const arrived = entries.filter((e) => e.isIntersecting).map((e) => e.target);
    if (!arrived.length) return;
    for (const tile of arrived) watcher.unobserve(tile);
    load(arrived);
  }, { rootMargin: "400px" });

  for (const tile of pending) watcher.observe(tile);
  return () => watcher.disconnect();
}
