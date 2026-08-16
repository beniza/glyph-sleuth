"""Render the site to static HTML files.

Pages are generated, not assembled in the browser: a reader with JS off, and a
crawler, get the same facts a visitor does. JS is enhancement on top of served
markup — filtering, sliders, the drawing canvas — and never the thing that
produces the content.

The design is the prototype's, recreated in a real stylesheet rather than the
wall of inline styles its template format produced. Tokens, type scale and copy
come from docs/prototype/README.md, which is final.
"""
import html as html_module
import io
import json
import os
import re
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_SITE = os.path.join(ROOT, "site")

# GitHub Pages serves a project site under /<repo>/, not at the domain root, so
# every internal URL needs that prefix — without it the stylesheet 404s and the
# page renders unstyled. Set SITE_BASE="" to build for a root domain, or for
# serving the folder locally.
BASE = os.environ.get("SITE_BASE", "/glyph-sleuth").rstrip("/")

# Loaded from Google's CDN, like every specimen. We host no font files.
WEBFONTS = ("https://fonts.googleapis.com/css2"
            "?family=IBM+Plex+Sans:wght@400;500;600"
            "&family=IBM+Plex+Sans+Condensed:wght@500;600"
            "&family=IBM+Plex+Mono:wght@400;500"
            "&display=swap")

NAV = [("Home", "/"), ("Scripts", "/scripts/"), ("Languages", "/languages/"),
       ("Fonts", "/fonts/"), ("Inspect", "/inspect/"), ("Identify", "/identify/"),
       ("Compare", "/compare/"), ("Regex", "/regex/")]


def esc(value):
    """Everything that reaches a page goes through here."""
    if value is None:
        return ""
    return html_module.escape(str(value), quote=True)


def link(path):
    """An internal path, prefixed with wherever the site is actually served."""
    if path.startswith(("http://", "https://", "#", "mailto:")):
        return path
    if BASE and path.startswith(BASE + "/"):
        return path
    return BASE + path


def slug(name):
    """The stable handle a family's URL is keyed on."""
    return re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")


def font_href(font):
    return link(f"/font/{slug(font['name'])}/")


def page(title, body, kind=None, code=None, description=None):
    """The shell every page shares: masthead, nav, content, colophon."""
    nav = "\n".join(
        f'        <a href="{link(href)}">{esc(label)}</a>' for label, href in NAV)
    where = ""
    if kind:
        where = (f'<div class="where">{esc(kind)}'
                 + (f' · <span class="mono">{esc(code)}</span>' if code else "")
                 + "</div>")
    meta = f'\n  <meta name="description" content="{esc(description)}">' if description else ""

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)} · Glyph Sleuth</title>{meta}
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="{WEBFONTS}">
  <link rel="stylesheet" href="{link("/style.css")}">
</head>
<body>
  <header class="masthead">
    <div class="column">
      <a class="wordmark" href="{link("/")}">Glyph Sleuth</a>
      <nav aria-label="Sections">
{nav}
      </nav>
    </div>
  </header>
  <div class="trail">
    <div class="column">{where}</div>
  </div>
  <main class="column">
{body}
  </main>
  <footer class="colophon">
    <div class="column">
      <p>Read-only. Nothing you type leaves the browser. We host no font files:
         specimens are drawn from wherever each family is actually distributed.</p>
      <p><a href="https://github.com/beniza/glyph-sleuth">Source and corrections ↗ — external</a></p>
    </div>
  </footer>
</body>
</html>
"""


def counts(fonts):
    """What we indexed, and how much of it we actually measured.

    Stated together on purpose: an index of 1,900 families where 40 carry real
    numbers is two different facts, and reporting only the first is the kind of
    claim this site exists to argue against.
    """
    measured = sum(1 for f in fonts if f.get("tier") == "measured")
    return len(fonts), measured


def home(fonts, scripts, languages):
    total, measured = counts(fonts)
    script_links = "\n".join(
        f'          <a href="{link("/script/" + s["code"] + "/")}">{esc(s["name"])}</a>'
        for s in scripts[:12])
    language_links = "\n".join(
        f'          <a href="{link("/lang/" + l["id"] + "/")}">{esc(l["name"])}</a>'
        for l in languages[:12])
    family_links = "\n".join(
        f'          <a href="{font_href(f)}">{esc(f["name"])}</a>'
        for f in fonts[:12])

    body = f"""    <section class="claim">
      <h1>Glyph Sleuth</h1>
      <p class="lede">Coverage says a font contains the character.
         It does not say the font will draw it.</p>
      <p>Glyph Sleuth reports both, and the evidence behind both: every family
         checked against the characters and the sequences a language actually
         writes.</p>
      <p class="quiet">Read-only. Nothing you type leaves the browser.</p>
    </section>

    <section>
      <h2 class="eyebrow">What is indexed</h2>
      <dl class="facts">
        <div><dt>Families indexed</dt><dd class="mono">{total:,}</dd></div>
        <div><dt>Measured from a release</dt><dd class="mono">{measured:,}</dd></div>
        <div><dt>Not measured yet</dt><dd class="mono">{total - measured:,}</dd></div>
      </dl>
      <p class="quiet">A family is <em>measured</em> when we have read its own
         released font file: coverage from <span class="mono">cmap</span>, the
         script tags it declares from <span class="mono">GSUB</span> and
         <span class="mono">GPOS</span>, and a shaping verdict per sequence.
         The rest are indexed and findable, and say so rather than implying a
         number nobody computed.</p>
    </section>

    <section>
      <h2 class="eyebrow">Start with a question</h2>
      <div class="paths">
        <div>
          <span class="q">Which font can set this?</span>
          <div class="links">
{family_links or '          <span class="quiet">Nothing indexed yet — run the generator.</span>'}
          </div>
        </div>
        <div>
          <span class="q">What is this character?</span>
          <div class="links">
            <a href="{link("/inspect/")}">Paste or type anything</a>
          </div>
        </div>
        <div>
          <span class="q">Only have a picture of it?</span>
          <div class="links">
            <a href="{link("/identify/")}">Draw it, or drop an image</a>
          </div>
          <p class="quiet">Shape similarity against real glyph outlines,
             computed in the browser. Not handwriting recognition.</p>
        </div>
      </div>
    </section>

    <section>
      <h2 class="eyebrow">Browse the index</h2>
      <div class="paths">
        <div>
          <span class="q">Scripts</span>
          <div class="links">
{script_links or '          <span class="quiet">None yet.</span>'}
          </div>
          <div><a href="{link("/scripts/")}">All scripts, with counts</a></div>
        </div>
        <div>
          <span class="q">Languages</span>
          <div class="links">
{language_links or '          <span class="quiet">None yet.</span>'}
          </div>
          <div><a href="{link("/languages/")}">All languages, filterable</a></div>
        </div>
        <div>
          <span class="q">Font families</span>
          <div><a href="{link("/fonts/")}">All {total:,} indexed families</a></div>
        </div>
      </div>
    </section>
"""
    return page("Glyph Sleuth", body,
                description="Coverage says a font contains the character. It does not "
                            "say the font will draw it. Glyph Sleuth reports both, with "
                            "the evidence behind both.")


def write(path, markup):
    """One directory per route, so URLs end in a slash and carry no extension."""
    full = os.path.join(OUT_SITE, path.strip("/"), "index.html") if path != "/" \
        else os.path.join(OUT_SITE, "index.html")
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with io.open(full, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(markup)
    return full


def load(name):
    path = os.path.join(ROOT, "web", "data", f"{name}.json")
    if not os.path.exists(path):
        return None
    with io.open(path, encoding="utf-8") as handle:
        return json.load(handle)


def main():
    """Build the site from whatever the generator has produced.

    Without web/data the build stops and says so: an empty site would look like
    a working one, which is worse than an error.
    """
    fonts = load("fonts")
    if not fonts:
        raise SystemExit("No web/data — run: python web/build/gen_index.py --limit 60")

    scripts = (load("scripts") or {}).get("scripts", [])
    languages = (load("languages") or {}).get("languages", [])

    shutil.copyfile(os.path.join(ROOT, "web", "style.css"),
                    os.path.join(OUT_SITE, "style.css"))
    print(f"  wrote {write('/', home(fonts['fonts'], scripts, languages))}")


if __name__ == "__main__":
    main()
