"""Two invariants over the built site: `python web/build/check_site.py`

Both were learned from bugs that shipped, and both are the same shape — a page
claiming something the build never gave it.

**Every internal link resolves.** Nothing checked this across ~34,000 pages. A
wrong path in one of our own tests 404'd silently and only surfaced because a
font failed to load on the error page.

**Every named face has a source on the same page.** `face_head()` and
`face_styles()` in render.py return nothing when a family has no stylesheet and
no webfont, and for weeks the pages went on naming the family anyway: the
evidence matrix printed "clean" beside a rendering the browser had substituted,
the glyph grid captioned another font with this font's glyph names. `/char/` was
fixed once and the lesson never left that function.

Checked over the output rather than trusted per page, because per-page is exactly
how three page types stayed broken after the fourth was fixed.

Regex, not a parser: the input is our own generated markup, and adding a
dependency to check it would be its own risk.
"""
import os
import re
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SITE = os.path.join(ROOT, "site")
BASE = os.environ.get("SITE_BASE", "/glyph-sleuth").rstrip("/")

# How many failures to print before saying how many more there are. A wall of
# 30,000 identical lines hides the one that is different.
SHOWN = 25

# `data-src` is in here on purpose: the Try it panel fetches its coverage from
# one, and a URL we fetch is as much a link as one a reader clicks. The leading
# boundary matters — without it `href` also matches inside `data-href`, and the
# check would be right by accident rather than by intent.
LINK = re.compile(r'(?:^|[\s])(?:href|src|data-src)="([^"]+)"')
# A table that stopped short. render.py's `capped()` writes both of these and
# the note; the checker's job is to notice if the note ever goes missing.
TRUNCATED = re.compile(r'data-showing="(\d+)"\s+data-of="(\d+)"')

FACE_ATTR = re.compile(r'data-face="([^"]*)"')
FONT_FAMILY = re.compile(r'font-family:\s*"([^"]+)"')
CSS2_FAMILY = re.compile(r'[?&]family=([^&:"]+)')


# The one directory under site/ that is committed rather than generated: the
# design prototype the build is checked against. It is a client-side template,
# so its markup is full of `href="{{ font.source.url }}"` — expressions its own
# support.js resolves in the browser, not links that go nowhere. Checking it
# would report 25 problems that are not problems, every run, until nobody read
# the output.
SKIP = ("mockup",)


def pages(root=SITE):
    for folder, dirs, files in os.walk(root):
        if folder == root:
            dirs[:] = [d for d in dirs if d not in SKIP]
        for name in files:
            if name.endswith(".html"):
                yield os.path.join(folder, name)


def internal(url):
    """Is this a link into our own site, and therefore ours to keep working?

    A protocol-relative `//host/x` is somebody else's, and so is anything with a
    scheme. A bare fragment or query stays on the page it came from.
    """
    if not url or url.startswith(("#", "?", "mailto:", "data:", "//")):
        return False
    return not urllib.parse.urlsplit(url).scheme


def resolves(url, page):
    """Does this internal link land on a file that exists?"""
    path = urllib.parse.urlsplit(url).path
    if not path:
        return True
    if path.startswith("/"):
        if BASE and not (path == BASE or path.startswith(BASE + "/")):
            return False            # absolute, but outside the prefix we serve
        target = os.path.join(SITE, urllib.parse.unquote(path[len(BASE):]).lstrip("/"))
    else:
        target = os.path.join(os.path.dirname(page), urllib.parse.unquote(path))
    if os.path.isfile(target):
        return True
    # A directory URL is served by its index.
    return os.path.isfile(os.path.join(target, "index.html"))


def faces_declared(html):
    """Every family this page can actually set text in.

    Three ways a face arrives, and the page has to carry one of them: Google's
    css2 URL naming the family, a foundry stylesheet we linked, or an @font-face
    of our own. A foundry stylesheet does not name its family in the URL, so its
    presence is taken as declaring whatever it declares — we cannot read someone
    else's CSS from here, and a stylesheet link is a real attempt to load a face
    rather than the silence this check exists to catch.
    """
    declared = {unquote_family(name) for name in FONT_FAMILY.findall(html)}
    for hit in CSS2_FAMILY.findall(html):
        declared.add(urllib.parse.unquote_plus(hit).strip())
    return declared


def foreign_stylesheets(html):
    return [url for url in LINK.findall(html)
            if not internal(url) and ".css" in url and "fonts.googleapis.com" not in url]


def unquote_family(name):
    return name.strip().strip("'\"")


def check(root=SITE):
    """[(page, problem)] — empty when the site is honest."""
    problems, checked, external = [], 0, 0
    for page in pages(root):
        with open(page, encoding="utf-8") as handle:
            html = handle.read()
        shown = os.path.relpath(page, root).replace(os.sep, "/")

        for url in set(LINK.findall(html)):
            if not internal(url):
                # Counted so the summary can say what was skipped rather than
                # implying everything was checked. A fragment or a mailto is
                # neither ours to resolve nor a URL anyone would fetch.
                external += url.startswith(("http://", "https://", "//"))
                continue
            checked += 1
            if not resolves(url, page):
                problems.append((shown, f"link goes nowhere: {url}"))

        # A table that stopped short must say so on the same page. `capped()` in
        # render.py emits the marker and the note together, so a bare marker means
        # somebody took the note out.
        for count, of in TRUNCATED.findall(html):
            if int(count) < int(of) and "cap-note" not in html:
                problems.append((shown, f"shows {count} of {of} rows and says nothing"))

        declared = faces_declared(html)
        has_foreign = bool(foreign_stylesheets(html))
        for family in set(FACE_ATTR.findall(html)):
            if not family or family in declared or has_foreign:
                continue
            problems.append((shown, f'names the face "{family}" and carries no source for it'))
    return problems, checked, external


def main():
    if not os.path.isdir(SITE):
        raise SystemExit("No site/ — run: python web/build/render.py")

    problems, checked, external = check()
    total = sum(1 for _ in pages())
    print(f"  {total:,} pages · {checked:,} internal links · {external:,} external, not fetched")

    if not problems:
        print("  every link resolves, and every named face has a source")
        return 0

    for page, problem in problems[:SHOWN]:
        print(f"  !! {page}: {problem}")
    if len(problems) > SHOWN:
        print(f"  ... and {len(problems) - SHOWN:,} more")
    print(f"  {len(problems):,} problems")
    return 1


if __name__ == "__main__":
    sys.exit(main())
