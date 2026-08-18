// Characters, codepoints and coverage. Knows nothing about the DOM.
// Ported from the archived first attempt, where it was the port of chars.py —
// same query readings, same coverage rule, so the site and the desktop
// companion can't drift into answering differently.

export const MAX_CP = 0x110000;

// ------------------------------------------------------------------ data

// Filled by load(); everything below degrades politely until then.
export const data = { blocks: [], fonts: [], languages: [], scripts: [],
                      names: null, formulaic: [] };

export async function load(base = "data/") {
  const [blocks, fonts, languages, scripts, formulaic] = await Promise.all([
    fetch(base + "blocks.json").then((r) => r.json()),
    fetch(base + "fonts.json").then((r) => r.json()),
    fetch(base + "languages.json").then((r) => r.json()),
    fetch(base + "scripts.json").then((r) => r.json()),
    fetch(base + "names-formulaic.json").then((r) => r.json()),
  ]);
  data.blocks = blocks.blocks;
  data.unicode = blocks.unicode;
  data.fonts = fonts.fonts;
  data.version = fonts.version || "";
  data.languages = languages.languages;
  data.scripts = scripts.scripts;
  data.formulaic = formulaic;
  return data;
}

// The name table is 1.4 MB, so it arrives only when something actually needs it.
let namesPending = null;
export function loadNames(base = "data/") {
  if (!namesPending) {
    namesPending = fetch(base + "names.txt")
      .then((r) => r.text())
      .then((text) => {
        const names = new Map();
        for (const line of text.split("\n")) {
          const tab = line.indexOf("\t");
          if (tab > 0) names.set(parseInt(line.slice(0, tab), 16), line.slice(tab + 1));
        }
        data.names = names;
        return names;
      });
  }
  return namesPending;
}

export function charName(cp) {
  if (data.names && data.names.has(cp)) return data.names.get(cp);
  for (const [prefix, lo, hi] of data.formulaic) {
    if (cp >= lo && cp <= hi) return `${prefix}-${hex(cp)}`;
  }
  return data.names ? `<unnamed U+${hex(cp)}>` : `U+${hex(cp)}`;
}

export const hex = (cp) => cp.toString(16).toUpperCase().padStart(4, "0");

// -------------------------------------------------------------- coverage

/** Is a codepoint in a sorted [[first, last], ...] list? Bisected, not scanned. */
export function covers(ranges, cp) {
  let lo = 0, hi = ranges.length - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (cp < ranges[mid][0]) hi = mid - 1;
    else if (cp > ranges[mid][1]) lo = mid + 1;
    else return true;
  }
  return false;
}

export function countIn(ranges) {
  let total = 0;
  for (const [first, last] of ranges) total += last - first + 1;
  return total;
}

/** Characters a face can't produce — directly or by composing the pieces.
 *  If the face has every piece of the NFD decomposition, the renderer will
 *  build the precomposed character anyway, so it is not missing. */
export function missingFrom(ranges, text) {
  const missing = new Set();
  for (const ch of unique(text)) {
    const cp = ch.codePointAt(0);
    if (covers(ranges, cp)) continue;
    const pieces = ch.normalize("NFD");
    if (pieces !== ch && [...pieces].every((p) => covers(ranges, p.codePointAt(0)))) continue;
    missing.add(ch);
  }
  return missing;
}

/** [{font, missing}] over the given text, best coverage first. */
export function rankFonts(text, fonts = data.fonts, limit = 0) {
  const wanted = unique(stripFormatting(text));
  const rows = fonts.map((font) => ({ font, missing: missingFrom(font.ranges, wanted) }));
  rows.sort((a, b) =>
    a.missing.size - b.missing.size ||
    countIn(b.font.ranges) - countIn(a.font.ranges) ||
    a.font.name.localeCompare(b.font.name));
  return limit ? rows.slice(0, limit) : rows;
}

export function fontsWith(cp, fonts = data.fonts) {
  return fonts.filter((font) => covers(font.ranges, cp));
}

/** How many codepoints of first..last a face covers. Ranges are sorted, so this
 *  stops as soon as it passes the end. */
export function countInRange(ranges, first, last) {
  let total = 0;
  for (const [lo, hi] of ranges) {
    if (hi < first) continue;
    if (lo > last) break;
    total += Math.min(hi, last) - Math.max(lo, first) + 1;
  }
  return total;
}

/** [{font, count}] for the faces with anything at all to draw in first..last,
 *  most coverage first. Offering a face that draws none of a block is offering
 *  a page of empty boxes. */
export function fontsForRange(first, last, fonts = data.fonts) {
  const scored = [];
  for (const font of fonts) {
    const count = countInRange(font.ranges, first, last);
    if (count) scored.push({ font, count });
  }
  scored.sort((a, b) => b.count - a.count || a.font.name.localeCompare(b.font.name));
  return scored;
}

// Latin and the shared punctuation almost every face carries say nothing about
// what a font is *for*, so they don't get a vote on which block dominates it.
const COMMON_BLOCKS = new Set([
  "Basic Latin", "Latin-1 Supplement", "Latin Extended-A", "Latin Extended-B",
  "Latin Extended Additional", "General Punctuation", "Spacing Modifier Letters",
  "Combining Diacritical Marks", "Currency Symbols", "Letterlike Symbols",
  "Number Forms", "Mathematical Operators", "Geometric Shapes", "Private Use Area",
  "Alphabetic Presentation Forms", "Superscripts and Subscripts", "Arrows",
  "Miscellaneous Symbols", "Dingbats", "Specials", "Halfwidth and Fullwidth Forms",
  // Phonetics and diacritics are what a broad Latin face carries, never the
  // script it is for — nobody sets a page of IPA Extensions.
  "IPA Extensions", "Phonetic Extensions", "Phonetic Extensions Supplement",
  "Combining Diacritical Marks Supplement", "Combining Diacritical Marks Extended",
  "Combining Diacritical Marks for Symbols", "Latin Extended-C", "Latin Extended-D",
  "Latin Extended-E", "Latin Extended-F", "Latin Extended-G", "Modifier Tone Letters",
  "Supplemental Punctuation", "Small Form Variants",
]);

/** The block this face exists for, or null when there isn't one.
 *
 *  "Largest block" alone is the wrong test: DejaVu's biggest non-Latin block is
 *  Greek, but DejaVu is not a Greek font — it is a workhorse that carries a bit
 *  of everything, and for those the Latin pangram is the honest specimen. So the
 *  block has to actually dominate the face: at least half of everything it has
 *  outside Latin and punctuation. */
export function dominantBlock(font) {
  const spend = new Map();
  let total = 0;
  for (const [first, last] of font.ranges) {
    const block = blockOf(first);
    if (!block || COMMON_BLOCKS.has(block)) continue;
    const count = last - first + 1;
    spend.set(block, (spend.get(block) || 0) + count);
    total += count;
  }
  let best = null;
  for (const [block, count] of spend) {
    if (!best || count > best.count) best = { block, count };
  }
  return best && best.count >= 24 && best.count >= total * 0.5 ? best.block : null;
}

// ------------------------------------------------------------- scripts

/** How many of a script's codepoints a face covers, block by block.
 *  Returns { chars, covered, blocks: [{ name, chars, covered }] } — the shape
 *  the support matrix is drawn from. */
export function scriptCoverage(font, script) {
  const blocks = script.blocks.map((block) => ({
    name: block.name,
    chars: block.chars,
    covered: block.ranges.reduce(
      (total, [first, last]) => total + countInRange(font.ranges, first, last), 0),
  }));
  return {
    chars: blocks.reduce((total, block) => total + block.chars, 0),
    covered: blocks.reduce((total, block) => total + block.covered, 0),
    blocks,
  };
}

/** Faces with anything to offer this script, the ones that cover all of it
 *  first. A script is not one block, so "covers Tamil" has to mean every block
 *  of Tamil — including the supplement almost nothing has. */
export function fontsForScript(script, fonts = data.fonts) {
  const rows = [];
  for (const font of fonts) {
    const coverage = scriptCoverage(font, script);
    if (coverage.covered) rows.push({ font, ...coverage });
  }
  rows.sort((a, b) => b.covered - a.covered || a.font.name.localeCompare(b.font.name));
  return rows;
}

export function scriptByCode(code) {
  return data.scripts.find((script) => script.code === code) || null;
}

export function scriptsOf(lang) {
  return (lang.scripts || []).map(scriptByCode).filter(Boolean);
}

/** Languages SIL records as written in this script — the reverse of the list on
 *  a language, and the reason a script deserves its own page. */
export function languagesUsing(script, limit = 0) {
  const names = script.languages
    .map((id) => data.languages.find((lang) => lang.id === id))
    .filter(Boolean)
    .sort((a, b) => a.name.localeCompare(b.name));
  return limit ? names.slice(0, limit) : names;
}

/** Which of these scripts the text is actually written in — the one covering
 *  most of its characters. A language's exemplars belong to one orthography,
 *  and showing Latin letters beside the Arabic page is a lie by placement. */
export function scriptOfText(text, scripts) {
  let best = null;
  for (const script of scripts) {
    let hits = 0;
    for (const ch of new Set([...stripFormatting(text)])) {
      const cp = ch.codePointAt(0);
      if (script.blocks.some((block) =>
        block.ranges.some(([first, last]) => cp >= first && cp <= last))) hits++;
    }
    if (hits && (!best || hits > best.hits)) best = { script, hits };
  }
  return best ? best.script : null;
}

/** Letters of a script to set as a specimen. Letters only: marks alone are a row
 *  of dotted circles, and the signs, digits and punctuation a script block also
 *  holds say nothing about how the face draws the writing system. */
export function scriptLetters(script, limit = 22) {
  const letters = [];
  for (const block of script.blocks) {
    for (const [first, last] of block.ranges) {
      for (let cp = first; cp <= last && letters.length < limit; cp++) {
        const ch = String.fromCodePoint(cp);
        if (standin(cp) || !/\p{L}/u.test(ch)) continue;
        letters.push(ch);
      }
    }
    if (letters.length >= limit) break;
  }
  return letters;
}

// ---------------------------------------------------------- reading on

/** The one outbound further-reading link an entity page carries.
 *
 *  One link, not a row of them (conventions.md), and the first source that
 *  actually covers the entity wins: Richard Ishida's script notes, then Writing
 *  Systems Technical Resources, then Wikipedia as the always-available
 *  fallback. Which of the first two covers a given entity is not guessable, so
 *  the generator records the real URLs in `sources` and this only chooses —
 *  a fabricated link is worse than the fallback.
 *
 *  writingsystems.info is ScriptSource's successor; ScriptSource closes at the
 *  end of September 2026 and is deliberately absent. So is Omniglot: wrong
 *  trust register for this audience. */
export function furtherReading(entity) {
  const name = entity.name.replace(/ \(.*\)$/, "");
  const sources = entity.sources || {};
  const thing = entity.kind === "language" ? "language" : "script";

  if (sources.r12a) {
    return { url: sources.r12a, external: true,
             label: `Orthography and encoding notes for ${name} at r12a.io` };
  }
  if (sources.writingsystems) {
    return { url: sources.writingsystems, external: true,
             label: `${name} at Writing Systems Technical Resources` };
  }
  const slug = `${name.replace(/ /g, "_")}_${thing}`;
  return { url: `https://en.wikipedia.org/wiki/${slug}`, external: true,
           label: `${name} ${thing} at Wikipedia` };
}

/** The Unicode chart PDF for a block — the authority on what is in it. */
export function blockChart(block) {
  const first = block.ranges[0][0];
  return `https://www.unicode.org/charts/PDF/U${hex(first - (first % 0x80))}.pdf`;
}

// --------------------------------------------------------- taking it away

/** Where to get the actual font files. Google serves a zip of the family; every
 *  other foundry gets you to its own release page, so the label says so rather
 *  than promising a file that doesn't arrive. */
export function download(font) {
  if (font.source === "google") {
    return { url: `https://fonts.google.com/download?family=${font.name.replace(/ /g, "+")}`,
             label: "Download", direct: true };
  }
  return { url: font.url, label: "Download", direct: false };
}

/** The CSS someone needs to set text in this face on their own site, and which
 *  of three honest states it is in.
 *
 *  We host no font files at all, so this never points at us. The chain is
 *  Google Fonts if the family is actually distributed there, then the foundry's
 *  own hosted stylesheet, then a self-host template — never a fabricated
 *  @import for a family that has none, which is what the prototype did. */
export function useIt(font) {
  if (font.source === "google") {
    const slug = font.name.replace(/ /g, "+");
    return {
      kind: "google",
      note: "Served from Google Fonts.",
      code: `<link rel="stylesheet"\n      href="https://fonts.googleapis.com/css2?family=${slug}&display=swap">\n\n`
        + `font-family: "${font.name}", sans-serif;`,
    };
  }
  if (font.css) {
    return {
      kind: "foundry",
      note: "Served from the foundry's own site.",
      code: `<link rel="stylesheet" href="${font.css}">\n\n`
        + `font-family: "${font.name}", sans-serif;`,
    };
  }
  const file = `${font.name.replace(/ /g, "")}.woff2`;
  return {
    kind: "self-host",
    note: "This family is not served from a public CDN — download it and host the file yourself.",
    code: `@font-face {\n  font-family: "${font.name}";\n  src: url("${file}") format("woff2");\n`
      + `  font-display: swap;\n}\n\nfont-family: "${font.name}", sans-serif;`,
  };
}

// A specimen sheet shows a line, not an essay: forty faces each repeating a
// paragraph is the same clutter a table is, in a different shape.
export const SPECIMEN_CHARS = 110;

/** The text an entry is set in: one flattened line, cut on a word. */
export function trimToSpecimen(text) {
  const flat = text.replace(/\s+/g, " ").trim();
  if (flat.length <= SPECIMEN_CHARS) return flat;
  const cut = flat.slice(0, SPECIMEN_CHARS);
  const lastSpace = cut.lastIndexOf(" ");
  return (lastSpace > SPECIMEN_CHARS * 0.6 ? cut.slice(0, lastSpace) : cut) + "…";
}

/** Every distinct character, in first-seen order — one row each, not one per use. */
export function unique(text) {
  return [...new Set([...text])];
}

/** Space and newlines are the renderer's business, not the font's. */
export function stripFormatting(text) {
  return [...text].filter((ch) => !/\s/u.test(ch)).join("");
}

// ------------------------------------------------------------- blocks

export function blockOf(cp) {
  let lo = 0, hi = data.blocks.length - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (cp < data.blocks[mid][0]) hi = mid - 1;
    else if (cp > data.blocks[mid][1]) lo = mid + 1;
    else return data.blocks[mid][2];
  }
  return null;
}

export function blockRange(name) {
  const wanted = name.toLowerCase().replace(/_/g, " ");
  const found = data.blocks.find((b) => b[2].toLowerCase() === wanted);
  return found ? [found[0], found[1]] : null;
}

// --------------------------------------------------------- properties

const matchers = new Map();

/** \p{...} against the browser's own Unicode tables, so the answer is the answer
 *  a real regex gives — and every property label shown is one you can paste
 *  straight into code.
 *  ponytail: JS regex has no \p{Block=...}, so blocks come from the UCD table. */
export function matchesProperty(ch, expr) {
  const block = /^(?:blk|block)\s*=\s*(.+)$/i.exec(expr);
  if (block) {
    const range = blockRange(block[1].trim());
    return !!range && ch.codePointAt(0) >= range[0] && ch.codePointAt(0) <= range[1];
  }
  if (!matchers.has(expr)) {
    let re = null;
    try { re = new RegExp(`^\\p{${expr}}$`, "u"); } catch { re = null; }
    matchers.set(expr, re);
  }
  const re = matchers.get(expr);
  return !!re && re.test(ch);
}

export function validProperty(expr) {
  if (/^(?:blk|block)\s*=/i.test(expr)) return !!blockRange(expr.split("=")[1].trim());
  try { new RegExp(`\\p{${expr}}`, "u"); return true; } catch { return false; }
}

/** Codepoints matching a \p{...}, capped — the whole codespace is 1.1M wide. */
export function matchingProperty(expr, limit = 5000) {
  const found = [];
  const range = /^(?:blk|block)\s*=\s*(.+)$/i.test(expr) ? blockRange(expr.split("=")[1].trim()) : null;
  const [start, end] = range || [0, MAX_CP - 1];
  for (let cp = start; cp <= end && found.length < limit; cp++) {
    if (cp >= 0xd800 && cp <= 0xdfff) continue;
    if (matchesProperty(String.fromCodePoint(cp), expr)) found.push(cp);
  }
  return found;
}

// A short label for characters with no ink of their own.
const STANDIN = new Map([
  [0x20, "SP"], [0x09, "TAB"], [0x0a, "LF"], [0x0d, "CR"], [0xa0, "NBSP"],
  [0x200b, "ZWSP"], [0x200c, "ZWNJ"], [0x200d, "ZWJ"], [0xfeff, "BOM"],
]);

export function standin(cp) {
  if (STANDIN.has(cp)) return STANDIN.get(cp);
  const ch = String.fromCodePoint(cp);
  if (/\p{Cc}|\p{Cf}|\p{Zl}|\p{Zp}|\p{Zs}|\p{Cs}|\p{Cn}/u.test(ch)) return "�";
  return null;
}

// ------------------------------------------------------- query parsing

const CP_PREFIXED = /^(?:U\+|u\+|0x|0X|\\u|\\U|&#x|&#X)([0-9A-Fa-f]{1,6});?$/;
const PROP = /^\\?p\{(.+)\}$/;
const RANGE = /^(?:U\+|0x|)([0-9A-Fa-f]{2,6})\s*(?:\.\.|-|…)\s*(?:U\+|0x|)([0-9A-Fa-f]{2,6})$/i;

const valid = (cp) => Number.isInteger(cp) && cp >= 0 && cp < MAX_CP;
const query = (kind, value, label, alternates = []) => ({ kind, value, label, alternates });

/** Work out what the user meant, including the alternates shown under the box
 *  as the readings we rejected. */
export function parse(text, { fonts = [], languages = [], scripts = [] } = {}) {
  const raw = text.trim();
  if (!raw) return query("empty", null, "nothing yet");

  let m = PROP.exec(raw);
  if (m && (raw.startsWith("\\p") || raw.startsWith("p{"))) {
    const expr = m[1].trim();
    return query("prop", expr, `\\p{${expr}}`);
  }

  m = CP_PREFIXED.exec(raw);
  if (m && valid(parseInt(m[1], 16))) return query("char", parseInt(m[1], 16), "codepoint");

  m = RANGE.exec(raw);
  if (m) {
    const [lo, hi] = [parseInt(m[1], 16), parseInt(m[2], 16)];
    if (valid(lo) && valid(hi) && lo <= hi) return query("range", [lo, hi], "codepoint range");
  }

  if ([...raw].length === 1) {
    const alternates = /^[0-9a-fA-F]$/.test(raw) ? [query("char", parseInt(raw, 16), "codepoint")] : [];
    return query("char", raw.codePointAt(0), "character", alternates);
  }

  // A bare number. In a Unicode tool "2731" means U+2731, but decimal is a real
  // reading too, so it goes in the alternates rather than being thrown away.
  if (/^[0-9A-Fa-f]{2,7}$/.test(raw)) {
    const readings = [];
    const asHex = parseInt(raw, 16);
    if (valid(asHex)) readings.push(query("char", asHex, "hex codepoint"));
    if (/^[0-9]+$/.test(raw) && valid(parseInt(raw, 10))) {
      readings.push(query("char", parseInt(raw, 10), "decimal codepoint"));
    }
    if (readings.length) {
      const [head, ...tail] = readings;
      return query(head.kind, head.value, head.label, [...tail, query("name", raw, "name search")]);
    }
  }

  const lowered = raw.toLowerCase();

  // "Devanagari" is both a script and a block, and the script is the bigger
  // answer — it spans three blocks. The block stays on offer as the alternate.
  const block = data.blocks.find((b) => b[2].toLowerCase() === lowered.replace(/_/g, " "));
  const script = scripts.find((s) => s.name.toLowerCase() === lowered
    || s.code.toLowerCase() === lowered);
  if (script) {
    return query("script", script.code, "script",
                 block ? [query("block", block[2], "unicode block")] : []);
  }
  if (block) return query("block", block[2], "unicode block");

  const font = fonts.find((f) => f.name.toLowerCase() === lowered);
  if (font) return query("font", font.name, "font family");

  const language = languages.find(
    (l) => l.tag.toLowerCase() === lowered || l.name.toLowerCase() === lowered);
  if (language) return query("lang", language.id || language.tag, "language");

  const parts = raw.replace(/,/g, " ").split(/\s+/).filter(Boolean);
  if (parts.length > 1) {
    const cps = codepointsFromTokens(parts);
    if (cps) return query("codepoints", cps, `${cps.length} codepoints`, [query("text", raw, "literal text")]);
  }

  if (/^[A-Za-z][A-Za-z \-']*$/.test(raw)) {
    return query("name", raw, "name search", [query("text", raw, "text to cover")]);
  }

  return query("text", raw, `text · ${[...raw].length} chars`);
}

export function codepointsFromTokens(tokens) {
  const out = [];
  for (let token of tokens) {
    token = token.trim().replace(/;$/, "");
    if (!token) continue;
    const prefixed = CP_PREFIXED.exec(token);
    let cp;
    if (prefixed) cp = parseInt(prefixed[1], 16);
    else if (/^[0-9]+$/.test(token)) cp = parseInt(token, 10);
    else if (/^[0-9A-Fa-f]{2,6}$/.test(token)) cp = parseInt(token, 16);
    else return null;
    if (!valid(cp)) return null;
    out.push(cp);
  }
  return out.length ? out : null;
}

/** Free-form codepoint notation -> the string it denotes, and how it was read. */
export function textFromCodepoints(text) {
  const tokens = text.replace(/,/g, " ").split(/\s+/).filter(Boolean);
  const cps = codepointsFromTokens(tokens);
  if (!cps) return [null, null];
  const allBytes = tokens.length > 1 && tokens.every((t) => /^[0-9A-Fa-f]{2}$/.test(t.trim()));
  if (allBytes) {
    try {
      const bytes = Uint8Array.from(tokens, (t) => parseInt(t, 16));
      const decoded = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
      return [decoded, "utf-8 bytes"];
    } catch { /* not valid UTF-8, so they were codepoints after all */ }
  }
  return [cps.map((c) => String.fromCodePoint(c)).join(""), "codepoints"];
}

/** Names sharing a keyword with this one, rarest keyword first, so ASTERISK
 *  outranks LATIN. */
const STOPWORDS = new Set(`LETTER CAPITAL SMALL WITH AND SIGN MARK SYMBOL COMBINING MODIFIER
CHARACTER FORM ABOVE BELOW OVERLAY LEFT RIGHT UPPER LOWER MIDDLE CENTRE CENTER OPEN HEAVY LIGHT
MEDIUM BOLD VERY EXTREMELY OF THE DIGIT NUMBER SPACING NON FINAL INITIAL ISOLATED MEDIAL TURNED
REVERSED ROTATED INVERTED`.split(/\s+/));

export function keywords(name) {
  const words = new Set(name.replace(/-/g, " ").split(/\s+/).filter((w) => w.length > 1));
  const kept = [...words].filter((w) => !STOPWORDS.has(w));
  return kept.length ? kept : [...words];
}

let keywordIndex = null;
function index() {
  if (!keywordIndex) {
    keywordIndex = new Map();
    for (const [cp, name] of data.names || []) {
      for (const word of name.replace(/-/g, " ").split(" ")) {
        if (!keywordIndex.has(word)) keywordIndex.set(word, []);
        keywordIndex.get(word).push(cp);
      }
    }
  }
  return keywordIndex;
}

export function variants(cp, limit = 200) {
  const idx = index();
  const name = charName(cp);
  if (name.startsWith("<")) return [];
  const scores = new Map();
  for (const word of keywords(name)) {
    const hits = idx.get(word);
    if (!hits) continue;
    const weight = 1 / hits.length;
    for (const other of hits) scores.set(other, (scores.get(other) || 0) + weight);
  }
  scores.delete(cp);
  const ranked = [...scores].sort((a, b) => b[1] - a[1] || a[0] - b[0]).map(([c]) => c);
  return [cp, ...ranked.slice(0, limit)];
}

export function searchNames(text, limit = 300) {
  const idx = index();
  const words = text.toUpperCase().replace(/-/g, " ").split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  let hits = null;
  for (const word of words) {
    const matches = new Set();
    for (const [key, cps] of idx) if (key.startsWith(word)) for (const cp of cps) matches.add(cp);
    hits = hits ? new Set([...hits].filter((cp) => matches.has(cp))) : matches;
    if (!hits.size) return [];
  }
  return [...hits].sort((a, b) => a - b).slice(0, limit);
}

export function normalizationVariants(text) {
  return ["NFC", "NFD", "NFKC", "NFKD"].map((form) => [form, text.normalize(form)]);
}

export function encodings(cp) {
  const ch = String.fromCodePoint(cp);
  const bytes = (array) => [...array].map((b) => b.toString(16).toUpperCase().padStart(2, "0")).join(" ");
  const units = [];
  for (let i = 0; i < ch.length; i++) units.push(ch.charCodeAt(i).toString(16).toUpperCase().padStart(4, "0"));
  return {
    "UTF-8": bytes(new TextEncoder().encode(ch)),
    "UTF-16": units.join(" "),
    "Decimal": String(cp),
    "HTML": `&#${cp};`,
    "CSS": `\\${hex(cp).toLowerCase()}`,
    "JS": cp > 0xffff ? `\\u{${hex(cp)}}` : `\\u${hex(cp)}`,
    "URL": encodeURIComponent(ch),
  };
}

// ------------------------------------------------------- did the face load?

/** A CSS font shorthand for asking about one family, quoted safely.
 *
 *  Family names carry spaces, dots and apostrophes — "Baloo Chettan 2", "RIT
 *  Rachana", "M PLUS 1p" — and an unquoted name in a font shorthand is parsed
 *  as a list of keywords, so the question silently becomes a different question.
 */
export function fontShorthand(size, family, fallback = "") {
  const quoted = `"${String(family).replace(/["\\]/g, "\\$&")}"`;
  return `${size}px ${quoted}${fallback ? `, ${fallback}` : ""}`;
}
