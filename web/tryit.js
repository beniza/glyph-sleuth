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
  const style = panel.querySelector('[data-try="style"]');
  const axes = [...panel.querySelectorAll("[data-axis]")];
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
    // Every axis away from its default, set on the font itself: width, slant,
    // and a font's own, which CSS has no property for.
    const moved = axes.filter((axis) => axis.value !== axis.dataset.default)
      .map((axis) => `"${axis.dataset.axis}" ${axis.value}`);
    if (moved.length) rules.push(`font-variation-settings: ${moved.join(", ")}`);
    return rules.join("; ");
  };

  // What was typed is in the address once previewed, so "this sentence, in this
  // family" is a link someone can be sent. Replaced, not pushed: Back still
  // leaves the page. As typed, not as read — U+0D15 stays U+0D15 in the link.
  //
  // And how it was set: `px` (not `size`, which is the specimen's above),
  // `weight`, `italic`, and `off` for the features switched off. A default is
  // left out, so a plain link stays plain.
  const switches = () => [...panel.querySelectorAll("[data-feature]")];
  const remember = () => {
    const url = new URL(location.href);
    const off = switches().filter((box) => !box.checked).map((box) => box.dataset.feature);
    const state = {
      text: field.value,
      px: size.value === size.defaultValue ? "" : size.value,
      // The weight the menu starts on is the default, whichever option that is.
      weight: weight && !weight.selectedOptions[0]?.defaultSelected ? weight.value : "",
      italic: italic?.checked ? "1" : "",
      off: off.join(","),
      var: axes.filter((axis) => axis.value !== axis.dataset.default)
        .map((axis) => `${axis.dataset.axis}:${axis.value}`).join(","),
    };
    for (const [key, value] of Object.entries(state)) {
      value ? url.searchParams.set(key, value) : url.searchParams.delete(key);
    }
    history.replaceState(null, "", url);
  };

  // Read back on arrival, each only if this family offers it: a weight it does
  // not have, or a feature it does not declare, is ignored rather than invented.
  const given = new URL(location.href).searchParams;
  const px = Number(given.get("px"));
  if (px) size.value = String(Math.min(Number(size.max), Math.max(Number(size.min), Math.round(px))));
  sizeValue.textContent = `${size.value}px`;
  if (weight && [...weight.options].some((option) => option.value === given.get("weight"))) {
    weight.value = given.get("weight");
  }
  if (italic && given.get("italic") === "1") italic.checked = true;
  const off = new Set((given.get("off") || "").split(",").filter(Boolean));
  for (const box of switches()) if (off.has(box.dataset.feature)) box.checked = false;
  // Axes, each held to the font's own range; an axis it lacks is ignored.
  for (const part of (given.get("var") || "").split(",").filter(Boolean)) {
    const [tag, value] = part.split(":");
    const axis = axes.find((each) => each.dataset.axis === tag);
    if (axis && value !== "" && Number.isFinite(Number(value))) {
      axis.value = String(Math.min(Number(axis.max), Math.max(Number(axis.min), Number(value))));
    }
  }

  // The style menu names what the sliders are at, or says "custom": it is a way
  // to set them, never a claim of its own.
  const coordsOf = (option) => JSON.parse(option.dataset.coords || "{}");
  const showAxes = () => {
    for (const axis of axes) axis.parentElement.querySelector("[data-axis-value]").textContent = axis.value;
  };
  const nameStyle = () => {
    if (!style) return;
    const now = Object.fromEntries(axes.map((axis) => [axis.dataset.axis, Number(axis.value)]));
    now.wght = Number(weight?.value || 400);
    const match = [...style.options].find((option) => option.value
      && Object.entries(coordsOf(option)).every(([tag, value]) => now[tag] === undefined || now[tag] === value));
    style.value = match ? match.value : "";
  };
  showAxes();
  nameStyle();

  // A link that switched features off shows which: they are the point of it.
  if (switches().some((box) => !box.checked)) panel.querySelector(".try-features").open = true;

  const render = async () => {
    remember();
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
    remember();
  });
  for (const control of panel.querySelectorAll("select, [type=checkbox]")) {
    if (control === style) continue;
    control.addEventListener("change", () => {
      nameStyle();
      return out.hidden ? remember() : render();
    });
  }
  // Choosing a style sets the weight and every axis it names.
  style?.addEventListener("change", () => {
    const option = style.selectedOptions[0];
    if (!option || !option.value) return;
    for (const [tag, value] of Object.entries(coordsOf(option))) {
      if (tag === "wght" && weight) {
        if (![...weight.options].some((each) => Number(each.value) === value)) {
          weight.add(new Option(String(value), String(value)));
        }
        weight.value = String(value);
      }
      const axis = axes.find((each) => each.dataset.axis === tag);
      if (axis) axis.value = String(value);
    }
    showAxes();
    return out.hidden ? remember() : render();
  });
  for (const axis of axes) {
    axis.addEventListener("input", () => {
      showAxes();
      nameStyle();
      if (!out.hidden) out.setAttribute("style", styles());
      remember();
    });
  }

  // Arriving with a line to try previews it at once: that is what the link was for.
  if (given.get("text")) {
    field.value = given.get("text");
    render();
  }
}
