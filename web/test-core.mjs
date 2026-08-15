// Smallest thing that fails if the web core drifts from chars.py: `node web/test-core.mjs`.
// Mirrors test_core.py — same inputs, same expected readings.
import assert from "node:assert/strict";
import * as core from "./core.js";

// The client normally loads these; here we hand it just enough to answer.
core.data.blocks = [[0x0000, 0x007f, "Basic Latin"], [0x0900, 0x097f, "Devanagari"],
                    [0x2700, 0x27bf, "Dingbats"]];
core.data.formulaic = [["CJK UNIFIED IDEOGRAPH", 0x4e00, 0x9fff]];
core.data.names = new Map([
  [0x2731, "HEAVY ASTERISK"], [0x002a, "ASTERISK"], [0x066d, "ARABIC FIVE POINTED STAR"],
  [0x0041, "LATIN CAPITAL LETTER A"], [0x00c0, "LATIN CAPITAL LETTER A WITH GRAVE"],
]);

function test_parse() {
  const p = (t) => core.parse(t);
  assert.equal(p("U+2731").kind, "char");
  assert.equal(p("U+2731").value, 0x2731);
  assert.equal(p("0x2731").value, 0x2731);
  assert.equal(p("\\u2731").value, 0x2731);
  assert.equal(p("&#x2731;").value, 0x2731);
  assert.equal(p("✱").kind, "char");
  assert.equal(p("✱").value, 0x2731);

  // A bare hex number reads as hex, with decimal offered as the alternative.
  const bare = p("2731");
  assert.equal(bare.value, 0x2731);
  assert.equal(bare.label, "hex codepoint");
  assert.deepEqual(bare.alternates.map((a) => a.label), ["decimal codepoint", "name search"]);

  assert.equal(p("U+2700..U+27BF").kind, "range");
  assert.deepEqual(p("U+2700..U+27BF").value, [0x2700, 0x27bf]);
  assert.equal(p("\\p{Script=Devanagari}").kind, "prop");
  assert.equal(p("\\p{Script=Devanagari}").value, "Script=Devanagari");
  assert.equal(p("Dingbats").kind, "block");
  assert.equal(p("heavy asterisk").kind, "name");
  assert.equal(p("41 42 43").kind, "codepoints");
  assert.deepEqual(p("41 42 43").value, [41, 42, 43]);      // digits read as decimal
  assert.deepEqual(p("U+41 U+42").value, [0x41, 0x42]);     // prefixed reads as hex
  assert.equal(p("Hello, world!").kind, "text");
  assert.equal(p("").kind, "empty");

  // A known font family and a known language win over the generic readings.
  const known = { fonts: [{ name: "Charis SIL" }], languages: [{ tag: "hi", name: "Hindi" }] };
  assert.equal(core.parse("Charis SIL", known).kind, "font");
  assert.equal(core.parse("Hindi", known).kind, "lang");
}

function test_codepoint_conversion() {
  assert.deepEqual(core.textFromCodepoints("U+48 U+49"), ["HI", "codepoints"]);
  assert.deepEqual(core.textFromCodepoints("E0 A4 95"), ["क", "utf-8 bytes"]);
  assert.deepEqual(core.textFromCodepoints("not codepoints"), [null, null]);
}

function test_coverage() {
  const ranges = [[0x41, 0x5a], [0x300, 0x36f]];
  assert.ok(core.covers(ranges, 0x41));
  assert.ok(core.covers(ranges, 0x5a));
  assert.ok(!core.covers(ranges, 0x5b));
  assert.ok(core.covers(ranges, 0x300));
  assert.equal(core.countIn(ranges), 26 + 0x70);

  // Composition: À is covered by a face with A and the combining grave, because
  // that is how the renderer will build it. This is the rule langs.py uses.
  assert.equal(core.missingFrom(ranges, "À").size, 0);
  assert.deepEqual([...core.missingFrom(ranges, "Ǆ")], ["Ǆ"]);
  assert.deepEqual([...core.missingFrom([[0x41, 0x5a]], "À")], ["À"]);
}

function test_ranking() {
  const fonts = [
    { name: "Narrow", ranges: [[0x41, 0x42]] },
    { name: "Wide", ranges: [[0x41, 0x5a]] },
  ];
  const ranked = core.rankFonts("ABC", fonts);
  assert.equal(ranked[0].font.name, "Wide");
  assert.equal(ranked[0].missing.size, 0);
  assert.equal(ranked[1].missing.size, 1);
  // Whitespace is the renderer's business, not the font's.
  assert.equal(core.rankFonts("A B", fonts)[0].missing.size, 0);
}

function test_properties() {
  assert.ok(core.matchesProperty("क", "Script=Devanagari"));
  assert.ok(!core.matchesProperty("A", "Script=Devanagari"));
  assert.ok(core.matchesProperty("A", "Lu"));
  assert.ok(core.validProperty("Script=Devanagari"));
  assert.ok(!core.validProperty("Script=NotAScript"));
  // JS regex has no \p{Block=...}, so blocks are answered from the UCD table.
  assert.ok(core.matchesProperty("✱", "Block=Dingbats"));
  assert.ok(!core.matchesProperty("A", "Block=Dingbats"));
  assert.ok(core.validProperty("Block=Dingbats"));
  assert.equal(core.matchingProperty("Block=Dingbats").length, 0x27bf - 0x2700 + 1);
}

function test_blocks() {
  assert.equal(core.blockOf(0x2731), "Dingbats");
  assert.equal(core.blockOf(0x41), "Basic Latin");
  assert.deepEqual(core.blockRange("Dingbats"), [0x2700, 0x27bf]);
  assert.equal(core.blockRange("No Such Block"), null);
}

function test_names() {
  assert.equal(core.charName(0x2731), "HEAVY ASTERISK");
  assert.equal(core.charName(0x4e2d), "CJK UNIFIED IDEOGRAPH-4E2D");
  assert.deepEqual(core.searchNames("heavy asterisk"), [0x2731]);
  // ASTERISK is rare, LETTER is common, so the asterisks rank above the letters.
  assert.equal(core.variants(0x2731)[0], 0x2731);
  assert.ok(core.variants(0x2731).includes(0x002a));
  assert.ok(!core.keywords("LATIN CAPITAL LETTER A").includes("LETTER"));
}

function test_encodings() {
  const e = core.encodings(0x2731);
  assert.equal(e["UTF-8"], "E2 9C B1");
  assert.equal(e["UTF-16"], "2731");
  assert.equal(e["HTML"], "&#10033;");
  assert.equal(core.encodings(0x1f600)["UTF-16"], "D83D DE00");
}

function test_standin() {
  assert.equal(core.standin(0x20), "SP");
  assert.equal(core.standin(0x200d), "ZWJ");
  assert.equal(core.standin(0x41), null);
  assert.ok(core.standin(0x0009));
}

const tests = { test_parse, test_codepoint_conversion, test_coverage, test_ranking,
                test_properties, test_blocks, test_names, test_encodings, test_standin };
for (const [name, test] of Object.entries(tests)) {
  test();
  console.log(`  ok  ${name}`);
}
console.log(`\n${Object.keys(tests).length} passed`);
