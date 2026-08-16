# Identify — final settled spec

*Supersedes the open questions in README.md's "Feature 2 — Identify" section. The base spec
(canvas mechanics, drop/paste handling, the IoU-minus-centroid scoring, the non-negotiable
honesty constraint, the state shape, the accessibility requirement that file-picker and
paste are real routes not niceties) stands as written. This resolves everything that was
still open.*

## Resolved

**Scope follows the active script — on the web app only.** Identify builds its atlas
against whatever script is contextually active (currently always Malayalam, since that's
the only script live; once more scripts exist, whichever one the user arrived from). No
on-page script picker on the web version — it's a quick, in-context lookup, not a general
search tool, and stays that way by design.

**The desktop companion gets the richer version.** Once the desktop companion exists (see
`addendum-desktop-companion.md`), its own Identify-equivalent lets the user explicitly
choose which script or scripts to search against, rather than being bound to "whatever
page you were just on." That's the appropriate place for cross-script matching — the
desktop tool already has fewer resource constraints and a power-user posture; the web app
doesn't need to grow that complexity to get it. Same "start narrow on the web, expand on
desktop" split the rest of this round has used for script scope generally.

**One reference face for now.** The atlas is built from a single fixed reference face
(Manjari) rather than offering a picker across all six families. Matches the same
start-narrow-expand-later shape used for Compare's script scope. A multi-face atlas/picker
is future work, not blocking anything now.

**Weak results get their own honest state, not a silently padded list.** When the top
candidates are all weak — no strong shape match — the page says so plainly, in its own
register: something like "No strong matches. Try a cleaner stroke, or drop a clearer
image." This message sits *above* the candidate list, not in place of it — the honesty
constraint already requires never hiding a score, so the ranked (if unconvincing) list
stays visible underneath for anyone who wants to look anyway. Same "absence is content"
instinct already used for the Paniya/Ravula zero-fit case on the script page.

**Explicit reassurance that the image never leaves the device.** Near the canvas/drop
target, a plain line confirming this, mirroring the existing home-page promise ("Read-only.
Nothing you type leaves the browser.") rather than inventing new phrasing: something like
"Nothing you draw or drop here is uploaded — it stays on your device." This matters more
here than for typed text, since the brief's own example use case is dropping a screenshot
of a bug report, which may carry more than the person intended to share.

## Unchanged from the base spec

Canvas mechanics (pointer events, stroke rendering, drop/paste/file-picker parity), the
`document.fonts.ready` wait before building the atlas, the 24×24 signature grid and IoU-
minus-centroid scoring, the state shape (`strokes`/`imageMask` in refs, `candidates`/
`atlasReady`/`brush` in render state), and the accessibility requirement that the candidate
list and both non-canvas input paths work without ever touching the canvas.
