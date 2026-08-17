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
  <script src="{link("/app.js")}" type="module" defer></script>
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


FOUNDRIES = {"google": "Google Fonts", "smc": "Swathanthra Malayalam Computing",
             "sil": "SIL", "rit": "Rachana Institute of Typography", "libre": "Libre"}

# What a script tag means, so "mlm2" is a fact a reader can act on rather than
# four characters. Authored, and only for tags we can say something true about;
# anything else shows the tag alone.
TAG_NOTES = {
    "mlym": "the original Malayalam tag; older shapers look for this one",
    "mlm2": "the v2 Malayalam tag every current shaper prefers",
    "deva": "the original Devanagari tag",
    "dev2": "the v2 Devanagari tag",
    "taml": "the original Tamil tag",
    "tml2": "the v2 Tamil tag",
    "latn": "Latin",
    "DFLT": "the fallback a shaper uses when no script matches",
}


# What to set a specimen in, per script we index deeply. Real words, never
# lorem: മലയാളം is the language's own name, സ്ത്രീ a four-consonant cluster,
# ക്ക a geminate, ൻ a chillu.
SPECIMENS = {
    "Mlym": ((0x0D00, 0x0D7F), "മലയാളം സ്ത്രീ ക്ക ൻ",
             "ൻ്റെ വാക്കുകൾ — Malayalam and Latin."),
}
LATIN_SPECIMEN = ("Handgloves & Quartz", "The quick brown fox jumps over the lazy dog.")


def specimen_text(font):
    """Text this face can actually draw.

    A Malayalam line set in a Latin face is a row of tofu demonstrating
    nothing. The prototype could hardcode Malayalam because it was a Malayalam
    app; an index of 1,885 families cannot.
    """
    for (first, last), line, second in SPECIMENS.values():
        if count_in_range(font.get("ranges") or [], first, last) > 40:
            return line, second
    return LATIN_SPECIMEN


def fact(value, label, href=None):
    """One cell of the facts strip: a mono value over a small caps label.

    Linked when the fact leads somewhere, and the value carries the link
    because that is what the reader is reaching for.
    """
    inner = f'<span class="value">{esc(value)}</span><span class="label">{esc(label)}</span>'
    return (f'        <a class="fact" href="{href}">{inner}</a>' if href
            else f'        <div class="fact">{inner}</div>')


def byline(font):
    """Foundry · designers · licence — the line under the family name."""
    parts = [FOUNDRIES.get(font.get("source"), (font.get("source") or "").upper())]
    if font.get("designers"):
        parts.append(", ".join(font["designers"]))
    if font.get("licence"):
        parts.append(font["licence"])
    return " · ".join(p for p in parts if p)


def font_page(font, blocks):
    name = font["name"]
    measured = font.get("tier") == "measured"
    # Measured coverage and read tables are different facts. Google publishes
    # coverage as metadata and nothing else, so a Google family has real
    # coverage and no idea what tags it declares — and saying "none" there
    # would be the site inventing an answer nobody looked for.
    parsed = bool(font.get("checksum"))
    note, snippet = use_it(font)
    results = (font.get("results") or {}).get("Mlym") or {}

    # The face itself, from wherever it is actually distributed. We serve none.
    face_css = ""
    if font.get("source") == "google":
        face_css = ("https://fonts.googleapis.com/css2?family="
                    + name.replace(" ", "+") + "&display=swap")
    elif font.get("css"):
        face_css = font["css"]

    # The facts strip. Only facts we have — no zeros standing in for things
    # nobody measured.
    facts = []
    if measured:
        mlym = count_in_range(font.get("ranges") or [], 0x0D00, 0x0D7F)
        if mlym:
            facts.append(fact(f"{mlym}/118", "Malayalam codepoints",
                              link("/block/malayalam/")))
        facts.append(fact(f"{count_in_range(font['ranges'], 0, 0x10FFFF):,}",
                          "codepoints in all"))
    if parsed:
        facts.append(fact(len(font.get("tags") or []), "script tags"))
        facts.append(fact(f"{font.get('gsub', 0)} · {font.get('gpos', 0)}",
                          "GSUB · GPOS lookups", font_href(font) + "shaping/"))
    if font.get("faces"):
        facts.append(fact(len(font["faces"]), "weights"))
    if results:
        clean = sum(1 for r in results.values()
                    if (r.get("hb") or {}).get("verdict") == "clean")
        facts.append(fact(f"{clean} of {len(results)}", "sequences clean"))

    head_row = [f'        <h1>{esc(name)}</h1>']
    if face_css:
        # The slider is enhancement: with JS off the specimen still sets at 64px.
        head_row.append('        <label class="size"><span>size</span>'
                        '<input type="range" min="24" max="132" step="4" value="64" '
                        'aria-label="Specimen size">'
                        '<span class="size-value mono">64px</span></label>')
    header = ['    <section class="entity-head">', '      <div class="head-row">'] \
        + head_row + ['      </div>', f'      <p class="byline">{esc(byline(font))}</p>']
    if face_css:
        line, second = specimen_text(font)
        header += [f'      <p class="specimen">{esc(line)}</p>',
                   f'      <p class="specimen-small">{esc(second)}</p>']
    if facts:
        header += ['      <div class="facts">'] + facts + ['      </div>']
    if not measured:
        header.append('      <p class="quiet">This family is <strong>not measured yet</strong>'
                      ' — we have not read its released font file, so it carries no coverage,'
                      ' no declared tags and no shaping verdict.</p>')
    header.append('    </section>')
    body = ["\n".join(header)]

    # Left column: what it covers, and what it declares.
    left = []
    rows = coverage_rows(font, blocks) if measured else []
    if rows:
        left.append('      <h2 class="eyebrow">Coverage, by block</h2>\n'
                    '      <table>\n      <tbody>\n' + "\n".join(rows) + '\n      </tbody>\n'
                    '      </table>\n'
                    '      <p class="quiet rule-top">A script is rarely one block, which is'
                    ' where support quietly dies.</p>')
    if parsed:
        tags = "\n".join(
            f'        <div class="pair"><span class="mono">{esc(tag)}</span>'
            f'<span class="quiet">{esc(TAG_NOTES.get(tag, ""))}</span></div>'
            for tag in font.get("tags") or [])
        left.append('      <h2 class="eyebrow">Declares</h2>\n' + tags +
                    '\n      <p class="quiet rule-top">From the GSUB and GPOS script lists. A'
                    ' face can cover every codepoint of a script and still declare only the'
                    ' tag an older shaper will not look for.</p>')
    elif measured:
        left.append('      <h2 class="eyebrow">Declares</h2>\n'
                    '      <p class="untested">not read</p>\n'
                    '      <p class="quiet">This family\'s coverage comes from the metadata'
                    ' its distributor publishes, which does not include the'
                    ' <span class="mono">GSUB</span> and <span class="mono">GPOS</span>'
                    ' tables. Which tags it declares is unknown here — not absent.</p>')

    # Middle column: the evidence.
    middle = []
    if results:
        evidence = evidence_rows(font)
        heads = "".join(f"<th>{label}</th>" for _key, label in ENGINES)
        shaper = next(iter(results.values())).get("hb") or {}
        middle.append('      <h2 class="eyebrow">Shapes</h2>\n'
                      '      <table class="matrix">\n        <thead><tr><th>Sequence</th>'
                      + heads + '</tr></thead>\n      <tbody>\n' + "\n".join(evidence)
                      + '\n      </tbody>\n      </table>\n'
                      f'      <p class="quiet">HarfBuzz {esc(shaper.get("version", ""))} ·'
                      f' read {esc((font.get("provenance") or {}).get("read", ""))}.'
                      ' Each line above reruns that row against your own copy of the'
                      ' font.</p>\n'
                      f'      <p class="quiet rule-top">{MATRIX_LEGEND}</p>')

    # Right column: taking it away.
    right = ['      <h2 class="eyebrow">Use it</h2>\n'
             f'      <pre class="snippet mono">{snippet}</pre>\n'
             f'      <p class="quiet">{esc(note)}</p>']
    links = []
    if font.get("tables"):
        links.append(f'<a href="{font_href(font)}shaping/">Shaping tables</a>')
    if font.get("url"):
        links.append(f'<a href="{esc(font["url"])}">Download {esc(name)} ↗</a>')
    links.append(f'<a href="{link("/compare/")}">Compare with another family</a>')
    right.append('      <div class="links">' + " ".join(links) + '</div>')

    if parsed and font.get("features"):
        chips = " ".join(f'<a class="chip" href="{link("/feature/" + tag + "/")}">{esc(tag)}</a>'
                         for tag in font["features"])
        right.append('      <h2 class="eyebrow">Implements</h2>\n      <div class="chips">'
                     + chips + '</div>')

    if font.get("axes"):
        axes = "\n".join(
            f'        <div class="pair"><span class="mono">{esc(axis["tag"])}'
            f' {axis["min"]:g}–{axis["max"]:g}</span>'
            f'<span class="quiet">axis, continuous</span></div>'
            for axis in font["axes"])
        right.append('      <h2 class="eyebrow">Variable</h2>\n' + axes)
    elif font.get("faces"):
        right.append('      <h2 class="eyebrow">Weights</h2>\n      <div class="chips">'
                     + " ".join(f'<span class="chip">{esc(face)}</span>'
                                for face in font["faces"]) + '</div>')

    if font.get("provenance"):
        source = font["provenance"]
        right.append('      <h2 class="eyebrow">Provenance</h2>\n'
                     '      <p class="quiet">Read from <span class="mono">'
                     f'{esc(source.get("file"))}</span> on {esc(source.get("read"))}, via '
                     f'<a href="{esc(source.get("release"))}">the release the foundry'
                     ' publishes ↗ — external</a>.<br>'
                     f'<span class="mono break">{esc(font.get("checksum"))}</span></p>')

    columns = [c for c in ("\n".join(left), "\n".join(middle), "\n".join(right)) if c.strip()]
    body.append('    <section class="columns">\n'
                + "\n".join(f'      <div>\n{column}\n      </div>' for column in columns)
                + '\n    </section>')

    head = ""
    if face_css:
        head = (f'  <link rel="stylesheet" href="{esc(face_css)}">\n'
                f'  <style>.specimen, .specimen-small {{ font-family: "{esc(name)}", serif; }}'
                '</style>')
    return page(name, "\n".join(body), kind="font family",
                code=font.get("slug") or slug(name),
                description=f"{name}: what it covers, the OpenType script tags it declares, "
                            f"and how it shapes the sequences the script turns on.",
                extra_head=head)


def verdict_of(font):
    """One word for how a family shapes, across the sequences we ran.

    A family nothing was run against gets "none", not a pass — the whole point
    of the tiers is that untested and clean are different answers.
    """
    results = (font.get("results") or {}).get("Mlym") or {}
    if not results:
        return "none"
    verdicts = {(r.get("hb") or {}).get("verdict") for r in results.values()}
    if "fail" in verdicts:
        return "fail"
    if "caveat" in verdicts:
        return "caveat"
    return "clean"


VERDICT_WORDS = {"clean": "shapes cleanly", "caveat": "shapes with caveats",
                 "fail": "breaks", "none": "not tested"}

MALAYALAM = (0x0D00, 0x0D7F)


def fonts_index(fonts):
    """Every indexed family, in the markup, with the controls to narrow it.

    The list is served whole; filter, facets and sort are enhancement over rows
    that are already there. With JS off this is still the full index, and a
    crawler sees every family rather than an empty shell.
    """
    total, measured = counts(fonts)
    ordered = sorted(fonts, key=lambda f: f["name"].lower())

    malayalam = sum(1 for f in ordered
                    if count_in_range(f.get("ranges") or [], *MALAYALAM) > 40)
    facets = [("all", "all", total),
              ("malayalam", "Malayalam", malayalam),
              ("measured", "measured", measured),
              ("not measured yet", "not measured yet", total - measured),
              ("clean", "shapes cleanly",
               sum(1 for f in ordered if verdict_of(f) == "clean")),
              ("fail", "breaks", sum(1 for f in ordered if verdict_of(f) == "fail"))]
    chips = "\n".join(
        f'        <button class="facet{" on" if key == "all" else ""}" data-facet="{key}"'
        f' data-count="{count}"><span>{esc(label)}</span>'
        f'<span class="count mono">{count:,}</span></button>'
        for key, label, count in facets if count or key == "all")

    sorts = "\n".join(
        f'        <button class="sort{" on" if key == "name" else ""}" data-sort="{key}">'
        f"{esc(label)}</button>"
        for key, label in (("name", "name"), ("verdict", "verdict"),
                           ("coverage", "coverage")))

    rows = []
    for font in ordered:
        covered = count_in_range(font.get("ranges") or [], 0, 0x10FFFF)
        mlym = count_in_range(font.get("ranges") or [], *MALAYALAM)
        verdict = verdict_of(font)
        state = (f'<span class="mono">{covered:,}</span>' if font.get("tier") == "measured"
                 else '<span class="untested">not measured yet</span>')
        shows = (f'<span class="{verdict}">{esc(VERDICT_WORDS[verdict])}</span>'
                 if verdict != "none" else '<span class="untested">not tested</span>')
        rows.append(
            f'      <tr data-name="{esc(font["name"].lower())}"'
            f' data-source="{esc(font.get("source", ""))}"'
            f' data-tier="{esc(font.get("tier", ""))}"'
            f' data-coverage="{covered}" data-malayalam="{mlym}"'
            f' data-verdict="{verdict}">'
            f'<th scope="row"><a href="{font_href(font)}">{esc(font["name"])}</a></th>'
            f'<td class="quiet">{esc(FOUNDRIES.get(font.get("source"), ""))}</td>'
            f'<td class="quiet mono">{esc(font.get("licence") or "—")}</td>'
            f"<td>{state}</td>"
            f"<td>{shows}</td></tr>")

    body = f"""    <section class="entity-head">
      <div class="head-row">
        <h1>Font families</h1>
        <p class="showing quiet">Showing <span data-showing>{total:,}</span> of {total:,}</p>
      </div>
      <p class="quiet">{measured:,} measured from their own released file ·
         {total - measured:,} not measured yet. Verdicts are for the Malayalam exemplar
         sequences; a family that breaks there may be flawless in another script, and one
         marked <em>not tested</em> has simply not been run against them.</p>
    </section>

    <section>
      <div class="controls">
        <input type="search" class="filter" placeholder="filter this list"
               aria-label="Filter families by name">
        <div class="facets">
{chips}
        </div>
      </div>
      <div class="sorts"><span class="eyebrow-inline">sort</span>
{sorts}
      </div>
      <table class="index">
        <thead><tr><th>Family</th><th>Foundry</th><th>Licence</th><th>Codepoints</th>
          <th>Malayalam verdict</th></tr></thead>
      <tbody>
{chr(10).join(rows)}
      </tbody>
      </table>
      <p class="empty quiet" hidden>Nothing matches that. Try a shorter word, or clear the
         filter to see all {total:,} families.</p>
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

    for asset in ("style.css", "app.js"):
        shutil.copyfile(os.path.join(ROOT, "web", asset), os.path.join(OUT_SITE, asset))
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
