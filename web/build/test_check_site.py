"""Smallest thing that fails if the site checker stops catching things:
`python web/build/test_check_site.py`

A checker nobody has watched fail is decoration. Both real bugs it exists for are
reproduced here as fixtures — a link that goes nowhere, and a page naming a face
it has no source for — so the checker is known to be able to say no.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_site  # noqa: E402

BASE = check_site.BASE


def site(pages):
    """A throwaway site tree. {relative path: html}."""
    root = tempfile.mkdtemp()
    for path, html in pages.items():
        full = os.path.join(root, path.replace("/", os.sep))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(html)
    return root


def problems(pages):
    found, _checked, _external = check_site.check(site(pages))
    return [problem for _page, problem in found]


def test_a_clean_site_has_nothing_to_say():
    assert problems({
        "index.html": f'<a href="{BASE}/font/manjari/">Manjari</a>',
        "font/manjari/index.html": f'<a href="{BASE}/">home</a>',
    }) == []


def test_a_link_that_goes_nowhere_is_caught():
    # The real one: a test of mine used /glyphs/rit-rachana/ where the route is
    # /font/rit-rachana/glyphs/. It 404'd silently for days.
    found = problems({"index.html": f'<a href="{BASE}/glyphs/rit-rachana/">glyphs</a>'})
    assert len(found) == 1
    assert "goes nowhere" in found[0]


def test_a_directory_link_is_served_by_its_index():
    assert problems({
        "index.html": f'<a href="{BASE}/block/malayalam/">Malayalam</a>',
        "block/malayalam/index.html": "<h1>Malayalam</h1>",
    }) == []


def test_relative_and_encoded_links_resolve():
    assert problems({
        "font/manjari/index.html": '<a href="lookups/">lookups</a>'
                                   '<a href="../rit%20rachana/">RIT</a>',
        "font/manjari/lookups/index.html": "<h1>lookups</h1>",
        "font/rit rachana/index.html": "<h1>RIT</h1>",
    }) == []


def test_external_links_are_counted_not_fetched():
    _found, _checked, external = check_site.check(site({
        "index.html": '<a href="https://smc.org.in/fonts/">SMC</a>'
                      '<a href="mailto:x@y.z">mail</a>'
                      '<a href="#top">top</a>',
    }))
    # The mailto and the fragment are neither ours to resolve nor external
    # fetches; only the http one counts.
    assert external == 1


def test_a_face_named_with_no_source_is_caught():
    # The bug the whole v0.3.0 webfont work came from: the page sets text in a
    # family it never loaded, and the browser quietly substitutes another.
    found = problems({
        "font/rit-rachana/index.html":
            '<p class="specimen" data-face="RIT Rachana">ക</p>',
    })
    assert len(found) == 1
    assert 'names the face "RIT Rachana"' in found[0]


def test_a_face_with_a_source_is_accepted_however_it_arrives():
    # Three ways a face legitimately reaches a page, and all three must pass or
    # the checker fails the build for families that are perfectly fine.
    ours = ('<style>@font-face { font-family: "RIT Rachana"; '
            f'src: url("{BASE}/webfonts/rit/R.woff2") format("woff2"); }}</style>'
            '<p data-face="RIT Rachana">ക</p>')
    google = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2'
              '?family=Noto+Sans+Malayalam&display=swap">'
              '<p data-face="Noto Sans Malayalam">ക</p>')
    foundry = ('<link rel="stylesheet" href="https://smc.org.in/fonts/manjari.css">'
               '<p data-face="Manjari">ക</p>')
    for name, html in (("ours", ours), ("google", google), ("foundry", foundry)):
        assert problems({"p/index.html": html}) == [], name


def test_an_empty_data_face_is_not_a_claim():
    assert problems({"p/index.html": '<span data-face="">x</span>'}) == []


def test_a_truncated_table_with_no_note_is_caught():
    # render.py's capped() writes the marker and the note together, so a marker
    # on its own means the note was taken out. Five caps on this site were
    # undisclosed at one time or another; this is the guard against the sixth.
    found = problems({"block/basic-latin/index.html":
                      '<table class="index" data-showing="100" data-of="1854">'
                      "<tr><th>Face</th></tr></table>"})
    assert len(found) == 1
    assert "shows 100 of 1854 rows and says nothing" in found[0]


def test_a_truncated_table_that_says_so_is_fine():
    assert problems({"block/basic-latin/index.html":
                     '<table class="index" data-showing="100" data-of="1854">'
                     "<tr><th>Face</th></tr></table>"
                     '<p class="quiet cap-note">Showing 100 of 1,854 families.</p>'}) == []
    # And a table showing everything needs nothing, marker or note.
    assert problems({"p/index.html":
                     '<table class="index" data-showing="40" data-of="40">'
                     "<tr><th>Face</th></tr></table>"}) == []


def test_the_committed_mockup_is_skipped():
    # site/mockup/ is the design prototype, committed on purpose and rendered by
    # its own support.js in the browser. Its href="{{ font.source.url }}" are
    # template expressions, not dead links. Checking it reported 25 problems that
    # were not problems, which is how a checker stops being read.
    root = site({
        "mockup/index.html": '<a href="{{ font.source.url }}">x</a>',
        "index.html": "<h1>real</h1>",
    })
    found, _checked, _external = check_site.check(root)
    assert found == []
    # And the skip is only the top-level directory of that name, not any
    # directory called mockup anywhere in the tree.
    deep = site({"font/mockup/index.html": '<a href="/nope/">x</a>'})
    assert len(check_site.check(deep)[0]) == 1


tests = {name: fn for name, fn in sorted(globals().items()) if name.startswith("test_")}
if __name__ == "__main__":
    for name, test in tests.items():
        test()
        print(f"  ok  {name}")
    print(f"\n{len(tests)} passed")
