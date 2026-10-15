// The tables Inspect reads, checked against the tables the build wrote:
// `node web/tests/test-inspect.mjs`, after a build.
//
// test-core.mjs proves the logic with hand-fed data. This proves the logic and
// the *served files* agree — a rename or a format change in the generator would
// leave Inspect reading nothing, and every unit test would still pass.
import assert from "node:assert/strict";
import fs from "node:fs";
import * as core from "../core.js";

const site = new URL("../../site/data/", import.meta.url);
const read = (name) => fs.readFileSync(new URL(name, site), "utf8");

if (!fs.existsSync(new URL("blocks.json", site))) {
  console.log("  no build to check — run web/build/render.py first");
  process.exit(0);
}

core.data.blocks = JSON.parse(read("blocks.json")).blocks;
core.data.formulaic = JSON.parse(read("names-formulaic.json"));
const props = JSON.parse(read("props.json"));
const sequences = JSON.parse(read("sequences.json"));
const families = JSON.parse(read("families.json"));

// The same parse loadNames() does, against the same file it fetches.
const names = new Map();
for (const line of read("names.txt").split("\n")) {
  const tab = line.indexOf("\t");
  if (tab > 0) names.set(parseInt(line.slice(0, tab), 16), line.slice(tab + 1));
}
core.data.names = names;

const hex = (cp) => cp.toString(16).toUpperCase().padStart(4, "0");

function test_tables_are_readable() {
  assert.ok(core.data.blocks.length > 300, `only ${core.data.blocks.length} blocks`);
  assert.ok(names.size > 40000, `only ${names.size} names`);
  // Formulaic ranges cover the names that are a pattern rather than a word,
  // which is how the served table stays 1.3 MB instead of 4.
  assert.ok(core.data.formulaic.length > 0);
  assert.equal(core.charName(0x4e2d), "CJK UNIFIED IDEOGRAPH-4E2D");
}

function test_the_readings_hold_against_real_tables() {
  assert.equal(core.charName(0x0d15), "MALAYALAM LETTER KA");
  assert.equal(core.blockOf(0x0d15), "Malayalam");
  assert.equal(core.blockOf(0x0b95), "Tamil");
  assert.equal(core.parse("0D15").label, "hex codepoint");
  assert.equal(core.parse("U+0D15").kind, "char");
  assert.equal(core.encodings(0x0d15)["UTF-8"], "E0 B4 95");
}

function test_clusters_are_not_codepoints() {
  // The gap this page exists to show: what reads as one character is often
  // several codepoints, and that is where a font's shaping decides the outcome.
  const segment = (text) =>
    [...new Intl.Segmenter(undefined, { granularity: "grapheme" }).segment(text)].length;
  assert.equal(segment("क्ष"), 1);
  assert.equal([..."क्ष"].length, 3);
  assert.equal(segment("மலை"), 2);
  assert.equal([..."மலை"].length, 3);
}

function test_props_explain_what_a_codepoint_does() {
  // Category alone cannot say why a matra typed after its consonant is drawn
  // before it. Indic_Syllabic_Category and Indic_Positional_Category can.
  const [category, role, place] = props[hex(0x093f)];
  assert.equal(category, "Mc");
  assert.equal(role, "Vowel_Dependent");
  assert.equal(place, "Left");

  assert.equal(props[hex(0x0d4d)][1], "Virama");
  assert.equal(props[hex(0x0d7b)][1], "Consonant_Dead");   // the atomic chillu
  assert.equal(props[hex(0x200d)][1], "Joiner");
  // Plain letters are absent on purpose: 6,054 entries rather than 143,041.
  assert.equal(props[hex(0x0041)], undefined);
}

function test_authored_sequences_are_recognisable() {
  // Typing the legacy nta should be identifiable as *that*, not as three
  // unrelated codepoints — which is what lets Inspect point at the verdicts.
  const known = new Map();
  for (const [script, entries] of Object.entries(sequences)) {
    if (script.startsWith("_")) continue;
    for (const entry of entries) {
      const text = entry.codes.split(" ")
        .map((code) => String.fromCodePoint(parseInt(code, 16))).join("");
      known.set(text, { ...entry, script });
    }
  }
  const legacy = known.get("ന്റ");
  assert.ok(legacy, "the legacy nta sequence is not in the served list");
  assert.equal(legacy.id, "ntaLegacy");
  assert.equal(legacy.script, "Mlym");

  // And the recommended spelling of the same shape is findable from it, which is
  // what the "other ways to write it" panel offers.
  const sameShape = [...known.values()].filter((entry) => entry.out === legacy.out);
  assert.ok(sameShape.length > 1, "no alternate spelling for the same output");
  assert.ok(sameShape.some((entry) => entry.id === "nta"));
}

function test_every_family_with_the_text_is_offered() {
  // Inspect named eight families of ten per block, while /char/0D7B/ listed
  // every family with the chillu. Asked about one codepoint, the two must now
  // give the same number — they read the same ranges.
  const cover = (cp) => {
    const block = core.blockAt(cp);
    const file = new URL(`cover/${hex(block[0])}.json`, site);
    return [block[0], fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, "utf8")) : []];
  };
  const page = new URL("../char/0D7B/index.html", site);
  if (!fs.existsSync(page)) {
    console.log("      (no /char/0D7B/ in this build — skipped)");
    return;
  }
  const html = fs.readFileSync(page, "utf8");
  const stated = html.match(/<span class="value">([\d,]+)<\/span><span class="label">families with it/);
  assert.ok(stated, "the character page no longer states its family count");
  const { families: found } = core.coveringAll([0x0d7b], new Map([cover(0x0d7b)]));
  assert.equal(found.length, Number(stated[1].replace(/,/g, "")),
               "Inspect and the character page disagree about who has U+0D7B");

  // Every family it can name has somewhere to be drawn from, or says it has none.
  for (const index of found) {
    const face = families.families[index];
    assert.ok(face.name && face.slug, JSON.stringify(face));
    assert.equal(typeof face.draw, "boolean");
    if (face.draw) assert.ok(face.css || face.rule, `${face.name} draws from nowhere`);
  }
  // Unknown is not zero: the page needs the count of families it could not ask.
  assert.equal(typeof families.unmeasured, "number");
}

const tests = { test_tables_are_readable, test_the_readings_hold_against_real_tables,
                test_clusters_are_not_codepoints, test_props_explain_what_a_codepoint_does,
                test_authored_sequences_are_recognisable, test_every_family_with_the_text_is_offered };
for (const [name, test] of Object.entries(tests)) {
  test();
  console.log(`  ok  ${name}`);
}
console.log(`\n${Object.keys(tests).length} passed`);
