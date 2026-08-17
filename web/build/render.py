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


def glyph_cell(glyph):
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
        return f'<span class="glyph">{esc(chr(glyph["cp"]))}</span>'
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


def glyphs_page(font):
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
            reach = (f'<a href="{link("/char/" + f"{glyph["cp"]:04X}" + "/")}" class="mono">'
                     f'U+{glyph["cp"]:04X}</a>')
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
            f'<td>{glyph_cell(glyph)}</td>'
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
            write(f"/font/{font['slug']}/lookups/", lookups_page(font))
            shaping += 1
        if font.get("glyphs"):
            write(f"/font/{font['slug']}/glyphs/", glyphs_page(font))
    write("/fonts/", fonts_index(fonts["fonts"], blocks))
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
