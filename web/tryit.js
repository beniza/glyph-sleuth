// "Try it": set your own text in this family, and say what the font cannot draw.
//
// Enhancement, and late enhancement at that. Nothing here runs until someone
// presses Preview, and the coverage it needs — the family's own cmap ranges — is
// fetched on that press from the file Compare already writes. A family page that
// nobody experiments with costs one extra script tag and no bytes beyond it.
//
// The honesty rule applies here as everywhere: a character this font does not
// have is drawn by something else, and the panel says so *in the line*, at the
// character, rather than leaving the reader to notice that one glyph looks
// wrong. That is the whole reason this is more than a contenteditable div.
import { parse, covers, hex } from "./core.js";

const panel = document.querySelector(".try");

if (panel) {
  const field = panel.querySelector('[data-try="text"]');
  const out = panel.querySelector('[data-try="out"]');
  const note = panel.querySelector('[data-try="note"]');
  const size = panel.querySelector('[data-try="size"]');
  const sizeValue = panel.querySelector('[data-try="size-value"]');
  const weight = panel.querySelector('[data-try="weight"]');
  const italic = panel.querySelector('[data-try="italic"]');
  const family = panel.dataset.face;

  let ranges = null;

  // The cmap, once, on first Preview. Until then this page has fetched nothing.
  const coverage = async () => {
    if (ranges) return ranges;
    try {
      const response = await fetch(panel.dataset.src);
      ranges = response.ok ? (await response.json()).ranges || [] : [];
    } catch {
      // Offline, or a family with no Compare data. Marking nothing beats
      // marking everything as missing.
      ranges = [];
    }
    return ranges;
  };

  // What the reader typed, which may not be text: core.parse reads U+0D15, a
  // bare 0D15, a range, an entity, and plain text, exactly as Inspect does — one
  // parser, so the two pages cannot disagree about what a string means.
  const asText = (raw) => {
    const query = parse(raw);
    if (!query) return "";
    if (query.kind === "char") return String.fromCodePoint(query.value);
    if (query.kind === "codepoints") return query.value.map((c) => String.fromCodePoint(c)).join("");
    if (query.kind === "range") {
      const [lo, hi] = query.value;
      // A range is a chart, not a sentence, and 0000..10FFFF is not a preview.
      const stop = Math.min(hi, lo + 255);
      const chars = [];
      for (let cp = lo; cp <= stop; cp += 1) chars.push(String.fromCodePoint(cp));
      return chars.join("");
    }
    return raw;
  };

  const styles = () => {
    const rules = [`font-family: "${family}", serif`, `font-size: ${size.value}px`];
    if (weight) rules.push(`font-weight: ${weight.value}`);
    if (italic) rules.push(`font-style: ${italic.checked ? "italic" : "normal"}`);
    const off = [...panel.querySelectorAll("[data-feature]")]
      .filter((box) => !box.checked)
      .map((box) => `"${box.dataset.feature}" 0`);
    if (off.length) rules.push(`font-feature-settings: ${off.join(", ")}`);
    return rules.join("; ");
  };

  const render = async () => {
    const text = asText(field.value);
    if (!text) {
      out.hidden = note.hidden = true;
      return;
    }
    const have = await coverage();

    // Marked per character, not per cluster: coverage is a cmap question and the
    // cmap is about codepoints. Combining marks are left unwrapped — boxing a
    // mark separates it from the base it belongs on and breaks the shaping the
    // reader came to look at, which would be a worse lie than the one this is
    // avoiding.
    const missing = new Set();
    let html = "";
    for (const ch of text) {
      const cp = ch.codePointAt(0);
      const known = !have.length || covers(have, cp);
      if (known || /\s/.test(ch)) {
        html += escapeHtml(ch);
        continue;
      }
      missing.add(cp);
      // No character name here: naming it would mean fetching the whole name
      // table onto a page that has no other use for it, to say something the
      // codepoint already links to.
      html += `<span class="uncovered" title="U+${hex(cp)} is not in `
        + `${escapeAttr(family)} — your browser drew this">${escapeHtml(ch)}</span>`;
    }

    out.innerHTML = html;
    out.setAttribute("style", styles());
    out.hidden = false;

    const total = [...text].length;
    note.hidden = false;
    if (!have.length) {
      note.textContent = `Set in ${family}. Its coverage list did not load, so nothing `
        + "here is marked as missing — that is this panel not knowing, not the font "
        + "having everything.";
    } else if (missing.size) {
      const listed = [...missing].slice(0, 8).map((cp) => `U+${hex(cp)}`).join(" · ");
      note.textContent = `${missing.size} of ${total} characters are not in ${family}: `
        + listed + (missing.size > 8 ? ` and ${missing.size - 8} more.` : ".")
        + " Your browser drew those in another face.";
    } else {
      note.textContent = `All ${total} characters are in ${family}, so everything above `
        + "is this font drawing.";
    }
  };

  const escapeHtml = (value) => value.replace(/[&<>]/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
  const escapeAttr = (value) => escapeHtml(String(value)).replace(/"/g, "&quot;");

  panel.querySelector('[data-try="go"]').addEventListener("click", render);
  // Enter previews; Shift+Enter is a newline, because multi-line is the point of
  // a textarea and a reader testing line breaks should get one.
  field.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      render();
    }
  });

  // The switches only redraw something already on screen; they never fetch and
  // never run before the first Preview.
  size.addEventListener("input", () => {
    sizeValue.textContent = `${size.value}px`;
    if (!out.hidden) out.setAttribute("style", styles());
  });
  for (const control of panel.querySelectorAll("select, [type=checkbox]")) {
    control.addEventListener("change", () => { if (!out.hidden) render(); });
  }
}
