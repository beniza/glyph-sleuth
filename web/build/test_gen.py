"""Smallest thing that fails if the index generator breaks: `python test_gen.py`.

Covers the range arithmetic, the family-merging rule, the stylesheet reading,
and the constraint the whole design rests on: nothing here downloads a font.
"""
import sys
import os

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


def test_no_font_is_ever_downloaded():
    """The constraint that shaped the whole design, asserted rather than trusted.

    No font binary is fetched, mirrored or hosted by our infrastructure — not
    even transiently in a build step. Real computed numbers come from a
    contributor's own machine, or they do not exist yet and the page says so.
    """
    source = open(gen_index.__file__, encoding="utf-8").read()
    for banned in ("fontTools", "woff2", "ttLib", "zipfile", "tarfile",
                   "build_face", "extract_fonts", "prune_fonts"):
        assert banned not in source, f"{banned} is back in the generator"
    # Fetching is text and JSON only, and the allowlist says so out loud.
    assert not hasattr(gen_index, "OUT_FONTS")


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
