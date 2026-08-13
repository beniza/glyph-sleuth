"""Smallest thing that fails if the non-obvious logic breaks: run `python test_core.py`.

Covers the query classifier, the UnicodeSet expander, composition-aware coverage,
and property matching. Not the UI, and not the font scan (that needs your fonts).
"""
import chars
import langs


def test_parse():
    p = chars.parse
    assert p("U+2731") == ("char", 0x2731, "codepoint", [])
    assert p("0x2731").value == 0x2731
    assert p("\\u2731").value == 0x2731
    assert p("&#x2731;").value == 0x2731
    assert p("✱") == ("char", 0x2731, "character", [])
    # bare numbers read as hex first — this is a Unicode tool — with decimal offered
    q = p("2731")
    assert (q.value, q.label) == (0x2731, "hex codepoint")
    assert [a.value for a in q.alternates if a.kind == "char"] == [2731]
    assert p("10033").value == 0x10033
    assert p("999999").value == 999999, "decimal is in range even when hex isn't"
    assert p("FFFFFF").kind == "name", "out of range as hex, not a decimal at all"

    # a lone hex digit is the character, with the codepoint as the alternate
    q = p("a")
    assert q.value == ord("a") and q.alternates[0].value == 0xA

    assert p("\\p{Lu}") == ("prop", "Lu", "\\p{Lu}", [])
    assert p("\\p{Script=Devanagari}").value == "Script=Devanagari"
    assert p("U+2700..U+27BF") == ("range", (0x2700, 0x27BF), "codepoint range", [])
    assert p("Dingbats") == ("block", "Dingbats", "unicode block", [])
    assert p("heavy asterisk").kind == "name"
    assert p("U+41 U+42 67").kind == "codepoints"
    assert p("Quivira", font_families=["Quivira"]).kind == "font"
    assert p("hi", lang_names=[("hi", "Hindi")]).kind == "lang"
    assert p("").kind == "empty"
    assert p("✱ Ǎ ა").kind == "text"


def test_describe():
    info = chars.describe(0x2731)
    assert info.name == "HEAVY ASTERISK"
    assert info.category == "So"
    assert info.block == "Dingbats"
    assert info.script == "Common"
    assert info.utf8 == "E2 9C B1"
    assert info.escape == "\\u2731"
    assert info.decimal == 10033

    astral = chars.describe(0x1F7B2)
    assert astral.utf16 == "D83D DFB2", astral.utf16
    assert astral.escape == "\\U0001f7b2"

    assert chars.char_name(chr(0x0A)) == "<control> LINE FEED"
    assert chars.standin(0x20) == "SP"
    assert chars.standin(0x41) is None


def test_properties():
    matched, unmatched = chars.properties_of("✱")
    assert "General_Category=Other_Symbol" in matched, matched
    assert "So" in matched
    assert "Block=Dingbats" in matched
    assert "Script=Common" in matched
    assert "Alphabetic" in unmatched
    # every label must survive a round trip through a real regex
    for label in matched:
        assert chars.matches_property("✱", label), label
    for label in unmatched:
        assert not chars.matches_property("✱", label), label
    assert not any("Not_Applicable" in m or "=None" in m for m in matched), matched
    assert chars.matches_property("A", "Lu")
    assert not chars.matches_property("a", "Lu")
    assert chars.matches_property("न", "Script=Devanagari")
    assert chars.PROPERTY_COUNT > 90, "regex should expose ~101 properties"
    assert len(chars.BLOCKS) > 300 and len(chars.SCRIPTS) > 150


def test_conversion():
    # bare digits read as decimal, matching how the classifier reads them
    text, how = chars.text_from_codepoints("U+2731 0x41 66")
    assert (text, how) == ("✱AB", "codepoints"), text
    text, how = chars.text_from_codepoints("e2 9c b1")
    assert (text, how) == ("✱", "utf-8 bytes")
    assert chars.text_from_codepoints("not codepoints") == (None, None)

    forms = dict(chars.normalization_variants("Ǎ"))
    assert forms["NFC"] == "Ǎ" and forms["NFD"] == "Ǎ"
    assert chars.case_variants("Ǎ")["lower"] == "ǎ"


def test_variants():
    ranked = chars.variants(0x2731)
    assert ranked[0] == 0x2731, "the character itself comes first"
    assert 0x2A in ranked, "plain ASTERISK is a variant of HEAVY ASTERISK"
    assert 0x273D in ranked
    # ASTERISK is rarer than LATIN, so asterisks must outrank anything else
    top = ranked[1:12]
    assert all("ASTERISK" in chars.char_name(chr(c)) for c in top), \
        [chars.char_name(chr(c)) for c in top]

    assert 0x2731 in chars.search_names("heavy asterisk")
    assert chars.search_names("nonexistentglyphname") == []


def test_unicode_set():
    e = langs.expand_unicode_set
    assert e("[a b c]") == {"a", "b", "c"}
    assert e("[a-e]") == set("abcde")
    assert e("[{ch} x]") == {"c", "h", "x"}
    assert e("[\\u0301]") == {"́"}
    assert e("[a \\- z]") == {"a", "-", "z"}
    assert e("[[a-c] [x]]") == {"a", "b", "c", "x"}
    assert e("") == set()
    assert e("[अ-ऋ]") == {chr(c) for c in range(0x905, 0x90C)}


def test_composition_coverage():
    a_caron = "Ǎ"          # Ǎ  = A + combining caron
    # a face with only the precomposed character
    assert langs.missing_from({0x01CD}, {a_caron}) == set()
    # a face with the pieces can build it
    assert langs.missing_from({0x41, 0x030C}, {a_caron}) == set()
    # a face with neither cannot
    assert langs.missing_from({0x42}, {a_caron}) == {a_caron}


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"  ok  {test.__name__}")
    print(f"\n{len(tests)} passed")
