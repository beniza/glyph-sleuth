// Enhancement only. Every fact on every page is in the served HTML; this makes
// a few of them adjustable. With JS off nothing here is missed except the
// ability to change a number.

import { copyButtons } from "./copy.js";

copyButtons();

// Only the family pages have a Try it panel, and only they pay for it.
if (document.querySelector(".try")) import("./tryit.js");

// --------------------------------------------------------------- the index
//
// Filter, facets and sort over rows the page already served. Nothing here
// fetches; with JS off the table is the full index, in name order.

const table = document.querySelector("table.index");
if (table) {
  const rows = [...table.tBodies[0].rows];
  const body = table.tBodies[0];
  const search = document.querySelector(".filter");
  const facets = [...document.querySelectorAll(".facet")];
  const sorts = [...document.querySelectorAll(".sort")];
  const showing = document.querySelector("[data-showing]");
  const empty = document.querySelector(".empty");

  let facet = "all";
  let sort = "name";

  const tagPick = document.querySelector('select[name="tag"]');
  const blockPick = document.querySelector('select[name="block"]');

  const has = (value, wanted) => value.split(" ").filter(Boolean).includes(wanted);

  const matches = (row, text) => {
    if (text && !row.dataset.name.includes(text)) return false;
    // The two questions engineers actually arrive with: does it declare this
    // tag, does it cover this block. They compose — "covers Devanagari but
    // declares only deva" is the gap worth finding, and needs both at once.
    if (tagPick?.value && !has(row.dataset.tags || "", tagPick.value)) return false;
    if (blockPick?.value && !has(row.dataset.blocks || "", blockPick.value)) return false;
    switch (facet) {
      case "all": return true;
      case "measured": return row.dataset.tier === "measured";
      case "not measured yet": return row.dataset.tier !== "measured";
      default: return row.dataset.verdict === facet;
    }
  };

  // Sorting a detached fragment, then putting it back once: reordering 1,885
  // rows in place is thousands of reflows and the page visibly stutters.
  const order = {
    name: (a, b) => a.dataset.name.localeCompare(b.dataset.name),
    coverage: (a, b) => Number(b.dataset.coverage) - Number(a.dataset.coverage),
    // Worst first — the reason to sort by verdict is to find what breaks.
    verdict: (a, b) => ["fail", "caveat", "clean", "none"].indexOf(a.dataset.verdict)
      - ["fail", "caveat", "clean", "none"].indexOf(b.dataset.verdict)
      || a.dataset.name.localeCompare(b.dataset.name),
  };

  const apply = () => {
    const text = (search?.value || "").trim().toLowerCase();
    const shown = rows.filter((row) => matches(row, text));
    shown.sort(order[sort]);

    const fragment = document.createDocumentFragment();
    shown.forEach((row) => fragment.appendChild(row));
    body.replaceChildren(fragment);   // clears what is there, then inserts once

    if (showing) showing.textContent = shown.length.toLocaleString();
    if (empty) empty.hidden = shown.length > 0;
    table.hidden = shown.length === 0;
  };

  search?.addEventListener("input", apply);
  tagPick?.addEventListener("change", apply);
  blockPick?.addEventListener("change", apply);
  facets.forEach((button) => button.addEventListener("click", () => {
    facet = button.dataset.facet;
    facets.forEach((other) => other.classList.toggle("on", other === button));
    apply();
  }));
  sorts.forEach((button) => button.addEventListener("click", () => {
    sort = button.dataset.sort;
    sorts.forEach((other) => other.classList.toggle("on", other === button));
    apply();
  }));
}

// ------------------------------------------------------------- the specimen
//
// The specimen size control. The size is in the URL so a size you chose is a
// size you can send someone — the same rule Compare follows for all its state.
const slider = document.querySelector(".size input");
const readout = document.querySelector(".size-value");
const specimens = document.querySelectorAll(".specimen");

if (slider && specimens.length) {
  const apply = (size, push) => {
    specimens.forEach((node) => { node.style.fontSize = `${size}px`; });
    if (readout) readout.textContent = `${size}px`;
    slider.value = size;
    if (push) {
      const url = new URL(location.href);
      url.searchParams.set("size", size);
      history.replaceState(null, "", url);   // replace, so Back still leaves the page
    }
  };

  const fromUrl = Number(new URL(location.href).searchParams.get("size"));
  if (fromUrl >= Number(slider.min) && fromUrl <= Number(slider.max)) apply(fromUrl, false);

  slider.addEventListener("input", () => apply(Number(slider.value), true));
}

// ------------------------------------------------------------------ compare
//
// The one page that cannot be generated per pair: 1,878 measured families are
// 1.7 million pairs. The shell and the family list are served; only the diff
// is fetched, one small file per family.

const compareOut = document.getElementById("compare-out");
if (compareOut) {
  const pickA = document.querySelector('select[name="a"]');
  const pickB = document.querySelector('select[name="b"]');
  const hint = document.getElementById("compare-hint");
  const base = document.querySelector('link[href$="style.css"]').href.replace("style.css", "");
  const cache = new Map();

  const load = async (slug) => {
    if (!cache.has(slug)) {
      const response = await fetch(`${base}data/font/${slug}.json`);
      if (!response.ok) throw new Error(`no data for ${slug}`);
      cache.set(slug, await response.json());
    }
    return cache.get(slug);
  };

  const cell = (value) => (value === undefined || value === null || value === ""
    ? '<span class="untested">absent</span>' : String(value));

  // Differences are what gets emphasised. Rows that agree stay muted, so the
  // eye lands on the disagreement — and there is deliberately no total: two
  // families with identical rows still differ in ways this cannot see.
  const row = (label, a, b, href) => {
    const differs = String(a) !== String(b);
    const name = href ? `<a href="${href}">${label}</a>` : label;
    return `<tr class="${differs ? "differs" : "agrees"}"><th scope="row">${name}</th>`
      + `<td>${cell(a)}</td><td>${cell(b)}</td></tr>`;
  };

  const render = (a, b) => {
    const rows = [];
    rows.push(row("Source", a.source, b.source));
    rows.push(row("Licence", a.licence, b.licence));
    rows.push(row("Release", a.version, b.version));
    rows.push(row("Script tags", a.tags.join(" "), b.tags.join(" ")));
    rows.push(row("GSUB lookups", a.gsub, b.gsub));
    rows.push(row("GPOS lookups", a.gpos, b.gpos));

    // The comparison that matters: both may declare akhn and differ by fifty
    // rules inside it. "48 against 62" never told you which feature moved.
    const features = [...new Set([...Object.keys(a.features), ...Object.keys(b.features)])].sort();
    const featureRows = features.map((tag) => {
      const one = a.features[tag];
      const two = b.features[tag];
      const count = (f) => (f ? `${f.gsub + f.gpos} rules · ${f.lookups} lookups` : null);
      return row(tag, count(one), count(two), `${base}feature/${tag}/`);
    });

    const scripts = [...new Set([...Object.keys(a.verdicts), ...Object.keys(b.verdicts)])].sort();
    const verdictRows = scripts.flatMap((script) => {
      const ids = [...new Set([...Object.keys(a.verdicts[script] || {}),
        ...Object.keys(b.verdicts[script] || {})])].sort();
      return ids.map((id) => row(`${script} · ${id}`,
        (a.verdicts[script] || {})[id], (b.verdicts[script] || {})[id]));
    });

    const differing = [...rows, ...featureRows, ...verdictRows]
      .filter((html) => html.includes("differs")).length;
    const table = (caption, body) => (body.length
      ? `<h2 class="eyebrow">${caption}</h2><table class="compare"><thead><tr><th></th>`
        + `<th>${a.name}</th><th>${b.name}</th></tr></thead><tbody>${body.join("")}</tbody></table>`
      : "");

    compareOut.innerHTML =
      `<p class="quiet">${differing} of ${rows.length + featureRows.length
        + verdictRows.length} rows differ. No score: two families with identical rows still
        differ in ways this table cannot see.</p>`
      + table("The families", rows)
      + table("Features, by rule count", featureRows)
      + table("Sequences", verdictRows);
  };

  const update = async () => {
    const a = pickA.value;
    const b = pickB.value;
    const url = new URL(location.href);
    a ? url.searchParams.set("a", a) : url.searchParams.delete("a");
    b ? url.searchParams.set("b", b) : url.searchParams.delete("b");
    history.replaceState(null, "", url);
    if (!a || !b) {
      compareOut.innerHTML = "";
      if (hint) hint.hidden = false;
      return;
    }
    if (hint) hint.hidden = true;
    compareOut.innerHTML = '<p class="quiet">Reading both families…</p>';
    try {
      render(...await Promise.all([load(a), load(b)]));
    } catch (error) {
      compareOut.innerHTML = `<p class="fail">Could not read one of those families: ${error.message}</p>`;
    }
  };

  const params = new URL(location.href).searchParams;
  if (params.get("a")) pickA.value = params.get("a");
  if (params.get("b")) pickB.value = params.get("b");
  pickA.addEventListener("change", update);
  pickB.addEventListener("change", update);
  document.getElementById("swap")?.addEventListener("click", () => {
    [pickA.value, pickB.value] = [pickB.value, pickA.value];
    update();
  });
  if (params.get("a") && params.get("b")) update();
}

// ------------------------------------------------------------------ inspect
//
// The one page whose content is genuinely computed in the browser, because it
// answers a question the reader brings. Its module is loaded only here — no
// other page pays for core.js or the Unicode tables it reads.

const inspectField = document.getElementById("inspect-input");
if (inspectField) {
  const base = document.querySelector('link[href$="style.css"]').href.replace("style.css", "");
  import(`${base}inspect.js`).then((inspect) => inspect.start(
    inspectField,
    document.getElementById("inspect-reading"),
    document.getElementById("inspect-out"),
    document.getElementById("inspect-faces"),
  ));
}

// -------------------------------------------------------- did the face load?
//
// Every panel that draws text in a named family claims that family drew it. If
// its stylesheet 404s the browser quietly substitutes something else and the page
// still looks like it is showing the font — the one failure that would undermine
// everything else on a site arguing that coverage is not correctness.
//
// Two earlier attempts got this wrong, both worth remembering:
//
//   * Measuring advance widths against a fallback marked Dyuthi, which draws the
//     character perfectly. A single glyph is one advance width and two fonts for
//     a script collide on round numbers; worse, a family installed locally is
//     indistinguishable from a fallback by measurement, and in that case it *is*
//     drawing the text.
//   * document.fonts.check() cannot say no. In Chrome it answers true for a
//     family that does not exist, and true for a loaded family asked about a
//     character it does not have, because system fallback counts as available.
//     A check that can only agree is decoration.
//
// What is provable is whether *our* @font-face arrived: the stylesheet either
// produced a FontFace for that family or it did not, and the face either loaded
// or errored. That is the failure we can honestly report — and it is the one that
// actually happens, since coverage was already measured from the font's own cmap
// at build time.

const faced = document.querySelectorAll("[data-face]");
if (faced.length) {
  (async () => {
    const unquote = (name) => name.replace(/^["']|["']$/g, "");
    const asked = new Map();

    const webfontFailed = async (family) => {
      if (!asked.has(family)) {
        asked.set(family, (async () => {
          const faces = [...document.fonts].filter(
            (face) => unquote(face.family) === family);
          // No @font-face at all: the stylesheet did not arrive, or the family
          // is spelled differently there than we think. Either way our face is
          // not drawing this.
          if (!faces.length) return "no stylesheet";
          await Promise.all(faces.map((face) => face.load().catch(() => {})));
          if (faces.some((face) => face.status === "loaded")) return "";
          return "the file failed";
        })());
      }
      return asked.get(family);
    };

    await document.fonts.ready;

    let missing = 0;
    for (const node of faced) {
      const family = node.dataset.face;
      if (!family) continue;
      const failure = await webfontFailed(family);
      if (!failure) continue;
      node.classList.add("fallback");
      node.title = `${family} did not load (${failure}) — your browser is drawing this `
        + "in another face";
      missing += 1;
    }

    // Said once per panel, where the drawing is, rather than as a badge on every
    // tile.
    if (missing) {
      for (const panel of document.querySelectorAll(".drawn, .drawn-rows, .cards")) {
        if (!panel.querySelector(".fallback")) continue;
        const note = document.createElement("p");
        note.className = "quiet fallback-note";
        note.textContent = "Marked families did not load, so what you see there is your "
          + "browser's fallback rather than the font. Their coverage figures still come "
          + "from the font's own tables.";
        panel.after(note);
      }
    }
  })();
}
