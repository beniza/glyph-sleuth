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
        assert not href.endswith(("/identify/", "/inspect/", "/regex/")),             f"{href} is not built yet"


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


tests = {name: fn for name, fn in sorted(globals().items()) if name.startswith("test_")}
if __name__ == "__main__":
    for name, test in tests.items():
        test()
        print(f"  ok  {name}")
    print(f"\n{len(tests)} passed")
