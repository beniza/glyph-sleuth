"""Render the site to static HTML files.

Pages are generated, not assembled in the browser: a reader with JS off, and a
crawler, get the same facts a visitor does. JS is enhancement on top of served
markup — filtering, sliders, the drawing canvas — and never the thing that
produces the content.

The design is the prototype's, recreated in a real stylesheet rather than the
wall of inline styles its template format produced. Tokens, type scale and copy
come from docs/prototype/README.md, which is final.
"""
import collections
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

# Only routes that exist. Inspect, Identify and Regex go back in when they are
# built — a nav item that 404s is the site promising something it does not have,
# on every page.
NAV = [("Home", "/"), ("Scripts", "/scripts/"), ("Languages", "/languages/"),
       ("Fonts", "/fonts/"), ("Compare", "/compare/")]


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
            <a href="{link("/block/basic-latin/")}">Browse a block</a>
            <a href="{link("/scripts/")}">Start from a script</a>
          </div>
          <p class="quiet">A field that reads any notation you paste is not built yet.</p>
        </div>
        <div>
          <span class="q">How does a font build this shape?</span>
          <div class="links">
            <a href="{link("/compare/")}">Compare two families, lookup by lookup</a>
          </div>
          <p class="quiet">Every measured family also lists its lookups and its glyphs,
             including the glyphs no rule can reach.</p>
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
            + trace_block(result.get("hb", {}).get("trace") or [])
            + "</td></tr>")
    return rows


def trace_block(steps):
    """The pipeline, step by step: which lookup changed the run, and to what.

    Folded shut by default — the verdict is the answer, this is the working
    behind it. Only steps that changed something are here; a real font skips
    dozens of lookups per sequence and listing those hides the two lines that
    matter.
    """
    if len(steps) < 2:
        return ""
    lines = []
    for step in steps:
        label = step["step"]
        if step.get("feature"):
            label = (f'<a href="{link("/feature/" + step["feature"] + "/")}">'
                     f'{esc(step["feature"])}</a> · lookup '
                     f'<span class="mono">{step["lookup"]}</span>')
        else:
            label = f'<span class="quiet">{esc(label)}</span>'
        lines.append(f'        <li><div class="step">{label}</div>'
                     f'<div class="run mono">{esc(" ".join(step["glyphs"]))}</div></li>')
    return ('\n      <details class="trace">\n'
            '        <summary>Trace: what each lookup did</summary>\n'
            '        <ol>\n' + "\n".join(lines) + "\n        </ol>\n"
            '        <p class="quiet">Read top to bottom. Glyph names are the font\'s own; '
            'a name changing means a substitution fired, and the order changing means the '
            'shaper moved a glyph.</p>\n'
            "      </details>")


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


# Latin and the punctuation almost every face carries say nothing about what a
# font is *for*, so they get no vote on which script it belongs to.
COMMON_BLOCKS = {
    "Basic Latin", "Latin-1 Supplement", "Latin Extended-A", "Latin Extended-B",
    "Latin Extended Additional", "General Punctuation", "Spacing Modifier Letters",
    "Combining Diacritical Marks", "Currency Symbols", "Letterlike Symbols",
    "Number Forms", "Mathematical Operators", "Geometric Shapes", "Private Use Area",
    "Alphabetic Presentation Forms", "Superscripts and Subscripts", "Arrows",
    "Miscellaneous Symbols", "Dingbats", "Specials", "Halfwidth and Fullwidth Forms",
    "IPA Extensions", "Phonetic Extensions", "Phonetic Extensions Supplement",
    "Combining Diacritical Marks Supplement", "Combining Diacritical Marks Extended",
    "Combining Diacritical Marks for Symbols", "Latin Extended-C", "Latin Extended-D",
    "Latin Extended-E", "Latin Extended-F", "Latin Extended-G", "Modifier Tone Letters",
    "Supplemental Punctuation", "Small Form Variants",
}

# Enough of a block to mean the face is for that script, rather than carrying a
# few of its codepoints incidentally.
SCRIPT_FLOOR = 24


def blocks_covered(font, blocks, floor=SCRIPT_FLOOR):
    """[(name, covered, total)] for the blocks this face meaningfully covers."""
    out = []
    for first, last, name in blocks:
        covered = count_in_range(font.get("ranges") or [], first, last)
        if covered >= min(floor, last - first + 1):
            out.append((name, covered, last - first + 1))
    return out


def dominant_block(font, blocks):
    """The block this face exists for, or None when there isn't one.

    "Largest block" alone is the wrong test: a workhorse carrying a bit of
    everything is for none of them in particular. The block has to actually
    dominate what the face has outside Latin and punctuation.
    """
    spend = [(name, covered, total) for name, covered, total in blocks_covered(font, blocks)
             if name not in COMMON_BLOCKS]
    if not spend:
        return None
    total_outside = sum(covered for _name, covered, _total in spend)
    best = max(spend, key=lambda row: row[1])
    return best if best[1] >= total_outside * 0.5 else None


# What to set a specimen in, per script. Real words, never lorem. The site is
# not about any one of these: the face's own dominant block picks the line.
SPECIMENS = {
    "Malayalam": ("മലയാളം സ്ത്രീ ക്ക ൻ", "ൻ്റെ വാക്കുകൾ — Malayalam and Latin."),
    "Devanagari": ("देवनागरी हिन्दी क्ष", "अक्षर — Devanagari and Latin."),
    "Arabic": ("العربية كتابة لا", "الحروف — Arabic and Latin."),
    "Tamil": ("தமிழ் எழுத்து ஸ்ரீ", "சொற்கள் — Tamil and Latin."),
    "Bengali": ("বাংলা ক্ষ লিপি", "শব্দ — Bengali and Latin."),
    "Greek and Coptic": ("Ελληνικά γράμμα", "λέξεις — Greek and Latin."),
    "Cyrillic": ("Кириллица буква", "слова — Cyrillic and Latin."),
    "Hebrew": ("עברית אות כתב", "מילים — Hebrew and Latin."),
    "Thai": ("ไทย อักษร", "คำ — Thai and Latin."),
    "Ethiopic": ("ግዕዝ ፊደል", "ቃላት — Ethiopic and Latin."),
}
# Blocks whose codepoints get a page each. Bounded on purpose: a page per
# assigned codepoint in Unicode is over a million files, and most would say
# nothing beyond a name. These are the ones the rest of the site links into.
# How many cells a block chart draws before it says what it dropped.
CHART_LIMIT = 256

# Which blocks get a page per codepoint: every block small enough to be about a
# writing system rather than a repertoire. Eleven blocks hold 110,233 of
# Unicode's 143,041 assigned codepoints — CJK Unified Ideographs with its nine
# extensions, and Hangul Syllables — and a page each for those would be a
# hundred thousand files saying little beyond a name. Everything under this
# bound gets one, which is 32,808 pages and covers every script whose shaping is
# worth inspecting. Tamil's chart cells were not links until this replaced a
# hand-picked list of three blocks.
CHAR_PAGE_MAX_BLOCK = 1000

LATIN_SPECIMEN = ("Handgloves & Quartz", "The quick brown fox jumps over the lazy dog.")


def specimen_text(font, blocks=()):
    """Text this face can actually draw.

    A line of Malayalam set in a Latin face is a row of tofu demonstrating
    nothing — and so is a line of Latin standing in for a Devanagari face. The
    font's own dominant block chooses.
    """
    dominant = dominant_block(font, blocks) if blocks else None
    if dominant and dominant[0] in SPECIMENS:
        return SPECIMENS[dominant[0]]
    return LATIN_SPECIMEN


def face_css_of(font):
    """Where the browser can get this face — Google's CDN, or the foundry's own
    stylesheet. Never a URL of ours; we serve no font files."""
    if font.get("source") == "google":
        return ("https://fonts.googleapis.com/css2?family="
                + font["name"].replace(" ", "+") + "&display=swap")
    return font.get("css") or ""


def face_head(font, name):
    """Load the family so the page can set specimens and glyphs in it."""
    css = face_css_of(font)
    if not css:
        return ""
    return (f'  <link rel="stylesheet" href="{esc(css)}">\n'
            f'  <style>.specimen, .specimen-small, .glyph '
            f'{{ font-family: "{esc(name)}", serif; }}</style>')


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
    # Whatever scripts we ran sequences against for this face — the site has
    # no default script, so this follows the data rather than a constant.
    results = {script: rows for script, rows in (font.get("results") or {}).items() if rows}

    # The face itself, from wherever it is actually distributed. We serve none.
    face_css = face_css_of(font)

    # The facts strip. Only facts we have — no zeros standing in for things
    # nobody measured.
    facts = []
    if measured:
        # The script the face is *for*, whichever that is — not one script the
        # site happens to know best, measured against every family.
        dominant = dominant_block(font, blocks)
        if dominant:
            name_of, covered, total_of = dominant
            facts.append(fact(f"{covered}/{total_of}", f"{name_of} codepoints",
                              link(f"/block/{slug(name_of)}/")))
        facts.append(fact(f"{count_in_range(font['ranges'], 0, 0x10FFFF):,}",
                          "codepoints in all"))
    if parsed:
        facts.append(fact(len(font.get("tags") or []), "script tags"))
        facts.append(fact(f"{font.get('gsub', 0)} · {font.get('gpos', 0)}",
                          "GSUB · GPOS lookups", font_href(font) + "lookups/"))
    if font.get("faces"):
        facts.append(fact(len(font["faces"]), "weights"))
    rows_all = [row for rows in results.values() for row in rows.values()]
    if rows_all:
        clean = sum(1 for r in rows_all if (r.get("hb") or {}).get("verdict") == "clean")
        facts.append(fact(f"{clean} of {len(rows_all)}", "sequences clean"))

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
        line, second = specimen_text(font, blocks)
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
    for script, script_rows in sorted(results.items()):
        evidence = evidence_rows(font, script)
        if not evidence:
            continue
        heads = "".join(f"<th>{label}</th>" for _key, label in ENGINES)
        shaper = next(iter(script_rows.values())).get("hb") or {}
        middle.append(f'      <h2 class="eyebrow">Shapes · {esc(script)}</h2>\n'
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
        links.append(f'<a href="{font_href(font)}lookups/">Lookups</a>')
    if font.get("glyphs"):
        links.append(f'<a href="{font_href(font)}glyphs/">Glyphs</a>')
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

    # The evidence gets the full width. It was in a third of it, beside two
    # other columns, and a matrix of four engine columns plus an hb-shape line
    # does not fit in 300px — the verdicts wrapped into each other and the
    # command ran under the panel to its right.
    if middle:
        body.append('    <section class="evidence">\n' + "\n".join(middle) + "\n    </section>")

    columns = [c for c in ("\n".join(left), "\n".join(right)) if c.strip()]
    if columns:
        body.append('    <section class="split">\n'
                    + "\n".join(f'      <div>\n{column}\n      </div>' for column in columns)
                    + '\n    </section>')

    head = face_head(font, name)
    return page(name, "\n".join(body), kind="font family",
                code=font.get("slug") or slug(name),
                description=f"{name}: what it covers, the OpenType script tags it declares, "
                            f"and how it shapes the sequences the script turns on.",
                extra_head=head)


def verdict_of(font):
    """One word for how a family shapes, across every sequence we ran on it.

    A family nothing was run against gets "none", not a pass — untested and
    clean are different answers, which is the argument the site is making.
    """
    rows = [row for rows in (font.get("results") or {}).values() for row in rows.values()]
    if not rows:
        return "none"
    verdicts = {(row.get("hb") or {}).get("verdict") for row in rows}
    if "fail" in verdicts:
        return "fail"
    if "caveat" in verdicts:
        return "caveat"
    return "clean"


VERDICT_WORDS = {"clean": "shapes cleanly", "caveat": "shapes with caveats",
                 "fail": "breaks", "none": "not tested"}


def fonts_index(fonts, blocks=()):
    """Every indexed family, in the markup, with the controls to narrow it.

    The filters are the questions an engineer actually arrives with — which
    families declare `dev2`, which cover Arabic, which have been measured at
    all — not a single script's lens over everything.
    """
    total, measured = counts(fonts)
    ordered = sorted(fonts, key=lambda f: f["name"].lower())

    # Only tags and blocks something in the index actually has: an empty filter
    # option is a dead end wearing the clothes of an answer.
    tag_counts, block_counts = collections.Counter(), collections.Counter()
    covered_by = {}
    for font in ordered:
        tag_counts.update(font.get("tags") or [])
        names = [name for name, _covered, _total in blocks_covered(font, blocks)
                 if name not in COMMON_BLOCKS]
        covered_by[id(font)] = names
        block_counts.update(names)

    def options(name, label, counted):
        rows = "\n".join(
            f'          <option value="{esc(slug(key) if name == "block" else key)}">'
            f"{esc(key)} ({count:,})</option>"
            for key, count in sorted(counted.items()))
        return (f'        <label class="pick"><span>{esc(label)}</span>\n'
                f'          <select name="{name}">\n'
                f'          <option value="">any</option>\n{rows}\n'
                "          </select></label>")

    facets = [("all", "all", total),
              ("measured", "measured", measured),
              ("not measured yet", "not measured yet", total - measured),
              ("clean", "shapes cleanly", sum(1 for f in ordered if verdict_of(f) == "clean")),
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
        verdict = verdict_of(font)
        tags = font.get("tags") or []
        names = covered_by[id(font)]
        dominant = dominant_block(font, blocks) if blocks else None
        state = (f'<span class="mono">{covered:,}</span>' if font.get("tier") == "measured"
                 else '<span class="untested">not measured yet</span>')
        shows = (f'<span class="{verdict}">{esc(VERDICT_WORDS[verdict])}</span>'
                 if verdict != "none" else '<span class="untested">not tested</span>')
        rows.append(
            f'      <tr data-name="{esc(font["name"].lower())}"'
            f' data-source="{esc(font.get("source", ""))}"'
            f' data-tier="{esc(font.get("tier", ""))}"'
            f' data-coverage="{covered}"'
            f' data-tags="{esc(" ".join(tags))}"'
            f' data-blocks="{esc(" ".join(slug(n) for n in names))}"'
            f' data-verdict="{verdict}">'
            f'<th scope="row"><a href="{font_href(font)}">{esc(font["name"])}</a></th>'
            f'<td class="quiet">{esc(FOUNDRIES.get(font.get("source"), ""))}</td>'
            f'<td class="quiet mono">{esc(font.get("licence") or "—")}</td>'
            f'<td class="quiet">{esc(dominant[0] if dominant else "")}</td>'
            f"<td>{state}</td>"
            f'<td class="mono">{esc(" ".join(tags))}</td>'
            f"<td>{shows}</td></tr>")

    body = f"""    <section class="entity-head">
      <div class="head-row">
        <h1>Font families</h1>
        <p class="showing quiet">Showing <span data-showing>{total:,}</span> of {total:,}</p>
      </div>
      <p class="quiet">{measured:,} measured from their own released file ·
         {total - measured:,} not measured yet. Filter by the OpenType script tag a family
         declares, or by the Unicode block it covers — a family may cover a block and still
         not declare the tag a shaper looks for, which is the gap worth finding.</p>
    </section>

    <section>
      <div class="controls">
        <input type="search" class="filter" placeholder="filter this list"
               aria-label="Filter families by name">
{options("tag", "script tag", tag_counts)}
{options("block", "covers block", block_counts)}
      </div>
      <div class="controls">
        <div class="facets">
{chips}
        </div>
        <div class="sorts"><span class="eyebrow-inline">sort</span>
{sorts}
        </div>
      </div>
      <table class="index">
        <thead><tr><th>Family</th><th>Foundry</th><th>Licence</th><th>Mainly</th>
          <th>Codepoints</th><th>Declares</th><th>Shaping</th></tr></thead>
      <tbody>
{chr(10).join(rows)}
      </tbody>
      </table>
      <p class="empty quiet" hidden>Nothing matches that. Try a shorter word, or clear the
         filters to see all {total:,} families.</p>
    </section>
"""
    return page("Font families", body, kind="index", code=f"{total:,} families",
                description=f"{total:,} freely licensed font families, {measured:,} of them "
                            f"measured from their own released file. Filter by declared "
                            f"OpenType script tag or by the Unicode block they cover.")


def rule_row(rule):
    """One rule, in the script first and the font's glyph names second.

    Glyph names are the font developer's private business: nobody should have to
    learn that Manjari calls chillu n `n1cil` to read what a lookup does. Where
    the cmap reaches a glyph we show the character; a ligature glyph has no
    codepoint of its own, so the output is drawn by letting the browser shape
    the input — which is the same substitution, performed rather than described.
    """
    into = (f'<span class="glyph">{esc(rule["outText"])}</span>' if rule.get("outText")
            else (f'<span class="glyph" data-shaped>{esc(rule["inText"])}</span>'
                  if rule.get("inText") else ""))
    shown = ""
    if rule.get("inText"):
        shown = (f'<span class="glyph">{esc(rule["inText"])}</span>'
                 f'<span class="arrow">→</span>{into}')
    return (f'<div class="rule">{shown}'
            f'<span class="names mono">{esc(rule["in"])} → {esc(rule["out"])}</span></div>')


def glyph_cell(glyph, chars_built=()):
    """The glyph itself, drawn rather than named.

    An encoded glyph is set from its codepoint. A glyph with no codepoint —
    every conjunct, half form and positional variant — is drawn by setting the
    input that produces it *and turning on the feature that does the
    producing*: without the feature the browser draws the input, not the glyph
    the rule builds. That is the only way to show it without publishing the
    outlines, and it has the advantage of being the shaper actually doing the
    substitution rather than a picture of one.
    """
    if glyph.get("cp") is not None:
        drawn = f'<span class="glyph">{esc(chr(glyph["cp"]))}</span>'
        # The glyph is what a reader points at, so it carries the link to the
        # character — where every other family's drawing of it is.
        return (f'<a href="{link(f"/char/{glyph["cp"]:04X}/")}">{drawn}</a>'
                if glyph["cp"] in chars_built else drawn)
    recipe = glyph.get("from")
    if recipe and recipe["features"]:
        features = " ".join(f"ff-{esc(tag)}" for tag in recipe["features"])
        return (f'<span class="glyph {features}" '
                f'title="{esc(recipe["text"])} with {esc(", ".join(recipe["features"]))} on">'
                f'{esc(recipe["text"])}</span>')
    if recipe:
        # Built by a lookup a chaining context calls, so no feature switch
        # produces it on its own. Drawing the input here would show the
        # unsubstituted characters as though they were the result.
        return (f'<span class="faint" title="built from {esc(recipe["text"])} by a lookup a '
                f'chaining context calls, so it cannot be produced on its own">'
                f'needs context</span>')
    # A contextual lookup only fires inside a wider run, so some glyphs cannot
    # be produced in isolation. Saying so beats an empty cell.
    return '<span class="faint" title="cannot be produced in isolation">not in isolation</span>'


def feature_styles(inventory):
    """One class per feature that produces a glyph, so the cells need no inline
    styles: .ff-pstf turns pstf on for that span alone."""
    tags = sorted({tag for glyph in inventory
                   for tag in (glyph.get("from") or {}).get("features", [])})
    rules = "\n".join(
        f'    .ff-{tag} {{ font-feature-settings: "{tag}" 1; }}' for tag in tags)
    return f"  <style>\n{rules}\n  </style>" if rules else ""


def glyphs_page(font, chars_built=()):
    """Every glyph in the family, and what the layout does with each one."""
    inventory = font.get("glyphs") or []
    name = font["name"]

    if not inventory:
        body = (f'    <section class="entity-head">\n      <h1>{esc(name)}: glyphs</h1>\n'
                '      <p class="quiet">This family is <strong>not measured yet</strong> — '
                'its font file has not been read, so there is no glyph list to show.</p>\n'
                "    </section>")
        return page(f"{name} glyphs", body, kind="glyphs",
                    code=font.get("slug") or slug(name))

    encoded = [g for g in inventory if g["cp"] is not None]
    built = [g for g in inventory if g["cp"] is None and (g["produced"] or g["consumed"])]
    orphans = [g for g in inventory if g["orphan"]]

    rows = []
    for glyph in inventory:
        if glyph["cp"] is not None:
            code = f'U+{glyph["cp"]:04X}'
            reach = (f'<a href="{link(f"/char/{glyph["cp"]:04X}/")}" class="mono">{code}</a>'
                     if glyph["cp"] in chars_built else f'<span class="mono">{code}</span>')
            state = "encoded"
        elif glyph["produced"]:
            reach = '<span class="quiet">built by a rule</span>'
            state = "built"
        else:
            reach = '<span class="fail">unreachable</span>'
            state = "orphan"
        chips = " ".join(
            f'<a class="chip" href="{link("/feature/" + tag + "/")}">{esc(tag)}</a>'
            for tag in glyph["produced"])
        used = " ".join(
            f'<a class="chip quiet-chip" href="{link("/feature/" + tag + "/")}">{esc(tag)}</a>'
            for tag in glyph["consumed"])
        rows.append(
            f'      <tr data-name="{esc(glyph["name"].lower())}" data-state="{state}">'
            f'<td>{glyph_cell(glyph, chars_built)}</td>'
            f'<th scope="row" class="mono">{esc(glyph["name"])}</th>'
            f"<td>{reach}</td>"
            f'<td><div class="chips">{chips}</div></td>'
            f'<td><div class="chips">{used}</div></td></tr>')

    facets = [("all", "all", len(inventory)),
              ("encoded", "encoded", len(encoded)),
              ("built", "built by a rule", len(built)),
              ("orphan", "unreachable", len(orphans))]
    chips_html = "\n".join(
        f'        <button class="facet{" on" if key == "all" else ""}" data-facet="{key}"'
        f' data-count="{count}"><span>{esc(label)}</span>'
        f'<span class="count mono">{count:,}</span></button>'
        for key, label, count in facets)

    body = f"""    <section class="entity-head">
      <div class="head-row">
        <h1>{esc(name)}: glyphs</h1>
        <p class="showing quiet">Showing <span data-showing>{len(inventory):,}</span>
           of {len(inventory):,}</p>
      </div>
      <p class="quiet">A font is not its codepoints. {len(built):,} of these
         {len(inventory):,} glyphs have no codepoint at all — they are the conjuncts, half
         forms and positional variants the layout rules build — and
         {len(orphans):,} are reachable by nothing: no codepoint, and no rule that produces
         them. However well drawn, those cannot appear in text.</p>
      <p class="quiet">Glyphs are drawn by your browser from the family's own
         distribution. An unencoded glyph is shown by setting the input that produces it,
         so what you see is the shaper doing the substitution rather than a picture of it.</p>
    </section>

    <section>
      <div class="controls">
        <input type="search" class="filter" placeholder="filter by glyph name"
               aria-label="Filter glyphs by name">
        <div class="facets">
{chips_html}
        </div>
      </div>
      <table class="index glyph-table">
        <thead><tr><th>Glyph</th><th>Name</th><th>Reached by</th><th>Produced by</th>
          <th>Consumed by</th></tr></thead>
      <tbody>
{chr(10).join(rows)}
      </tbody>
      </table>
      <p class="empty quiet" hidden>No glyph matches that name.</p>
    </section>
"""
    return page(f"{name} glyphs", body, kind="glyphs",
                code=font.get("slug") or slug(name),
                description=f"Every glyph in {name}: which are encoded, which the layout "
                            f"rules build, and which nothing can reach.",
                extra_head=face_head(font, name) + "\n" + feature_styles(inventory))


def font_data(font):
    """What Compare needs about one family, as a small file the browser fetches.

    Per-feature rule counts rather than a total, because that is the comparison
    that matters: two families both declaring `akhn` can differ by fifty rules
    inside it, and "48 lookups against 62" says nothing about which.

    The glyph inventory is deliberately left out — a thousand rows per family,
    and the diff never reads it.
    """
    features = {}
    for table in ("gsub", "gpos"):
        for row in (font.get("tables") or {}).get(table, []):
            entry = features.setdefault(row["feature"], {"gsub": 0, "gpos": 0, "lookups": 0,
                                                         "types": []})
            entry[table] += row["n"]
            entry["lookups"] += 1
            if row["type"] not in entry["types"]:
                entry["types"].append(row["type"])

    verdicts = {}
    for script, rows in (font.get("results") or {}).items():
        verdicts[script] = {sid: (row.get("hb") or {}).get("verdict")
                            for sid, row in rows.items()}

    return {
        "name": font["name"],
        "slug": font.get("slug") or slug(font["name"]),
        "source": font.get("source", ""),
        "licence": font.get("licence", ""),
        "version": font.get("version", ""),
        "tags": font.get("tags") or [],
        "gsub": font.get("gsub", 0),
        "gpos": font.get("gpos", 0),
        "features": features,
        "verdicts": verdicts,
        "ranges": font.get("ranges") or [],
    }


def compare_page(fonts):
    """The one page that cannot be generated per pair.

    1,878 measured families are 1.7 million pairs, so this ships as a shell and
    fetches the two families a reader picks. Every family is in the markup; the
    diff is the only part that needs JS.
    """
    comparable = sorted((f for f in fonts if f.get("tables")),
                        key=lambda f: f["name"].lower())
    options = "\n".join(
        f'          <option value="{esc(f.get("slug") or slug(f["name"]))}">'
        f'{esc(f["name"])}</option>' for f in comparable)

    # No default pair. HANDOFF rules out guessing one, and a comparison nobody
    # asked for is a claim that those two families are the interesting ones.
    body = f"""    <section class="entity-head">
      <h1>Compare</h1>
      <p class="quiet">Two families, side by side, down to the lookup: which OpenType
         features each declares, how many rules each feature carries, and where the two
         disagree on a sequence. Differences are what is emphasised — there is no score,
         because two families with identical verdicts still differ in ways this table
         cannot see.</p>
    </section>

    <section>
      <div class="controls">
        <label class="pick"><span>first</span>
          <select name="a" aria-label="First family">
          <option value="">Pick two families</option>
{options}
          </select></label>
        <label class="pick"><span>second</span>
          <select name="b" aria-label="Second family">
          <option value="">Pick two families</option>
{options}
          </select></label>
        <button class="facet" id="swap" type="button"><span>swap</span></button>
      </div>
      <p class="quiet" id="compare-hint">Pick two families to see the difference.
         {len(comparable):,} families have had their lookup tables read.</p>
      <div id="compare-out"></div>
    </section>
"""
    return page("Compare", body, kind="compare",
                code=f"{len(comparable):,} comparable",
                description="Two font families compared down to the OpenType lookup: "
                            "features declared, rules per feature, and where their "
                            "shaping verdicts disagree.")


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
        rules = "".join(rule_row(rule) for rule in row["rules"])
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


def lookups_page(font):
    name = font["name"]
    tables = font.get("tables") or {}
    body = [f'    <section class="claim">\n      <h1>{esc(name)}: lookups</h1>\n'
            f'      <p class="quiet">The working behind the verdicts on '
            f'<a href="{font_href(font)}">the family page</a>: which lookups each feature '
            f'runs, of what type, and the rules they carry.</p>\n    </section>']

    if not (tables.get("gsub") or tables.get("gpos")):
        body.append('    <section>\n      <p class="quiet">This family is '
                    '<strong>not measured yet</strong> — its font file has not been read, so '
                    'there are no lookups to show.</p>\n    </section>')
        return page(f"{name} lookups", "\n".join(body), kind="lookups",
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

    return page(f"{name} lookups", "\n".join(body), kind="lookups",
                code=slug(name),
                description=f"Every GSUB and GPOS lookup {name} runs, by feature, with the "
                            f"rules behind them.")


# How many faces one page will load to draw a character in. A grid of nine
# hundred webfonts is not a page; what is dropped is stated, as everywhere else.
DRAWN_LIMIT = 24


def face_styles(fonts):
    """Load these families, and give each a class that sets it.

    Google's CDN takes every family in one request, which is the difference
    between one stylesheet and twenty-four. Foundry families each bring their
    own. We serve none of it.
    """
    google = [font["name"].replace(" ", "+") for font in fonts
              if font.get("source") == "google"]
    links = []
    if google:
        query = "&".join(f"family={name}" for name in google)
        links.append('  <link rel="stylesheet" '
                     f'href="https://fonts.googleapis.com/css2?{query}&display=swap">')
    for font in fonts:
        if font.get("source") != "google" and font.get("css"):
            links.append(f'  <link rel="stylesheet" href="{esc(font["css"])}">')

    rules = "\n".join(
        f'    .f-{esc(font.get("slug") or slug(font["name"]))} '
        f'{{ font-family: "{esc(font["name"])}", serif; }}'
        for font in fonts)
    return "\n".join(links) + "\n  <style>\n" + rules + "\n  </style>"


# ------------------------------------------------------------------ features

# The registered names, so a tag nothing is authored about still says what it
# is. From the OpenType feature registry — a name, not a claim about the font.
REGISTERED = {
    "aalt": "Access all alternates", "abvf": "Above-base forms",
    "abvm": "Above-base mark positioning", "abvs": "Above-base substitutions",
    "akhn": "Akhand ligatures", "blwf": "Below-base forms",
    "blwm": "Below-base mark positioning", "blws": "Below-base substitutions",
    "calt": "Contextual alternates", "case": "Case-sensitive forms",
    "ccmp": "Glyph composition and decomposition", "cjct": "Conjunct forms",
    "clig": "Contextual ligatures", "cswh": "Contextual swash",
    "dist": "Distances", "dlig": "Discretionary ligatures", "dnom": "Denominators",
    "fina": "Terminal forms", "frac": "Fractions", "half": "Half forms",
    "haln": "Halant forms", "hlig": "Historical ligatures", "init": "Initial forms",
    "isol": "Isolated forms", "kern": "Kerning", "liga": "Standard ligatures",
    "lnum": "Lining figures", "locl": "Localised forms", "mark": "Mark positioning",
    "medi": "Medial forms", "mkmk": "Mark to mark positioning", "nukt": "Nukta forms",
    "numr": "Numerators", "onum": "Oldstyle figures", "ordn": "Ordinals",
    "pnum": "Proportional figures", "pref": "Pre-base forms",
    "pres": "Pre-base substitutions", "pstf": "Post-base forms",
    "psts": "Post-base substitutions", "rkrf": "Rakar forms", "rlig": "Required ligatures",
    "rphf": "Reph form", "salt": "Stylistic alternates", "sinf": "Scientific inferiors",
    "smcp": "Small capitals", "ss01": "Stylistic set 1", "subs": "Subscript",
    "sups": "Superscript", "swsh": "Swash", "titl": "Titling",
    "tnum": "Tabular figures", "vatu": "Vattu variants", "zero": "Slashed zero",
}


def feature_content():
    path = os.path.join(ROOT, "web", "content", "features.json")
    with io.open(path, encoding="utf-8") as handle:
        return json.load(handle)


def feature_page(tag, content, fonts):
    """One OpenType feature: what it does, where it runs, who implements it."""
    detail = (content.get("features") or {}).get(tag) or {}
    stages = content.get("stages") or []
    name = detail.get("name") or REGISTERED.get(tag) or "Unregistered feature"

    # Every family that runs this feature, with how much of it it runs. The
    # count is the interesting part: two families both "implementing" pres can
    # differ by sixty rules.
    implementers = []
    for font in fonts:
        rows = [row for table in ("gsub", "gpos")
                for row in (font.get("tables") or {}).get(table, [])
                if row["feature"] == tag]
        if rows:
            implementers.append((font, sum(row["n"] for row in rows), len(rows)))
    implementers.sort(key=lambda row: (-row[1], row[0]["name"].lower()))

    prose = "\n".join(f'      <p>{esc(paragraph)}</p>' for paragraph in detail.get("prose", []))
    if not prose:
        prose = ('      <p class="quiet">No write-up yet. The name above is the registered '
                 'one from the OpenType feature registry; what this feature does in a '
                 'particular font is the rule list on that font\'s lookups page.</p>')

    pipeline = ""
    if tag in stages:
        cells = "\n".join(
            f'        <li class="{"on" if stage == tag else ""}">'
            + (f'<a href="{link("/feature/" + stage + "/")}">{esc(stage)}</a>'
               if stage != tag else f'<span class="mono">{esc(stage)}</span>')
            + "</li>"
            for stage in stages)
        pipeline = ('    <section>\n      <h2 class="eyebrow">Where it runs</h2>\n'
                    f'      <ol class="pipeline">\n{cells}\n      </ol>\n'
                    '      <p class="quiet">The order a shaper applies these in. Position '
                    'matters: a feature cannot undo what an earlier one did, which is why '
                    'an error early in the list is the stubborn kind.</p>\n    </section>')

    examples = ""
    if detail.get("examples"):
        rows = "\n".join(
            f'      <tr><th scope="row" class="mono">{esc(ex["codes"])}</th>'
            f'<td><span class="glyph">{esc(ex["on"])}</span></td>'
            f'<td><span class="glyph">{esc(ex["off"])}</span></td>'
            f'<td class="quiet">{esc(ex["note"])}</td></tr>'
            for ex in detail["examples"])
        examples = ('    <section>\n      <h2 class="eyebrow">With it, and without</h2>\n'
                    '      <table>\n        <thead><tr><th>Sequence</th><th>Applied</th>'
                    '<th>Not applied</th><th></th></tr></thead>\n'
                    f'      <tbody>\n{rows}\n      </tbody>\n      </table>\n'
                    '      <p class="quiet">Both columns are set in your browser\'s own '
                    'fallback face for the script, so they show what the sequence means '
                    'rather than how any one family draws it.</p>\n    </section>')

    listed = "\n".join(
        f'      <tr><th scope="row"><a href="{font_href(font)}lookups/">'
        f'{esc(font["name"])}</a></th>'
        f'<td class="mono">{rules:,}</td><td class="mono">{lookups}</td>'
        f'<td class="quiet">{esc(FOUNDRIES.get(font.get("source"), ""))}</td></tr>'
        for font, rules, lookups in implementers[:200])
    who = ('    <section>\n      <h2 class="eyebrow">Implemented by</h2>\n'
           '      <table class="index">\n        <thead><tr><th>Family</th><th>Rules</th>'
           '<th>Lookups</th><th>Foundry</th></tr></thead>\n'
           f'      <tbody>\n{listed}\n      </tbody>\n      </table>\n'
           f'      <p class="quiet">{len(implementers):,} of the families whose tables we '
           f'have read run this feature'
           + (", the 200 largest shown." if len(implementers) > 200 else ".")
           + ' Rule counts are what the font actually carries, not what it declares.</p>\n'
           "    </section>") if implementers else (
        '    <section>\n      <h2 class="eyebrow">Implemented by</h2>\n'
        '      <p class="quiet">None of the families whose tables we have read run this '
        'feature.</p>\n    </section>')

    body = f"""    <section class="entity-head">
      <h1>{esc(tag)}</h1>
      <p class="byline">{esc(name)}
         {"· " + esc(detail["table"]) if detail.get("table") else ""}</p>
    </section>

    <section>
{prose}
    </section>

{pipeline}
{examples}
{who}
"""
    return page(f"{tag} — {name}", body, kind="opentype feature", code=tag,
                description=f"{tag}, {name}: what the feature does, where it runs in the "
                            f"shaping order, and which families implement it.")


# --------------------------------------------------------------- characters

def assigned_by_block(blocks):
    """{block name: [assigned codepoints]} — what is actually encoded.

    Unassigned codepoints get no page and no chart cell: nothing can cover them,
    and a coverage figure counting them would be wrong.
    """
    import unicodedata

    out = {}
    for first, last, name in blocks:
        found = []
        for cp in range(first, last + 1):
            try:
                unicodedata.name(chr(cp))
            except ValueError:
                continue
            found.append(cp)
        out[name] = found
    return out


def coverage_index(fonts, wanted):
    """{codepoint: [families covering it]} for the codepoints that get a page.

    Walked once per font rather than once per page: the naive version asks every
    family about every codepoint, which is 33,000 times 1,885 range walks.
    """
    index = collections.defaultdict(list)
    for font in fonts:
        for first, last in font.get("ranges") or []:
            for cp in range(first, last + 1):
                if cp in wanted:
                    index[cp].append(font)
    return index


def char_page(cp, name, block, covering, chars_built):
    """One codepoint: what it is, and how each indexed family draws it."""
    import unicodedata

    ch = chr(cp)
    category = unicodedata.category(ch)

    facts = [fact(f"U+{cp:04X}", "codepoint"),
             fact(category, "general category"),
             fact(f"{len(covering):,}", "families with it")]
    if block:
        facts.append(fact(block[2], "block", link(f"/block/{slug(block[2])}/")))

    encodings = {
        "UTF-8": " ".join(f"{b:02X}" for b in ch.encode("utf-8")),
        "UTF-16": " ".join(f"{b:04X}" for b in
                           ([cp] if cp <= 0xFFFF else
                            [0xD800 + ((cp - 0x10000) >> 10), 0xDC00 + ((cp - 0x10000) & 0x3FF)])),
        "HTML": f"&amp;#{cp};",
        "CSS": f"\\{cp:04x}",
        "Python": f"\\u{cp:04x}" if cp <= 0xFFFF else f"\\U{cp:08x}",
    }
    rows = "\n".join(
        f'        <div class="pair"><span class="quiet">{esc(label)}</span>'
        f'<span class="mono">{value}</span></div>'
        for label, value in encodings.items())

    neighbours = []
    for other in (cp - 1, cp + 1):
        if other in chars_built:
            neighbours.append(f'<a href="{link(f"/char/{other:04X}/")}">U+{other:04X}</a>')

    # Drawn, not just named. Two faces can both cover a codepoint and draw it
    # quite differently, and that difference is what a reader came to see.
    ordered = sorted(covering, key=lambda f: (f.get("tier") != "measured",
                                              f["name"].lower()))
    drawn = ordered[:DRAWN_LIMIT]
    tiles = "\n".join(
        f'        <a class="draws" href="{font_href(font)}">'
        f'<span class="tile-glyph f-{esc(font.get("slug") or slug(font["name"]))}">'
        f'{esc(ch)}</span>'
        f'<span class="draws-name">{esc(font["name"])}</span></a>'
        for font in drawn)
    faces = face_styles(drawn)
    # What the grid dropped, said out loud: twenty-four tiles where nine hundred
    # families have the character would otherwise read as "twenty-four have it".
    drawn_note = (f"Showing {len(drawn)} of {len(covering):,} families that cover it, "
                  "measured ones first — a page cannot load nine hundred webfonts."
                  if len(covering) > len(drawn) else
                  f"All {len(covering):,} indexed families that cover this codepoint.")

    body = f"""    <section class="entity-head">
      <div class="head-row">
        <h1><span class="glyph-large">{esc(ch) if category[0] not in "CZ" else ""}</span></h1>
        <p class="quiet">{" · ".join(neighbours)}</p>
      </div>
      <p class="byline">{esc(name)}</p>
      <div class="facts">
{chr(10).join(facts)}
      </div>
    </section>

    <section class="split">
      <div>
        <h2 class="eyebrow">How it is written down</h2>
{rows}
      </div>
      <div>
        <h2 class="eyebrow">How it is drawn</h2>
        <div class="drawn">
{tiles}
        </div>
        <p class="quiet">{drawn_note}
           Each is drawn by your browser in that family's own face, from that family's own
           distribution. Covering a codepoint is not the same as drawing it correctly in
           context — that is what a font's sequences show.</p>
      </div>
    </section>
"""
    return page(f"U+{cp:04X} {name}", body, kind="character", code=f"U+{cp:04X}",
                description=f"U+{cp:04X} {name}: encodings, and how each of the indexed font "
                            f"families draws it.",
                extra_head=faces)


# -------------------------------------------------------------------- blocks

def block_page(block, fonts, chars_built):
    """One Unicode block: its chart, and how well the index covers it."""
    import unicodedata

    first, last, name = block
    assigned = []
    for cp in range(first, last + 1):
        try:
            unicodedata.name(chr(cp))
        except ValueError:
            continue
        assigned.append(cp)

    covering = [(font, count_in_range(font.get("ranges") or [], first, last))
                for font in fonts]
    covering = [(font, n) for font, n in covering if n]
    complete = [font for font, n in covering if n >= len(assigned)]
    covering.sort(key=lambda row: (-row[1], row[0]["name"].lower()))

    # The chart, hatched where the codepoint is unassigned — and bounded. CJK
    # Unified Ideographs is 20,992 codepoints, and a page carrying every cell is
    # 300 KB of table nobody scrolls. What is dropped is stated, because a
    # silently short chart reads as a complete one.
    shown = min(last + 1, first + CHART_LIMIT)
    cells = []
    for cp in range(first, shown):
        try:
            unicodedata.name(chr(cp))
            reserved = False
        except ValueError:
            reserved = True
        if reserved:
            cells.append('        <div class="cell reserved" aria-hidden="true"></div>')
            continue
        glyph = chr(cp) if unicodedata.category(chr(cp))[0] not in "CZ" else ""
        inner = (f'<span class="glyph">{esc(glyph)}</span>'
                 f'<span class="cp mono">{cp:04X}</span>')
        cells.append(f'        <div class="cell">'
                     + (f'<a href="{link(f"/char/{cp:04X}/")}">{inner}</a>'
                        if cp in chars_built else inner)
                     + "</div>")

    families = "\n".join(
        f'      <tr><th scope="row"><a href="{font_href(font)}">{esc(font["name"])}</a></th>'
        f'<td class="mono">{n}/{len(assigned)}</td>'
        f'<td class="quiet">{esc(FOUNDRIES.get(font.get("source"), ""))}</td></tr>'
        for font, n in covering[:100])

    notes = []
    # A chart whose cells are links except where they silently are not is worse
    # than one that says which it is.
    if assigned and not any(cp in chars_built for cp in assigned):
        notes.append('<p class="quiet">The characters in this block do not have pages of '
                     f'their own: at {len(assigned):,} assigned codepoints it is a '
                     "repertoire rather than a writing system, and a page each would be "
                     "tens of thousands of files saying little beyond a name. The cells "
                     "above show the character and its codepoint.</p>")
    if shown <= last:
        notes.append(f'<p class="quiet">Showing the first {CHART_LIMIT:,} of '
                     f'{last - first + 1:,} codepoints in this block. The rest are in '
                     f'<a href="https://www.unicode.org/charts/PDF/U{first - (first % 0x80):04X}.pdf">'
                     "the Unicode chart ↗ — external</a>.</p>")
    truncated = "\n      ".join(notes)

    body = f"""    <section class="entity-head">
      <h1>{esc(name)}</h1>
      <p class="byline">U+{first:04X}–{last:04X}</p>
      <div class="facts">
{fact(f"{len(assigned)}", "assigned codepoints")}
{fact(f"{last - first + 1}", "codepoints in the block")}
{fact(f"{len(complete):,}", "families covering all of it")}
{fact(f"{len(covering):,}", "families covering some")}
      </div>
    </section>

    <section>
      <h2 class="eyebrow">The chart</h2>
      <div class="chart">
{chr(10).join(cells)}
      </div>
      <p class="quiet">Hatched cells are unassigned: no character has been encoded there,
         so no font can cover them and a coverage figure counting them would be wrong.</p>
      {truncated}
    </section>

    <section>
      <h2 class="eyebrow">Coverage across the index</h2>
      <table class="index">
        <thead><tr><th>Family</th><th>Covers</th><th>Foundry</th></tr></thead>
      <tbody>
{families}
      </tbody>
      </table>
    </section>
"""
    return page(name, body, kind="unicode block", code=f"U+{first:04X}–{last:04X}",
                description=f"{name} (U+{first:04X}–{last:04X}): the chart, and which font "
                            f"families cover it.")



# ------------------------------------------------------------------- scripts

def script_coverage(font, script):
    """How much of a script a face covers, block by block.

    A script is rarely one block — Devanagari takes three, Arabic nine — so
    "covers Tamil" has to mean every block of Tamil, including the supplement
    almost nothing has. That distinction is the whole reason this page exists.
    """
    rows = []
    for block in script["blocks"]:
        covered = sum(count_in_range(font.get("ranges") or [], first, last)
                      for first, last in block["ranges"])
        rows.append({"name": block["name"], "chars": block["chars"], "covered": covered})
    return {"chars": sum(r["chars"] for r in rows),
            "covered": sum(r["covered"] for r in rows), "blocks": rows}


def script_page(script, fonts, languages, chars_built):
    """One script: the blocks it spans, who writes it, what can set it."""
    ranked = []
    for font in fonts:
        coverage = script_coverage(font, script)
        if coverage["covered"]:
            ranked.append((font, coverage))
    ranked.sort(key=lambda row: (-row[1]["covered"], row[0]["name"].lower()))
    whole = [row for row in ranked if row[1]["covered"] >= row[1]["chars"]]

    blocks = "\n".join(
        f'      <tr><th scope="row">'
        + (f'<a href="{link("/block/" + slug(block["name"]) + "/")}">{esc(block["name"])}</a>'
           if block.get("name") else "")
        + f'</th><td class="mono">{block["chars"]}</td>'
        f'<td class="mono">{sum(1 for _font, cov in ranked if any(b["name"] == block["name"] and b["covered"] >= b["chars"] for b in cov["blocks"])):,}</td></tr>'
        for block in script["blocks"])

    written_by = [lang for lang in languages if script["code"] in (lang.get("scripts") or [])]
    langs_html = " ".join(
        f'<a href="{link("/lang/" + lang["id"] + "/")}">{esc(lang["name"])}</a>'
        for lang in sorted(written_by, key=lambda l: l["name"].lower())[:60])

    families = "\n".join(
        f'      <tr><th scope="row"><a href="{font_href(font)}">{esc(font["name"])}</a></th>'
        f'<td class="mono">{cov["covered"]}/{cov["chars"]}</td>'
        f'<td class="quiet">{esc(" · ".join(font.get("tags") or []) or "not read")}</td>'
        f'<td class="quiet">{esc(FOUNDRIES.get(font.get("source"), ""))}</td></tr>'
        for font, cov in ranked[:100])

    body = f"""    <section class="entity-head">
      <h1>{esc(script["name"])}</h1>
      <p class="byline">ISO 15924 <span class="mono">{esc(script["code"])}</span></p>
      <div class="facts">
{fact(len(script["blocks"]), "unicode blocks")}
{fact(f"{script['chars']:,}", "codepoints")}
{fact(f"{len(whole):,}", "families covering all of it")}
{fact(f"{len(ranked):,}", "families covering some")}
{fact(f"{len(written_by):,}", "languages written in it")}
      </div>
    </section>

    <section>
      <h2 class="eyebrow">The blocks it spans</h2>
      <table>
        <thead><tr><th>Block</th><th>Codepoints</th><th>Families covering it fully</th></tr></thead>
      <tbody>
{blocks}
      </tbody>
      </table>
      <p class="quiet">A script is rarely one block, and this is where support quietly dies:
         a family can cover the main block completely and have nothing at all in a
         supplement, while calling itself a font for the script.</p>
    </section>

    <section>
      <h2 class="eyebrow">Written by</h2>
      <div class="links">{langs_html or '<span class="quiet">No language in the index is recorded as using it.</span>'}</div>
    </section>

    <section>
      <h2 class="eyebrow">Families that can set it</h2>
      <table class="index">
        <thead><tr><th>Family</th><th>Covers</th><th>Declares</th><th>Foundry</th></tr></thead>
      <tbody>
{families}
      </tbody>
      </table>
      <p class="quiet">Coverage and declaration are different facts, shown side by side on
         purpose: a family covering every codepoint while declaring only the old script tag
         will still fall through to a default shaper on older stacks.</p>
    </section>
"""
    return page(script["name"], body, kind="script", code=script["code"],
                description=f"{script['name']} ({script['code']}): the Unicode blocks it "
                            f"spans, the languages written in it, and the font families "
                            f"that cover it.")


def missing_from(ranges, text):
    """Characters a face cannot produce, directly or by composing the pieces.

    Composition-aware: if the face has every piece of the NFD decomposition, the
    renderer builds the precomposed character anyway, so it is not missing.
    """
    import unicodedata

    missing = []
    for ch in dict.fromkeys(text):
        if ch.isspace():
            continue
        cp = ord(ch)
        if count_in_range(ranges, cp, cp):
            continue
        pieces = unicodedata.normalize("NFD", ch)
        if pieces != ch and all(count_in_range(ranges, ord(p), ord(p)) for p in pieces):
            continue
        missing.append(ch)
    return missing


def exemplar_needs(exemplars):
    """[(codepoint, the pieces that would build it)] for an exemplar set."""
    import unicodedata

    needs = []
    for ch in dict.fromkeys(exemplars):
        if ch.isspace():
            continue
        pieces = unicodedata.normalize("NFD", ch)
        needs.append((ord(ch), frozenset(ord(p) for p in pieces) if pieces != ch else None))
    return needs


def covered_subset(font, wanted):
    """Which of these codepoints a face has. Computed once per font, not once
    per language: the naive version re-scanned every font's ranges for every
    exemplar of every language, which is tens of millions of range walks."""
    ranges = font.get("ranges") or []
    return frozenset(cp for cp in wanted if count_in_range(ranges, cp, cp))


def language_fit(needs, covered):
    """The characters a face cannot produce from an exemplar set.

    Composition-aware: a precomposed character counts as present when the face
    has every piece, because that is how the renderer will build it.
    """
    gaps = []
    for cp, pieces in needs:
        if cp in covered:
            continue
        if pieces and pieces <= covered:
            continue
        gaps.append(chr(cp))
    return gaps


def lang_page(language, fonts, scripts, chars_built, coverage=None):
    """One language: what it needs written down, and what can write it."""
    exemplars = language.get("exemplars") or ""
    sample = (language.get("sample") or "").strip()

    fits, partial = [], []
    if exemplars:
        needs = exemplar_needs(exemplars)
        for font in fonts:
            if not font.get("ranges"):
                continue
            covered = (coverage or {}).get(id(font))
            if covered is None:
                covered = covered_subset(font, {cp for cp, _ in needs})
            gaps = language_fit(needs, covered)
            (fits if not gaps else partial).append((font, gaps))
        fits.sort(key=lambda row: row[0]["name"].lower())
        partial.sort(key=lambda row: (len(row[1]), row[0]["name"].lower()))

    tiles = "".join(
        f'<span class="tile">' +
        (f'<a href="{link(f"/char/{ord(ch):04X}/")}">{esc(ch)}</a>'
         if ord(ch) in chars_built else esc(ch)) + "</span>"
        for ch in exemplars if not ch.isspace())

    used = [script for script in scripts if script["code"] in (language.get("scripts") or [])]
    script_links = " ".join(
        f'<a href="{link("/script/" + s["code"] + "/")}">{esc(s["name"])}</a>' for s in used)

    nearly = "\n".join(
        f'      <tr><th scope="row"><a href="{font_href(font)}">{esc(font["name"])}</a></th>'
        f'<td class="mono">{len(gaps)}</td>'
        f'<td class="glyph-small">{esc("".join(gaps[:12]))}</td></tr>'
        for font, gaps in partial[:40])

    body = f"""    <section class="entity-head">
      <h1>{esc(language["name"])}</h1>
      <p class="byline">{esc(language.get("tag") or "")} ·
         ISO 639-3 <span class="mono">{esc(language.get("iso") or "")}</span></p>
      <div class="facts">
{fact(len([c for c in exemplars if not c.isspace()]), "exemplar characters")}
{fact(f"{len(fits):,}", "families that fit")}
{fact(len(used), "scripts it is written in")}
      </div>
      <p class="quiet">Written in {script_links or "a script not in the index"}. A language
         is not a script: several may write the same one, and one language may be written in
         several.</p>
    </section>

    <section>
      <h2 class="eyebrow">What it needs</h2>
      <div class="tiles">{tiles or '<span class="quiet">No exemplar set in SLDR for this language yet.</span>'}</div>
      <p class="quiet">The exemplar characters SIL's SLDR records for this language — what
         ordinary text in it actually requires, rather than a whole block.</p>
    </section>

    {'<section><h2 class="eyebrow">A line of it</h2><p class="specimen-small">'
     + esc(sample.split(chr(10))[0][:200]) + '</p>'
     '<p class="quiet">From the Universal Declaration of Human Rights, set in your '
     'browser&rsquo;s own face for the script.</p></section>' if sample else ''}

    <section>
      <h2 class="eyebrow">Nearly fits</h2>
      <table class="index">
        <thead><tr><th>Family</th><th>Missing</th><th>Which characters</th></tr></thead>
      <tbody>
{nearly}
      </tbody>
      </table>
      <p class="quiet">Families that cover most of the exemplar set and drop the rest to a
         fallback face. Naming the missing characters is the useful part: one absent letter
         is a different problem from twenty.</p>
    </section>
"""
    return page(language["name"], body, kind="language",
                code=language.get("tag") or language.get("iso"),
                description=f"{language['name']}: its exemplar characters, the scripts it is "
                            f"written in, and which font families can set it.")


def scripts_index(scripts, fonts):
    rows = []
    for script in sorted(scripts, key=lambda s: s["name"].lower()):
        whole = sum(1 for font in fonts
                    if script_coverage(font, script)["covered"] >= script["chars"])
        rows.append(
            f'      <tr data-name="{esc(script["name"].lower())}">'
            f'<th scope="row"><a href="{link("/script/" + script["code"] + "/")}">'
            f'{esc(script["name"])}</a></th>'
            f'<td class="mono">{esc(script["code"])}</td>'
            f'<td class="mono">{len(script["blocks"])}</td>'
            f'<td class="mono">{script["chars"]:,}</td>'
            f'<td class="mono">{whole:,}</td></tr>')
    body = f"""    <section class="entity-head">
      <div class="head-row">
        <h1>Scripts</h1>
        <p class="showing quiet">Showing <span data-showing>{len(scripts):,}</span>
           of {len(scripts):,}</p>
      </div>
      <p class="quiet">Every script the index records a language for, with the Unicode blocks
         it spans. The last column is the number of families covering every block of it —
         which is a much smaller number than the one covering the main block.</p>
    </section>

    <section>
      <div class="controls">
        <input type="search" class="filter" placeholder="filter this list"
               aria-label="Filter scripts by name">
      </div>
      <table class="index">
        <thead><tr><th>Script</th><th>Code</th><th>Blocks</th><th>Codepoints</th>
          <th>Families covering all</th></tr></thead>
      <tbody>
{chr(10).join(rows)}
      </tbody>
      </table>
      <p class="empty quiet" hidden>No script matches that.</p>
    </section>
"""
    return page("Scripts", body, kind="index", code=f"{len(scripts):,} scripts",
                description="Every script in the index, the Unicode blocks it spans, and how "
                            "many font families cover all of it.")


def languages_index(languages):
    rows = []
    for language in sorted(languages, key=lambda l: l["name"].lower()):
        exemplars = [c for c in (language.get("exemplars") or "") if not c.isspace()]
        rows.append(
            f'      <tr data-name="{esc(language["name"].lower())}">'
            f'<th scope="row"><a href="{link("/lang/" + language["id"] + "/")}">'
            f'{esc(language["name"])}</a></th>'
            f'<td class="mono">{esc(language.get("tag") or "")}</td>'
            f'<td class="mono">{esc(" ".join(language.get("scripts") or []))}</td>'
            f'<td class="mono">{len(exemplars) or ""}</td></tr>')
    body = f"""    <section class="entity-head">
      <div class="head-row">
        <h1>Languages</h1>
        <p class="showing quiet">Showing <span data-showing>{len(languages):,}</span>
           of {len(languages):,}</p>
      </div>
      <p class="quiet">Every language with a translation in the UDHR corpus, so there is real
         text to set. The scripts column is SIL's record of how the language is written — the
         first is the default, and the rest are real alternatives, not curiosities.</p>
    </section>

    <section>
      <div class="controls">
        <input type="search" class="filter" placeholder="filter this list"
               aria-label="Filter languages by name">
      </div>
      <table class="index">
        <thead><tr><th>Language</th><th>Tag</th><th>Scripts</th><th>Exemplars</th></tr></thead>
      <tbody>
{chr(10).join(rows)}
      </tbody>
      </table>
      <p class="empty quiet" hidden>No language matches that.</p>
    </section>
"""
    return page("Languages", body, kind="index", code=f"{len(languages):,} languages",
                description="Every language in the index, the scripts it is written in, and "
                            "the size of its exemplar set.")


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

    # Which codepoints get a page of their own. Not all 1.1 million: the blocks
    # of the scripts we have depth in, plus the Latin every face carries. The
    # set is passed to every page that might link a character, so a link is only
    # ever written to a page that exists — a 404 we generated ourselves is worse
    # than a plain codepoint.
    assigned = assigned_by_block(blocks)
    chars_built = {cp for name, cps in assigned.items()
                   if len(cps) <= CHAR_PAGE_MAX_BLOCK for cp in cps}
    print(f"  {len(chars_built):,} codepoints get a page; "
          f"{sum(1 for cps in assigned.values() if len(cps) > CHAR_PAGE_MAX_BLOCK)} blocks "
          f"are too large for one each")

    # Which families cover each of those codepoints, computed once. Asking per
    # page would be 33,000 pages times 1,885 families of range walking.
    covering_fonts = coverage_index(fonts["fonts"], chars_built)

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
            write(f"/font/{font['slug']}/lookups/", lookups_page(font))
            shaping += 1
        if font.get("glyphs"):
            write(f"/font/{font['slug']}/glyphs/", glyphs_page(font, chars_built))
    write("/fonts/", fonts_index(fonts["fonts"], blocks))

    # Features: one page each for every tag any indexed family runs, plus the
    # ones we have written about.
    content = feature_content()
    tags = {row["feature"] for font in fonts["fonts"]
            for table in ("gsub", "gpos")
            for row in (font.get("tables") or {}).get(table, [])}
    tags |= set(content.get("features") or {})
    tags |= set(content.get("stages") or [])
    for tag in sorted(tags):
        write(f"/feature/{tag}/", feature_page(tag, content, fonts["fonts"]))
    print(f"  wrote {len(tags)} feature pages")

    import bisect
    import unicodedata

    # Bisected, not scanned: "which block is this codepoint in" asked 33,000
    # times against 327 blocks is ten million comparisons for no reason.
    starts = [block[0] for block in blocks]
    written = 0
    for cp in sorted(chars_built):
        at = bisect.bisect_right(starts, cp) - 1
        block = blocks[at] if at >= 0 and blocks[at][1] >= cp else None
        write(f"/char/{cp:04X}/",
              char_page(cp, unicodedata.name(chr(cp)), block,
                        covering_fonts.get(cp, []), chars_built))
        written += 1
    print(f"  wrote {written:,} character pages")

    for block in blocks:
        write(f"/block/{slug(block[2])}/", block_page(block, fonts["fonts"], chars_built))
    print(f"  wrote {len(blocks)} block pages")

    for script in scripts:
        write(f"/script/{script['code']}/",
              script_page(script, fonts["fonts"], languages, chars_built))
    write("/scripts/", scripts_index(scripts, fonts["fonts"]))
    print(f"  wrote {len(scripts)} script pages")

    # Every codepoint any exemplar set needs, and which fonts have them —
    # computed once for all languages rather than re-walking every font's
    # ranges for every exemplar of every language.
    wanted = set()
    for language in languages:
        wanted |= {cp for cp, _pieces in exemplar_needs(language.get("exemplars") or "")}
    coverage = {id(font): covered_subset(font, wanted) for font in fonts["fonts"]}

    for language in languages:
        write(f"/lang/{language['id']}/",
              lang_page(language, fonts["fonts"], scripts, chars_built, coverage))
    write("/languages/", languages_index(languages))
    print(f"  wrote {len(languages)} language pages")
    write("/compare/", compare_page(fonts["fonts"]))

    # One small file per family with lookup tables, for Compare to fetch. Only
    # the families there is something to compare — not all 1,885.
    out = os.path.join(OUT_SITE, "data", "font")
    os.makedirs(out, exist_ok=True)
    written = 0
    for font in fonts["fonts"]:
        if not font.get("tables"):
            continue
        with io.open(os.path.join(out, f"{font['slug']}.json"), "w", encoding="utf-8") as handle:
            json.dump(font_data(font), handle, ensure_ascii=False, separators=(",", ":"))
        written += 1
    print(f"  wrote compare data for {written} families")
    measured = sum(1 for f in fonts["fonts"] if f.get("tier") == "measured")
    print(f"  wrote {len(fonts['fonts'])} font pages — {measured} measured, "
          f"{len(fonts['fonts']) - measured} not yet; {shaping} with lookups")


if __name__ == "__main__":
    main()
