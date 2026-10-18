// Inspect: read what a piece of text actually is.
//
// Loaded only by /inspect/, on demand. It reads the same tables the build reads —
// block ranges, names, Indic syllabic and positional categories, the authored
// sequence list, and which families cover each block — so a fact here and a fact
// on a character's own page come from one source.
//
// Nothing is sent anywhere. There is no server to send it to.

const BASE = document.querySelector('link[href$="style.css"]').href.replace("style.css", "");

const esc = (value) => String(value).replace(/[&<>"]/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const hex = (cp) => cp.toString(16).toUpperCase().padStart(4, "0");
const slug = (name) => name.toLowerCase().replace(/[^\w]+/g, "-").replace(/^-|-$/g, "");

// What a codepoint does in a cluster, in words rather than in property names.
const ROLES = {
  Virama: "virama — kills the inherent vowel and asks for a conjunct",
  Vowel_Dependent: "dependent vowel sign",
  Vowel_Independent: "independent vowel",
  Consonant: "consonant",
  Consonant_Dead: "dead consonant — carries no inherent vowel",
  Consonant_Medial: "medial consonant",
  Consonant_Final: "final consonant",
  Consonant_Subjoined: "subjoined consonant",
  Consonant_Preceding_Repha: "repha, drawn before the cluster",
  Consonant_Succeeding_Repha: "repha, drawn after the cluster",
  Consonant_With_Stacker: "consonant that stacks",
  Consonant_Killer: "consonant killer",
  Consonant_Placeholder: "placeholder for a missing consonant",
  Nukta: "nukta — modifies the consonant beneath it",
  Bindu: "bindu — nasalisation",
  Visarga: "visarga",
  Avagraha: "avagraha",
  Pure_Killer: "pure killer — removes the vowel without joining",
  Invisible_Stacker: "invisible stacker",
  Joiner: "zero-width joiner — asks for a joined form",
  Non_Joiner: "zero-width non-joiner — asks the shaper not to join",
  Gemination_Mark: "gemination mark",
  Tone_Mark: "tone mark",
  Cantillation_Mark: "cantillation mark",
  Syllable_Modifier: "syllable modifier",
  Modifying_Letter: "modifying letter",
  Number: "digit",
};

const POSITIONS = {
  Top: "sits above the base",
  Bottom: "sits below the base",
  Left: "drawn to the left of its base, whatever order it is typed in",
  Right: "drawn to the right of its base",
  Top_And_Bottom: "wraps above and below",
  Top_And_Right: "wraps above and right",
  Top_And_Left: "wraps above and left",
  Bottom_And_Right: "wraps below and right",
  Bottom_And_Left: "wraps below and left",
  Left_And_Right: "surrounds the base",
  Top_And_Left_And_Right: "wraps above, left and right",
  Overstruck: "struck through the base",
  Visual_Order_Left: "stored and drawn to the left",
};

// Characters that do something without drawing anything. Text that misbehaves
// often contains one of these and looks perfectly ordinary.
const INVISIBLE = {
  0x200b: "zero-width space",
  0x200c: "zero-width non-joiner (ZWNJ)",
  0x200d: "zero-width joiner (ZWJ)",
  0x200e: "left-to-right mark",
  0x200f: "right-to-left mark",
  0x00a0: "no-break space",
  0xfeff: "byte-order mark",
  0x2060: "word joiner",
  0x00ad: "soft hyphen",
};

export async function start(field, reading, out) {
  const core = await import(`${BASE}core.js`);
  const { sectionLinks } = await import(`${BASE}copy.js`);

  // Every heading this page draws can be linked to, and a link that names one
  // lands on it — once, on arrival. The sections exist only after the text is
  // read, so the browser's own jump to the fragment found nothing to jump to.
  let arrived = false;
  const linkable = (root) => {
    sectionLinks(root);
    const wanted = decodeURIComponent(location.hash.slice(1));
    if (arrived || !wanted) return;
    const target = document.getElementById(wanted);
    if (target && root.contains(target)) {
      target.scrollIntoView();
      arrived = true;
    }
  };
  const [blocks, formulaic, props, sequences, families, lazy] = await Promise.all([
    fetch(`${BASE}data/blocks.json`).then((r) => r.json()),
    fetch(`${BASE}data/names-formulaic.json`).then((r) => r.json()),
    fetch(`${BASE}data/props.json`).then((r) => r.json()),
    fetch(`${BASE}data/sequences.json`).then((r) => r.json()),
    fetch(`${BASE}data/families.json`).then((r) => r.json()),
    import(`${BASE}lazyfaces.js`),
  ]);
  core.data.blocks = blocks.blocks;
  core.data.formulaic = formulaic;
  await core.loadNames(`${BASE}data/`);

  const prop = (cp) => props[hex(cp)] || null;

  // The authored sequences, flattened: text -> what it is. This is what lets
  // Inspect say "you have typed the legacy nta" rather than listing three
  // codepoints and stopping.
  const known = new Map();
  for (const [script, entries] of Object.entries(sequences)) {
    if (script.startsWith("_")) continue;
    for (const entry of entries) {
      const text = entry.codes.split(" ")
        .map((code) => String.fromCodePoint(parseInt(code, 16))).join("");
      known.set(text, { ...entry, script });
    }
  }
  // Sequences that reach the same shape a different way: the alternate spellings
  // worth knowing, from that same authored list.
  const sameShape = new Map();
  for (const [text, entry] of known) {
    if (!entry.out) continue;
    sameShape.set(entry.out, (sameShape.get(entry.out) || []).concat([{ text, ...entry }]));
  }

  const clusters = (text) => (Intl.Segmenter
    ? [...new Intl.Segmenter(undefined, { granularity: "grapheme" }).segment(text)]
      .map((part) => part.segment)
    : [...text]);

  const copy = (value, label) =>
    `<button class="copy" data-copy="${esc(value)}" title="Copy">${label || "copy"}</button>`;

  function codepointsTable(codepoints) {
    return codepoints.map((ch) => {
      const cp = ch.codePointAt(0);
      const meta = prop(cp);
      const stand = core.standin(cp);
      const block = core.blockOf(cp);
      const role = meta && meta[1] ? ROLES[meta[1]] || meta[1].replace(/_/g, " ") : "";
      const place = meta && meta[2] ? POSITIONS[meta[2]] || meta[2].replace(/_/g, " ") : "";
      const notes = [role, place].filter(Boolean).join(" · ");
      const mark = meta && meta[0][0] === "M";
      return `<tr>
        <td class="glyph"${mark && !stand ? ` data-mark="${cp}"` : ""}>${stand
          ? `<span class="faint mono">${esc(stand)}</span>`
          : esc(mark ? "◌" + ch : ch)}</td>
        <th scope="row"><a class="mono" href="${BASE}char/${hex(cp)}/">U+${hex(cp)}</a></th>
        <td>${esc(core.charName(cp))}${notes ? `<div class="quiet">${esc(notes)}</div>` : ""}</td>
        <td class="quiet">${block
          ? `<a href="${BASE}block/${slug(block)}/">${esc(block)}</a>` : ""}</td>
        <td>${copy(ch, "⧉")}</td>
      </tr>`;
    }).join("");
  }

  function alternates(subject) {
    const rows = [];
    for (const form of ["NFC", "NFD", "NFKC", "NFKD"]) {
      const value = subject.normalize(form);
      if (value !== subject) {
        rows.push({ label: form, text: value, note: `${[...value].length} codepoints` });
      }
    }
    // Authored equivalents: the atomic chillu against the ZWJ sequence, the
    // recommended nta against the legacy one. Same shape, different encoding —
    // and which one a font handles is what the evidence pages measure.
    const match = known.get(subject);
    if (match) {
      for (const other of sameShape.get(match.out) || []) {
        if (other.text !== subject) {
          rows.push({ label: other.id, text: other.text,
            note: other.note || `another way to write ${match.out}` });
        }
      }
    }
    if (!rows.length) return "";
    return `<h2 class="eyebrow" id="other-spellings">Other ways to write it</h2>
      <div class="alts">${rows.map((row) => `<div class="alt">
        <span class="alt-glyph">${esc(row.text)}</span>
        <span class="alt-label mono">${esc(row.label)}</span>
        <span class="alt-codes mono quiet">${[...row.text]
          .map((c) => hex(c.codePointAt(0))).join(" ")}</span>
        <span class="quiet">${esc(row.note)}</span>
        ${copy(row.text)}
      </div>`).join("")}</div>
      <p class="quiet">Text that looks the same and encodes differently is the usual reason a
        search misses it, a font appears to fail, or two files refuse to compare equal.</p>`;
  }

  function recognised(subject, parts) {
    const hits = [];
    if (known.has(subject)) hits.push({ text: subject, ...known.get(subject) });
    for (const part of parts) {
      if (part !== subject && known.has(part)) hits.push({ text: part, ...known.get(part) });
    }
    if (!hits.length) return "";
    return `<h2 class="eyebrow" id="sequence">A sequence we test</h2>
      ${hits.map((hit) => `<p><strong class="mono">${esc(hit.id)}</strong> —
        ${esc(hit.note || "")}</p>
        <p class="quiet">Every measured family is checked against this one, so the verdicts
          sit on the <a href="${BASE}script/${esc(hit.script)}/">${esc(hit.script)}</a>
          families' own pages. It needs
          ${(hit.needs || []).map((tag) =>
            `<a class="mono" href="${BASE}feature/${tag}/">${tag}</a>`).join(", ")
            || "no features"}.</p>`).join("")}`;
  }

  // One file per block, fetched the first time a string touches that block. A
  // 404 is an answer — the build writes no file for a block nobody covers — but
  // a failed fetch is not, and must not be read as "no family has this".
  const coverFiles = new Map();
  const coverOf = (start) => {
    if (!coverFiles.has(start)) {
      coverFiles.set(start, fetch(`${BASE}data/cover/${hex(start)}.json`)
        .then((r) => (r.ok ? r.json() : r.status === 404 ? [] : null))
        .catch(() => null)
        // Not remembered: the next keystroke asks again.
        .then((entries) => (entries === null && coverFiles.delete(start), entries)));
    }
    return coverFiles.get(start);
  };

  // A mark in the codepoint list is drawn on a dotted circle, and the two have
  // to come from one font. The page font has neither, so each fell back on its
  // own: Chrome found one font for the pair, but Firefox drew the circle from
  // Segoe UI and the mark from Nirmala UI, whose shaper, handed a vowel sign
  // with nothing before it, added a dotted circle of its own — two on screen.
  // So each mark cell is drawn by one loadable family that has both, and is
  // hidden until that face is in hand. Unattributed, like the script page's
  // chart: the cell shows the character, not a claim about a font.
  const CIRCLE = 0x25CC;
  const markFaces = new Map();     // codepoint -> families with it and the circle
  const loaded = new Map();        // family -> settles true once its face is here
  const facesFor = (cp) => {
    if (!markFaces.has(cp)) {
      const block = core.blockAt(cp);
      const circle = core.blockAt(CIRCLE);
      markFaces.set(cp, !block || !circle ? Promise.resolve([])
        : Promise.all([coverOf(block[0]), coverOf(circle[0])]).then(([marks, shapes]) => {
          if (!marks || !shapes) return [];
          const { families: found } = core.coveringAll([cp, CIRCLE],
            new Map([[block[0], marks], [circle[0], shapes]]));
          const main = core.blockOf(cp);
          return found.map((index) => families.families[index]).filter((face) => face.draw)
            .sort((a, b) => (a.for !== main) - (b.for !== main)
              || a.name.toLowerCase().localeCompare(b.name.toLowerCase()));
        }));
    }
    return markFaces.get(cp);
  };
  const load = (face, text) => {
    if (!loaded.has(face.name)) {
      const arrived = new Promise((settle) => {
        if (face.css) {
          const link = document.createElement("link");
          link.rel = "stylesheet";
          link.href = face.css;
          link.onload = link.onerror = () => settle();
          document.head.append(link);
        } else {
          const style = document.createElement("style");
          style.textContent = face.rule;
          document.head.append(style);
          settle();
        }
      });
      loaded.set(face.name, arrived
        .then(() => document.fonts.load(`30px "${face.name}"`, text))
        .then((faces) => faces.length > 0, () => false));
    }
    return loaded.get(face.name);
  };
  const within = (promise, ms) =>
    Promise.race([promise, new Promise((settle) => setTimeout(() => settle(false), ms))]);
  async function drawMarks(root) {
    await Promise.all([...root.querySelectorAll("td[data-mark]")].map(async (cell) => {
      const cp = Number(cell.dataset.mark);
      const text = String.fromCodePoint(CIRCLE, cp);
      // The first three that cover it, in turn: one that fails to load is
      // not a reason to show the split drawing.
      for (const face of (await facesFor(cp)).slice(0, 3)) {
        if (await within(load(face, text), 4000)) {
          cell.style.fontFamily = `"${face.name}", serif`;
          break;
        }
      }
      // Shown whether or not a face arrived: a cell that never appears is worse.
      cell.dataset.drawn = "";
    }));
  }

  // ------------------------------------------------ how the families are set
  //
  // Someone choosing a font types their text, sets it the way they will use it,
  // picks the families they like and ranks them — and sends that as a link. So
  // the size, weight, italic and the ranked picks are all in the address, next
  // to the text, under the names Try it uses: px, weight, italic, pick.
  //
  // Feature switches are not here on purpose. They are per font and they are a
  // debugging tool: akhn off breaks every Malayalam conjunct, which no one
  // choosing a font wants to send. Each family's name leads to its Try it,
  // with the same text and setting, where they are.
  const WEIGHTS = [100, 200, 300, 400, 500, 600, 700, 800, 900];
  // px 0 is the layout's own size; weight 0 is each family's own regular,
  // which for a display family that ships only a bold is that bold — set
  // without comment, because nobody asked for anything else.
  const view = { px: 0, weight: 0, italic: false };
  let picks = [];          // family slugs, in the order they were ranked
  let fromLink = false;    // arrived with picks: someone sent this shortlist
  {
    const given = new URL(location.href).searchParams;
    const px = Number(given.get("px"));
    if (px) view.px = Math.min(160, Math.max(12, Math.round(px)));
    if (WEIGHTS.includes(Number(given.get("weight")))) view.weight = Number(given.get("weight"));
    view.italic = given.get("italic") === "1";
    picks = [...new Set((given.get("pick") || "").split(",").filter(Boolean))];
    fromLink = picks.length > 0;
  }

  // Replaced, not pushed, like every filter on the site: Back leaves the page.
  // A default is left out, so a plain link stays plain.
  const remember = () => {
    const url = new URL(location.href);
    const state = {
      t: field.value,
      px: view.px ? String(view.px) : "",
      weight: view.weight ? String(view.weight) : "",
      italic: view.italic ? "1" : "",
      pick: picks.join(","),
    };
    for (const [key, value] of Object.entries(state)) {
      value ? url.searchParams.set(key, value) : url.searchParams.delete(key);
    }
    history.replaceState(null, "", url);
  };

  // The face a family really has, nearest the one asked for. Asked for 700, a
  // family that publishes only 400 is set at 400 and says so: left to itself
  // the browser smears the regular into a bold, or slants it into an italic,
  // and shows that under the family's name. `font-synthesis: none` forbids it.
  const faceOf = (face) => {
    const weights = face.weights && face.weights.length ? face.weights : [400];
    const wanted = view.weight || 400;
    const weight = weights.reduce((best, w) =>
      (Math.abs(w - wanted) < Math.abs(best - wanted) ? w : best), weights[0]);
    const italic = view.italic && face.italic;
    const short = [view.weight && weight !== view.weight ? `no ${view.weight}, set at ${weight}` : "",
      view.italic && !face.italic ? "no italic" : ""].filter(Boolean).join(" · ");
    return { weight, italic, short };
  };

  // The family's own page, at its Try it, with this text set this way.
  const tryLink = (face) => {
    const { weight, italic } = faceOf(face);
    const url = new URL(`${BASE}font/${face.slug}/`, location.href);
    if (field.value) url.searchParams.set("text", field.value);
    if (view.px) url.searchParams.set("px", String(view.px));
    if (weight !== 400) url.searchParams.set("weight", String(weight));
    if (italic) url.searchParams.set("italic", "1");
    return `${url.pathname}${url.search}#try-it`;
  };

  // Apply the setting to every drawing under `root`, and say where a family
  // could not follow it.
  const restyle = (root, bySlug) => {
    for (const span of root.querySelectorAll(".tile-glyph[data-slug]")) {
      const face = bySlug.get(span.dataset.slug);
      if (!face) continue;
      const { weight, italic, short } = faceOf(face);
      span.style.fontWeight = String(weight);
      span.style.fontStyle = italic ? "italic" : "normal";
      span.style.fontSynthesis = "none";
      span.style.fontSize = view.px ? `${view.px}px` : "";
      const tile = span.closest(".draws");
      const note = tile.querySelector(".draws-short");
      note.textContent = short;
      note.hidden = !short;
      tile.href = tryLink(face);
    }
    for (const button of root.querySelectorAll("[data-pick]")) {
      const on = picks.includes(button.dataset.pick);
      button.setAttribute("aria-pressed", String(on));
      button.textContent = on ? "★" : "☆";
    }
  };

  const setWords = () => [view.px ? `${view.px}px` : "",
    view.weight ? `weight ${view.weight}` : "", view.italic ? "italic" : ""]
    .filter(Boolean).join(", ");

  let stopShortlist = () => {};
  let scrolledToShortlist = false;

  let drawing = 0;
  let stopWatching = () => {};

  // Every family that has every codepoint of the text — the question a
  // character page answers for one codepoint, asked of the whole string. This
  // used to show eight families of ten per block, chosen for covering the
  // *whole* block, so a family with the chillu but not every archaic sign was
  // absent here while the chillu's own page listed it.
  async function drawnBy(panel, subject, codepoints) {
    const turn = ++drawing;
    stopWatching();
    stopShortlist();
    const cps = codepoints.map((ch) => ch.codePointAt(0));
    const starts = [...new Set(cps.map((cp) => core.blockAt(cp)).filter(Boolean)
      .map((block) => block[0]))];
    const files = await Promise.all(starts.map(coverOf));
    if (turn !== drawing) return;
    if (files.includes(null)) {
      panel.innerHTML = `<h2 class="eyebrow" id="families">Drawn by every family that has it</h2>
        <p class="quiet">The coverage tables did not load, so this cannot say which
          families have this text. Nothing here means none do.</p>`;
      linkable(panel);
      return;
    }
    const { families: found, nobody, unknown } = core.coveringAll(
      cps, new Map(starts.map((start, at) => [start, files[at]])));

    // The block the text is mostly in, ignoring the Latin and punctuation that
    // almost every face carries — families drawn for it come first.
    const counts = new Map();
    for (const cp of cps) {
      const block = core.blockOf(cp);
      if (block) counts.set(block, (counts.get(block) || 0) + 1);
    }
    const common = /^(Basic Latin|Latin-1|General Punctuation|Spacing Modifier)/;
    const ranked = [...counts].sort((a, b) => b[1] - a[1]);
    const main = (ranked.find(([name]) => !common.test(name)) || ranked[0] || [])[0];

    const all = found.map((index) => families.families[index]);
    const drawable = all.filter((face) => face.draw)
      .sort((a, b) => (a.for !== main) - (b.for !== main)
        || a.name.toLowerCase().localeCompare(b.name.toLowerCase()));
    const undrawable = all.length - drawable.length;
    const unmeasured = families.unmeasured
      ? ` ${families.unmeasured.toLocaleString()} families have not been measured yet, so `
        + "whether they have it is not known and they are not counted."
      : "";

    const name = (cp) => `<a class="mono" href="${BASE}char/${hex(cp)}/">U+${hex(cp)}</a>`;
    if (!drawable.length) {
      const why = unknown.length
        ? `${unknown.map(name).join(", ")} ${unknown.length === 1 ? "is" : "are"} outside every
           Unicode block, so no family's coverage can be asked about it.`
        : nobody.length
          ? `No indexed family has ${nobody.map(name).join(", ")}.`
          : `No indexed family has every codepoint of this text.`;
      panel.innerHTML = `<h2 class="eyebrow" id="families">Drawn by every family that has it</h2>
        <p class="quiet">${why}${undrawable
          ? ` ${undrawable.toLocaleString()} ${undrawable === 1 ? "family has" : "families have"}
             it but ${undrawable === 1 ? "publishes" : "publish"} no webfont we can load or
             re-serve, so ${undrawable === 1 ? "it cannot" : "they cannot"} be drawn here.`
          : ""}${unmeasured}</p>`;
      linkable(panel);
      return;
    }

    // A phrase is not a glyph. Tiles of a long word are columns of clipped
    // text, so past a few characters the families become rows and the text
    // gets the full width to be read in.
    const long = clusters(subject).length > 3 || subject.length > 8;
    const bySlug = new Map(drawable.map((face) => [face.slug, face]));

    // Every tile asks for its face rather than claiming one: `data-family`, not
    // `data-face`, until lazyfaces.js has the face in hand. Two thousand Latin
    // families are two thousand webfonts, so they arrive as they are scrolled to.
    const familyDrawing = (face, row) =>
      `<a class="draws${row ? " draws-row" : ""}" href="${esc(tryLink(face))}">`
      + `<span class="draws-name">${esc(face.name)}${face.for === main ? " ·" : ""}</span>`
      + `<span class="draws-short" hidden></span>`
      + `<span class="tile-glyph" style="font-family:&quot;${esc(face.name)}&quot;,serif"`
      + ` data-family="${esc(face.name)}" data-slug="${esc(face.slug)}"`
      + (face.css ? ` data-css="${esc(face.css)}"` : "")
      + (face.rule ? ` data-rule="${esc(face.rule)}"` : "")
      + `>${esc(subject)}</span></a>`;
    const tiles = drawable.map((face) =>
      `<div class="draws-cell">${familyDrawing(face, long)}`
      + `<button type="button" class="pick" data-pick="${esc(face.slug)}" aria-pressed="false"`
      + ` title="Add to the shortlist" aria-label="Shortlist ${esc(face.name)}">☆</button></div>`)
      .join("");

    const settled = `All ${drawable.length.toLocaleString()} indexed `
      + `${drawable.length === 1 ? "family that has" : "families that have"} every codepoint `
      + "of this text and can be loaded, families drawn for this script first."
      + (undrawable
        ? ` A further ${undrawable.toLocaleString()} have it but publish no webfont we can `
          + "load or re-serve, so they cannot be drawn here."
        : "")
      + unmeasured;
    const grid = `<div class="${long ? "drawn-rows" : "drawn"}">${tiles}</div>`;
    // Someone sent a shortlist: it is what they meant to show, so it leads and
    // the rest wait one click away. Never removed — a link showing three of
    // forty-two families as though they were all would be its own small lie.
    const sent = fromLink && picks.some((pick) => bySlug.has(pick));
    panel.innerHTML = `<h2 class="eyebrow" id="families">Drawn by every family that has it</h2>
      <div class="set-in" role="group" aria-label="How every family is set">
        <label><span class="quiet">size</span><input type="range" min="12" max="160" step="1"
          data-set="px" value="${view.px || (long ? 34 : 44)}" aria-label="Size">
          <span class="mono" data-set-value>${view.px ? `${view.px}px` : "auto"}</span></label>
        <label><span class="quiet">weight</span><select data-set="weight" aria-label="Weight">
          <option value="0">as published</option>
          ${WEIGHTS.map((w) => `<option${w === view.weight ? " selected" : ""}>${w}</option>`).join("")}
          </select></label>
        <label><input type="checkbox" data-set="italic"${view.italic ? " checked" : ""}>
          <span>italic</span></label>
      </div>
      <p class="quiet set-note">Each family is set in the nearest weight it publishes, and in
        italic only if it has one; where that is not what was asked, its name says so. Nothing
        here is emboldened or slanted by the browser. ☆ adds a family to a shortlist you can
        rank and send.</p>
      <div data-shortlist></div>
      ${sent
        ? `<details class="others"><summary>Show all ${drawable.length.toLocaleString()}
             ${drawable.length === 1 ? "family" : "families"} that have this text</summary>
             ${grid}</details>`
        : grid}
      <p class="quiet"><span data-drawn-note="${esc(settled)}">${esc(settled)}</span>
        The same codepoints, drawn by each family's own face. Having every codepoint is not
        the same as drawing them correctly together — where they differ, the difference is
        the font's: which lookups it carries, and which sequences it was built to handle. A
        dot marks a family drawn for this script rather than one that merely covers it.</p>`;

    const box = panel.querySelector("[data-shortlist]");
    const indexed = new Set(all.map((face) => face.slug));

    // The shortlist: the picks in their order, drawn as rows so the text is read
    // whole, each with ↑ ↓ × and a grip to drag by. The buttons are the way that
    // works everywhere — by keyboard, and on a phone, where dragging does not.
    const shortlist = () => {
      stopShortlist();
      const shown = picks.filter((pick) => bySlug.has(pick)).map((pick) => bySlug.get(pick));
      const absent = picks.filter((pick) => !bySlug.has(pick));
      if (!shown.length && !absent.length) {
        box.innerHTML = "";
        return;
      }
      const words = setWords();
      const count = `${shown.length} ${shown.length === 1 ? "family" : "families"}`;
      const said = fromLink
        ? `Picked by whoever sent this link: ${count}${words ? `, set at ${words}` : ""}, in
           their order. Every other family that has this text is below.`
        : `Your shortlist: ${count}${words ? `, set at ${words}` : ""}. Drag a row or use the
           arrows to rank them; the link keeps the order.`;
      const rows = shown.map((face, at) =>
        `<li class="pick-row" draggable="true" data-row="${esc(face.slug)}">`
        + `<span class="grip" aria-hidden="true" title="Drag to reorder">⠿</span>`
        + familyDrawing(face, true)
        + `<span class="pick-moves">`
        + `<button type="button" data-move="-1"${at === 0 ? " disabled" : ""}`
        + ` aria-label="Move ${esc(face.name)} up">↑</button>`
        + `<button type="button" data-move="1"${at === shown.length - 1 ? " disabled" : ""}`
        + ` aria-label="Move ${esc(face.name)} down">↓</button>`
        + `<button type="button" data-drop aria-label="Remove ${esc(face.name)}">×</button>`
        + `</span></li>`).join("");
      // A pick this text cannot show is named, not dropped silently: the sender
      // chose it, and the reader should know it was there.
      const why = (pick) => (indexed.has(pick)
        ? "has this text but publishes no webfont we can load"
        : "does not have every codepoint of this text, or is not a family we index");
      const missing = absent.length
        ? `<p class="quiet">Not shown: ${absent.map((pick) =>
          `<span class="mono">${esc(pick)}</span> (${why(pick)})`).join(", ")}.</p>`
        : "";
      box.innerHTML = `<h2 class="eyebrow" id="shortlist">Shortlist</h2>
        <p class="quiet">${said}</p>
        ${rows ? `<ol class="shortlist">${rows}</ol>` : ""}${missing}
        <p class="share-row"><button type="button" class="preview" data-share>Copy link to
          this shortlist</button> <span class="quiet" data-shared role="status"></span></p>`;
      restyle(box, bySlug);
      sectionLinks(box);
      stopShortlist = lazy.watch(box.querySelectorAll("[data-family]"), null);
    };

    const changed = () => {
      remember();
      restyle(panel, bySlug);
      shortlist();
    };
    // Once the reader changes the picks they are theirs, not the sender's.
    const repicked = () => {
      fromLink = false;
      changed();
    };
    const move = (from, to) => {
      if (to < 0 || to >= picks.length || from === to) return;
      const [pick] = picks.splice(from, 1);
      picks.splice(to, 0, pick);
      repicked();
    };

    panel.addEventListener("click", async (event) => {
      const target = event.target.closest("button");
      if (!target) return;
      const row = target.closest("[data-row]");
      if (target.dataset.pick) {
        const pick = target.dataset.pick;
        picks = picks.includes(pick) ? picks.filter((p) => p !== pick) : [...picks, pick];
        repicked();
      } else if (target.dataset.move && row) {
        const at = picks.indexOf(row.dataset.row);
        move(at, at + Number(target.dataset.move));
        box.querySelector(`[data-row="${CSS.escape(row.dataset.row)}"] [data-move="${target.dataset.move}"]`)
          ?.focus();
      } else if (target.hasAttribute("data-drop") && row) {
        picks = picks.filter((p) => p !== row.dataset.row);
        repicked();
      } else if (target.hasAttribute("data-share")) {
        remember();
        const status = box.querySelector("[data-shared]");
        // The link lands on the shortlist, not on the top of Inspect.
        const link = new URL(location.href);
        link.hash = "shortlist";
        try {
          await navigator.clipboard.writeText(link.href);
          status.textContent = "Copied. It carries the text, the setting and this order.";
        } catch {
          status.textContent = "Could not copy — the address bar holds the same link.";
        }
      }
    });

    // Dragging, for a mouse: drop a row on another and it takes that place.
    let dragged = null;
    box.addEventListener("dragstart", (event) => {
      dragged = event.target.closest("[data-row]")?.dataset.row || null;
      if (dragged) event.dataTransfer.setData("text/plain", dragged);
    });
    box.addEventListener("dragover", (event) => {
      if (dragged && event.target.closest("[data-row]")) event.preventDefault();
    });
    box.addEventListener("drop", (event) => {
      const onto = event.target.closest("[data-row]");
      if (!dragged || !onto) return;
      event.preventDefault();
      move(picks.indexOf(dragged), picks.indexOf(onto.dataset.row));
      dragged = null;
    });

    for (const control of panel.querySelectorAll("[data-set]")) {
      control.addEventListener("input", () => {
        if (control.dataset.set === "px") {
          view.px = Number(control.value);
          panel.querySelector("[data-set-value]").textContent = `${view.px}px`;
        }
        if (control.dataset.set === "weight") view.weight = Number(control.value);
        if (control.dataset.set === "italic") view.italic = control.checked;
        changed();
      });
    }

    restyle(panel, bySlug);
    shortlist();
    linkable(panel);
    // A sent shortlist is what the link is for, and it sits below the codepoint
    // table: go to it, once, even from a link copied out of the address bar.
    if (sent && !location.hash && !scrolledToShortlist) {
      box.querySelector("#shortlist")?.scrollIntoView();
      scrolledToShortlist = true;
    }
    stopWatching = lazy.watch(panel.querySelectorAll(".drawn [data-family], .drawn-rows [data-family]"),
      panel.querySelector("[data-drawn-note]"));
  }

  function warnings(subject, codepoints, parts) {
    const notes = [];
    const invisibles = codepoints.filter((ch) => INVISIBLE[ch.codePointAt(0)]);
    if (invisibles.length) {
      notes.push(`Contains ${invisibles.length} invisible character(s): `
        + [...new Set(invisibles.map((ch) => INVISIBLE[ch.codePointAt(0)]))].join(", ")
        + ". They draw nothing and change everything.");
    }
    if (subject.normalize("NFC") !== subject) {
      notes.push("Not in NFC. Most software searches and compares in NFC, so this may not "
        + "match text that looks identical to it.");
    }
    const first = codepoints.length ? prop(codepoints[0].codePointAt(0)) : null;
    if (first && first[0][0] === "M") {
      notes.push("Starts with a combining mark, which has no base to attach to — a shaper "
        + "will draw it on a dotted circle.");
    }
    const scripts = new Set(codepoints.map((ch) => core.blockOf(ch.codePointAt(0)))
      .filter(Boolean)
      .filter((name) => !/^(Basic Latin|Latin-1|General Punctuation)/.test(name)));
    if (scripts.size > 1) {
      notes.push(`Mixes ${scripts.size} scripts: ${[...scripts].join(", ")}. Ordinary in `
        + "prose, worth knowing in an identifier, a filename or a domain.");
    }
    if (parts.length !== codepoints.length) {
      notes.push(`${parts.length} cluster${parts.length === 1 ? "" : "s"} from `
        + `${codepoints.length} codepoints — what reads as one character is several `
        + "codepoints, and a font's lookups decide what you see.");
    }
    if (!notes.length) return "";
    return `<h2 class="eyebrow" id="worth-knowing">Worth knowing</h2>
      <ul class="notes">${notes.map((note) => `<li>${esc(note)}</li>`).join("")}</ul>`;
  }

  function elsewhere(subject, codepoints) {
    const codes = codepoints.map((ch) => hex(ch.codePointAt(0)));
    const command = `hb-shape --font-file=YOUR.ttf --unicodes=${codes.join(",")}`;
    const rows = [
      ["Codepoints", codes.map((code) => `U+${code}`).join(" ")],
      ["JS escape", codepoints.map((ch) => `\\u{${hex(ch.codePointAt(0))}}`).join("")],
      ["HTML", codepoints.map((ch) => `&#x${hex(ch.codePointAt(0))};`).join("")],
      ["UTF-8", codepoints.map((ch) => core.encodings(ch.codePointAt(0))["UTF-8"]).join(" ")],
      ["hb-shape", command],
    ];
    // Forty bytes of hex is a wall, not information. Show the beginning and
    // say what was left out; copy still takes the whole thing.
    const shorten = (value) => (value.length <= 96 ? esc(value)
      : `${esc(value.slice(0, 96))}<span class="quiet"> … ${value.length} characters</span>`);
    return `<h2 class="eyebrow" id="take-it-away">Take it away</h2>
      <div class="pairs">${rows.map(([label, value]) => `<div class="pair">
        <span class="quiet">${esc(label)}</span>
        <span class="row-copy"><span class="mono break">${shorten(value)}</span>
          ${copy(value)}</span>
      </div>`).join("")}</div>
      <p class="quiet">Or check it against other people's tools:
        <a href="https://r12a.github.io/app-analysestring/index.html?chars=${encodeURIComponent(subject)}"
           target="_blank" rel="noopener">r12a String Analyser ↗</a> ·
        <a href="https://r12a.github.io/uniview/?charlist=${encodeURIComponent(subject)}"
           target="_blank" rel="noopener">Uniview ↗</a> — external. They disagree with us
        often enough to be worth having side by side.</p>`;
  }

  function show(text) {
    if (!text) {
      out.innerHTML = "";
      reading.textContent = "";
      drawing += 1;
      stopWatching();
      return;
    }
    const query = core.parse(text);
    const others = (query.alternates || []).map((alternate) => alternate.label).filter(Boolean);
    reading.innerHTML = `Read as <strong>${esc(query.label)}</strong>`
      + (others.length ? ` · also reads as ${others.map(esc).join(", ")}` : "");

    let subject = text;
    if (query.kind === "char") subject = String.fromCodePoint(query.value);
    else if (query.kind === "codepoints") {
      subject = query.value.map((cp) => String.fromCodePoint(cp)).join("");
    } else if (query.kind === "range") {
      const [first, last] = query.value;
      subject = Array.from({ length: Math.min(last - first + 1, 128) },
        (_, index) => String.fromCodePoint(first + index)).join("");
    }

    const codepoints = [...subject];
    const parts = clusters(subject);

    out.innerHTML = `<div class="specimen-line">${esc(subject)}
        ${copy(subject, "copy text")}</div>
      <div class="inspect-grid">
        <div>
          <h2 class="eyebrow" id="codepoints">${codepoints.length} codepoint${codepoints.length === 1 ? "" : "s"}
            in ${parts.length} cluster${parts.length === 1 ? "" : "s"}</h2>
          <div class="scroll"><table class="index tight"><tbody>
            ${codepointsTable(codepoints)}
          </tbody></table></div>
        </div>
        <div>
          ${recognised(subject, parts)}
          ${alternates(subject)}
          ${warnings(subject, codepoints, parts)}
          ${elsewhere(subject, codepoints)}
        </div>
      </div>
      <section id="drawn-by"></section>`;
    linkable(out);
    drawMarks(out);
    drawnBy(out.querySelector("#drawn-by"), subject, codepoints);
  }

  // Copy buttons are app.js’s, for every page at once — see copy.js.

  const url = new URL(location.href);
  if (url.searchParams.get("t")) field.value = url.searchParams.get("t");
  show(field.value);

  let pending;
  field.addEventListener("input", () => {
    clearTimeout(pending);
    pending = setTimeout(() => {
      remember();
      show(field.value);
    }, 150);
  });
}
