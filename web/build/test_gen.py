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


def test_cache_holds_facts_not_fonts():
    """A warm cache skips the download, the parse and the shaping.

    What it stores is the derived facts, keyed on the URL of the exact file they
    came from — gstatic and foundry URLs carry a version, so a new release is a
    new key rather than a stale hit. It never stores the font: that would put a
    binary on disk, which is the one thing the policy rules out.
    """
    import shutil
    import tempfile

    original = gen_index.CACHE
    gen_index.CACHE = tempfile.mkdtemp()
    try:
        url = "https://fonts.gstatic.com/s/x/v9/abc.woff2"
        assert gen_index.cached(url) is None
        blob = sample_font(codepoints=(0x0D15,))
        first = gen_index.measure_and_shape(blob, url, "abc.woff2")
        assert first["ranges"] == [[0x0D15, 0x0D15]]

        # Second time round the bytes are never touched — passing nonsense as
        # the blob proves the answer came from the cache.
        again = gen_index.measure_and_shape(b"not a font", url, "abc.woff2")
        assert again == first

        # A different version of the same family is a different key.
        assert gen_index.cached("https://fonts.gstatic.com/s/x/v10/abc.woff2") is None

        # Nothing in the cache is a font file.
        for name in os.listdir(gen_index.CACHE):
            assert name.endswith(".json"), name
            with open(os.path.join(gen_index.CACHE, name), encoding="utf-8") as handle:
                json.load(handle)
    finally:
        shutil.rmtree(gen_index.CACHE, ignore_errors=True)
        gen_index.CACHE = original


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


def sample_font(codepoints=(0x0D15, 0x0D16, 0x0D7B), fea=None, axes=None,
                extra_glyphs=()):
    """A real font, built in memory, so the parser is tested against the thing
    it actually parses rather than a stub of it."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    names = [".notdef"] + [f"g{cp:04X}" for cp in codepoints] + list(extra_glyphs)
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
    single = by_feature["pres"]["rules"][0]
    assert (single["in"], single["out"]) == ("g0D15", "g0D16")

    # And the characters behind the names, because "g0D15" is one developer's
    # private naming and ക is the thing a reader recognises.
    assert single["inText"] == "ക" and single["outText"] == "ഖ"
    assert rule["inText"] == "ക്ക"
    # A glyph the cmap does not reach has no character to show, and that is
    # reported as nothing rather than guessed at. Real ligature glyphs are the
    # usual case: Manjari's k1k1 has no codepoint of its own.
    assert gen_index.glyph_text(["k1k1"], {"k1": 0x0D15}) is None

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


def test_glyph_inventory():
    """Every glyph in the font, and what the layout rules do with it.

    A font is not its codepoints. The glyphs that carry the writing — half
    forms, conjuncts, chillus, positional variants — have no codepoints at all,
    and a glyph no rule ever produces can never appear in text however well
    drawn it is. That is the thing worth making obvious.
    """
    fea = """
    feature akhn { sub g0D15 g0D4D g0D15 by lig; } akhn;
    """
    blob = sample_font(codepoints=(0x0D15, 0x0D4D), fea=fea, extra_glyphs=("lig", "orphan"))
    glyphs = gen_index.glyphs(blob)
    by_name = {g["name"]: g for g in glyphs}

    # Encoded glyphs carry the codepoint that reaches them.
    assert by_name["g0D15"]["cp"] == 0x0D15
    # A ligature has no codepoint, and is produced by the feature that builds it.
    assert by_name["lig"]["cp"] is None
    assert by_name["lig"]["produced"] == ["akhn"]
    # The components are consumed by it, which is how you read the pipeline
    # backwards from a shape you can see.
    assert "akhn" in by_name["g0D15"]["consumed"]

    # And the finding the page exists for: a glyph nothing can reach.
    assert by_name["orphan"]["cp"] is None
    assert by_name["orphan"]["produced"] == []
    assert by_name["orphan"]["consumed"] == []
    # .notdef is not an orphan worth reporting — it is the fallback by design.
    assert ".notdef" not in [g["name"] for g in glyphs if g.get("orphan")]
    assert by_name["orphan"]["orphan"] is True
    assert by_name["g0D15"]["orphan"] is False


def test_every_built_glyph_carries_a_recipe():
    """A glyph with no codepoint still has to be drawable.

    The page can only show an unencoded glyph by setting the text that produces
    it and turning on the feature that does the producing — there is no other
    way without publishing outlines. So each built glyph records that recipe:
    the input characters, and the feature to enable.
    """
    fea = """
    feature akhn { sub g0D15 g0D4D g0D15 by lig; } akhn;
    feature pstf { sub g0D16 by variant; } pstf;
    """
    blob = sample_font(codepoints=(0x0D15, 0x0D16, 0x0D4D), fea=fea,
                       extra_glyphs=("lig", "variant", "orphan"))
    by_name = {g["name"]: g for g in gen_index.glyphs(blob)}

    # A ligature: the components, in order, as text the browser can shape.
    assert by_name["lig"]["from"]["text"] == "ക്ക"
    assert by_name["lig"]["from"]["features"] == ["akhn"]

    # A single substitution: the source character, plus the feature that swaps
    # it — without the feature the browser would draw the source, not this.
    assert by_name["variant"]["from"]["text"] == "ഖ"
    assert by_name["variant"]["from"]["features"] == ["pstf"]

    # Encoded glyphs need no recipe; they are reachable by typing.
    assert by_name["g0D15"].get("from") is None
    # And an orphan has none to give, which is the point of it being an orphan.
    assert by_name["orphan"].get("from") is None


def test_orphans_are_counted_from_every_rule():
    """The rule *samples* are capped at six; the roles must not be.

    Computing "unreachable" from the sampled rules called 441 of Manjari's 911
    glyphs unreachable — every glyph produced by a seventh rule or later. The
    page would have accused a good font of carrying dead weight, in the site's
    own confident voice.
    """
    sources = list(range(0x0D15, 0x0D15 + 12))
    many = "\n".join(f"    sub g{cp:04X} g0D4D by lig{n};"
                     for n, cp in enumerate(sources))
    fea = "feature akhn {\n" + many + "\n} akhn;"
    blob = sample_font(codepoints=tuple(sources) + (0x0D4D,), fea=fea,
                       extra_glyphs=tuple(f"lig{n}" for n in range(12)) + ("orphan",))
    by_name = {g["name"]: g for g in gen_index.glyphs(blob)}

    # The twelfth ligature is past the sample cap and is still not an orphan.
    assert by_name["lig11"]["produced"] == ["akhn"]
    assert by_name["lig11"]["orphan"] is False
    # And the one nothing reaches still is.
    assert by_name["orphan"]["orphan"] is True


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


def test_expected_output_is_checked():
    """"It shaped something" is not "it shaped the right thing".

    The verdict used to pass any run with no .notdef and no dotted circle, so a
    font substituting the wrong glyph passed. The check is font-independent:
    shape the expected text with the same font and compare the glyph runs.
    Glyph *names* could not do this — every foundry names its glyphs
    differently.
    """
    blob = sample_font(codepoints=(0x0D15, 0x0D16))

    # Input shapes to what the author said it should.
    assert gen_index.shape(blob, "0D15", expected="ക")["verdict"] == "clean"

    # Input shapes to something else. Not a failure — the font drew a glyph —
    # but not the agreed result either, which is exactly what "caveat" is for.
    off = gen_index.shape(blob, "0D15", expected="ഖ")
    assert off["verdict"] == "caveat"
    assert "expected" in off["note"]

    # With nothing to compare against, the old rule stands and says so.
    assert gen_index.shape(blob, "0D15")["verdict"] == "clean"
    # A missing glyph is still a failure, whatever was expected.
    assert gen_index.shape(blob, "0D15 0D7B", expected="ക")["verdict"] == "fail"


def test_devanagari_sequences():
    # A second script, to prove the depth is not Malayalam-shaped: same file,
    # same fields, and the dev2/deva split is the same trap as mlm2/mlym.
    entries = gen_index.sequences("Deva")
    assert entries, "no Devanagari sequences"
    by_id = {entry["id"]: entry for entry in entries}
    assert by_id["kssa"]["codes"] == "0915 094D 0937"
    assert by_id["kssa"]["out"] == "क्ष"
    for entry in entries:
        assert entry["langs"] and entry["out"] and entry["note"]
        # Codes must be real hex, or the shaper silently gets nothing.
        assert all(0 <= int(code, 16) <= 0x10FFFF for code in entry["codes"].split())


def test_every_shaped_script_declares_its_blocks():
    # A script with sequences but no blocks would never be shaped — nothing
    # would match the gate that decides which families to open.
    for script in gen_index.all_sequences():
        assert script in gen_index.SHAPED_SCRIPTS, f"{script} has sequences but no blocks"


def test_trace_shows_which_lookup_fired():
    """A verdict is a claim; a trace is a demonstration.

    HarfBuzz will report every lookup it runs, so a reader can see the run
    change from three glyphs to one and read off which lookup of which feature
    did it — rather than taking "clean" on trust.
    """
    fea = """
    feature akhn { sub g0D15 g0D4D g0D15 by lig; } akhn;
    """
    blob = sample_font(codepoints=(0x0D15, 0x0D4D), fea=fea, extra_glyphs=("lig",))
    steps = gen_index.trace(blob, "0D15 0D4D 0D15", ["akhn"])

    # It starts from what the cmap gave, before any lookup ran.
    assert steps[0]["step"] == "after cmap"
    assert len(steps[0]["glyphs"]) == 3

    # And there is a step, naming the feature, where the run actually changed.
    fired = [s for s in steps if s.get("feature") == "akhn"]
    assert fired, [s["step"] for s in steps]
    assert fired[-1]["glyphs"] == ["lig"]
    assert isinstance(fired[-1]["lookup"], int)

    # Only steps that changed something are kept: a lookup that matched
    # nothing is noise, and there are dozens of those in a real font.
    assert all(step["glyphs"] != step.get("before") for step in steps[1:])

    # A sequence nothing touches still traces, and says so rather than being
    # an empty list the page has to guess at.
    quiet = gen_index.trace(blob, "0D15", [])
    assert quiet[0]["step"] == "after cmap"
    assert len(quiet) == 1


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
