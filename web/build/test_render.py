"""Smallest thing that fails if the pages break: `python test_render.py`.

The pages are generated HTML, not assembled in the browser, so what these
assert is that the content is *in* the markup — a reader with JS off, and a
search engine, see the same facts a visitor does.
"""
import os
import html as html_module
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
                        ("Languages", "/languages/"), ("Compare", "/compare/")):
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

    # Every link on the page goes to a route the build actually writes. The
    # prototype's inert "picture of it" promise is gone; so is the temptation to
    # link Identify before it exists, which would be the same fault with a href.
    for href in re.findall(r'href="([^"]+)"', html):
        if href.startswith(("http://", "https://")):
            continue
        assert not href.endswith(("/identify/", "/regex/")), f"{href} is not built yet"


def test_home_links_are_real_paths():
    html = render.home([], scripts=[{"code": "Mlym", "name": "Malayalam", "chars": 118}],
                       languages=[{"id": "mal", "name": "Malayalam", "tag": "ml"}])
    # Hash routes were a prototype artefact. A generated page needs a real URL
    # or there is nothing for a crawler to follow.
    assert "#/" not in html
    assert f'href="{render.link("/script/Mlym/")}"' in html
    assert f'href="{render.link("/lang/mal/")}"' in html


def test_no_script_is_the_default_subject():
    """Malayalam was how the tiers got built, not what the site is about.

    A page about a Devanagari face must not measure itself against Malayalam,
    and the index must not have a Malayalam column. The flagship script is a
    depth of coverage, never a lens the whole site is seen through.
    """
    deva = {"name": "Annapurna SIL", "source": "sil", "tier": "measured",
            "checksum": "x", "ranges": [[0x0020, 0x007E], [0x0900, 0x097F]],
            "tags": ["deva", "dev2"], "gsub": 128, "gpos": 4, "features": [],
            "axes": [], "faces": [], "licence": "OFL", "url": "x", "css": None}
    html = render.font_page(deva, FULL_BLOCKS)
    assert "Devanagari" in html
    assert "Malayalam" not in html

    index = render.fonts_index([deva])
    assert "Malayalam" not in index


def test_dominant_script_is_the_font_s_own():
    latin_and_deva = {"ranges": [[0x0020, 0x007E], [0x0900, 0x097F]]}
    assert render.dominant_block(latin_and_deva, FULL_BLOCKS)[0] == "Devanagari"
    # Latin and punctuation say nothing about what a face is *for*, so a
    # Latin-only face has no script to name rather than being called Basic Latin.
    assert render.dominant_block({"ranges": [[0x0020, 0x007E]]}, FULL_BLOCKS) is None
    # A handful of stray codepoints outside Latin is not a script either.
    assert render.dominant_block({"ranges": [[0x0020, 0x007E], [0x0900, 0x0903]]},
                                 FULL_BLOCKS) is None


def test_precomputed_coverage_agrees_with_walking_it():
    """The build works out each family's block coverage once, by bisection.

    Asking per call was 327 range walks, and the language pages asked once per
    fitting family per language — eighteen seconds a page. The fast path has to
    give exactly the same answers as the slow one, or the pages are quietly
    wrong in a way no reader could catch.
    """
    blocks = [[0x0020, 0x007F, "Basic Latin"], [0x00A0, 0x00FF, "Latin-1 Supplement"],
              [0x0900, 0x097F, "Devanagari"], [0x0D00, 0x0D7F, "Malayalam"]]
    cases = [
        {"name": "Latin only", "ranges": [[0x0020, 0x007E]]},
        {"name": "Deva face", "ranges": [[0x0020, 0x007E], [0x0900, 0x097F]]},
        {"name": "Straddles a boundary", "ranges": [[0x0070, 0x00B0]]},
        {"name": "Two scripts", "ranges": [[0x0900, 0x093F], [0x0D00, 0x0D7F]]},
        {"name": "A few strays", "ranges": [[0x0020, 0x007E], [0x0900, 0x0903]]},
        {"name": "Nothing", "ranges": []},
    ]
    slow = [(render.blocks_covered(dict(font), blocks),
             render.dominant_block(dict(font), blocks)) for font in cases]
    render.prepare_fonts(cases, blocks)
    fast = [(render.blocks_covered(font, blocks), render.dominant_block(font, blocks))
            for font in cases]
    assert slow == fast, [(a, b) for a, b in zip(slow, fast) if a != b]

    # And the precompute really did fill in per-block counts.
    deva = cases[1]
    assert deva["_blocks"]["Devanagari"] == 128
    assert deva["_dominant"][0] == "Devanagari"


def test_index_filters_on_what_engineers_ask():
    """Script tags and block coverage, which is what the questions are about:
    "which families declare dev2", "which cover Arabic"."""
    fonts = [
        {"name": "Annapurna SIL", "slug": "a", "source": "sil", "tier": "measured",
         "checksum": "x", "ranges": [[0x0900, 0x097F]], "tags": ["deva", "dev2"],
         "licence": "OFL"},
        {"name": "Scheherazade", "slug": "s", "source": "sil", "tier": "measured",
         "checksum": "x", "ranges": [[0x0600, 0x06FF]], "tags": ["arab"],
         "licence": "OFL"},
    ]
    html = render.fonts_index(fonts, FULL_BLOCKS)

    # Every row carries its tags and the blocks it covers, so the filters are a
    # DOM pass rather than a fetch.
    assert 'data-tags="deva dev2"' in html
    assert "devanagari" in html and "arabic" in html

    # And the controls exist, with counts, listing what is actually there.
    assert 'name="tag"' in html and 'name="block"' in html
    assert 'value="dev2"' in html
    assert 'value="arabic"' in html
    # No tag or block that nothing carries.
    assert 'value="mlym"' not in html


def test_compare_page_is_a_shell_with_real_pickers():
    """Compare is the one page that cannot be generated per pair.

    1,878 measured families are 1.7 million pairs, so the page ships as a shell
    and fetches the two families a reader picks. What must still be in the
    markup is the list of families and what the page is for — a crawler and a
    reader with JS off both get that.
    """
    tables = {"gsub": [{"feature": "akhn", "type": "Ligature", "index": 0, "flag": 0,
                        "n": 60, "rules": []}], "gpos": []}
    fonts = [dict(MANJARI, slug="manjari", tables=tables),
             dict(MANJARI, name="Gayathri", slug="gayathri", gsub=62, tables=tables),
             {"name": "RIT Panmana", "slug": "rit-panmana", "tier": "stub", "ranges": []}]
    html = render.compare_page(fonts)

    # Both pickers, listing only families there is something to compare.
    assert html.count('<option value="manjari"') == 2
    assert html.count('<option value="gayathri"') == 2
    assert "rit-panmana" not in html, "a family with no tables has nothing to diff"

    # No guessed default pair — the prototype's manjari,gayathri default is
    # exactly the kind of invented answer HANDOFF rules out.
    assert 'selected' not in html
    assert "Pick two families" in html

    # It says what it compares, in the markup.
    assert "lookup" in html.lower()


def test_font_data_file_carries_what_compare_needs():
    font = dict(MANJARI, slug="manjari", tables={"gsub": [
        {"feature": "akhn", "type": "Ligature", "index": 0, "flag": 0, "n": 60, "rules": []}],
        "gpos": []})
    payload = render.font_data(font)

    assert payload["name"] == "Manjari"
    assert payload["tags"] == MANJARI["tags"]
    # Per-feature rule counts, which is the comparison that matters: two
    # families both declaring akhn can differ by fifty rules inside it.
    assert payload["features"]["akhn"]["gsub"] == 60
    assert payload["features"]["akhn"]["lookups"] == 1
    # Verdicts travel too, so the diff can show where they disagree.
    assert payload["verdicts"]["Mlym"]["nta"] == "clean"
    # The glyph inventory does not: it is a thousand rows per family and the
    # comparison never reads it.
    assert "glyphs" not in payload


def test_specimen_suits_the_font():
    """Setting Malayalam words in a Latin face shows a row of tofu.

    The prototype could hardcode Malayalam because it was a Malayalam app. An
    index of 1,885 families cannot: the specimen has to be text the face can
    actually draw, or the page is demonstrating the wrong thing.
    """
    malayalam = {"name": "Manjari", "ranges": [[0x0D00, 0x0D7F]]}
    devanagari = {"name": "Annapurna SIL", "ranges": [[0x0900, 0x097F]]}
    latin = {"name": "ABeeZee", "ranges": [[0x0020, 0x007E]]}

    # Each face demonstrates itself in its own script, chosen from the face,
    # never from a script the site happens to know best.
    assert "മ" in render.specimen_text(malayalam, FULL_BLOCKS)[0]
    assert "दे" in render.specimen_text(devanagari, FULL_BLOCKS)[0]
    assert "മ" not in render.specimen_text(devanagari, FULL_BLOCKS)[0]
    assert render.specimen_text(latin, FULL_BLOCKS)[0].strip()
    assert "മ" not in render.specimen_text(latin, FULL_BLOCKS)[0]
    # A Latin face carrying a handful of Malayalam codepoints is still a Latin
    # face; the threshold is coverage, not presence.
    assert "മ" not in render.specimen_text(
        {"ranges": [[0x0020, 0x007E], [0x0D00, 0x0D05]]}, FULL_BLOCKS)[0]


def test_fonts_index_controls():
    """Filter, facets and sort — over rows that are already served.

    The controls narrow what is shown; they never fetch. With JS off the page
    is the full index, which is also what a crawler reads.
    """
    fonts = [
        dict(MANJARI, name="Manjari", slug="manjari"),
        dict(MANJARI, name="Gayathri", slug="gayathri", results={"Mlym": {
            "nta": {"hb": {"verdict": "fail", "glyphs": [], "note": "", "command": ""},
                    "dw": None, "ct": None, "gr": None}}}),
        {"name": "ABeeZee", "slug": "abeezee", "source": "google", "tier": "measured",
         "licence": "OFL", "ranges": [[0x20, 0x7E]], "tags": [], "checksum": "x"},
        {"name": "RIT Panmana", "slug": "rit-panmana", "source": "rit", "tier": "stub",
         "ranges": [], "licence": "", "url": "x", "css": None},
    ]
    html = render.fonts_index(fonts)

    # A text filter, and the facets the design calls for, each carrying its own
    # count so the number is visible before you click it. No script-specific
    # facet: the index is not seen through one script's lens.
    assert 'type="search"' in html
    for facet, count in (("all", 4), ("measured", 3), ("not measured yet", 1)):
        assert f'data-facet="{facet}"' in html, facet
        assert f'data-count="{count}"' in html, (facet, count)

    # Sort controls, name first because that is the order the page is served in.
    for key in ("name", "coverage", "verdict"):
        assert f'data-sort="{key}"' in html, key

    # Every row carries what the filters need, so filtering is a DOM pass and
    # never a fetch.
    assert 'data-name="manjari"' in html
    assert 'data-source="smc"' in html
    assert 'data-tier="measured"' in html
    assert 'data-coverage="' in html
    assert 'data-verdict="clean"' in html and 'data-verdict="fail"' in html
    # And a family with nothing shaped says so rather than claiming a verdict.
    assert 'data-verdict="none"' in html

    # The count the design shows, correct before any JS runs — JS only updates
    # the first number as the filters narrow it.
    assert re.search(r"Showing\s*<span data-showing>4</span>\s*of\s*4", html)


def test_fonts_index_lists_every_family_in_the_html():
    """The nav promises this page, so it has to exist — and it has to carry the
    families in the markup, not fetch them.

    Filtering and sorting are JS on top of rows that are already there; with JS
    off it is still a full list, and a crawler sees every family.
    """
    fonts = [dict(MANJARI), dict(MANJARI, name="Gayathri", tier="measured"),
             {"name": "RIT Panmana", "source": "rit", "tier": "stub", "ranges": [],
              "licence": "", "url": "x", "css": None}]
    html = render.fonts_index(fonts)

    for font in fonts:
        assert esc_name(font["name"]) in html
        assert render.font_href(font) in html
    # Counts, and the split between what we measured and what we did not.
    assert "3" in html and "2" in html
    # The unmeasured one is marked as such rather than shown as covering nothing.
    assert "not measured yet" in html


def esc_name(name):
    return render.esc(name)


def test_slug_survives_a_name_that_is_not_latin():
    """RIT's families name themselves in Malayalam.

    Stripping to [a-z0-9] left those slugs empty, so the page was written to
    /font//index.html — it landed at /font/, and every other such family
    overwrote it. A site about scripts cannot assume its own font names are
    Latin.
    """
    assert render.slug("ആര്‍ഐടി താര")
    assert render.slug("ആര്‍ഐടി താര") != render.slug("ആര്‍ഐടി രചന")
    # Latin names are unchanged by this — the old slugs still work.
    assert render.slug("Noto Sans Malayalam") == "noto-sans-malayalam"
    assert render.slug("Baloo Chettan 2") == "baloo-chettan-2"
    # And a name of pure punctuation still has to produce *something*.
    assert render.slug("!!!")


def test_slugs_are_unique():
    # Two families sharing a slug means one page silently overwrites the other,
    # which is how a family disappears from a site that claims to index it.
    names = ["Noto Sans", "Noto  Sans", "noto sans", "Noto-Sans", "Meera", "Meera Inimai"]
    taken = {}
    slugs = [render.unique_slug(name, taken) for name in names]
    assert len(set(slugs)) == len(slugs), slugs
    assert slugs[0] == "noto-sans"


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
FULL_BLOCKS = BLOCKS + [[0x0600, 0x06FF, "Arabic"], [0x0900, 0x097F, "Devanagari"]]


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


def test_the_snippet_is_marked_up_without_becoming_a_hole():
    # Highlighting means inserting markup into a string, which is how a
    # highlighter becomes an injection. Escaping happens per token, so a family
    # named with a tag comes out as text and not as a tag.
    marked = render.highlight('font-family: "<script>x</script>";')
    assert "<span" in marked
    assert "&lt;script&gt;" in marked
    assert "<script>" not in marked
    # The three token kinds, and nothing dropped: strip the markup and the
    # snippet must be exactly what went in.
    plain = re.sub(r"<[^>]+>", "", render.highlight('@font-face { src: url("a.woff2"); }'))
    assert html_module.unescape(plain) == '@font-face { src: url("a.woff2"); }'


def test_google_is_asked_for_the_weights_the_control_offers():
    # The weight control may only offer faces that will actually arrive. Ask the
    # CDN for the regular alone and pick 800 and the browser smears the outlines
    # into a fake bold — which is exactly the kind of claim this site exists to
    # catch someone else making.
    many = dict(MANJARI, source="google", name="Abhaya Libre", css=None,
                faces=["400", "500", "800"])
    css = render.face_css_of(many)
    assert ":wght@400;500;800" in css
    page = render.font_page(many, BLOCKS)
    for weight in ("400", "500", "800"):
        assert f'<option value="{weight}">' in page
    # One face is no choice, so there is no control and no axis in the request.
    one = dict(MANJARI, source="google", name="ABeeZee", css=None, faces=["400"])
    assert "wght@" not in render.face_css_of(one)
    assert 'data-try="weight"' not in render.font_page(one, BLOCKS)
    # Italic is offered only where an italic face exists — never synthesised.
    assert 'data-try="italic"' not in render.font_page(many, BLOCKS)
    both = dict(many, faces=["400", "400i"])
    assert ":ital,wght@0,400;1,400" in render.face_css_of(both)
    assert 'data-try="italic"' in render.font_page(both, BLOCKS)


def test_two_releases_of_one_family_show_where_they_differ():
    # Google and a foundry carry about thirty families in common. Only one used
    # to survive and it was Google's, so Charis SIL reported two faces where SIL
    # ships eight, and "not read" where SIL's release has 263 GSUB lookups.
    google = {"name": "Charis SIL", "source": "google", "tier": "measured",
              "url": "https://fonts.google.com/specimen/Charis+SIL",
              "version": "3", "ranges": [[0x0041, 0x005A]],
              "faces": ["400", "400i"], "tags": None, "gsub": None, "gpos": None}
    font = dict(MANJARI, name="Charis SIL", source="sil", version="7.000",
                faces=["400", "500", "600", "700"], gsub=263, gpos=90,
                webfont="webfonts/sil/font-charis/Charis-Regular.woff2",
                alternates=[google])
    page = render.font_page(font, BLOCKS)

    assert "Two releases" in page
    assert "SIL v7.000" in page and "Google Fonts v3" in page
    # Rows that differ are here...
    assert "weights published" in page
    assert "GSUB · GPOS lookups" in page
    # ...and the page says plainly which release everything else came from.
    assert "is the SIL v7.000 release" in page
    assert "never merged" in page


def test_only_the_rows_that_differ_appear():
    """A row repeating one number twice is furniture.

    My first version of this asserted that two agreeing releases produce no table
    at all. That premise was wrong: Google and a foundry almost always differ on
    *delivery* — served here against Google's CDN — and saying so is real
    information a reader installing a font wants. What must be suppressed is a
    row where the two numbers are identical.
    """
    twin = {"name": "Manjari", "source": "google", "tier": "measured",
            "version": MANJARI.get("version"), "ranges": MANJARI["ranges"],
            "faces": MANJARI.get("faces"), "tags": MANJARI.get("tags"),
            "gsub": MANJARI.get("gsub"), "gpos": MANJARI.get("gpos"),
            "provenance": MANJARI.get("provenance")}
    html = render.two_releases(dict(MANJARI, alternates=[twin]))
    rows = re.findall(r'<th scope="row">([^<]+)</th>', html)
    # Everything measured agrees, so only how you get it is left.
    assert rows == ["webfont"], rows

    # And a genuine difference in a measured figure does appear.
    fewer = dict(twin, gsub=4, gpos=1)
    rows = re.findall(r'<th scope="row">([^<]+)</th>',
                      render.two_releases(dict(MANJARI, alternates=[fewer])))
    assert "GSUB · GPOS lookups" in rows


def test_a_family_with_one_release_is_unchanged():
    # Only ~30 of 1,885 families have a second release. The rest must render
    # exactly as before, or this change is a redesign wearing a bug fix's name.
    assert render.two_releases(MANJARI) == ""
    assert "Two releases" not in render.font_page(MANJARI, BLOCKS)


def test_the_glyphs_page_says_what_the_cap_dropped():
    # 4,000 shown out of 22,000 read as complete, because the page printed the
    # capped number on both sides of "showing N of N". Every other cap on the
    # site is disclosed; this one was the exception.
    inventory = [{"name": f"g{i}", "cp": None, "produced": [], "consumed": [],
                  "orphan": False} for i in range(10)]
    capped = dict(MANJARI, glyphs=inventory, glyph_count=22000)
    page = render.glyphs_page(capped)
    assert "Showing" in page and "of 22,000" in page
    assert "first 10 of the 22,000 glyphs" in page
    assert "21,990 are not shown" in page

    # Nothing dropped: no note, and the two numbers agree.
    whole = dict(MANJARI, glyphs=inventory, glyph_count=10)
    page = render.glyphs_page(whole)
    assert "are not shown" not in page

    # A measurement taken before the total was recorded must not guess. It says
    # what it has and claims nothing about what it does not.
    unknown = dict(MANJARI, glyphs=inventory)
    unknown.pop("glyph_count", None)
    page = render.glyphs_page(unknown)
    assert "are not shown" not in page
    assert "of 10" in page


def test_every_face_we_serve_gets_its_own_rule():
    # One @font-face per face, each carrying the weight and style that face
    # declares. Without the descriptors all four rules claim to be the regular,
    # the browser uses whichever it loaded last, and the weight control moves
    # nothing while looking like it does.
    family = dict(MANJARI, source="rit", css=None, licence="OFL-1.1",
                  name="RIT Rachana", faces=["400", "700", "400i"],
                  webfont="webfonts/rit/R/R-Regular.woff2",
                  webfonts={"400": "webfonts/rit/R/R-Regular.woff2",
                            "700": "webfonts/rit/R/R-Bold.woff2",
                            "400i": "webfonts/rit/R/R-Italic.woff2"})
    rule = render.face_rule(family)
    assert rule.count("@font-face") == 3
    assert "R-Bold.woff2\") format(\"woff2\"); font-weight: 700; font-style: normal" in rule
    assert "R-Italic.woff2\") format(\"woff2\"); font-weight: 400; font-style: italic" in rule

    page = render.font_page(family, BLOCKS)
    assert '<option value="700">' in page
    assert 'data-try="italic"' in page


def test_a_variable_face_is_offered_across_its_axis():
    # Two endpoints in the face list, but every round weight between them is a
    # real thing to ask for — the file covers them all.
    variable = dict(MANJARI, source="rit", css=None, licence="OFL-1.1", name="Vazirmatn",
                    faces=["100", "900"], axes=[{"tag": "wght", "min": 100, "max": 900}],
                    webfont="webfonts/libre/v/V.woff2",
                    webfonts={"100 900": "webfonts/libre/v/V.woff2"})
    rule = render.face_rule(variable)
    assert rule.count("@font-face") == 1
    assert "font-weight: 100 900" in rule
    page = render.font_page(variable, BLOCKS)
    for weight in ("100", "400", "900"):
        assert f'<option value="{weight}">' in page


def test_try_it_is_absent_where_we_cannot_draw_the_family():
    # A box that sets your text in a font the browser cannot load would set it in
    # some other font and present that as this family — the same lie the glyph
    # grid and the evidence matrix were fixed for.
    unloadable = dict(MANJARI, source="rit", css=None, webfont=None, licence="OFL-1.1")
    page = render.font_page(unloadable, BLOCKS)
    assert 'class="try"' not in page
    assert "No specimen here" in page

    servable = dict(unloadable, webfont="webfonts/rit/RIT-Rachana/RIT-Rachana-Regular.woff2")
    served = render.font_page(servable, BLOCKS)
    assert 'class="try"' in served
    # And it fetches its coverage from the file Compare already writes, rather
    # than inlining a second copy of the ranges into every family page.
    assert "/data/font/" in served


def test_lookups_page_shows_the_working():
    font = dict(MANJARI, tables={
        "gsub": [{"feature": "akhn", "type": "Ligature", "index": 0, "flag": 0, "n": 60,
                  "rules": [{"in": "k1 xx k1", "out": "k1k1"}]},
                 {"feature": "akhn", "type": "Chaining context", "index": 1, "flag": 0,
                  "n": 25, "rules": []}],
        "gpos": [{"feature": "abvm", "type": "Mark to base", "index": 0, "flag": 0,
                  "n": 464, "rules": []}],
    })
    html = render.lookups_page(font)

    # Named "lookups", not "shaping": shaping is the engine's job and a script
    # engineer cannot change it. Lookups are the part they write.
    assert "lookups" in html and "shaping tables" not in html

    # Grouped by feature, because that is how a reader thinks about it: what
    # does akhn actually do in this font?
    assert "akhn" in html and "abvm" in html
    assert "Ligature" in html and "Mark to base" in html
    # A rule reads as what it does — in the script first, and the font's own
    # glyph names second. Nobody should have to learn that this family calls
    # chillu n "n1cil" to understand a substitution.
    assert "k1 xx k1" in html and "k1k1" in html
    # The counts are the full counts, even where only a few rules are shown.
    assert "60" in html and "464" in html
    # A contextual lookup lists no rules, and says why rather than looking empty.
    assert "chains other lookups" in html

    # It is a page about one family, and says whose working this is.
    assert "Manjari" in html
    assert render.font_href(font) in html


def test_lookups_page_needs_the_tables():
    # Nothing to show for a family whose file we never opened, and the page
    # says that instead of rendering an empty table.
    stub = {"name": "RIT Panmana", "source": "rit", "tier": "stub", "ranges": [],
            "licence": "", "url": "x", "css": None, "tags": [], "features": [],
            "axes": [], "faces": []}
    html = render.lookups_page(stub)
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


def test_char_page_draws_the_glyph_in_each_family():
    """Naming the families that have a character is half an answer.

    Two faces can both cover U+0D15 and draw it quite differently, and that
    difference is the thing a reader came to see. Each family draws it in its
    own face, loaded from its own distribution.
    """
    fonts = [
        {"name": "Manjari", "slug": "manjari", "source": "smc", "tier": "measured",
         "ranges": [[0x0D00, 0x0D7F]], "licence": "OFL",
         "css": "https://smc.org.in/fonts/manjari.css"},
        {"name": "Baloo Chettan 2", "slug": "baloo-chettan-2", "source": "google",
         "tier": "measured", "ranges": [[0x0D00, 0x0D7F]], "licence": "OFL"},
        {"name": "ABeeZee", "slug": "abeezee", "source": "google", "tier": "measured",
         "ranges": [[0x0020, 0x007E]], "licence": "OFL"},
    ]
    # Which families cover it is worked out once for the whole build, so the
    # page is handed the list rather than filtering 1,885 families itself.
    index = render.coverage_index(fonts, {0x0D15})
    assert [f["name"] for f in index[0x0D15]] == ["Manjari", "Baloo Chettan 2"]

    html = render.char_page(0x0D15, "MALAYALAM LETTER KA",
                            [0x0D00, 0x0D7F, "Malayalam"], index[0x0D15], {0x0D15})

    # A tile per family that has it, each drawn in that family.
    assert 'class="draws' in html
    assert html.count('class="tile-glyph') == 2, "one tile per covering family"
    # The face is loaded from where the family is actually distributed: the
    # foundry's own stylesheet, and Google's CDN for Google's families.
    assert "https://smc.org.in/fonts/manjari.css" in html
    assert "family=Baloo+Chettan+2" in html
    # A family without the character is not shown drawing it.
    assert "ABeeZee" not in html
    # Each tile is keyed to its own family, so no two rows borrow a face.
    assert ".f-manjari" in html and ".f-baloo-chettan-2" in html
    # And the tile links to the family it draws.
    assert render.link("/font/manjari/") in html


def test_char_page_says_how_many_faces_it_drew():
    # Loading a hundred webfonts on one page is not a page. The cap is stated,
    # because a grid of twenty-four when there are nine hundred reads as
    # "twenty-four families have this" unless it says otherwise.
    fonts = [{"name": f"Face {n}", "slug": f"face-{n}", "source": "google",
              "tier": "measured", "ranges": [[0x0D00, 0x0D7F]], "licence": "OFL"}
             for n in range(40)]
    html = render.char_page(0x0D15, "MALAYALAM LETTER KA",
                            [0x0D00, 0x0D7F, "Malayalam"], fonts, {0x0D15})
    assert html.count('class="tile-glyph') == render.DRAWN_LIMIT
    assert f"{render.DRAWN_LIMIT} of 40" in html


def test_every_script_gets_character_pages():
    """Tamil's chart cells were not links, because character pages existed only
    for Latin and the two scripts we shape.

    The bound is now the block's size, not a hand-picked list: every block small
    enough to be about a writing system gets a page per codepoint. Eleven blocks
    hold 110,233 of Unicode's 143,041 assigned codepoints, and a page each for
    those would be a hundred thousand files saying little beyond a name.
    """
    blocks = [[0x0B80, 0x0BFF, "Tamil"], [0x0D00, 0x0D7F, "Malayalam"],
              [0x4E00, 0x9FFF, "CJK Unified Ideographs"]]
    assigned = render.assigned_by_block(blocks)

    assert len(assigned["Tamil"]) <= render.CHAR_PAGE_MAX_BLOCK
    assert len(assigned["Malayalam"]) <= render.CHAR_PAGE_MAX_BLOCK
    assert len(assigned["CJK Unified Ideographs"]) > render.CHAR_PAGE_MAX_BLOCK

    # Unassigned codepoints are never included: nothing can cover them.
    assert 0x0B80 not in assigned["Tamil"]
    assert 0x0B95 in assigned["Tamil"]                    # TAMIL LETTER KA


def test_block_page_says_when_its_characters_have_no_pages():
    # A chart of cells that are links except where they silently are not is
    # worse than a chart that says which it is.
    big = [0x4E00, 0x9FFF, "CJK Unified Ideographs"]
    html = render.block_page(big, [], chars_built=set())
    assert "do not have pages of their own" in html


def test_pages_only_link_characters_that_exist():
    """A page per assigned codepoint would be over a million files, so only some
    blocks get one — and the pages that link characters are told which.

    Writing a link to a page we chose not to build is a 404 of our own making,
    which is worse than showing the codepoint as plain text.
    """
    font = dict(MANJARI, slug="manjari", glyphs=[
        {"name": "k1", "cp": 0x0D15, "produced": [], "consumed": ["akhn"], "orphan": False},
        {"name": "A", "cp": 0x0041, "produced": [], "consumed": [], "orphan": False},
    ])
    # Only Latin A has a page in this build.
    html = render.glyphs_page(font, chars_built={0x0041})
    assert f'href="{render.link("/char/0041/")}"' in html
    assert "/char/0D15/" not in html
    # The codepoint is still shown, just not as a link.
    assert "U+0D15" in html


def test_feature_page_says_what_it_cannot():
    content = {"stages": ["akhn", "pres"], "features": {
        "akhn": {"name": "Akhand ligatures", "table": "GSUB",
                 "prose": ["akhn forms the conjuncts."], "examples": []}}}
    fonts = [dict(MANJARI, slug="manjari", tables={"gsub": [
        {"feature": "akhn", "type": "Ligature", "index": 0, "flag": 0, "n": 60, "rules": []}],
        "gpos": []})]

    written = render.feature_page("akhn", content, fonts)
    assert "Akhand ligatures" in written
    assert "akhn forms the conjuncts." in written
    # Who runs it, and how much of it they run — the count is the interesting part.
    assert "Manjari" in written and "60" in written

    # A tag nothing is authored about gets its registered name and no invention.
    bare = render.feature_page("tnum", content, fonts)
    assert "Tabular figures" in bare
    assert "No write-up yet" in bare
    assert "None of the families" in bare


DEVA_SCRIPT = {"code": "Deva", "name": "Devanagari", "chars": 128, "languages": ["hin"],
               "blocks": [{"name": "Devanagari", "chars": 128,
                           "ranges": [[0x0900, 0x097F]]}]}
BRAI_SCRIPT = {"code": "Brai", "name": "Braille", "chars": 256, "languages": ["hin"],
               "blocks": [{"name": "Braille Patterns", "chars": 256,
                           "ranges": [[0x2800, 0x28FF]]}]}


def test_language_ranks_the_families_that_fit_first():
    """The page said "59 families that fit" and then listed near misses.

    Which meant a Latin face missing all 67 Devanagari exemplars appeared above
    every family that actually works. The families that fit are the answer to
    "what do I set this in", so they come first, as cards, and a face drawn for
    the script outranks a pan-Unicode one that merely includes the block.
    """
    dedicated = {"name": "Annapurna SIL", "slug": "annapurna-sil", "source": "sil",
                 "tier": "measured", "ranges": [[0x0900, 0x097F]], "licence": "OFL",
                 "css": None}
    workhorse = {"name": "AAA Workhorse", "slug": "aaa", "source": "google",
                 "tier": "measured", "licence": "OFL",
                 "ranges": [[0x0020, 0x007E], [0x0900, 0x097F], [0x4E00, 0x4FFF]]}
    latin = {"name": "ABeeZee", "slug": "abeezee", "source": "google", "tier": "measured",
             "ranges": [[0x0020, 0x007E]], "licence": "OFL"}
    language = {"id": "hin", "tag": "hi", "iso": "hin", "name": "Hindi",
                "exemplars": "अआकखग", "scripts": ["Deva", "Brai"],
                "sample": "सभी मनुष्यों को गौरव"}
    blocks = [[0x0020, 0x007F, "Basic Latin"], [0x0900, 0x097F, "Devanagari"],
              [0x2800, 0x28FF, "Braille Patterns"], [0x4E00, 0x4FFF, "CJK Unified Ideographs"]]

    html = render.lang_page(language, [latin, workhorse, dedicated],
                            [BRAI_SCRIPT, DEVA_SCRIPT], set(), blocks)

    # Cards, and the one built for the script leads even though its name sorts last.
    assert html.index("Annapurna SIL") < html.index("AAA Workhorse")
    assert "built for Devanagari" in html
    # A Latin face missing every exemplar is not offered as a near miss at all.
    assert "ABeeZee" not in html
    # Each card is set in real words of the language, in that family's own face.
    assert "सभी मनुष्यों को" in html
    assert ".f-annapurna-sil" in html


def test_language_keeps_the_default_script_first():
    # SIL marks the default by giving the bare tag its script. Sorting these
    # alphabetically is how Hindi read "written in Braille, Devanagari, Latin".
    language = {"id": "hin", "tag": "hi", "iso": "hin", "name": "Hindi",
                "exemplars": "अ", "scripts": ["Deva", "Brai"], "sample": ""}
    html = render.lang_page(language, [], [BRAI_SCRIPT, DEVA_SCRIPT], set(), [])
    assert html.index("Devanagari") < html.index("Braille")


def test_script_page_shows_the_alphabet():
    """Seeing a script's characters used to take four clicks — language, script,
    a font, that font's glyph list — and ended in one family's glyph dump."""
    html = render.script_page(DEVA_SCRIPT, [], [], chars_built={0x0915, 0x093E})

    assert "The characters" in html
    # Grouped by Unicode's own categories, so the grouping is checkable.
    assert "Letters" in html and "Marks" in html
    # क is a letter and links to its character page.
    assert f'href="{render.link("/char/0915/")}"' in html
    # A combining mark is shown on a dotted circle rather than floating.
    assert "◌" in html


def test_nav_groups_the_tools():
    """Four browsable sections and a Tools group, not a flat pile of nine.

    A tool answers a question you bring; an index answers one it already holds.
    The group is a disclosure so it opens by click and by keyboard with no
    JavaScript — the nav has to work on a page whose JS never ran.
    """
    html = render.page("X", "<p>y</p>")

    assert '<details class="tools"><summary>Tools</summary>' in html
    for label, href in render.TOOLS:
        assert f'href="{render.link(href)}"' in html, href
        assert f">{label}</a>" in html, label
    # Still no link to a tool that does not exist.
    for missing in ("/regex/", "/identify/"):
        assert f'href="{render.link(missing)}"' not in html, missing
    # And Compare moved into the group rather than being listed twice.
    assert html.count(f'href="{render.link("/compare/")}"') == 1


def test_inspect_is_a_shell_that_admits_what_it_needs():
    html = render.inspect_page()

    # The field, and the notations worth advertising.
    assert 'id="inspect-input"' in html
    assert "U+0D15" in html
    # The promise, stated where it is made.
    assert "Nothing you type leaves the page" in html
    # It is the one page whose content genuinely needs JS, so it says so and
    # points at a route that does not — rather than rendering an empty shell.
    assert "<noscript>" in html
    assert "needs" in html and "JavaScript" in html
    assert render.link("/block/basic-latin/") in html


def test_every_drawn_face_names_itself():
    """A panel that draws text in a named family is claiming that family drew it.

    If the stylesheet 404s, or the family loads without these characters, the
    browser silently substitutes another face and the page looks like it is
    showing the font. The client can only measure that if the markup says which
    family each drawing is supposed to be — so it does, everywhere the claim is
    made, and a page that drops the attribute fails here rather than misleading
    someone quietly.
    """
    font = {"name": "Manjari", "slug": "manjari", "source": "smc", "tier": "measured",
            "ranges": [[0x0D00, 0x0D7F]], "licence": "OFL",
            "css": "https://smc.org.in/fonts/manjari.css", "checksum": "x",
            "tags": ["mlym"], "features": [], "axes": [], "faces": [], "url": "x"}
    blocks = [[0x0020, 0x007F, "Basic Latin"], [0x0D00, 0x0D7F, "Malayalam"]]

    # The font page's own specimen: the drawing most likely to be trusted.
    page = render.font_page(font, blocks)
    assert 'data-face="Manjari"' in page

    # The character page's grid of families.
    chars = render.char_page(0x0D15, "MALAYALAM LETTER KA", blocks[1],
                             [font], {0x0D15})
    assert 'data-face="Manjari"' in chars

    # The language page's cards.
    language = {"id": "mal", "tag": "ml", "iso": "mal", "name": "Malayalam",
                "exemplars": "ക", "scripts": ["Mlym"], "sample": "മലയാളം"}
    script = {"code": "Mlym", "name": "Malayalam", "chars": 118, "languages": ["mal"],
              "blocks": [{"name": "Malayalam", "chars": 118, "ranges": [[0x0D00, 0x0D7F]]}]}
    cards = render.lang_page(language, [font], [script], set(), blocks)
    assert 'data-face="Manjari"' in cards


tests = {name: fn for name, fn in sorted(globals().items()) if name.startswith("test_")}
if __name__ == "__main__":
    for name, test in tests.items():
        test()
        print(f"  ok  {name}")
    print(f"\n{len(tests)} passed")
