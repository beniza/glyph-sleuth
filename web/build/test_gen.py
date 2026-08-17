"""Smallest thing that fails if the index generator breaks: `python test_gen.py`.

Covers the range arithmetic, the family-merging rule, the stylesheet reading,
and the constraint the whole design rests on: nothing here downloads a font.
"""
import hashlib
import io
import json
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_index


def test_ranges_from():
    assert gen_index.ranges_from([]) == []
    assert gen_index.ranges_from([0x41]) == [[0x41, 0x41]]
    # Runs merge; gaps don't.
    assert gen_index.ranges_from([0x41, 0x42, 0x43]) == [[0x41, 0x43]]
    assert gen_index.ranges_from([0x41, 0x43]) == [[0x41, 0x41], [0x43, 0x43]]
    # Unsorted input still comes out sorted and merged — the client bisects it.
    assert gen_index.ranges_from([0x43, 0x41, 0x42]) == [[0x41, 0x43]]


def test_parse_google_ranges():
    # Google publishes coverage per subset as "32-126,160-255,8470".
    coverage = {"latin": "32-33,35", "malayalam": "3328-3455"}
    assert gen_index.parse_google_ranges(coverage) == [[32, 33], [35, 35], [3328, 3455]]
    # Subsets overlap constantly; the union is what matters, counted once.
    assert gen_index.parse_google_ranges({"a": "65-70", "b": "68-72"}) == [[65, 72]]
    assert gen_index.parse_google_ranges({}) == []


def test_json_guard():
    # Google prefixes its metadata JSON with an anti-hijacking guard, )]}'
    # — drop it and every family fetch fails with "Expecting value: line 1".
    assert gen_index.loads(")]}'\n{\"family\": \"Abel\"}") == {"family": "Abel"}
    assert gen_index.loads('{"family": "Abel"}') == {"family": "Abel"}


def test_same_family():
    same = lambda a, b: gen_index.same_family(gen_index.squash(a), gen_index.squash(b))
    assert same("Charis SIL", "Charis")
    assert same("Gentium Book Plus", "Gentium Book")
    assert same("Noto Sans Malayalam", "Noto Sans Malayalam")
    # The rule that matters: a shared prefix is not a shared family. Meera is
    # Malayalam and Meera Inimai is Tamil, and hiding one behind the other
    # would be a wrong answer, not a tidier list.
    assert not same("Meera", "Meera Inimai")
    assert not same("Noto Sans", "Noto Sans Malayalam")
    assert not same("Anek Malayalam", "Anek Tamil")


def test_family_from_stylesheet():
    sheet = """
    @font-face {
      font-family: 'Manjari';
      src: url('/fonts/Manjari-Regular.woff2') format('woff2');
      font-weight: 400;
    }
    """
    assert gen_index.family_from_stylesheet(sheet) == "Manjari"
    assert gen_index.family_from_stylesheet('@font-face{font-family:"RIT Rachana";}') == "RIT Rachana"
    assert gen_index.family_from_stylesheet("nothing here") is None


def test_google_record():
    meta = {"family": "Baloo Chettan 2", "category": "display", "designers": ["Ek Type"]}
    detail = {"coverage": {"latin": "65-90"}, "license": "ofl"}
    font = gen_index.google_record(meta, detail)
    assert font["name"] == "Baloo Chettan 2"
    assert font["ranges"] == [[65, 90]]
    assert font["source"] == "google"
    assert font["licence"] == "OFL"                       # not the API's "ofl"
    assert font["css"] == "https://fonts.googleapis.com/css2?family=Baloo+Chettan+2"
    # Measured: this family's coverage is a real number, from Google's metadata.
    assert font["tier"] == "measured"
    # A family Google lists without coverage tells us nothing worth recording.
    assert gen_index.google_record(meta, {"license": "ofl"}) is None


def test_foundry_record():
    # We do not open font files, so a foundry family is indexed without
    # coverage until someone runs the desktop companion against it. Saying
    # "not measured yet" is the honest state; a guessed range would not be.
    font = gen_index.foundry_record(
        name="Manjari", source="smc",
        page="https://smc.org.in/fonts/#/manjari",
        css="https://smc.org.in/fonts/manjari.css")
    assert font["name"] == "Manjari"
    assert font["tier"] == "stub"
    assert font["ranges"] == []
    assert "ranges" in font and font.get("covers") is None
    assert font["css"] == "https://smc.org.in/fonts/manjari.css"


def test_no_font_is_ever_served():
    """The constraint that shaped the design, asserted rather than trusted.

    Reading a font is fine — that is what every font QA tool does, and the
    licences permit it plainly. Redistributing one is not. So the generator may
    download and parse a release in memory, but must never write a font file
    into what we publish, and must never keep one.
    """
    source = open(gen_index.__file__, encoding="utf-8").read()
    # No output directory for fonts, and no woff2 conversion: the two things
    # the archive did that made us a font host.
    assert not hasattr(gen_index, "OUT_FONTS")
    # `flavor` is how fontTools re-emits a face as a webfont. Reading a .woff2 a
    # foundry already serves is fine; writing one of our own is what made the
    # archive a font host.
    assert "flavor" not in source, "we are re-emitting webfonts again"
    # Nothing is opened for binary writing, so no font can reach the disk.
    assert '"wb"' not in source and "'wb'" not in source, "something writes binary files"
    # Everything written goes to the data directory, never a font directory.
    assert gen_index.OUT_DATA.endswith(os.path.join("web", "data"))


def test_parsed_fonts_are_not_kept():
    # A parsed release lives in memory and is dropped. If a path to a font file
    # is ever returned in a record, we have started hosting by accident.
    record = gen_index.foundry_record(
        name="Manjari", source="smc", page="https://smc.org.in/fonts/#/manjari",
        css="https://smc.org.in/fonts/manjari.css")
    assert "file" not in record, "a font path is back in the index"


def sample_font(codepoints=(0x0D15, 0x0D16, 0x0D7B), fea=None, axes=None):
    """A real font, built in memory, so the parser is tested against the thing
    it actually parses rather than a stub of it."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    names = [".notdef"] + [f"g{cp:04X}" for cp in codepoints]
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(names)
    builder.setupCharacterMap({cp: f"g{cp:04X}" for cp in codepoints})
    empty = TTGlyphPen(None).glyph()
    builder.setupGlyf({name: empty for name in names})
    builder.setupHorizontalMetrics({name: (500, 0) for name in names})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable({"familyName": "Test Face", "styleName": "Regular",
                            "version": "1.234"})
    builder.setupOS2()
    builder.setupPost()
    if axes:
        builder.setupFvar(axes, [])
    if fea:
        addOpenTypeFeaturesFromString(builder.font, fea)
    blob = io.BytesIO()
    builder.save(blob)
    return blob.getvalue()


def test_measure_coverage():
    facts = gen_index.measure(sample_font())
    # cmap -> the same range form the client bisects.
    assert facts["ranges"] == [[0x0D15, 0x0D16], [0x0D7B, 0x0D7B]]
    # Nothing declared and nothing to shape with, said plainly rather than as 0.
    assert facts["tags"] == []
    assert facts["gsub"] == 0 and facts["gpos"] == 0
    assert facts["features"] == []
    assert facts["axes"] == []
    # No silf table: Graphite is not applicable, which is not the same as failing.
    assert facts["graphite"] is False


def test_measure_opentype():
    fea = """
    languagesystem mlm2 dflt;
    feature akhn {
        sub g0D15 g0D16 by g0D7B;
    } akhn;
    feature pres {
        sub g0D16 by g0D15;
    } pres;
    """
    facts = gen_index.measure(sample_font(fea=fea))
    # The tag the font declares is the tier-2 evidence the whole site turns on:
    # a face can cover every codepoint and still declare only the old tag.
    assert facts["tags"] == ["mlm2"]
    assert sorted(facts["features"]) == ["akhn", "pres"]
    assert facts["gsub"] == 2                 # one lookup per feature here
    assert facts["gpos"] == 0


def test_measure_variable():
    facts = gen_index.measure(sample_font(axes=[("wght", 400, 400, 700, "Weight")]))
    assert facts["axes"] == [{"tag": "wght", "min": 400, "default": 400, "max": 700}]


def test_measure_provenance():
    blob = sample_font()
    facts = gen_index.measure(blob)
    # A number nobody can reproduce is a number nobody should trust: every
    # measurement carries the file it came from and the version it claims.
    assert facts["checksum"] == "sha256:" + hashlib.sha256(blob).hexdigest()
    assert facts["version"] == "1.234"
    assert facts["family"] == "Test Face"


def test_pick_faces():
    # One face per family, and it must be the upright regular — a specimen set
    # in Bold Italic tells you about the wrong drawing.
    members = ["Manjari-Bold.ttf", "Manjari-Regular.ttf", "Manjari-Thin.ttf",
               "OFL.txt", "documentation/manual.pdf"]
    assert gen_index.pick_faces(members) == ["Manjari-Regular.ttf"]
    # No Regular in the release: take the first face rather than nothing.
    assert gen_index.pick_faces(["Gayathri-Thin.ttf", "Gayathri-Bold.ttf"]) \
        == ["Gayathri-Bold.ttf"]
    # Two families in one archive are two answers, not one.
    both = gen_index.pick_faces(["Meera-Regular.ttf", "MeeraInimai-Regular.ttf"])
    assert len(both) == 2
    assert gen_index.pick_faces(["README.md"]) == []


def test_font_url_with_query():
    # SMC cache-busts its own stylesheet: the src URL ends
    # ".woff2?v=Version2.000", so a plain endswith() sees no font at all and
    # every SMC family silently falls back to a stub.
    assert gen_index.is_font_url("/downloads/fonts/manjari/Manjari-Regular.woff2?v=Version2.000")
    assert gen_index.is_font_url("https://x/Gayathri-Regular.ttf")
    assert not gen_index.is_font_url("/fonts/manjari.css")
    assert not gen_index.is_font_url("/fonts/specimen.png?woff2=no")


def test_extract_fonts():
    blob = io.BytesIO()
    with zipfile.ZipFile(blob, "w") as archive:
        archive.writestr("release/Manjari-Regular.ttf", b"font bytes")
        archive.writestr("release/OFL.txt", b"licence")
        # macOS resource forks look like fonts and are not.
        archive.writestr("__MACOSX/._Manjari-Regular.ttf", b"junk")
    found = gen_index.extract_fonts(blob.getvalue())
    assert list(found) == ["release/Manjari-Regular.ttf"]
    assert found["release/Manjari-Regular.ttf"] == b"font bytes"


def test_lookup_tables():
    """What the shaping page shows: which lookups a feature actually runs.

    "48 GSUB lookups" is a number; this is the working behind it — the type of
    each lookup, how many rules it carries, and a few of the rules themselves.
    """
    fea = """
    languagesystem mlm2 dflt;
    feature akhn {
        sub g0D15 g0D4D g0D15 by g0D7B;   # a ligature: three in, one out
    } akhn;
    feature pres {
        sub g0D15 by g0D16;               # a single substitution
    } pres;
    """
    tables = gen_index.lookups(sample_font(codepoints=(0x0D15, 0x0D16, 0x0D4D, 0x0D7B), fea=fea))

    by_feature = {row["feature"]: row for row in tables["gsub"]}
    assert set(by_feature) == {"akhn", "pres"}

    # The type is named, not left as the raw integer the table stores.
    assert by_feature["akhn"]["type"] == "Ligature"
    assert by_feature["pres"]["type"] == "Single"

    # And a rule reads as what it does: these glyphs become that one.
    rule = by_feature["akhn"]["rules"][0]
    assert rule["in"] == "g0D15 g0D4D g0D15"
    assert rule["out"] == "g0D7B"
    assert by_feature["pres"]["rules"][0] == {"in": "g0D15", "out": "g0D16"}

    # A font with no positioning has no GPOS rows — not a row saying zero.
    assert tables["gpos"] == []


def test_lookup_rules_are_capped():
    # A real family carries thousands of rules. The page shows enough to see
    # the shape of the lookup and says how many more there are.
    fea = "feature pres {\n" + "\n".join(
        f"    sub g{cp:04X} by g0D7B;" for cp in range(0x0D15, 0x0D25)) + "\n} pres;"
    codepoints = tuple(range(0x0D15, 0x0D25)) + (0x0D7B,)
    tables = gen_index.lookups(sample_font(codepoints=codepoints, fea=fea))
    row = tables["gsub"][0]
    assert row["n"] == 16                       # every rule counted
    assert len(row["rules"]) == gen_index.RULE_SAMPLES  # only a few shown


def test_google_face_url():
    # Google's css2 serves woff2 to a modern UA and ttf to an old one. Either
    # is readable; what matters is getting a real file URL out of the sheet,
    # because the metadata alone stops at coverage.
    sheet = """
    /* malayalam */
    @font-face {
      font-family: 'Manjari';
      font-style: normal;
      font-weight: 400;
      src: url(https://fonts.gstatic.com/s/manjari/v9/abc.woff2) format('woff2');
      unicode-range: U+0307, U+0323, U+0D00-0D7F;
    }
    """
    assert gen_index.face_url_from_stylesheet(sheet) == \
        "https://fonts.gstatic.com/s/manjari/v9/abc.woff2"
    assert gen_index.face_url_from_stylesheet("/* nothing */") is None


def test_only_relevant_families_are_parsed():
    """Downloading 1,900 releases to answer a question about Malayalam would be
    rude to the CDN and slow for no gain.

    A family is worth opening when it covers a script we have sequences for —
    that is where tiers 2 and 3 mean anything.
    """
    malayalam = {"ranges": [[0x0D00, 0x0D7F]]}
    latin_only = {"ranges": [[0x0020, 0x007E]]}
    assert gen_index.worth_parsing(malayalam)
    assert not gen_index.worth_parsing(latin_only)


def test_shape_verdicts():
    # Tier 3, and the reason the site exists: a face can cover every codepoint
    # of a sequence and still not draw it. A .notdef in the output, or a
    # leftover dotted circle, is the font failing — not the text being wrong.
    blob = sample_font(codepoints=(0x0D15, 0x0D4D))

    clean = gen_index.shape(blob, "0D15")
    assert clean["verdict"] == "clean"
    assert clean["glyphs"], "no glyph run came back"

    # A codepoint the font does not have shapes to .notdef, which is a fail
    # however cleanly the rest of the run went.
    missing = gen_index.shape(blob, "0D15 0D7B")
    assert missing["verdict"] == "fail"
    assert ".notdef" in missing["note"] or "0D7B" in missing["note"]


def test_woff2_is_unwrapped_before_shaping():
    """HarfBuzz reads sfnt, not woff2 — and foundries serve woff2.

    Handed compressed bytes it finds no glyphs at all, so every sequence comes
    back .notdef and every family looks broken. Silent, and completely wrong:
    the fonts are fine.
    """
    from fontTools.ttLib import TTFont
    packed = io.BytesIO()
    font = TTFont(io.BytesIO(sample_font(codepoints=(0x0D15,))))
    font.flavor = "woff2"
    font.save(packed)
    blob = packed.getvalue()
    assert blob[:4] == b"wOF2"

    assert gen_index.as_sfnt(blob)[:4] != b"wOF2"
    assert gen_index.shape(blob, "0D15")["verdict"] == "clean"
    # A plain TTF is passed through untouched.
    plain = sample_font(codepoints=(0x0D15,))
    assert gen_index.as_sfnt(plain) == plain


def test_hb_shape_command():
    # The command a reader can paste to reproduce the verdict themselves. A
    # verdict nobody can re-run is an assertion, not evidence.
    line = gen_index.hb_shape_command("Manjari-Regular.ttf", "0D7B 0D4D 0D31",
                                      ["blwf", "pres"], "ml")
    assert "--font-file=Manjari-Regular.ttf" in line
    assert "--unicodes=0D7B,0D4D,0D31" in line
    assert "--features=blwf,pres" in line
    assert "--script=Mlym" in line and "--language=ml" in line


def test_sequences_are_authored_content():
    # Not generated, and not duplicated: the companion reads this same file, so
    # both products share one definition of what a verdict is about.
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(gen_index.__file__))),
                        "content", "sequences.json")
    data = json.load(open(path, encoding="utf-8"))
    nta = [s for s in data["Mlym"] if s["id"] == "nta"][0]
    assert nta["codes"] == "0D7B 0D4D 0D31"
    assert nta["out"] == "ൻ്റ"


def test_sources_are_declarative():
    # Adding a foundry stays one entry, which is why it never rots.
    for source in gen_index.SOURCES:
        assert source["host"] in ("github", "github-repos", "gitlab", "css")
        assert "skip" in source and "page" in source
    # The deliberate exclusions stay excluded, with their reasons in the file.
    text = open(gen_index.__file__, encoding="utf-8").read()
    for name in ("Last Resort", "STIX", "Liberation", "Source Han"):
        assert name in text, f"{name} lost its exclusion note"


tests = {name: fn for name, fn in sorted(globals().items()) if name.startswith("test_")}
if __name__ == "__main__":
    for name, test in tests.items():
        test()
        print(f"  ok  {name}")
    print(f"\n{len(tests)} passed")
