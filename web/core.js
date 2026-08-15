// Characters, codepoints and coverage. Knows nothing about the DOM.
// The port of chars.py — same query readings, same coverage rule, so the web app
// and the desktop app can't drift into answering differently.

export const MAX_CP = 0x110000;

// ------------------------------------------------------------------ data

// Filled by load(); everything below degrades politely until then.
export const data = { blocks: [], fonts: [], languages: [], names: null, formulaic: [] };

export async function load(base = "data/") {
  const [blocks, fonts, languages, formulaic] = await Promise.all([
    fetch(base + "blocks.json").then((r) => r.json()),
    fetch(base + "fonts.json").then((r) => r.json()),
    fetch(base + "languages.json").then((r) => r.json()),
    fetch(base + "names-formulaic.json").then((r) => r.json()),
  ]);
  data.blocks = blocks.blocks;
  data.unicode = blocks.unicode;
  data.fonts = fonts.fonts;
  data.version = fonts.version || "";
  data.languages = languages.languages;
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
 *  Same rule as langs.missing_from: if the face has every piece of the NFD
 *  decomposition, the renderer will build the precomposed character anyway. */
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
 *  a real regex gives — same contract as chars.py leaning on the regex engine.
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

/** Work out what the user meant. Mirrors chars.parse, including the alternates
 *  that get shown under the box as the readings we rejected. */
export function parse(text, { fonts = [], languages = [] } = {}) {
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

  const block = data.blocks.find((b) => b[2].toLowerCase() === lowered.replace(/_/g, " "));
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

/** Names sharing a keyword with this one, rarest keyword first — the same
 *  1/frequency scoring as chars.variants, so ASTERISK outranks LATIN. */
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

export function caseVariants(ch) {
  const out = {};
  for (const [label, value] of [["upper", ch.toUpperCase()], ["lower", ch.toLowerCase()]]) {
    if (value && value !== ch) out[label] = value;
  }
  return out;
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
