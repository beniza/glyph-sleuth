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
        assert f'href="{href}"' in html, href
        assert f">{label}</a>" in html, label
    # Styles are a stylesheet, not a wall of inline attributes.
    assert '<link rel="stylesheet" href="/style.css">' in html
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
    assert 'href="/identify/"' in html


def test_home_links_are_real_paths():
    html = render.home([], scripts=[{"code": "Mlym", "name": "Malayalam", "chars": 118}],
                       languages=[{"id": "mal", "name": "Malayalam", "tag": "ml"}])
    # Hash routes were a prototype artefact. A generated page needs a real URL
    # or there is nothing for a crawler to follow.
    assert "#/" not in html
    assert 'href="/script/Mlym/"' in html
    assert 'href="/lang/mal/"' in html


def test_font_href_is_stable():
    # The slug is what every link between pages is keyed on, so it has to
    # survive spaces, case and punctuation the same way every time.
    assert render.font_href({"name": "Noto Sans Malayalam"}) == "/font/noto-sans-malayalam/"
    assert render.font_href({"name": "RIT Rachana"}) == "/font/rit-rachana/"
    assert render.font_href({"name": "Baloo Chettan 2"}) == "/font/baloo-chettan-2/"


tests = {name: fn for name, fn in sorted(globals().items()) if name.startswith("test_")}
if __name__ == "__main__":
    for name, test in tests.items():
        test()
        print(f"  ok  {name}")
    print(f"\n{len(tests)} passed")
