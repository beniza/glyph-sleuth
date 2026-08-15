// The window. Everything runs in the browser against a precomputed index —
// there is no server, and nothing you type leaves the page.
import * as core from "./core.js";

const $ = (sel) => document.querySelector(sel);
const el = (tag, props = {}, ...kids) => {
  const node = Object.assign(document.createElement(tag), props);
  for (const kid of kids.flat()) if (kid != null) node.append(kid);
  return node;
};

const MAX_ROWS = 40;
const MAX_TILES = 120;

// ------------------------------------------------------- serving the faces

// Google serves its families from a CDN; the SIL faces it doesn't carry we host
// ourselves. Either way a face is only fetched once something needs it drawn,
// and Google's `text=` parameter means we pull the glyphs, not the whole font.
const requested = new Set();

function ensureFonts(fonts, sample) {
  // Whitespace has no outline, so a subset of nothing but spaces comes back as a
  // zero-glyph font the browser refuses. Ask only for ink, and only from faces
  // that have some of it.
  const text = core.stripFormatting(sample);
  const google = [];
  for (const font of fonts) {
    if (text && ![...text].some((ch) => core.covers(font.ranges, ch.codePointAt(0)))) continue;
    const key = font.name + "|" + text;
    if (requested.has(key)) continue;
    requested.add(key);
    if (font.source === "google") google.push(font);
    else if (font.file) addFace(font);
  }
  // One stylesheet per batch, not per family: 60 rows is one request.
  for (let i = 0; i < google.length; i += 20) {
    const families = google.slice(i, i + 20)
      .map((f) => "family=" + encodeURIComponent(f.name).replace(/%20/g, "+"));
    const chars = [...new Set([...text])].join("");
    const url = `https://fonts.googleapis.com/css2?${families.join("&")}`
      + (chars ? `&text=${encodeURIComponent(chars)}` : "") + "&display=swap";
    document.head.append(el("link", { rel: "stylesheet", href: url }));
  }
}

const hosted = new Set();
function addFace(font) {
  if (hosted.has(font.name)) return;
  hosted.add(font.name);
  const style = el("style");
  style.textContent = `@font-face{font-family:"${font.name}";src:url("${font.file}") format("woff2");font-display:swap}`;
  document.head.append(style);
}

const stack = (font) => `"${font.name}", var(--display)`;

// ------------------------------------------------------------------ pieces

function glyphCell(text, font) {
  const cell = el("span", { className: "glyph" });
  if (font) cell.style.fontFamily = stack(font);
  const cp = [...text][0]?.codePointAt(0);
  const mark = text.length === 1 && cp != null ? core.standin(cp) : null;
  if (mark) cell.append(el("span", { className: "standin", textContent: mark }));
  else cell.textContent = text;
  return cell;
}

// Who published the face. Every one of these links to its own download page.
// "RIT", not "Rachana": SMC ships a font *called* Rachana, and a foundry tag
// that reads like a family name beside it is a puzzle, not a label.
const FOUNDRIES = { google: "Google Fonts", sil: "SIL", smc: "SMC", rit: "RIT",
                    libre: "Libre" };

// -------------------------------------------------------------- specimens

/** Where to get the file, and the CSS to use it on your own site. Two actions,
 *  because those are the two things anyone does after finding the right face. */
function actions(font) {
  const source = core.download(font);
  const get = el("a", { className: "act", href: source.url, target: "_blank",
                        rel: "noopener", textContent: source.label,
                        title: source.direct
                          ? `Download the ${font.name} family from Google Fonts`
                          : `Get ${font.name} from ${FOUNDRIES[font.source] || font.source}` });
  const use = el("button", { className: "act", type: "button", textContent: "Use on web" });
  use.setAttribute("aria-expanded", "false");
  const row = el("div", { className: "spec-acts" }, get, use);
  use.onclick = () => toggleEmbed(use, font);
  return row;
}

function toggleEmbed(button, font) {
  const entry = button.closest(".spec");
  const open = entry.querySelector(".embed");
  if (open) {
    open.remove();
    button.setAttribute("aria-expanded", "false");
    return;
  }
  const snippet = core.embed(font);
  const copy = el("button", { className: "act", type: "button", textContent: "Copy" });
  const note = el("span", {
    textContent: font.source === "google"
      ? "Served by Google Fonts — no file to host."
      : "Download the file first, then serve it beside your CSS.",
  });
  copy.onclick = async () => {
    await navigator.clipboard.writeText(snippet);
    copy.textContent = "Copied";
    setTimeout(() => { copy.textContent = "Copy"; }, 1400);
  };
  entry.append(el("div", { className: "embed" },
    el("pre", {}, el("code", { textContent: snippet })),
    el("div", { className: "row" }, copy, note)));
  button.setAttribute("aria-expanded", "true");
}

/** One entry per face: who made it, what it costs you, how it sets your text.
 *  The specimen gets the width and the size; everything else is a caption. */
function specimen(font, sample, missing) {
  const meta = el("span", { className: "spec-meta",
                            textContent: FOUNDRIES[font.source] || font.source });
  if (font.licence) {
    meta.append(" · ", font.licenceUrl
      ? el("a", { href: font.licenceUrl, target: "_blank", rel: "noopener",
                  textContent: font.licence, title: `${font.name} licence` })
      : font.licence);
  }
  const head = el("header", { className: "spec-head" },
    el("a", { className: "spec-name", href: font.url, target: "_blank", rel: "noopener",
              textContent: font.name }),
    meta);

  if (missing) {
    head.append(missing.size
      ? el("span", { className: "spec-status gap" }, `${missing.size} missing`,
           el("span", { className: "chars", textContent: [...missing].slice(0, 10).join(" ") }))
      : el("span", { className: "spec-status ok", textContent: "sets it completely" }));
  } else {
    head.append(el("span", { className: "spec-meta",
                             textContent: `${core.countIn(font.ranges).toLocaleString()} characters` }));
  }
  head.append(actions(font));

  const single = [...sample].length === 1;
  const body = el("div", { className: "spec-sample" + (single ? " one" : ""),
                           style: `font-family:${stack(font)}`, textContent: sample });
  return el("article", { className: "spec" }, head, body);
}

/** The list Preview and Language show: every face that can set the text. */
function specimenList(rows, full) {
  const sample = core.trimToSpecimen(full);
  ensureFonts(rows.map((r) => r.font), sample);
  const list = el("div", { className: "specimens" });
  for (const { font, missing } of rows) list.append(specimen(font, sample, missing));
  return list;
}

/** One character in many faces. A wall of tiles answers "what does it look
 *  like" at a glance, where a list of rows makes you read to compare. */
function glyphWall(fonts, ch) {
  ensureFonts(fonts, ch);
  const wall = el("div", { className: "wall" });
  for (const font of fonts) {
    const tile = el("button", { className: "tile", type: "button",
                                title: `${font.name} — see the family` },
      el("span", { className: "g", style: `font-family:${stack(font)}`, textContent: ch }),
      el("span", { className: "n", textContent: font.name }));
    tile.onclick = () => runQuery(font.name);
    wall.append(tile);
  }
  return wall;
}

// ------------------------------------------------------------------ search

function showSearch(query) {
  const out = $("#search-results");
  out.replaceChildren();
  $("#inspector").replaceChildren();

  if (query.kind === "empty") {
    out.append(el("p", { className: "status" },
      `${core.data.fonts.length.toLocaleString()} freely available families indexed — `
      + `Google Fonts, SIL, SMC, Rachana and the libre classics, covering Unicode `
      + `${core.data.unicode}. Type anything above.`));
    return;
  }

  if (query.kind === "char") return showChar(query.value);
  if (query.kind === "font") {
    const font = core.data.fonts.find((f) => f.name === query.value);
    return showFont(font);
  }
  if (query.kind === "lang") {
    select($("#lang-pick"), query.value);
    return switchMode("language");
  }
  if (query.kind === "block") {
    select($("#browse-block"), query.value);
    return switchMode("browse");
  }
  if (query.kind === "name") return showNameSearch(query.value);
  if (query.kind === "prop") return showProperty(query.value);
  if (query.kind === "range") return showCodepoints(rangeList(...query.value), query.label);
  if (query.kind === "codepoints") return showCodepoints(query.value, query.label);
  return showText(query.value);
}

const rangeList = (lo, hi) => Array.from({ length: Math.min(hi - lo + 1, 2000) }, (_, i) => lo + i);

function showChar(cp) {
  const ch = String.fromCodePoint(cp);
  const found = core.fontsWith(cp);
  const out = $("#search-results");
  out.append(el("p", { className: "count" },
    el("b", { textContent: found.length.toLocaleString() }),
    ` of ${core.data.fonts.length.toLocaleString()} families draw this`
    + (found.length > MAX_TILES ? ` — showing ${MAX_TILES}` : "")));
  out.append(found.length
    ? glyphWall(found.slice(0, MAX_TILES), ch)
    : el("p", { className: "status" }, "No indexed family covers this character."));
  inspectChar(cp);
}

function showCodepoints(cps, label) {
  const out = $("#search-results");
  const table = el("table");
  table.append(el("thead", {}, el("tr", {},
    el("th", { textContent: "Char" }), el("th", { textContent: "Codepoint" }),
    el("th", { textContent: "Name" }), el("th", { textContent: "Families" }))));
  const body = el("tbody");
  for (const cp of cps.slice(0, 500)) {
    const row = el("tr", {},
      el("td", {}, glyphCell(String.fromCodePoint(cp))),
      el("td", { className: "num", textContent: "U+" + core.hex(cp) }),
      el("td", { textContent: core.charName(cp) }),
      el("td", { className: "num", textContent: core.fontsWith(cp).length.toLocaleString() }));
    row.onclick = () => runQuery("U+" + core.hex(cp));
    body.append(row);
  }
  table.append(body);
  out.append(el("p", { className: "count", textContent: `${label} — ${cps.length.toLocaleString()} characters` }), table);
  if (cps.length) inspectChar(cps[0]);
}

function showText(text) {
  const ranked = core.rankFonts(text);
  const complete = ranked.filter((row) => !row.missing.size).length;
  $("#search-results").append(
    el("p", { className: "count" }, el("b", { textContent: complete.toLocaleString() }),
      ` families set this text completely — best ${Math.min(MAX_ROWS, ranked.length)} shown`),
    specimenList(ranked.slice(0, MAX_ROWS), text));
  $("#preview-text").value = text;
}

function showNameSearch(text) {
  core.loadNames().then(() => {
    const hits = core.searchNames(text);
    if (!hits.length) {
      $("#search-results").replaceChildren(el("p", { className: "status" }, `No character name matches “${text}”.`));
      return;
    }
    $("#search-results").replaceChildren();
    showCodepoints(hits, `name search · ${text}`);
  });
}

function showProperty(expr) {
  if (!core.validProperty(expr)) {
    $("#search-results").append(el("p", { className: "status" },
      `The regex engine rejects \\p{${expr}}. Blocks, scripts and general categories work: `
      + `\\p{Script=Devanagari}, \\p{Block=Dingbats}, \\p{Lu}.`));
    return;
  }
  const hits = core.matchingProperty(expr, 2000);
  showCodepoints(hits, `\\p{${expr}}`);
}

/** One face, at every size worth judging it at — the page a foundry prints. */
function showFont(font) {
  if (!font) return;
  const out = $("#search-results");
  const sample = specimenTextFor(font);
  ensureFonts([font], sample + LADDER_TEXT);

  const facts = [
    `${core.countIn(font.ranges).toLocaleString()} characters`,
    font.licence,
    font.designers?.length ? font.designers.join(", ") : null,
  ].filter(Boolean).join(" · ");

  const entry = specimen(font, sample, null);
  entry.querySelectorAll(".spec-meta")[1]?.remove();
  entry.querySelector(".spec-meta").textContent =
    `${FOUNDRIES[font.source] || font.source} · ${facts}`;
  out.append(entry);

  // The size ladder a specimen sheet always ends on: one line per size, so the
  // face can be judged at text sizes and display sizes in the same glance.
  const ladder = el("div", { className: "specimens" });
  for (const size of [64, 44, 30, 20, 14]) {
    ladder.append(el("article", { className: "spec" },
      el("header", { className: "spec-head" },
        el("span", { className: "spec-meta", textContent: `${size}px` })),
      el("div", { className: "spec-sample", style: `font-family:${stack(font)};font-size:${size}px`,
                  textContent: LADDER_TEXT })));
  }
  out.append(el("h2", { textContent: "At every size" }), ladder);
  select($("#browse-font"), font.name);
}

const LADDER_TEXT = "Hamburgefonstiv 0123456789";

/** A face is best judged setting the script it exists for: a Malayalam family
 *  showing Latin proves nothing. Falls back to the Latin pangram for the faces
 *  that really are Latin faces. */
function specimenTextFor(font) {
  const block = core.dominantBlock(font);
  if (block) {
    const range = core.blockRange(block);
    for (const lang of core.data.languages) {
      if (!lang.sample) continue;
      const head = core.stripFormatting(lang.sample.slice(0, 60));
      const inScript = [...head].some((ch) => {
        const cp = ch.codePointAt(0);
        return cp >= range[0] && cp <= range[1];
      });
      if (inScript && !core.missingFrom(font.ranges, head).size) return core.trimToSpecimen(lang.sample);
    }
  }
  return LADDER_TEXT;
}

// --------------------------------------------------------------- inspector

function inspectChar(cp) {
  const ch = String.fromCodePoint(cp);
  const panel = $("#inspector");
  panel.replaceChildren();
  panel.append(el("div", { className: "hero", textContent: core.standin(cp) ? "" : ch }));
  if (core.standin(cp)) panel.append(el("p", {}, el("span", { className: "standin", textContent: core.standin(cp) })));

  const facts = el("dl", { className: "facts" });
  const fact = (term, value) => {
    const dd = el("dd", { textContent: value });
    facts.append(el("dt", { textContent: term }), dd);
    return dd;
  };
  // The name table is a lazy 1.4 MB, so the name lands a moment after the rest.
  const nameCell = fact("Name", core.charName(cp));
  core.loadNames().then(() => { nameCell.textContent = core.charName(cp); });
  fact("Codepoint", "U+" + core.hex(cp));
  fact("Block", core.blockOf(cp) || "—");
  for (const [label, value] of Object.entries(core.encodings(cp))) fact(label, value);
  panel.append(facts);

  const found = core.fontsWith(cp).length;
  panel.append(el("p", { className: "count" },
    `${found.toLocaleString()} of ${core.data.fonts.length.toLocaleString()} indexed families have it`));

  const props = PROPS.filter((p) => core.matchesProperty(ch, p));
  if (props.length) {
    panel.append(el("h2", { textContent: "Matches" }),
      el("p", { className: "mono", textContent: props.map((p) => `\\p{${p}}`).join("  ") }));
  }

  const norm = core.normalizationVariants(ch).filter(([, v]) => v !== ch);
  if (norm.length) {
    panel.append(el("h2", { textContent: "Normalisation" }),
      el("p", { className: "mono", textContent: norm.map(([f, v]) => `${f} ${[...v].map((c) => "U+" + core.hex(c.codePointAt(0))).join(" ")}`).join("\n") }));
  }

  // Characters that share a keyword with this one — needs the name table.
  core.loadNames().then(() => {
    const others = core.variants(cp, 24).slice(1);
    if (!others.length) return;
    const strip = el("p", { className: "hero", style: "font-size:26px" });
    for (const other of others) {
      const button = el("button", { className: "cell", title: `${core.charName(other)}  U+${core.hex(other)}`,
                                    style: "display:inline-block;width:auto;padding:2px 6px" },
        el("span", { className: "g", textContent: String.fromCodePoint(other) }));
      button.onclick = () => runQuery("U+" + core.hex(other));
      strip.append(button);
    }
    panel.append(el("h2", { textContent: "Shares a name" }), strip);
  });
}

// Reported for a single character, in reading order. JS regex knows these
// natively; Block comes from the UCD table core.js carries.
const PROPS = ["L", "Lu", "Ll", "Lt", "Lm", "Lo", "M", "Mn", "Mc", "N", "Nd", "P", "S", "Sm",
  "Sc", "Z", "C", "Alphabetic", "Uppercase", "Lowercase", "White_Space", "Emoji",
  "Diacritic", "Extender", "Join_Control", "Dash", "Quotation_Mark", "Math",
  "Ideographic", "Default_Ignorable_Code_Point"];

// ----------------------------------------------------------------- preview

function setupPreview() {
  const picker = $("#preview-lang");
  // Every option carries a real sample, so picking one always fills the box.
  for (const lang of core.data.languages) {
    if (lang.sample) picker.append(el("option", { value: lang.id, textContent: lang.name }));
  }
  const english = core.data.languages.find((l) => l.iso === "eng" && l.sample);
  if (english) picker.value = english.id;
  setSample(english);
  picker.onchange = () => {
    setSample(core.data.languages.find((l) => l.id === picker.value));
    runPreview();
  };
  $("#preview-run").onclick = runPreview;
  let typing;
  $("#preview-text").oninput = () => { clearTimeout(typing); typing = setTimeout(runPreview, 350); };
}

function setSample(lang) {
  const box = $("#preview-text");
  box.value = lang?.sample || "The quick brown fox jumps over the lazy dog.";
  box.dir = lang?.dir || "ltr";
}

function runPreview() {
  const text = $("#preview-text").value;
  const out = $("#preview-results");
  out.replaceChildren();
  const wanted = core.stripFormatting(text);
  if (!wanted) {
    out.append(el("p", { className: "status" },
      "Type or paste something above to see which families can set it."));
    return;
  }
  const ranked = core.rankFonts(text);
  const complete = ranked.filter((r) => !r.missing.size);
  out.append(el("p", { className: "count" }, el("b", { textContent: complete.length.toLocaleString() }),
    ` of ${core.data.fonts.length.toLocaleString()} families set this completely`));
  out.append(specimenList(ranked.slice(0, MAX_ROWS), text));
}

// ------------------------------------------------------------------ browse

function setupBrowse() {
  const blocks = $("#browse-block");
  for (const [lo, hi, name] of core.data.blocks) {
    blocks.append(el("option", { value: name, textContent: `${name}  (U+${core.hex(lo)}–U+${core.hex(hi)})` }));
  }
  // Which fonts are worth offering depends on the block, so showBrowse fills both.
  blocks.onchange = showBrowse;
  $("#browse-font").onchange = drawBlock;
  blocks.value = "Basic Latin";
}

/** Offer only the faces with something to draw in this block, most coverage
 *  first. A picker of 1,885 families, nearly all of which render the block as
 *  empty boxes, is a worse answer than a picker of the 40 that can set it.
 *  Keeps the current face selected when it survives the new block. */
function fillFonts() {
  const picker = $("#browse-font");
  const range = core.blockRange($("#browse-block").value);
  const previous = picker.value;
  picker.replaceChildren();
  const offered = range ? core.fontsForRange(range[0], range[1]) : [];
  for (const { font, count } of offered) {
    picker.append(el("option", { value: font.name, textContent: `${font.name}  (${count})` }));
  }
  picker.disabled = !offered.length;
  if (!offered.length) {
    picker.append(el("option", { value: "", textContent: "no indexed family covers this block" }));
  } else if (offered.some((row) => row.font.name === previous)) {
    picker.value = previous;
  }
}

/** The block decides the font list, so the two are always redrawn together. */
function showBrowse() {
  fillFonts();
  drawBlock();
}

function drawBlock() {
  const range = core.blockRange($("#browse-block").value);
  const font = core.data.fonts.find((f) => f.name === $("#browse-font").value);
  const grid = $("#browse-grid");
  grid.replaceChildren();
  if (!range) return;
  const [lo, hi] = range;
  const cps = rangeList(lo, hi);
  const drawable = cps.filter((cp) => !font || core.covers(font.ranges, cp));
  if (font) ensureFonts([font], drawable.map((c) => String.fromCodePoint(c)).join(""));
  const box = el("div", { className: "grid" });
  for (const cp of cps) {
    const absent = font && !core.covers(font.ranges, cp);
    const cell = el("button", { className: "cell" + (absent ? " absent" : ""),
                                title: `${core.charName(cp)}  U+${core.hex(cp)}` },
      el("span", { className: "g", style: font && !absent ? `font-family:${stack(font)}` : "",
                   textContent: absent ? "·" : String.fromCodePoint(cp) }),
      el("span", { className: "cp", textContent: core.hex(cp) }));
    cell.onclick = () => runQuery("U+" + core.hex(cp));
    box.append(cell);
  }
  grid.append(el("p", { className: "count" },
    font ? `${drawable.length} of ${cps.length} drawn by ${font.name}` : `${cps.length} characters`), box);
}

// ---------------------------------------------------------------- language

function setupLanguage() {
  const picker = $("#lang-pick");
  for (const lang of core.data.languages) {
    picker.append(el("option", { value: lang.id, textContent: `${lang.name} — ${lang.tag}` }));
  }
  picker.onchange = showLanguage;
  picker.value = core.data.languages.find((l) => l.iso === "hin")?.id || picker.options[0].value;
}

function showLanguage() {
  const lang = core.data.languages.find((l) => l.id === $("#lang-pick").value);
  const out = $("#lang-results");
  out.replaceChildren();
  if (!lang) return;

  // Exemplars are what the language needs; the UDHR text is only prose, so
  // coverage is judged on the exemplars when SLDR gave us any.
  const wanted = lang.exemplars || core.stripFormatting(lang.sample || "");
  if (!wanted) {
    out.append(el("p", { className: "status" }, "No exemplar characters or sample text for this language."));
    return;
  }
  const ranked = core.rankFonts(wanted);
  const complete = ranked.filter((r) => !r.missing.size);
  out.append(el("p", { className: "count" },
    `${lang.exemplars ? `${[...new Set([...wanted])].length} exemplar characters (SIL SLDR)` : "no exemplars — judged on the sample text"}`
    + ` · ${complete.length.toLocaleString()} of ${core.data.fonts.length.toLocaleString()} families can set it`));

  if (lang.sample) {
    const best = complete[0]?.font || ranked[0].font;
    ensureFonts([best], lang.sample);
    out.append(el("h2", { textContent: `Sample — ${lang.name}, set in ${best.name}` }),
      el("p", { className: "sample", dir: lang.dir, style: `font-family:${stack(best)}`,
                textContent: lang.sample.slice(0, 400) }));
  }
  out.append(el("h2", { textContent: "Families" }),
    specimenList(ranked.slice(0, MAX_ROWS), lang.sample || wanted));
}

// ----------------------------------------------------------------- convert

function setupConvert() {
  const text = $("#convert-text"), cps = $("#convert-cps");
  text.oninput = () => {
    cps.value = [...text.value].map((c) => "U+" + core.hex(c.codePointAt(0))).join(" ");
    $("#convert-note").textContent = `${[...text.value].length} characters`;
    convertTable(text.value);
  };
  cps.oninput = () => {
    const [decoded, how] = core.textFromCodepoints(cps.value);
    $("#convert-note").textContent = decoded == null ? "not a list of codepoints" : `read as ${how}`;
    if (decoded != null) { text.value = decoded; convertTable(decoded); }
  };
}

function convertTable(text) {
  const table = el("table");
  table.append(el("thead", {}, el("tr", {},
    el("th", { textContent: "Char" }), el("th", { textContent: "Codepoint" }),
    el("th", { textContent: "Name" }))));
  const body = el("tbody");
  for (const ch of [...text].slice(0, 300)) {
    const cp = ch.codePointAt(0);
    body.append(el("tr", {},
      el("td", {}, glyphCell(ch)),
      el("td", { className: "num", textContent: "U+" + core.hex(cp) }),
      el("td", { textContent: core.charName(cp) })));
  }
  table.append(body);
  $("#convert-table").replaceChildren(table);
}

// -------------------------------------------------------------------- shell

function select(picker, value) {
  if ([...picker.options].some((o) => o.value === value)) picker.value = value;
}

// ------------------------------------------------------------ size ladder

const SIZE_KEY = "glyph-sleuth-size";

/** One control for how big every specimen is drawn, remembered between visits.
 *  The ladder presets are the sizes type is actually set at; the slider is for
 *  everything between. */
function setupSize() {
  const slider = $("#size");
  const out = $("#size-out");
  const saved = Number(localStorage.getItem(SIZE_KEY));
  if (saved >= Number(slider.min) && saved <= Number(slider.max)) slider.value = saved;

  const apply = (remember) => {
    const size = Number(slider.value);
    document.documentElement.style.setProperty("--specimen", `${size}px`);
    out.replaceChildren(String(size), el("span", { textContent: "px" }));
    for (const preset of document.querySelectorAll(".ladder button")) {
      preset.setAttribute("aria-pressed", String(Number(preset.dataset.size) === size));
    }
    if (remember) localStorage.setItem(SIZE_KEY, String(size));
  };
  slider.oninput = () => apply(true);
  for (const preset of document.querySelectorAll(".ladder button")) {
    preset.onclick = () => { slider.value = preset.dataset.size; apply(true); };
  }
  apply(false);
}

// Specimens only appear in these modes, so the size control only appears there.
const SPECIMEN_MODES = new Set(["search", "preview", "language"]);

function switchMode(mode) {
  for (const button of document.querySelectorAll("nav button")) {
    button.setAttribute("aria-selected", String(button.dataset.mode === mode));
  }
  for (const section of document.querySelectorAll("main section")) {
    section.hidden = section.id !== mode;
  }
  $("#specimen-bar").hidden = !SPECIMEN_MODES.has(mode);
  // Rendered on first sight, not at startup: each mode pulls webfonts to draw
  // its specimens, and a tab nobody opened should cost nothing.
  if (mode === "language") showLanguage();
  if (mode === "browse") showBrowse();
  if (mode === "preview") runPreview();
}

function echo(query) {
  const box = $("#echo");
  box.replaceChildren();
  if (query.kind === "empty") return;
  box.append("read as ", el("b", { textContent: query.label }));
  if (query.alternates.length) {
    box.append(" · or ");
    query.alternates.forEach((alt, i) => {
      const button = el("button", { textContent: alt.label });
      button.onclick = () => { showSearch(alt); switchMode("search"); };
      if (i) box.append(", ");
      box.append(button);
    });
  }
}

function runQuery(text) {
  $("#omni").value = text;
  update();
  switchMode("search");
}

function update() {
  const query = core.parse($("#omni").value,
    { fonts: core.data.fonts, languages: core.data.languages });
  echo(query);
  showSearch(query);
  const url = new URL(location);
  if ($("#omni").value) url.searchParams.set("q", $("#omni").value);
  else url.searchParams.delete("q");
  history.replaceState(null, "", url);
}

async function main() {
  document.querySelectorAll("nav button").forEach((button) => {
    button.onclick = () => switchMode(button.dataset.mode);
  });
  try {
    await core.load();
  } catch (error) {
    $("#search-results").replaceChildren(el("p", { className: "status" },
      "Could not load the font index. Run scripts/gen_web_index.py, then serve this directory."));
    return;
  }
  if (core.data.version) {
    document.querySelector(".wordmark span").textContent = `web ${core.data.version}`;
  }
  setupSize();
  setupPreview();
  setupBrowse();
  setupLanguage();
  setupConvert();
  let timer;
  $("#omni").oninput = () => { clearTimeout(timer); timer = setTimeout(update, 120); };
  $("#omni").value = new URL(location).searchParams.get("q") || "";
  switchMode("search");
  update();
}

main();
