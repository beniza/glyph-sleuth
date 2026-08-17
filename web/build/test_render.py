"""Smallest thing that fails if the pages break: `python test_render.py`.

The pages are generated HTML, not assembled in the browser, so what these
assert is that the content is *in* the markup — a reader with JS off, and a
search engine, see the same facts a visitor does.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render


def test_escaping():
    # Every value that reaches a page goes through this. A font named with an
    # ampersand is ordinary; a font named with a script tag is the reason.
    assert render.esc("Fira Sans & Co") == "Fira Sans &amp; Co"
    assert render.esc('<script>alert("x")</script>') == \
        "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;"
    assert render.esc(None) == ""
    assert render.esc(118) == "118"


def test_every_internal_link_carries_the_base():
    """The site is served from /glyph-sleuth/, not from the domain root.

    Absolute paths written from "/" gave a masthead that 404s on the domain
    root and a stylesheet that never loads — the page rendered unstyled and the
    wordmark went nowhere. Every internal URL goes through link().
    """
    assert render.link("/") == f"{render.BASE}/"
    assert render.link("/fonts/") == f"{render.BASE}/fonts/"
    # Already-based paths are not doubled up.
    assert render.link(render.link("/fonts/")) == f"{render.BASE}/fonts/"
    # External URLs are left exactly as they are.
    assert render.link("https://smc.org.in/") == "https://smc.org.in/"

    html = render.home([{"name": "Manjari", "tier": "measured", "ranges": []}],
                       scripts=[{"code": "Mlym", "name": "Malayalam"}],
                       languages=[{"id": "mal", "name": "Malayalam", "tag": "ml"}])
    for href in re.findall(r'(?:href|src)="([^"]+)"', html):
        if href.startswith(("http://", "https://", "#", "mailto:")):
            continue
        assert href.startswith(render.BASE + "/"), f"{href} escapes the base path"


def test_page_shell():
    html = render.page("Malayalam", "<p>body text</p>", kind="script", code="Mlym")

    # Real HTML, servable as a file, readable without running anything.
    assert html.startswith("<!doctype html>")
    assert '<html lang="en">' in html
    assert "<p>body text</p>" in html
    # The shell contributes no h1 of its own — the page owns its one heading,
    # so a body that brings one is never competing with the masthead.
    assert "<h1" not in html
    # The title says what the page is before it says the site name.
    assert "<title>Malayalam · Glyph Sleuth</title>" in html
    # The nav is on every page, as real links rather than a JS router.
    for label, href in (("Scripts", "/scripts/"), ("Fonts", "/fonts/"),
                        ("Identify", "/identify/"), ("Compare", "/compare/")):
        assert f'href="{render.link(href)}"' in html, href
        assert f">{label}</a>" in html, label
    # Styles are a stylesheet, not a wall of inline attributes.
    assert f'<link rel="stylesheet" href="{render.link("/style.css")}">' in html
    assert "style=" not in html


def test_page_needs_no_javascript():
    html = render.page("Malayalam", "<p>the facts</p>", kind="script", code="Mlym")
    # JS is enhancement. If a page's own content depended on it, the generated
    # HTML would be pointless — which is the whole reason we generate it.
    assert "<noscript" not in html
    for script in re.findall(r"<script[^>]*>", html):
        assert "defer" in script or "type=\"module\"" in script, script


def test_home_says_what_it_measured():
    fonts = [
        {"name": "Manjari", "source": "smc", "tier": "measured",
         "ranges": [[0x0D00, 0x0D7F]], "licence": "OFL"},
        {"name": "Chilanka", "source": "smc", "tier": "measured",
         "ranges": [[0x0D00, 0x0D7E]], "licence": "OFL"},
        {"name": "RIT Panmana", "source": "rit", "tier": "stub",
         "ranges": [], "licence": ""},
    ]
    html = render.home(fonts, scripts=[], languages=[])

    # Exactly one h1 on a real page.
    assert len(re.findall(r"<h1", html)) == 1

    # The claim, verbatim — it is the product in one sentence.
    assert "Coverage says a font contains the character." in html
    assert "It does not say the font will draw it." in html
    assert "Nothing you type leaves the browser." in html

    # The counts are real, and indexed is reported separately from measured:
    # an index of 1,900 families where 40 carry real numbers is two facts, and
    # giving only the first is the claim this site exists to argue against.
    # The prototype's authored 1,885 is gone.
    assert "1,885" not in html
    facts = re.search(r'<dl class="facts">(.+?)</dl>', html, re.S).group(1)
    assert re.search(r"Families indexed.*?<dd[^>]*>3</dd>", facts, re.S)
    assert re.search(r"Measured from a release.*?<dd[^>]*>2</dd>", facts, re.S)
    assert re.search(r"Not measured yet.*?<dd[^>]*>1</dd>", facts, re.S)

    # The promise the prototype left inert now goes somewhere.
    assert f'href="{render.link("/identify/")}"' in html


def test_home_links_are_real_paths():
    html = render.home([], scripts=[{"code": "Mlym", "name": "Malayalam", "chars": 118}],
                       languages=[{"id": "mal", "name": "Malayalam", "tag": "ml"}])
    # Hash routes were a prototype artefact. A generated page needs a real URL
    # or there is nothing for a crawler to follow.
    assert "#/" not in html
    assert f'href="{render.link("/script/Mlym/")}"' in html
    assert f'href="{render.link("/lang/mal/")}"' in html


def test_font_href_is_stable():
    # The slug is what every link between pages is keyed on, so it has to
    # survive spaces, case and punctuation the same way every time.
    base = render.BASE
    assert render.font_href({"name": "Noto Sans Malayalam"}) == f"{base}/font/noto-sans-malayalam/"
    assert render.font_href({"name": "RIT Rachana"}) == f"{base}/font/rit-rachana/"
    assert render.font_href({"name": "Baloo Chettan 2"}) == f"{base}/font/baloo-chettan-2/"


MANJARI = {
    "name": "Manjari", "source": "smc", "licence": "OFL", "tier": "measured",
    "version": "2.200", "ranges": [[0x0020, 0x007E], [0x0D00, 0x0D7F]],
    "tags": ["DFLT", "latn", "mlm2", "mlym"], "gsub": 48, "gpos": 3,
    "features": ["akhn", "blwf", "pres"], "axes": [], "graphite": False,
    "url": "https://smc.org.in/fonts/#/manjari",
    "css": "https://smc.org.in/fonts/manjari.css",
    "checksum": "sha256:ffdb7aac", "faces": [],
    "provenance": {"file": "Manjari-Regular.woff2",
                   "release": "https://smc.org.in/fonts/manjari.css", "read": "2026-08-17"},
    "results": {"Mlym": {
        "nta": {"hb": {"verdict": "clean", "glyphs": ["nta"], "note": "",
                       "command": "hb-shape --font-file=Manjari-Regular.woff2 "
                                  "--unicodes=0D7B,0D4D,0D31 --features=blwf,pres "
                                  "--script=Mlym --language=ml"},
                "dw": None, "ct": None, "gr": None},
    }},
}

BLOCKS = [[0x0020, 0x007F, "Basic Latin"], [0x0D00, 0x0D7F, "Malayalam"]]


def test_font_page_shows_its_evidence():
    html = render.font_page(MANJARI, BLOCKS)

    # Tier 1: what it covers, by block, not as one number.
    assert "Malayalam" in html and "Basic Latin" in html
    # Tier 2: the tags it declares. This is the fact coverage cannot give you.
    for tag in ("mlym", "mlm2"):
        assert tag in html
    # Tier 3: the verdict, and the command that reproduces it.
    assert "hb-shape --font-file=Manjari-Regular.woff2" in html
    assert "clean" in html

    # Provenance: which file, from where, when. A number nobody can reproduce
    # is a number nobody should trust.
    assert "Manjari-Regular.woff2" in html
    assert "2026-08-17" in html
    assert "sha256:ffdb7aac" in html


def test_matrix_says_not_tested_rather_than_nothing():
    """The three treatments, and the reason the matrix exists.

    A blank cell reads as a pass. DirectWrite and CoreText are not reachable
    from this build, and Graphite does not apply to a font with no silf table
    — three different facts, none of them "it worked".
    """
    html = render.font_page(MANJARI, BLOCKS)
    for engine in ("HarfBuzz", "DirectWrite", "CoreText", "Graphite"):
        assert engine in html, engine
    assert "not tested" in html
    assert "not applicable" in html
    # And the legend that stops empty columns reading as a rendering bug.
    assert "cannot reach DirectWrite or CoreText" in html


def test_use_it_never_invents_an_import():
    # Google: its own CDN.
    google = dict(MANJARI, source="google", name="Baloo Chettan 2",
                  css="https://fonts.googleapis.com/css2?family=Baloo+Chettan+2")
    assert "fonts.googleapis.com/css2?family=Baloo+Chettan+2" in render.font_page(google, BLOCKS)

    # A foundry that serves its own stylesheet: point at theirs.
    smc = render.font_page(MANJARI, BLOCKS)
    assert "https://smc.org.in/fonts/manjari.css" in smc
    assert "googleapis.com/css2?family=Manjari" not in smc

    # Neither: say so, and give a @font-face template rather than a fake link.
    alone = dict(MANJARI, source="rit", css=None, name="RIT Rachana")
    html = render.font_page(alone, BLOCKS)
    assert "@font-face" in html
    assert "not served from a public CDN" in html
    # And no page points at a font *file* served by us. The self-host template
    # names a bare filename on purpose: it is the reader's copy, not ours.
    ours = re.compile(r'(?:href|src)="[^"]*' + re.escape(render.BASE) + r'[^"]*\.(?:woff2?|ttf|otf)')
    for state in (smc, html):
        assert not ours.search(state), "we are linking a font file of our own"


def test_shaping_page_shows_the_working():
    font = dict(MANJARI, tables={
        "gsub": [{"feature": "akhn", "type": "Ligature", "index": 0, "flag": 0, "n": 60,
                  "rules": [{"in": "k1 xx k1", "out": "k1k1"}]},
                 {"feature": "akhn", "type": "Chaining context", "index": 1, "flag": 0,
                  "n": 25, "rules": []}],
        "gpos": [{"feature": "abvm", "type": "Mark to base", "index": 0, "flag": 0,
                  "n": 464, "rules": []}],
    })
    html = render.shaping_page(font)

    # Grouped by feature, because that is how a reader thinks about it: what
    # does akhn actually do in this font?
    assert "akhn" in html and "abvm" in html
    assert "Ligature" in html and "Mark to base" in html
    # A rule reads as what it does.
    assert "k1 xx k1" in html and "k1k1" in html
    # The counts are the full counts, even where only a few rules are shown.
    assert "60" in html and "464" in html
    # A contextual lookup lists no rules, and says why rather than looking empty.
    assert "chains other lookups" in html

    # It is a page about one family, and says whose working this is.
    assert "Manjari" in html
    assert render.font_href(font) in html


def test_shaping_page_needs_the_tables():
    # Nothing to show for a family whose file we never opened, and the page
    # says that instead of rendering an empty table.
    stub = {"name": "RIT Panmana", "source": "rit", "tier": "stub", "ranges": [],
            "licence": "", "url": "x", "css": None, "tags": [], "features": [],
            "axes": [], "faces": []}
    html = render.shaping_page(stub)
    assert "not measured yet" in html
    assert "<table" not in html


def test_coverage_measured_but_tables_unread():
    """Google's metadata gives coverage and nothing else.

    Rendering that as "script tags declared: none" states, in the site's own
    voice, that the font declares no tags — when nobody looked. Measured
    coverage and unread tables are two different facts and the page has to keep
    them apart, or it is doing the exact thing it accuses coverage badges of.
    """
    google = {"name": "ABeeZee", "source": "google", "tier": "measured",
              "licence": "OFL", "ranges": [[0x0020, 0x007E]], "tags": [],
              "gsub": 0, "gpos": 0, "features": [], "axes": [], "faces": ["400"],
              "css": "https://fonts.googleapis.com/css2?family=ABeeZee",
              "url": "https://fonts.google.com/specimen/ABeeZee"}
    html = render.font_page(google, BLOCKS)

    # Coverage is real and shown.
    assert "Basic Latin" in html
    # The tables were never opened, and the page says that rather than "none".
    assert ">none<" not in html
    assert "not read" in html
    assert "does not include" in html
    # No invented lookup counts either.
    assert "GSUB lookups" not in html


def test_unmeasured_family_says_so():
    stub = {"name": "RIT Panmana", "source": "rit", "tier": "stub", "ranges": [],
            "licence": "", "url": "https://gitlab.com/rit-fonts/RIT-Panmana",
            "css": None, "tags": [], "features": [], "axes": [], "faces": []}
    html = render.font_page(stub, BLOCKS)
    assert "not measured yet" in html
    # No invented zeros: a family we did not read has no coverage, which is not
    # the same as covering nothing.
    assert "0/0" not in html
    assert "0 codepoints" not in html


tests = {name: fn for name, fn in sorted(globals().items()) if name.startswith("test_")}
if __name__ == "__main__":
    for name, test in tests.items():
        test()
        print(f"  ok  {name}")
    print(f"\n{len(tests)} passed")
