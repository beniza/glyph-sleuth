// Smallest thing that fails if the web core drifts from chars.py: `node web/test-core.mjs`.
// Mirrors test_core.py — same inputs, same expected readings.
import assert from "node:assert/strict";
import * as core from "./core.js";

// The client normally loads these; here we hand it just enough to answer.
core.data.blocks = [[0x0000, 0x007f, "Basic Latin"], [0x0370, 0x03ff, "Greek and Coptic"],
                    [0x0900, 0x097f, "Devanagari"], [0x0d00, 0x0d7f, "Malayalam"],
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
  const known = { fonts: [{ name: "Charis SIL" }], languages: [{ tag: "hi", name: "Hindi" }],
                  scripts: [{ code: "Deva", name: "Devanagari" }] };
  assert.equal(core.parse("Charis SIL", known).kind, "font");
  assert.equal(core.parse("Hindi", known).kind, "lang");
  // A name that is both a script and a block reads as the script — it spans
  // three blocks — with the block offered as the alternate reading.
  const deva = core.parse("Devanagari", known);
  assert.equal(deva.kind, "script");
  assert.equal(deva.value, "Deva");
  assert.deepEqual(deva.alternates.map((a) => a.kind), ["block"]);
  assert.equal(core.parse("Deva", known).kind, "script");
  // A block with no script of that name still reads as a block.
  assert.equal(core.parse("Dingbats", known).kind, "block");
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

function test_range_coverage() {
  const ranges = [[0x41, 0x5a], [0x900, 0x97f]];
  assert.equal(core.countInRange(ranges, 0x41, 0x5a), 26);
  assert.equal(core.countInRange(ranges, 0x900, 0x97f), 0x80);
  assert.equal(core.countInRange(ranges, 0x4b, 0x54), 10);        // inside one range
  assert.equal(core.countInRange(ranges, 0x30, 0x45), 5);         // straddling the start
  assert.equal(core.countInRange(ranges, 0x2700, 0x27bf), 0);     // nothing in the block
  assert.equal(core.countInRange([], 0, 0x10ffff), 0);

  // Browse only offers faces with something to draw, most coverage first.
  const fonts = [
    { name: "Latin only", ranges: [[0x41, 0x5a]] },
    { name: "Some Devanagari", ranges: [[0x41, 0x5a], [0x900, 0x90f]] },
    { name: "All Devanagari", ranges: [[0x900, 0x97f]] },
  ];
  const offered = core.fontsForRange(0x900, 0x97f, fonts);
  assert.deepEqual(offered.map((row) => row.font.name), ["All Devanagari", "Some Devanagari"]);
  assert.deepEqual(offered.map((row) => row.count), [0x80, 16]);
  assert.equal(core.fontsForRange(0x2700, 0x27bf, fonts).length, 0);
  // A tie in coverage falls back to the name, so the list never reshuffles.
  const tied = core.fontsForRange(0x41, 0x5a, [fonts[1], fonts[0]]);
  assert.deepEqual(tied.map((row) => row.font.name), ["Latin only", "Some Devanagari"]);
}

function test_dominant_block() {
  // A Malayalam face carries Latin too; what it is *for* is Malayalam.
  const manjari = { name: "Manjari", ranges: [[0x20, 0x7e], [0x0d00, 0x0d7f]] };
  assert.equal(core.dominantBlock(manjari), "Malayalam");
  // A Latin-only face has no other block to name.
  assert.equal(core.dominantBlock({ name: "Abel", ranges: [[0x20, 0x7e], [0xa0, 0xff]] }), null);
  // A handful of stray codepoints outside Latin is not a script.
  assert.equal(core.dominantBlock({ name: "Stray", ranges: [[0x20, 0x7e], [0x2700, 0x2703]] }), null);
  // Two scripts: the one with more glyphs wins, if it dominates what's there.
  const both = { name: "Both", ranges: [[0x0900, 0x090f], [0x0d00, 0x0d7f]] };
  assert.equal(core.dominantBlock(both), "Malayalam");
  // A workhorse carrying a bit of everything is for none of them in particular,
  // so it gets the Latin pangram rather than a script it merely also has.
  // Three scripts, no majority: DejaVu is not a Greek font just because Greek
  // is its largest non-Latin block.
  const workhorse = { name: "DejaVu-ish",
                      ranges: [[0x20, 0x7e], [0x0370, 0x03b0], [0x0900, 0x0940],
                               [0x0d00, 0x0d40], [0x2700, 0x2740]] };
  assert.equal(core.dominantBlock(workhorse), null);
}

function test_specimen_text() {
  assert.equal(core.trimToSpecimen("A short line."), "A short line.");
  // Paragraphs collapse to one line: the entry is a specimen, not the document.
  assert.equal(core.trimToSpecimen("two\n\nparagraphs  here"), "two paragraphs here");
  const long = "word ".repeat(60);
  const cut = core.trimToSpecimen(long);
  assert.ok(cut.length <= core.SPECIMEN_CHARS + 1, cut.length);
  assert.ok(cut.endsWith("…"));
  assert.ok(!cut.includes("wor…"));                       // cut on a word, not mid-word
  // A script with no spaces has nowhere to break, so it cuts where it must.
  const unbroken = "ക".repeat(300);
  assert.equal(core.trimToSpecimen(unbroken).length, core.SPECIMEN_CHARS + 1);
}

function test_scripts() {
  const tamil = {
    code: "Taml", name: "Tamil",
    blocks: [{ name: "Tamil", chars: 4, ranges: [[0x0b85, 0x0b88]] },
             { name: "Tamil Supplement", chars: 2, ranges: [[0x11fc0, 0x11fc1]] }],
    languages: ["tam"],
  };
  const partial = { name: "Covers the old block", ranges: [[0x0b85, 0x0b88]] };
  const whole = { name: "Covers both", ranges: [[0x0b85, 0x0b88], [0x11fc0, 0x11fc1]] };
  const none = { name: "Latin only", ranges: [[0x41, 0x5a]] };

  // A script is not one block, so covering Tamil means covering the supplement
  // too — the distinction the whole support matrix exists to show.
  const half = core.scriptCoverage(partial, tamil);
  assert.equal(half.chars, 6);
  assert.equal(half.covered, 4);
  assert.deepEqual(half.blocks.map((b) => b.covered), [4, 0]);
  assert.equal(core.scriptCoverage(whole, tamil).covered, 6);

  const offered = core.fontsForScript(tamil, [none, partial, whole]);
  assert.deepEqual(offered.map((row) => row.font.name), ["Covers both", "Covers the old block"]);
  assert.equal(offered[0].covered, 6);
  assert.equal(offered[1].blocks[1].covered, 0);
}

function test_script_of_text() {
  const latn = { code: "Latn", name: "Latin", blocks: [{ name: "Basic Latin", chars: 26,
                 ranges: [[0x41, 0x5a], [0x61, 0x7a]] }], languages: [] };
  const deva = { code: "Deva", name: "Devanagari", blocks: [{ name: "Devanagari", chars: 128,
                 ranges: [[0x900, 0x97f]] }], languages: [] };
  // Afar's exemplars are Latin even when you are looking at its Arabic page.
  assert.equal(core.scriptOfText("abcdefghi", [deva, latn]).code, "Latn");
  assert.equal(core.scriptOfText("कखगघ", [deva, latn]).code, "Deva");
  assert.equal(core.scriptOfText("✱✱✱", [deva, latn]), null);

  // A specimen of a script shows letters; a row of combining marks is a row of
  // dotted circles, and digits and punctuation say nothing about the face.
  const marks = { code: "Test", name: "Test",
                  blocks: [{ name: "Devanagari", chars: 8, ranges: [[0x0900, 0x0907]] }],
                  languages: [] };
  const letters = core.scriptLetters(marks);
  assert.ok(letters.length > 0);
  assert.ok(letters.every((ch) => /\p{L}/u.test(ch)), letters.join(""));
  assert.ok(!letters.includes("ं"));                      // U+0902, a combining mark
  // Arabic's first block opens with signs and marks; the specimen starts at the
  // first real letter instead.
  const arabic = { code: "Arab", name: "Arabic",
                   blocks: [{ name: "Arabic", chars: 40, ranges: [[0x0600, 0x0627]] }],
                   languages: [] };
  assert.equal(core.scriptLetters(arabic)[0], "ؠ");
}

function test_reading_on() {
  const script = { code: "Mlym", name: "Malayalam",
                   blocks: [{ name: "Malayalam", chars: 118, ranges: [[0x0d00, 0x0d7f]] }],
                   languages: [] };
  const links = Object.fromEntries(core.scriptLinks(script).map((l) => [l.label, l.url]));
  assert.match(links.ScriptSource, /key=Mlym$/);
  assert.equal(links["Script notes"], "https://r12a.github.io/scripts/mlym/");
  assert.equal(links.Uniview, "https://r12a.github.io/uniview/?blocks=Mlym");
  assert.equal(links.Wikipedia, "https://en.wikipedia.org/wiki/Malayalam_script");
  assert.equal(links.Omniglot, "https://www.omniglot.com/writing/malayalam.htm");
  // A two-word script name has to survive both conventions.
  const old = core.scriptLinks({ code: "Xsux", name: "Old Persian", blocks: [], languages: [] });
  assert.match(old[3].url, /Old_Persian_script$/);
  assert.match(old[4].url, /oldpersian\.htm$/);

  const lang = core.languageLinks({ iso: "mal", name: "Malayalam (chillus)" });
  assert.match(lang[0].url, /key=mal$/);
  assert.match(lang[1].url, /Malayalam_language$/);        // the qualifier is not part of it

  // The chart PDF is named for the block's 128-codepoint boundary.
  assert.equal(core.blockChart({ ranges: [[0x0d02, 0x0d7f]] }),
               "https://www.unicode.org/charts/PDF/U0D00.pdf");
}

function test_taking_it_away() {
  const google = { name: "Baloo Chettan 2", source: "google", url: "https://fonts.google.com/specimen/x" };
  const hosted = { name: "RIT Rachana", source: "rit", url: "https://gitlab.com/rit-fonts/RIT-Rachana",
                   file: "fonts/RITRachana.woff2" };

  // Google hands over a zip; every other foundry hands over its own page, and
  // the flag is what lets the button avoid promising a file that never arrives.
  assert.equal(core.download(google).url,
               "https://fonts.google.com/download?family=Baloo+Chettan+2");
  assert.equal(core.download(google).direct, true);
  assert.equal(core.download(hosted).url, "https://gitlab.com/rit-fonts/RIT-Rachana");
  assert.equal(core.download(hosted).direct, false);

  assert.match(core.embed(google), /fonts\.googleapis\.com\/css2\?family=Baloo\+Chettan\+2/);
  assert.match(core.embed(google), /font-family: "Baloo Chettan 2"/);
  // A self-hosted face gets an @font-face naming the file, not a link to ours.
  assert.match(core.embed(hosted), /@font-face/);
  assert.match(core.embed(hosted), /url\("RITRachana\.woff2"\)/);
  assert.ok(!core.embed(hosted).includes("googleapis"));
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
                test_range_coverage, test_dominant_block, test_specimen_text,
                test_scripts, test_script_of_text, test_reading_on,
                test_taking_it_away, test_properties, test_blocks, test_names, test_encodings,
                test_standin };
for (const [name, test] of Object.entries(tests)) {
  test();
  console.log(`  ok  ${name}`);
}
console.log(`\n${Object.keys(tests).length} passed`);
