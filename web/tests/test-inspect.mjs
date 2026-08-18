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

// The same parse loadNames() does, against the same file it fetches.
const names = new Map();
for (const line of read("names.txt").split("\n")) {
  const tab = line.indexOf("\t");
  if (tab > 0) names.set(parseInt(line.slice(0, tab), 16), line.slice(tab + 1));
}
core.data.names = names;

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

const tests = { test_tables_are_readable, test_the_readings_hold_against_real_tables,
                test_clusters_are_not_codepoints };
for (const [name, test] of Object.entries(tests)) {
  test();
  console.log(`  ok  ${name}`);
}
console.log(`\n${Object.keys(tests).length} passed`);
