// Did the face we named actually arrive?
//
// Shared by app.js, which checks the faces in the markup on load, and by
// lazyfaces.js, which checks each face it injects on scroll. It lives here
// because app.js ran its check exactly once and lazily-loaded tiles were
// promoted afterwards — so for a while they were never checked at all, and the
// comment claiming otherwise was simply wrong. One implementation, one wording,
// both paths.
//
// Two earlier attempts at this got it wrong and are worth keeping in mind:
//
//   * Measuring advance widths marked Dyuthi as not drawing a character it draws
//     perfectly. One glyph is one advance, two fonts for a script collide on
//     round numbers, and a locally installed family is indistinguishable from a
//     fallback by measurement.
//   * document.fonts.check() cannot say no. Chrome answers true for a family
//     that does not exist, and true for a loaded family asked about a character
//     it lacks, because system fallback counts as available.
//
// What is provable is whether *our* @font-face arrived: the stylesheet either
// produced a FontFace for that family or it did not, and the face either loaded
// or errored.

const unquote = (name) => name.replace(/^["']|["']$/g, "");
const asked = new Map();

/** "" if this family's face is really here, else why it is not. */
export function faceFailure(family) {
  if (!asked.has(family)) {
    asked.set(family, (async () => {
      const faces = [...document.fonts].filter(
        (face) => unquote(face.family) === family);
      // No @font-face at all: the stylesheet did not arrive, or the family is
      // spelled differently there than we think. Either way our face is not
      // drawing this.
      if (!faces.length) return "no stylesheet";
      await Promise.all(faces.map((face) => face.load().catch(() => {})));
      if (faces.some((face) => face.status === "loaded")) return "";
      return "the file failed";
    })());
  }
  return asked.get(family);
}

/** Mark the nodes whose named family is not actually drawing them.
 *  Returns how many were marked. */
export async function markMissing(nodes) {
  let missing = 0;
  for (const node of nodes) {
    const family = node.dataset.face;
    if (!family) continue;
    const failure = await faceFailure(family);
    if (!failure) continue;
    node.classList.add("fallback");
    node.title = `${family} did not load (${failure}) — your browser is drawing this `
      + "in another face";
    missing += 1;
  }
  return missing;
}

/** Said once per panel, where the drawing is, rather than as a badge on every
 *  tile. Idempotent: a second lazily-loaded failure must not add a second note. */
export function noteFallbacks() {
  for (const panel of document.querySelectorAll(".drawn, .drawn-rows, .cards")) {
    if (!panel.querySelector(".fallback")) continue;
    if (panel.nextElementSibling?.classList.contains("fallback-note")) continue;
    const note = document.createElement("p");
    note.className = "quiet fallback-note";
    note.textContent = "Marked families did not load, so what you see there is your "
      + "browser's fallback rather than the font. Their coverage figures still come "
      + "from the font's own tables.";
    panel.after(note);
  }
}
