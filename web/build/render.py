"""Render the site to static HTML files.

Pages are generated, not assembled in the browser: a reader with JS off, and a
crawler, get the same facts a visitor does. JS is enhancement on top of served
markup — filtering, sliders, the drawing canvas — and never the thing that
produces the content.

The design is the prototype's, recreated in a real stylesheet rather than the
wall of inline styles its template format produced. Tokens, type scale and copy
come from docs/prototype/README.md, which is final.
"""
import hashlib
import html as html_module
import io
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_index as gen

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
    """The stable handle a family's URL is keyed on.

    Unicode letters are kept, not stripped: RIT's families name themselves in
    Malayalam, and reducing those to [a-z0-9] left an empty slug, so the page
    was written to /font//index.html and landed at /font/ — where the next such
    family overwrote it. A site about scripts cannot assume its own font names
    are Latin.
    """
    cleaned = re.sub(r"[^\w]+", "-", str(name).lower(), flags=re.UNICODE).strip("-")
    # A name of pure punctuation still needs a handle to live at.
    return cleaned or "font-" + hashlib.sha1(str(name).encode("utf-8")).hexdigest()[:8]


def unique_slug(name, taken):
    """A slug no other family already has.

    Two families sharing one is how a page silently overwrites another, and how
    a family disappears from a site that claims to index it.
    """
    base = slug(name)
    candidate, n = base, 2
    while candidate in taken and taken[candidate] != name:
        candidate, n = f"{base}-{n}", n + 1
    taken[candidate] = name
    return candidate


def font_href(font):
    """Where a family's page lives. The slug is assigned once, in the build, so
    the link and the file agree even when disambiguation changed it."""
    return link(f"/font/{font.get('slug') or slug(font['name'])}/")


def page(title, body, kind=None, code=None, description=None, extra_head=""):
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
{extra_head}
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


def count_in_range(ranges, first, last):
    total = 0
    for lo, hi in ranges:
        if hi < first:
            continue
        if lo > last:
            break
        total += min(hi, last) - max(lo, first) + 1
    return total


def use_it(font):
    """The CSS to set text in this face, and which of three honest states it is
    in. Mirrors core.js useIt() — the client needs the same answer on Compare.

    Never a fabricated @import for a family that has none, which is what the
    prototype's font page did for every family regardless.
    """
    name = esc(font["name"])
    if font.get("source") == "google":
        slug_name = font["name"].replace(" ", "+")
        return ("Served from Google Fonts.",
                f'&lt;link rel="stylesheet"\n      href="https://fonts.googleapis.com/css2'
                f'?family={slug_name}&amp;display=swap"&gt;\n\n'
                f'font-family: "{name}", sans-serif;')
    if font.get("css"):
        return ("Served from the foundry's own site.",
                f'&lt;link rel="stylesheet" href="{esc(font["css"])}"&gt;\n\n'
                f'font-family: "{name}", sans-serif;')
    file = font["name"].replace(" ", "") + ".woff2"
    return ("This family is not served from a public CDN — download it and host the file "
            "yourself.",
            f'@font-face {{\n  font-family: "{name}";\n  src: url("{file}") format("woff2");\n'
            f'  font-display: swap;\n}}\n\nfont-family: "{name}", sans-serif;')


# The matrix, and why three of its four columns are usually empty. Stated on
# the page so a reader does not read an empty column as a rendering fault.
MATRIX_LEGEND = ("A browser cannot reach DirectWrite or CoreText, so those columns are "
                 "filled from platform test runs and are empty until one exists. Graphite "
                 "reads <em>not applicable</em> for a font carrying no "
                 "<span class=\"mono\">silf</span> table.")

ENGINES = [("hb", "HarfBuzz"), ("dw", "DirectWrite"), ("ct", "CoreText"), ("gr", "Graphite")]


def verdict_cell(value, applicable=True):
    """A verdict, or the honest absence of one.

    Three states, three treatments: a verdict; "not tested", because we have
    not run it; "not applicable", because the question does not arise. A blank
    would read as a pass, which is the one thing it must never do.
    """
    if value is None:
        return ('<span class="untested">not applicable</span>' if not applicable
                else '<span class="untested">not tested</span>')
    verdict = value.get("verdict", "")
    return f'<span class="{esc(verdict)}">{esc(verdict)}</span>'


def coverage_rows(font, blocks):
    """What the face covers, block by block — the blocks it actually touches."""
    rows = []
    for first, last, name in blocks:
        covered = count_in_range(font.get("ranges") or [], first, last)
        if not covered:
            continue
        rows.append(f'      <tr><th scope="row">{esc(name)}</th>'
                    f'<td class="mono">U+{first:04X}–{last:04X}</td>'
                    f'<td class="mono">{covered}/{last - first + 1}</td></tr>')
    return rows


def evidence_rows(font, script="Mlym"):
    rows = []
    for entry in gen.sequences(script):
        result = ((font.get("results") or {}).get(script) or {}).get(entry["id"])
        if not result:
            continue
        cells = []
        for key, _label in ENGINES:
            applicable = not (key == "gr" and not font.get("graphite"))
            cells.append(f"<td>{verdict_cell(result.get(key), applicable)}</td>")
        note = result.get("hb", {}).get("note") or entry.get("note") or ""
        command = result.get("hb", {}).get("command", "")
        rows.append(
            f'      <tr><th scope="row"><span class="specimen-inline">{esc(entry["out"])}</span>'
            f'<span class="mono"> {esc(entry["codes"])}</span></th>'
            + "".join(cells) + "</tr>\n"
            f'      <tr class="detail"><td colspan="5"><code class="mono">{esc(command)}</code>'
            + (f'<div class="quiet">{esc(note)}</div>' if note else "")
            + "</td></tr>")
    return rows


def font_page(font, blocks):
    name = font["name"]
    measured = font.get("tier") == "measured"
    # Measured coverage and read tables are different facts. Google publishes
    # coverage as metadata and nothing else, so a Google family has real
    # coverage and no idea what tags it declares — and saying "none" there
    # would be the site inventing an answer nobody looked for.
    parsed = bool(font.get("checksum"))
    note, snippet = use_it(font)

    facts = [("Foundry", font.get("source", "").upper() or "—"),
             ("Licence", font.get("licence") or "—")]
    if measured:
        facts.append(("Codepoints", f"{count_in_range(font['ranges'], 0, 0x10FFFF):,}"))
    # Lookup counts and a release version only exist if we opened the file.
    if parsed:
        facts += [("Release", font.get("version") or "—"),
                  ("GSUB lookups", font.get("gsub", 0)),
                  ("GPOS lookups", font.get("gpos", 0))]
    facts_html = "\n".join(
        f'        <div><dt>{esc(label)}</dt><dd class="mono">{esc(value)}</dd></div>'
        for label, value in facts)

    # The face itself, from wherever it is actually distributed. We serve none.
    face_css = ""
    if font.get("source") == "google":
        face_css = ("https://fonts.googleapis.com/css2?family="
                    + font["name"].replace(" ", "+") + "&display=swap")
    elif font.get("css"):
        face_css = font["css"]

    body = [f'    <section class="claim">\n      <h1>{esc(name)}</h1>']
    if not measured:
        body.append('      <p class="quiet">This family is indexed but '
                    '<strong>not measured yet</strong> — we have not read its released font '
                    'file, so it carries no coverage, no declared tags and no shaping '
                    'verdict. What is below is what the foundry publishes about it.</p>')
    body.append("    </section>")

    body.append('    <section>\n      <h2 class="eyebrow">Facts</h2>\n'
                f'      <dl class="facts">\n{facts_html}\n      </dl>\n    </section>')

    if face_css:
        body.append('    <section>\n      <h2 class="eyebrow">Specimen</h2>\n'
                    '      <p class="specimen">മലയാളം സ്ത്രീ ൻ്റ</p>\n'
                    '      <p class="quiet">Drawn by your browser from the family\'s own '
                    'distribution, not from us.</p>\n    </section>')

    if measured:
        rows = coverage_rows(font, blocks)
        if rows:
            body.append('    <section>\n      <h2 class="eyebrow">Coverage, by block</h2>\n'
                        '      <table>\n        <thead><tr><th>Block</th><th>Range</th>'
                        '<th>Covered</th></tr></thead>\n      <tbody>\n'
                        + "\n".join(rows) + "\n      </tbody>\n      </table>\n"
                        '      <p class="quiet">A script is rarely one block, which is where '
                        'support quietly dies.</p>\n    </section>')

        tags = font.get("tags") or []
        if parsed:
            told = ('      <p class="mono">' + esc(" · ".join(tags)) + "</p>\n"
                    '      <p class="quiet">From the <span class="mono">GSUB</span> and '
                    '<span class="mono">GPOS</span> script lists. A face can cover every '
                    'codepoint of a script and still declare only the tag an older shaper '
                    'will not look for.</p>\n')
        else:
            # "none" here would be the site asserting the font declares no tags,
            # when nobody opened the file to look. Measured coverage and unread
            # tables are two facts, and blurring them is the exact move this
            # site exists to argue against.
            told = ('      <p class="untested">not read</p>\n'
                    '      <p class="quiet">This family\'s coverage comes from the metadata '
                    'its distributor publishes, which does not include the '
                    '<span class="mono">GSUB</span> and <span class="mono">GPOS</span> '
                    'tables. Which tags it declares is unknown here — not absent.</p>\n')
        body.append('    <section>\n      <h2 class="eyebrow">Script tags declared</h2>\n'
                    + told + "    </section>")

        evidence = evidence_rows(font)
        if evidence:
            heads = "".join(f"<th>{label}</th>" for _key, label in ENGINES)
            body.append('    <section>\n      <h2 class="eyebrow">Evidence</h2>\n'
                        f'      <table class="matrix">\n        <thead><tr><th>Sequence</th>'
                        f"{heads}</tr></thead>\n      <tbody>\n"
                        + "\n".join(evidence) + "\n      </tbody>\n      </table>\n"
                        f'      <p class="quiet">{MATRIX_LEGEND}</p>\n    </section>')

    body.append('    <section>\n      <h2 class="eyebrow">Use it</h2>\n'
                f'      <p class="quiet">{esc(note)}</p>\n'
                f'      <pre class="snippet mono">{snippet}</pre>\n    </section>')

    provenance = font.get("provenance")
    if provenance:
        body.append('    <section>\n      <h2 class="eyebrow">Provenance</h2>\n'
                    f'      <p class="quiet">Read from <span class="mono">'
                    f'{esc(provenance.get("file"))}</span> on {esc(provenance.get("read"))}, '
                    f'via <a href="{esc(provenance.get("release"))}">the release the foundry '
                    f'publishes ↗ — external</a>. Checksum '
                    f'<span class="mono">{esc(font.get("checksum"))}</span>.</p>\n'
                    "    </section>")

    if font.get("url"):
        body.append('    <section>\n      <h2 class="eyebrow">Where it comes from</h2>\n'
                    f'      <p><a href="{esc(font["url"])}">{esc(name)} at its source ↗ '
                    "— external</a></p>\n    </section>")

    # The specimen is set in the family itself, loaded from its own
    # distribution. A page-scoped rule rather than an inline style, so the
    # markup stays free of presentation attributes.
    head = ""
    if face_css:
        head = (f'  <link rel="stylesheet" href="{esc(face_css)}">\n'
                f'  <style>.specimen {{ font-family: "{esc(name)}", serif; }}</style>')
    return page(name, "\n".join(body), kind="font family", code=slug(name),
                description=f"{name}: what it covers, the OpenType script tags it declares, "
                            f"and how it shapes the sequences the script turns on.",
                extra_head=head)


def fonts_index(fonts):
    """Every indexed family, in the markup.

    The list is served whole; filtering and sorting are enhancement on top of
    rows that are already there. With JS off this is still the full index, and
    a crawler sees every family rather than an empty shell.
    """
    total, measured = counts(fonts)
    rows = []
    for font in sorted(fonts, key=lambda f: f["name"].lower()):
        covered = count_in_range(font.get("ranges") or [], 0, 0x10FFFF)
        state = (f'<span class="mono">{covered:,}</span>' if font.get("tier") == "measured"
                 else '<span class="untested">not measured yet</span>')
        tags = " · ".join(font.get("tags") or [])
        rows.append(
            f'      <tr><th scope="row"><a href="{font_href(font)}">{esc(font["name"])}</a></th>'
            f'<td class="quiet">{esc(font.get("source", "").upper())}</td>'
            f'<td class="quiet">{esc(font.get("licence") or "—")}</td>'
            f'<td>{state}</td>'
            f'<td class="mono">{esc(tags)}</td></tr>')

    body = f"""    <section class="claim">
      <h1>Font families</h1>
      <p class="quiet">{total:,} indexed · {measured:,} measured from their own release ·
         {total - measured:,} not measured yet. Codepoints counts what the family covers
         across all of Unicode; the script tags are what it declares, where we have read
         the file.</p>
    </section>

    <section>
      <table class="index">
        <thead><tr><th>Family</th><th>Source</th><th>Licence</th><th>Codepoints</th>
          <th>Script tags</th></tr></thead>
      <tbody>
{chr(10).join(rows)}
      </tbody>
      </table>
    </section>
"""
    return page("Font families", body, kind="index", code=f"{total:,} families",
                description=f"{total:,} freely licensed font families, {measured:,} of them "
                            f"measured from their own released file.")


def lookup_rows(rows):
    """One row per lookup, grouped under its feature.

    A feature is not one lookup: akhn in a Malayalam face is a ligature lookup
    for the chillus, another for the conjuncts, and a chaining context that
    decides when they apply. Collapsing that to a count is how "48 lookups"
    ends up meaning nothing.
    """
    out, seen = [], None
    for row in rows:
        feature = row["feature"]
        head = ""
        if feature != seen:
            head = (f'      <tr class="feature"><th colspan="3" scope="rowgroup">'
                    f'<a href="{link("/feature/" + feature + "/")}">{esc(feature)}</a>'
                    "</th></tr>\n")
            seen = feature
        rules = "".join(
            f'<div class="rule"><span class="mono">{esc(rule["in"])}</span>'
            f' → <span class="mono">{esc(rule["out"])}</span></div>'
            for rule in row["rules"])
        if not rules:
            rules = ('<div class="quiet">This lookup chains other lookups rather than '
                     'mapping glyphs, so there is nothing to list — only when it fires.</div>'
                     if "ontext" in row["type"] else "")
        shown = len(row["rules"])
        more = (f'<div class="quiet">{row["n"] - shown:,} more</div>'
                if row["n"] > shown and shown else "")
        out.append(head +
                   f'      <tr><th scope="row" class="mono">{row["index"]}</th>'
                   f'<td>{esc(row["type"])}<div class="quiet mono">{row["n"]:,} rules</div></td>'
                   f"<td>{rules}{more}</td></tr>")
    return out


def shaping_page(font):
    name = font["name"]
    tables = font.get("tables") or {}
    body = [f'    <section class="claim">\n      <h1>{esc(name)}: shaping tables</h1>\n'
            f'      <p class="quiet">The working behind the verdicts on '
            f'<a href="{font_href(font)}">the family page</a>: which lookups each feature '
            f'runs, of what type, and the rules they carry.</p>\n    </section>']

    if not (tables.get("gsub") or tables.get("gpos")):
        body.append('    <section>\n      <p class="quiet">This family is '
                    '<strong>not measured yet</strong> — its font file has not been read, so '
                    'there are no lookups to show.</p>\n    </section>')
        return page(f"{name} shaping tables", "\n".join(body), kind="shaping tables",
                    code=slug(name))

    for key, title, note in (
            ("gsub", "GSUB — substitution",
             "What the font swaps: conjuncts, chillus, below-base forms."),
            ("gpos", "GPOS — positioning",
             "What the font moves: mark attachment, kerning. Positioning rewrites no "
             "glyphs, so the count is how many attachments the lookup carries — a "
             "mark-to-base with no marks never fires.")):
        rows = lookup_rows(tables.get(key) or [])
        if not rows:
            continue
        body.append(f'    <section>\n      <h2 class="eyebrow">{esc(title)}</h2>\n'
                    '      <table class="lookups">\n'
                    '        <thead><tr><th>Lookup</th><th>Type</th><th>Rules</th></tr></thead>\n'
                    "      <tbody>\n" + "\n".join(rows) + "\n      </tbody>\n      </table>\n"
                    f'      <p class="quiet">{note}</p>\n    </section>')

    return page(f"{name} shaping tables", "\n".join(body), kind="shaping tables",
                code=slug(name),
                description=f"Every GSUB and GPOS lookup {name} runs, by feature, with the "
                            f"rules behind them.")


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

    blocks = (load("blocks") or {}).get("blocks", [])

    shutil.copyfile(os.path.join(ROOT, "web", "style.css"),
                    os.path.join(OUT_SITE, "style.css"))
    write("/", home(fonts["fonts"], scripts, languages))
    print("  wrote home")

    # Assign every slug up front, so a collision is resolved before anything
    # links to it — and so no page can overwrite another's file.
    taken = {}
    for font in fonts["fonts"]:
        font["slug"] = unique_slug(font["name"], taken)

    shaping = 0
    for font in fonts["fonts"]:
        write(f"/font/{font['slug']}/", font_page(font, blocks))
        if font.get("tables"):
            write(f"/font/{font['slug']}/shaping/", shaping_page(font))
            shaping += 1
    write("/fonts/", fonts_index(fonts["fonts"]))
    measured = sum(1 for f in fonts["fonts"] if f.get("tier") == "measured")
    print(f"  wrote {len(fonts['fonts'])} font pages — {measured} measured, "
          f"{len(fonts['fonts']) - measured} not yet; {shaping} with shaping tables")


if __name__ == "__main__":
    main()
