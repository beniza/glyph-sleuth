"""Smallest thing that fails if the index generator breaks: `python test_gen.py`.

Covers the range arithmetic, the family-merging rule, the stylesheet reading,
and the constraint the whole design rests on: a font file is published only
when a licence in its own release permits it.
"""
import hashlib
import io
import json
import os
import urllib.error
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


def test_only_a_licensed_font_is_ever_served():
    """The constraint that shaped the design, restated after it was revisited.

    It began as "never write a font file". That was stricter than the licences
    require and it cost the families it mattered most for: RIT and SIL host no
    stylesheet, so every page that named one drew it in a fallback under a
    verdict of its own. What the licences actually govern is redistribution, and
    the OFL permits it outright.

    So the rule now is narrower and still a rule: we publish the foundry's own
    build, unmodified, only when we have read a licence out of the same release
    that permits it, and only into one directory.
    """
    source = open(gen_index.__file__, encoding="utf-8").read()
    # `flavor` is how fontTools re-emits a face as a webfont. We re-serve the
    # woff2 the foundry built and shipped; a file we generated is not the file
    # they signed off, and converting is how a font host starts.
    assert "flavor" not in source, "we are re-emitting webfonts again"
    # One writer, one directory. Anything else opening a font for writing is a
    # second path to publication that this test does not govern.
    assert source.count('"wb"') + source.count("'wb'") == 1, "something else writes binary"
    assert gen_index.OUT_WEBFONTS.endswith(os.path.join("web", "webfonts"))
    assert gen_index.OUT_DATA.endswith(os.path.join("web", "data"))


def test_a_failed_download_keeps_the_measurement_we_already_had():
    """A family measured last week is still measured when today's fetch fails.

    This is how twelve RIT families lost their coverage, tags and shaping in one
    build: the download 401'd, the exception handler returned a stub, and a
    perfectly good cached measurement went out as "not measured yet". A network
    failure costs the webfont and nothing else.
    """
    source = {"id": "rit", "host": "gitlab", "group": "rit-fonts",
              "page": "https://gitlab.com/rit-fonts/{project}", "skip": set()}

    def boom():
        raise urllib.error.HTTPError("u", 401, "Unauthorized", {}, None)

    # No pytest fixture: this file is also run as a plain script by CI, where a
    # `monkeypatch` argument would just be a TypeError.
    probe, cache = gen_index.release_probe, gen_index.cached
    gen_index.release_probe = lambda *a, **k: ("1.5.2", "1.5.2", boom)
    gen_index.cached = lambda url: {"ranges": [[0x0D15, 0x0D15]], "tags": ["mlym"],
                                    "family": "RIT Rachana", "licence": "OFL-1.1",
                                    "webfont": "webfonts/rit/RIT-Rachana/x.woff2",
                                    "read": "2026-08-01"}
    try:
        record = gen_index.foundry_family(source, "RIT-Rachana")
    finally:
        gen_index.release_probe, gen_index.cached = probe, cache

    assert record["tier"] == "measured", "a 401 turned a measured family into a stub"
    assert record["ranges"] == [[0x0D15, 0x0D15]]
    assert record["provenance"]["read"] == "2026-08-01", "provenance claims a fresh read"
    # The webfont the cache names is not on disk here, so it is dropped: we
    # cannot promise a file nobody wrote.
    assert record["webfont"] is None


def test_a_failed_download_keeps_a_webfont_that_is_still_on_disk():
    """Dropping it whenever the fetch failed was too eager.

    A read timeout on RIT Rachana made the flagship family undrawable — no
    specimen, no Try it, five browser tests red — while all four of its woff2
    files sat on disk, published by the build before. What a failed fetch costs
    is a *fresh* copy, not the one we already have.
    """
    source = {"id": "rit", "host": "gitlab", "group": "rit-fonts",
              "page": "https://gitlab.com/rit-fonts/{project}", "skip": set()}

    def boom():
        raise TimeoutError("The read operation timed out")

    here = os.path.join("webfonts", "test-kept", "Kept.woff2")
    full = os.path.join(gen_index.ROOT, "web", *here.split(os.sep))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "wb") as handle:
        handle.write(b"wOF2")

    probe, cache = gen_index.release_probe, gen_index.cached
    gen_index.release_probe = lambda *a, **k: ("1.0", "1.0", boom)
    gen_index.cached = lambda url: {"ranges": [[0x0D15, 0x0D15]], "family": "Kept",
                                    "licence": "OFL-1.1", "read": "2026-08-01",
                                    "webfont": here.replace(os.sep, "/"),
                                    "webfonts": {"400": here.replace(os.sep, "/")},
                                    "glyph_count": 1, "glyphs": [{"name": "a"}]}
    try:
        record = gen_index.foundry_family(source, "Kept")
    finally:
        gen_index.release_probe, gen_index.cached = probe, cache
        os.remove(full)
        os.rmdir(os.path.dirname(full))

    assert record["webfont"], "a timeout dropped a webfont that was still on disk"
    assert record["tier"] == "measured"


def test_the_scripts_cache_notices_the_composite_table_changing():
    """The fix for composites deployed green and changed nothing.

    `write_scripts` caches on the Unicode version and a hash of the input codes.
    Adding the expansion changed neither: the codes were identical, the version
    was identical, and the build served the result computed before the fix.
    Hiragana was still missing and CI was still green.

    Third time this pattern has bitten — see `webfont_present` and
    `counted_glyphs`. A cache keyed only on its inputs is stale whenever the
    function changes, and only the author knows that happened.
    """
    source = io.open(gen_index.__file__, encoding="utf-8").read()
    scripts_key = source[source.index('key = "scripts:%s:%s"') - 400:
                         source.index('key = "scripts:%s:%s"') + 200]
    assert "SCRIPT_PARTS" in scripts_key, (
        "the scripts cache key does not depend on the composite table, so "
        "changing that table will silently reuse the old answer")


def test_a_composite_script_code_is_expanded_not_dropped():
    """Japanese and Korean had no script page at all.

    langtags writes them `ja-Jpan` and `ko-Kore` — composite ISO 15924 codes that
    stand for several scripts — and `script_names()` maps UCD script *values*, so
    it has nothing for either. `script_index()` then did a bare `continue`, and
    Hiragana appeared nowhere on the site.
    """
    assert gen_index.SCRIPT_PARTS["Jpan"] == ("Hani", "Hira", "Kana")
    assert gen_index.SCRIPT_PARTS["Kore"] == ("Hang", "Hani")

    # The variants, which are what actually cost Chinese: `zh` is recorded as
    # Hans and Hant, both resolved to nothing, and Mandarin linked no script at
    # all. Fifteen languages were affected by Hans alone, and the drop report is
    # what surfaced them.
    assert gen_index.SCRIPT_PARTS["Hans"] == ("Hani",)
    assert gen_index.SCRIPT_PARTS["Hant"] == ("Hani",)
    assert gen_index.expand_scripts(["Hans", "Hant"]) == ["Hani"], "Han listed twice"
    assert gen_index.expand_scripts(["Latf", "Latg", "Latn"]) == ["Latn"]

    # Every part of every composite resolves to a real UCD script *with blocks*,
    # or expanding them just moves the silent drop one step along.
    names = gen_index.script_names()
    for code, parts in gen_index.SCRIPT_PARTS.items():
        for part in parts:
            engine = names.get(part)
            assert engine, f"{code} expands to {part}, which resolves to nothing"
            assert gen_index.script_blocks(engine), f"{part} covers no blocks"

    # Two different reasons for being in that table, and the difference matters.
    # Jpan and Kore have no UCD script value at all. Hrkt has one —
    # Katakana_Or_Hiragana — which covers no blocks, so it would be dropped one
    # step later and a reader would still find nothing.
    assert names.get("Jpan") is None and names.get("Kore") is None
    assert names.get("Hrkt") == "Katakana_Or_Hiragana"
    assert not gen_index.script_blocks("Katakana_Or_Hiragana")

    # The language's own page links these codes, so the expansion has to happen
    # where the language gets them too — /lang/jpn/ listed Jpan, which resolves
    # to no script page, and Japanese linked Braille and Latin and nothing else.
    assert gen_index.expand_scripts(["Jpan", "Brai", "Latn"]) == [
        "Hani", "Hira", "Kana", "Brai", "Latn"]
    # Order kept, and Han not repeated when two composites both reach it.
    assert gen_index.expand_scripts(["Kore", "Jpan"]) == [
        "Hang", "Hani", "Hira", "Kana"]
    assert gen_index.expand_scripts(["Mlym"]) == ["Mlym"]

    index = gen_index.script_index([
        {"id": "jpn", "scripts": ["Jpan"]},
        {"id": "kor", "scripts": ["Kore"]},
        {"id": "mal", "scripts": ["Mlym"]},
    ])
    by_code = {entry["code"]: entry for entry in index}
    # Japanese reaches Han, Hiragana and Katakana; Korean reaches Hangul and Han.
    for code in ("Hani", "Hira", "Kana", "Hang", "Mlym"):
        assert code in by_code, f"{code} is missing from the index"
    assert "jpn" in by_code["Hira"]["languages"]
    assert "kor" in by_code["Hang"]["languages"]
    # Han is reached by both, and appears once.
    assert sorted(by_code["Hani"]["languages"]) == ["jpn", "kor"]
    assert [e["code"] for e in index].count("Hani") == 1


def test_a_second_release_is_kept_rather_than_dropped():
    """Google and a foundry publishing one family is two releases, not a duplicate.

    `same_family` matches "charis" with "charissil" through the `sil` suffix, and
    the loop used to `continue` on that — so SIL's own record went on the floor
    and the page reported Google's two faces where SIL ships eight.

    Two projects of the *same* foundry family are still a duplicate, and the
    first still wins. This asserts both halves, because collapsing them is what
    caused the bug.
    """
    assert gen_index.same_family("charis", "charissil")
    trimmed = gen_index.alternate({"name": "Charis SIL", "source": "google",
                                   "ranges": [[65, 90]], "faces": ["400"],
                                   "glyphs": [{"name": "a"}] * 4000,
                                   "tables": {"gsub": [1, 2, 3]}})
    # The two large fields are exactly what a comparison never reads.
    assert "glyphs" not in trimmed and "tables" not in trimmed
    assert trimmed["source"] == "google" and trimmed["faces"] == ["400"]


def test_the_glyph_cap_keeps_the_total_it_dropped():
    """A CJK face has tens of thousands of glyphs and the page is not a font
    editor, so the inventory is capped. But truncating and keeping no count is
    how the page came to show 4,000 and read as complete — the one thing this
    site may not do. Every other cap here is disclosed.
    """
    blob = sample_font(codepoints=tuple(range(0x0D00, 0x0D40)))
    inventory, total = gen_index.glyphs(blob, limit=10)
    assert len(inventory) == 10, "the cap stopped working"
    assert total == 65, "the total was lost with the glyphs that were dropped"
    # Uncapped, the two agree, so a page can tell "complete" from "truncated".
    inventory, total = gen_index.glyphs(blob)
    assert len(inventory) == total


def test_a_measurement_taken_before_the_total_is_a_cache_miss():
    # Same shape and reason as webfont_present: a warm cache holds a short list
    # with nothing to compare it against, so the page cannot disclose a shortfall
    # it cannot see. Only families with a glyph list re-measure.
    assert not gen_index.counted_glyphs({"glyphs": [{"name": "a"}]})
    assert gen_index.counted_glyphs({"glyphs": [{"name": "a"}], "glyph_count": 900})
    # Nothing to re-measure for a family we never read a glyph list from.
    assert gen_index.counted_glyphs({"ranges": []})
    assert gen_index.counted_glyphs({})


def test_a_throttled_fetch_is_retried_but_not_forever():
    """GitLab answers 401, not 429, for a throttled anonymous artifact download.

    It cost RIT Rachana its webfont in an otherwise green build — one family of
    twelve, nothing else wrong. So 401 is retriable here, which is unusual and is
    the reason this test names it.

    The attempt count is asserted deliberately: an unbounded retry does not fail
    a build, it hangs one, and a hung CI job is worse than a red one.
    """
    calls = []

    def opener(fail_times, code=401):
        def fake(request, timeout=None):
            calls.append(request.full_url)
            if len(calls) <= fail_times:
                raise urllib.error.HTTPError(request.full_url, code, "nope", {}, None)
            return io.BytesIO(b"wOF2")
        return fake

    real = gen_index.urllib.request.urlopen
    try:
        # Fails twice, succeeds on the third. Sleep is injected so the test does
        # not actually wait 4.5 seconds.
        gen_index.urllib.request.urlopen = opener(2)
        assert gen_index.fetch("https://gitlab.com/x", sleep=lambda _s: None) == b"wOF2"
        assert len(calls) == 3

        # Always failing: raises, and stops.
        calls.clear()
        gen_index.urllib.request.urlopen = opener(99)
        try:
            gen_index.fetch("https://gitlab.com/x", sleep=lambda _s: None)
            raise AssertionError("a persistent 401 should still raise")
        except urllib.error.HTTPError:
            pass
        assert len(calls) == gen_index.RETRIES, f"{len(calls)} attempts, expected bounded"

        # A read timeout is socket.timeout, which is a TimeoutError and not a
        # URLError. The first version of retriable() missed it and RIT Rachana
        # lost its measurement to one on the very next build.
        calls.clear()
        timeouts = []

        def slow(request, timeout=None):
            timeouts.append(1)
            if len(timeouts) < 2:
                raise TimeoutError("The read operation timed out")
            return io.BytesIO(b"wOF2")

        gen_index.urllib.request.urlopen = slow
        assert gen_index.fetch("https://gitlab.com/x", sleep=lambda _s: None) == b"wOF2"
        assert len(timeouts) == 2

        # A 404 is an answer, not a failure. Seven SIL projects have no release
        # and must stay fast.
        calls.clear()
        gen_index.urllib.request.urlopen = opener(99, code=404)
        try:
            gen_index.fetch("https://api.github.com/x", sleep=lambda _s: None)
            raise AssertionError("a 404 should raise")
        except urllib.error.HTTPError:
            pass
        assert len(calls) == 1, "a 404 was retried"
    finally:
        gen_index.urllib.request.urlopen = real


def test_the_github_token_only_goes_to_github():
    """CI hands the generator a GITHUB_TOKEN, and it was attached to every
    download — including RIT's, which are on gitlab.com. GitLab answered 401 and
    twelve Malayalam families dropped to "not measured yet" in one build. The
    401 was the lucky outcome: the unlucky one is a CI credential sitting in
    another company's access log.
    """
    assert gen_index.for_github("https://api.github.com/repos/silnrsi/font-andika/releases")
    assert gen_index.for_github("https://objects.githubusercontent.com/x/y.tar.xz")
    assert gen_index.for_github("https://release-assets.githubusercontent.com/a/b.zip")
    assert not gen_index.for_github(
        "https://gitlab.com/rit-fonts/RIT-Rachana/-/jobs/artifacts/1.5.2/download?job=build-tag")
    assert not gen_index.for_github("https://smc.org.in/fonts/manjari.css")
    assert not gen_index.for_github("https://fonts.gstatic.com/s/x/v9/abc.woff2")
    # Not a substring match: a host that merely ends in the right letters is a
    # different host, and that is how a token reaches somewhere it should not.
    assert not gen_index.for_github("https://github.com.example.net/x")


def test_an_unrecognised_licence_publishes_nothing():
    # Default deny: we are serving someone else's copyrighted file from our own
    # domain, and a licence we cannot read is a no rather than a guess.
    ofl = {"OFL.txt": b"SIL OPEN FONT LICENSE Version 1.1"}
    assert gen_index.find_licence(ofl) == ("OFL-1.1", "SIL OPEN FONT LICENSE Version 1.1")
    assert gen_index.find_licence({"LICENSE.txt": b"All rights reserved."}) == ("", "")
    assert gen_index.find_licence({}) == ("", "")
    # A release with no licence file at all is the common case for the ones we
    # must not touch, and it must not fall through to some default.
    assert gen_index.find_licence({"web/X-Regular.woff2": b"wOF2"}) == ("", "")


def test_the_webfont_matches_the_face_we_measured():
    # A specimen set in the release's Bold while the coverage came from Regular
    # is two different fonts wearing one name.
    members = {"Andika-7.000/Andika-Regular.ttf": b"",
               "Andika-7.000/web/Andika-Regular.woff2": b"",
               "Andika-7.000/web/Andika-Bold.woff2": b""}
    assert (gen_index.webfont_for("Andika-7.000/Andika-Regular.ttf", members)
            == "Andika-7.000/web/Andika-Regular.woff2")
    # A release that ships no woff2 publishes nothing: we do not convert.
    assert gen_index.webfont_for("X-Regular.ttf", {"X-Regular.ttf": b""}) is None


def test_a_cached_measurement_cannot_promise_a_file_that_is_gone():
    # The cache holds facts, not bytes, and web/webfonts is build output. A warm
    # cache on a fresh checkout would otherwise skip the download and leave the
    # page pointing at a woff2 nobody wrote.
    assert gen_index.webfont_present({"webfont": None, "ranges": []})
    assert not gen_index.webfont_present({"webfont": "webfonts/rit/Nope/Nope.woff2"})
    # Measured before any of this existed: the cache cannot answer, so it is a miss.
    assert not gen_index.webfont_present({"ranges": []})


def test_parsed_fonts_are_not_kept():
    # A parsed release lives in memory and is dropped. If a path to a font file
    # is ever returned in a record, we have started hosting by accident.
    record = gen_index.foundry_record(
        name="Manjari", source="smc", page="https://smc.org.in/fonts/#/manjari",
        css="https://smc.org.in/fonts/manjari.css")
    assert "file" not in record, "a font path is back in the index"


def sample_font(codepoints=(0x0D15, 0x0D16, 0x0D7B), fea=None, axes=None,
                extra_glyphs=(), family="Test Face", style="Regular",
                weight=400, italic=False):
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
    builder.setupNameTable({"familyName": family, "styleName": style,
                            "version": "1.234"})
    builder.setupOS2(usWeightClass=weight, fsSelection=0x01 if italic else 0x40)
    builder.setupPost()
    if axes:
        builder.setupFvar(axes, [])
    if fea:
        addOpenTypeFeaturesFromString(builder.font, fea)
    blob = io.BytesIO()
    builder.save(blob)
    return blob.getvalue()


def test_a_face_is_weighed_by_its_own_tables_not_its_filename():
    # A file called Foo-Medium.ttf is a claim; usWeightClass is what the browser
    # matches against. Where they disagree, guessing from the name would put a
    # weight in the control that never arrives when someone picks it.
    blob = sample_font(style="Medium", weight=500)
    assert gen_index.face_style(blob) == (500, False, "Test Face")
    assert gen_index.face_style(sample_font(weight=700, italic=True))[:2] == (700, True)
    assert gen_index.face_key(700, True) == "700i"
    assert gen_index.face_key(400, False) == "400"


def test_siblings_are_grouped_by_family_name_not_by_filename():
    # RIT's archives are why. pick_faces splits a stem on "-", so every
    # RIT-Something face lands under "rit" — and a release carrying two families
    # would hand back one of them wearing the other's name.
    members = {
        "ttf/RIT-Rachana-Regular.ttf": sample_font(family="RIT Rachana"),
        "ttf/RIT-Rachana-Bold.ttf": sample_font(family="RIT Rachana", weight=700),
        "ttf/RIT-Unny-Regular.ttf": sample_font(family="RIT Unny"),
    }
    found = gen_index.sibling_faces("ttf/RIT-Rachana-Regular.ttf", members)
    assert sorted(name for name, _w, _i in found) == [
        "ttf/RIT-Rachana-Bold.ttf", "ttf/RIT-Rachana-Regular.ttf"]
    assert sorted(w for _n, w, _i in found) == [400, 700]


def test_only_the_regular_is_measured_however_many_faces_ship():
    # The family page reports coverage, script tags and shaping verdicts. Those
    # are the regular's; the Bold's cmap under the family's name would be a
    # different font's numbers.
    members = {
        "X-Regular.ttf": sample_font(family="X", codepoints=(0x0D15,)),
        "X-Bold.ttf": sample_font(family="X", weight=700, codepoints=(0x0D15, 0x0D16)),
    }
    assert gen_index.pick_faces(members) == ["X-Regular.ttf"]
    assert gen_index.measure(members["X-Regular.ttf"])["ranges"] == [[0x0D15, 0x0D15]]


def test_a_variable_face_is_one_file_over_a_range():
    # One file covering 100-900 is one @font-face with a weight range, not nine
    # faces. Missing that would ask for eight files that do not exist.
    assert gen_index.wght_axis({"axes": [{"tag": "wght", "min": 100, "max": 900}]}) == (100, 900)
    assert gen_index.wght_axis({"axes": [{"tag": "wdth", "min": 75, "max": 125}]}) is None
    assert gen_index.wght_axis({}) is None


def test_nothing_is_published_without_a_licence_however_many_faces():
    published = gen_index.publish_family("rit", "X", "X-Regular.ttf", {}, "", "", {})
    assert published == {"faces": [], "webfont": None, "webfonts": {}}


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
    glyphs, _total = gen_index.glyphs(blob)
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
    by_name = {g["name"]: g for g in gen_index.glyphs(blob)[0]}

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
    by_name = {g["name"]: g for g in gen_index.glyphs(blob)[0]}

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
