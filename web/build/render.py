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
from concurrent.futures import ThreadPoolExecutor

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
       ("Fonts", "/fonts/")]

# The tools, grouped behind one nav item: they answer a question you bring
# rather than one the index answers, and listing five of them beside four
# browsable sections made the masthead read as a flat pile.
#
# Only what exists is listed. Regex and Identify go in when they are built —
# a nav item that 404s is the site promising something it does not have, on
# every page.
TOOLS = [("Inspect", "/inspect/"), ("Compare", "/compare/")]


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
    # A disclosure rather than a hover menu: it opens on click and on the
    # keyboard, and it needs no JavaScript to do either.
    tools = "\n".join(
        f'          <a href="{link(href)}">{esc(label)}</a>' for label, href in TOOLS)
    nav += ('        <details class="tools">'
            '<summary>Tools</summary>'
            f'<div class="tools-menu">{tools}</div>'
            '</details>')
    where = ""
    if kind:
        where = (f'<div class="where">{esc(kind)}'
                 + (f' · <span class="mono">{esc(code)}</span>' if code else "")
                 + "</div>")
    meta = f'\n  <meta name="description" content="{esc(description)}">' if description else ""

    # Wide content scrolls inside its own box; the page itself never scrolls
    # sideways. A seven-column index at 380px pushed 300px of table past the
    # viewport, which the brief rules out and a browser test now catches. Done
    # here rather than at each of the nine places a table is built, so a table
    # added later is contained by default.
    body = re.sub(r"(<table\b[\s\S]*?</table>)",
                  r'<div class="scroll">\1</div>', body)

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
      <p>Read-only. Nothing you type leaves the browser. Specimens are drawn from
         wherever each family is actually distributed — and where a foundry
         distributes no webfont, from our copy of its own release build, under
         the licence that release ships.</p>
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
            <a href="{link("/block/basic-latin/")}">Browse a block</a>
          </div>
          <p class="quiet">Read in your browser, against the same Unicode tables
             the rest of the site is built from.</p>
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


def try_it(font, name):
    """Set your own text in this family, with the switches the font really has.

    Two things this deliberately does not offer, because a browser cannot do
    them and pretending otherwise is the failure mode this whole site is about:

    * **A script-tag switch (mlym against mlm2).** Nothing in CSS selects an
      OpenType script tag. The shaper picks it from the characters, and
      HarfBuzz takes mlm2 wherever a font declares it. The family page already
      says which tags this font declares; which one a browser used is not ours
      to choose, and a dropdown implying otherwise would be a lie in the shape
      of a control. `hb-shape --script=mlym` is on every row of the evidence
      matrix and does answer it.
    * **A weight or style this family does not publish.** Asked for 800 with
      one weight loaded, a browser smears the outlines and calls it bold. So
      the weights offered are the ones the family actually ships, and where we
      know of only one there is no control at all.

    What is real: size, the features the font's own tables declare, and the
    weights it publishes. Turning a feature off is the interesting one — it is
    the difference between what the font can draw and what it draws by default.
    """
    if not can_draw(font):
        return ""

    faces = font.get("faces") or []
    weights = sorted({f.rstrip("i") for f in faces if f.rstrip("i").isdigit()}, key=int)
    italic = any(f.endswith("i") for f in faces)

    # A variable face is one file covering everything between two numbers, so the
    # choices are the round weights inside its own range — not the two endpoints,
    # which is all the face list can say.
    axis = next((a for a in (font.get("axes") or []) if a.get("tag") == "wght"), None)
    if axis:
        low, high = int(axis["min"]), int(axis["max"])
        weights = [str(w) for w in range(100, 1000, 100) if low <= w <= high] or [str(low)]
    features = [t for t in (font.get("features") or []) if t not in ("aalt",)]

    controls = ['        <label class="try-size"><span class="quiet">size</span>'
                '<input type="range" min="12" max="96" step="1" value="14" '
                'data-try="size" aria-label="Preview size">'
                '<span class="mono" data-try="size-value">14px</span></label>']
    if len(weights) > 1:
        options = "".join(f'<option value="{esc(w)}">{esc(w)}</option>' for w in weights)
        controls.append('        <label class="try-weight"><span class="quiet">weight</span>'
                        f'<select data-try="weight">{options}</select></label>')
    if italic:
        controls.append('        <label class="try-italic">'
                        '<input type="checkbox" data-try="italic"><span>italic</span></label>')

    # Every feature the font's own tables declare, off meaning "as the font
    # ships it" rather than "off": unchecking is what shows you the rule.
    chips = "".join(
        f'<label class="feat"><input type="checkbox" data-feature="{esc(tag)}" checked>'
        f'<span class="mono">{esc(tag)}</span></label>' for tag in features)
    feature_block = (
        '        <details class="try-features"><summary>Features '
        f'({len(features)})</summary>\n'
        '          <p class="quiet">Every feature this font declares, on as it ships. '
        'Untick one to see what it was doing.</p>\n'
        f'          <div class="feats">{chips}</div>\n        </details>'
        if features else "")

    return f"""      <h2 class="eyebrow">Try it</h2>
      <div class="try" data-face="{esc(name)}"
           data-src="{link(f"/data/font/{font.get('slug') or slug(name)}.json")}">
        <label class="field">
          <span class="eyebrow-inline">your text, codepoints or a range</span>
          <textarea data-try="text" rows="2" spellcheck="false"
                    placeholder="paste anything, or try 0D15, U+0D15 U+0D4D U+0D15, 0D15..0D3F"
                    aria-label="Text to set in {esc(name)}"></textarea>
        </label>
        <div class="try-controls">
{chr(10).join(controls)}
          <button type="button" class="preview" data-try="go">Preview</button>
        </div>
{feature_block}
        <output class="try-out" data-try="out" hidden></output>
        <p class="quiet" data-try="note" hidden></p>
        <noscript><p class="quiet">Setting your own text needs JavaScript. The specimen
           above and every figure on this page are in the HTML without it.</p></noscript>
      </div>"""


# The snippet is HTML and CSS, so it is marked up as HTML and CSS rather than
# left as one grey block. Three token kinds carry all of it: the tag or at-rule,
# the names inside it, and the quoted values. Anything unmatched falls through as
# plain text, which is why this cannot mangle a snippet it does not recognise.
SNIPPET_TOKENS = re.compile(
    r'(?P<string>"[^"]*")'
    r"|(?P<tag></?[a-zA-Z-]+|/?>|@font-face|[{}])"
    r"|(?P<name>[a-zA-Z-]+(?=\s*[:=]))")


def highlight(snippet):
    """The snippet with its tags, names and strings marked up.

    Escaping happens here, per token, so the markup this adds cannot be confused
    with markup in the snippet: a family called `<b>` comes out as text.
    """
    out, at = [], 0
    for match in SNIPPET_TOKENS.finditer(snippet):
        out.append(esc(snippet[at:match.start()]))
        kind = match.lastgroup
        out.append(f'<span class="t-{kind}">{esc(match.group())}</span>')
        at = match.end()
    out.append(esc(snippet[at:]))
    return "".join(out)


def use_it(font):
    """The CSS to set text in this face, and which of three honest states it is
    in. Mirrors core.js useIt() — the client needs the same answer on Compare.

    Never a fabricated @import for a family that has none, which is what the
    prototype's font page did for every family regardless.

    Returned raw, not escaped. It is shown in a <pre> and also handed to a copy
    button, and a snippet escaped at the source puts &amp; on someone's
    clipboard — a stylesheet URL that 404s when they paste it.
    """
    name = font["name"]
    if font.get("source") == "google":
        slug_name = font["name"].replace(" ", "+")
        return ("Served from Google Fonts.",
                f'<link rel="stylesheet"\n      href="https://fonts.googleapis.com/css2'
                f'?family={slug_name}&display=swap">\n\n'
                f'font-family: "{name}", sans-serif;')
    if font.get("css"):
        return ("Served from the foundry's own site.",
                f'<link rel="stylesheet" href="{font["css"]}">\n\n'
                f'font-family: "{name}", sans-serif;')
    file = font["name"].replace(" ", "") + ".woff2"
    served = ("The specimens here are drawn from our copy of the foundry's own release "
              "build, kept under the licence that release ships. Do not link to it: it is "
              "this site's copy, not a CDN. Take the file from the foundry and serve it "
              "yourself — "
              if font.get("webfont") else
              "This family is not served from a public CDN — download it and host the file "
              "yourself: ")
    return (served + "the template below names a bare filename because the URL is yours.",
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
    # The verdict in each row is HarfBuzz's, read from the font's own tables at
    # build time — it stands whether or not a browser here can load the face.
    # The drawing beside it does not: with no face to set it in, the browser
    # substitutes one, and a shaped sequence rendered by a different font under
    # this font's name is the exact claim this site exists to disprove. So where
    # we cannot load it, the row is its codepoints and nothing more.
    drawn = can_draw(font)
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
            '      <tr><th scope="row">'
            + (f'<span class="specimen-inline">{esc(entry["out"])}</span>' if drawn else "")
            + f'<span class="mono">{esc(entry["codes"])}</span></th>'
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


def prepare_fonts(fonts, blocks):
    """Work out each family's block coverage once, for the whole build.

    Asking "how much of every block does this face cover" was 327 range walks
    per call, and the language pages called it — through made_for and
    dominant_block — once per fitting family per language. That was eighteen
    seconds a page, and there are 526 language pages.

    One pass over the font's own ranges answers it instead: find the block each
    range starts in by bisection, then walk forward while the blocks overlap.
    """
    import bisect

    starts = [block[0] for block in blocks]
    for font in fonts:
        counts = {}
        for first, last in font.get("ranges") or []:
            at = max(bisect.bisect_right(starts, first) - 1, 0)
            for index in range(at, len(blocks)):
                block_first, block_last, name = blocks[index]
                if block_first > last:
                    break
                overlap = min(block_last, last) - max(block_first, first) + 1
                if overlap > 0:
                    counts[name] = counts.get(name, 0) + overlap
        font["_blocks"] = counts
        font["_dominant"] = dominant_from(counts, blocks)
    return fonts


def block_sizes(blocks):
    return {name: last - first + 1 for first, last, name in blocks}


def dominant_from(counts, blocks):
    """The block a face exists for, from its per-block counts.

    "Largest block" alone is the wrong test: a workhorse carrying a bit of
    everything is for none of them in particular, so the block has to dominate
    what the face has outside Latin and punctuation.
    """
    sizes = block_sizes(blocks)
    spend = [(name, covered, sizes.get(name, covered))
             for name, covered in counts.items()
             if name not in COMMON_BLOCKS and covered >= min(SCRIPT_FLOOR, sizes.get(name, 1))]
    if not spend:
        return None
    total_outside = sum(covered for _name, covered, _total in spend)
    best = max(spend, key=lambda row: row[1])
    return best if best[1] >= total_outside * 0.5 else None


def blocks_covered(font, blocks, floor=SCRIPT_FLOOR):
    """[(name, covered, total)] for the blocks this face meaningfully covers."""
    sizes = block_sizes(blocks)
    counts = font.get("_blocks")
    if counts is not None:
        return [(name, covered, sizes.get(name, covered))
                for first, last, name in blocks
                if (covered := counts.get(name, 0)) >= min(floor, last - first + 1)]
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
    if "_dominant" in font:
        return font["_dominant"]
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
    stylesheet. Empty where neither exists, including where we serve it
    ourselves: that is an @font-face rule, not a stylesheet URL."""
    if font.get("source") == "google":
        return ("https://fonts.googleapis.com/css2?family="
                + font["name"].replace(" ", "+") + google_axes(font) + "&display=swap")
    return font.get("css") or ""


def google_axes(font):
    """`:ital,wght@0,400;1,400` — the faces this family actually publishes.

    Without this the CDN sends the regular alone, and the weight control under
    "Try it" would be asking the browser to smear one set of outlines into a
    bold. Only the weights Google lists for the family are requested, so the
    control can only offer faces that will arrive.
    """
    faces = font.get("faces") or []
    pairs = sorted({(1 if f.endswith("i") else 0, int(f.rstrip("i")))
                    for f in faces if f.rstrip("i").isdigit()})
    if len(pairs) < 2:
        return ""
    if not any(ital for ital, _ in pairs):
        return ":wght@" + ";".join(str(w) for _, w in pairs)
    return ":ital,wght@" + ";".join(f"{ital},{w}" for ital, w in pairs)


def face_rule(font):
    """The @font-face for a family whose file we publish ourselves, or "".

    RIT and SIL host no stylesheet, so for years these families were named on
    pages that drew them in a fallback. Their releases ship a woff2 and an OFL,
    and gen_index re-serves that file unmodified — so here it becomes a rule
    pointing at our own copy.
    """
    web = font.get("webfont")
    if not web:
        return ""
    # One rule per face the release ships, each carrying the weight and style the
    # face declares, so `font-weight: 700` reaches the real bold instead of the
    # browser smearing the regular into one. A variable face is a single file
    # over a range and its key says so: "100 900".
    faces = font.get("webfonts") or {web: web}
    rules = []
    for key, path in sorted(faces.items()):
        if key == web:                                  # a record from before faces were read
            weight, style = "400", "normal"
        elif " " in key:                                # variable: a weight range
            weight, style = key, "normal"
        else:
            weight = key.rstrip("i") or "400"
            style = "italic" if key.endswith("i") else "normal"
        rules.append(f'@font-face {{ font-family: "{esc(font["name"])}"; '
                     f'src: url("{link("/" + path)}") format("woff2"); '
                     f'font-weight: {esc(weight)}; font-style: {style}; font-display: swap; }}')
    return " ".join(rules)


def can_draw(font):
    """Can a browser actually set text in this family?

    Every panel that names a family claims that family drew the text. Where the
    answer here is no the page must say so rather than let the browser
    substitute something and the verdict beside it read as a measurement of what
    is on screen.
    """
    return bool(face_css_of(font) or font.get("webfont"))


def why_not_drawn(font):
    """Why a browser cannot set text in this family — the two reasons differ.

    Junicode is OFL and we may re-serve it; its release simply ships no webfont
    build, and we do not make one, because a file we generated is not the file
    the foundry released. A family with no licence we can read is a different
    answer entirely, and saying the wrong one about someone's licence is worse
    than saying nothing.
    """
    if font.get("licence"):
        return ("its release ships no webfont build, and we publish only files a "
                "foundry built itself")
    return ("we could not read a licence in its release that permits us to re-serve "
            "its file")


def face_head(font, name):
    """Load the family so the page can set specimens and glyphs in it."""
    css = face_css_of(font)
    rule = face_rule(font)
    if not css and not rule:
        return ""
    head = f'  <link rel="stylesheet" href="{esc(css)}">\n' if css else ""
    return (head + "  <style>"
            + (rule + " " if rule else "")
            + f'.specimen, .specimen-small, .specimen-inline, .glyph '
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


def release_label(record):
    """"SIL v7.000" — who published this release, and which one."""
    who = FOUNDRIES.get(record.get("source"), (record.get("source") or "").upper())
    version = record.get("version") or ""
    return f"{who} v{version}" if version else who


def webfont_state(record):
    """How a browser would get this release, in three words."""
    if record.get("webfont"):
        return "served here"
    if record.get("source") == "google":
        return "Google's CDN"
    if record.get("css"):
        return "foundry stylesheet"
    return "none published"


def two_releases(font):
    """The same family, published twice, wherever the two disagree.

    Google and a foundry both carry about thirty families. Only one used to
    survive, and it was Google's — so Charis SIL reported two faces where SIL
    ships eight, and "not read" for tags where SIL's release has 263 GSUB
    lookups. That difference is not noise to be resolved; it is the argument this
    site makes, and a reader deciding which release to install needs it.

    Only differing rows appear. Two releases that agree have nothing to say here,
    and a row repeating one number twice is furniture.

    Nothing on this page merges the two. Every other figure, the specimen, the
    evidence matrix, the lookups and the glyphs come wholly from the primary
    record — which this table names, so it is never a mystery which release a
    number belongs to.
    """
    alternates = font.get("alternates") or []
    if not alternates:
        return ""
    other = alternates[0]

    def codepoints(record):
        return f"{count_in_range(record.get('ranges') or [], 0, 0x10FFFF):,}"

    def tags(record):
        found = record.get("tags")
        return ", ".join(found) if found else ("not read" if found is None else "none")

    def lookups(record):
        if record.get("gsub") is None and record.get("gpos") is None:
            return "not read"
        return f"{record.get('gsub', 0)} · {record.get('gpos', 0)}"

    def weights(record):
        return f"{len(record.get('faces') or [])}" or "0"

    def read(record):
        return (record.get("provenance") or {}).get("read") or "not read"

    rows = []
    for label, of in (("codepoints", codepoints), ("script tags", tags),
                      ("GSUB · GPOS lookups", lookups), ("weights published", weights),
                      ("webfont", webfont_state), ("file read", read)):
        mine, theirs = of(font), of(other)
        if mine == theirs:
            continue
        rows.append(f'      <tr><th scope="row">{esc(label)}</th>'
                    f'<td class="mono">{esc(mine)}</td>'
                    f'<td class="mono">{esc(theirs)}</td></tr>')
    if not rows:
        return ""

    return ('    <section class="releases">\n'
            '      <h2 class="eyebrow">Two releases</h2>\n'
            f'      <p class="quiet">{esc(release_label(font))} and '
            f'{esc(release_label(other))} publish this family separately. '
            'Where they differ:</p>\n'
            '      <table class="index">\n'
            '        <thead><tr><th></th>'
            f'<th>{esc(release_label(font))}</th>'
            f'<th><a href="{esc(other.get("url") or "")}">{esc(release_label(other))} ↗</a>'
            '</th></tr></thead>\n'
            '      <tbody>\n' + "\n".join(rows) + '\n      </tbody>\n'
            '      </table>\n'
            f'      <p class="quiet">Everything else on this page — the specimen, the '
            f'evidence, the lookups, the glyphs — is the {esc(release_label(font))} release. '
            'The two are measured separately and never merged: a number from one release '
            'reported under the other\'s name would be a different font\'s number.</p>\n'
            '    </section>')


def moved_slugs(font):
    """[(alternate, old slug)] for the URLs this family used to live at.

    Only where the two publishers disagree about the name. Where they agree there
    is nothing to redirect, and emitting a stub would be a page pointing at
    itself.
    """
    out = []
    for other in font.get("alternates") or []:
        moved = slug(other.get("name") or "")
        if moved and moved != font["slug"]:
            out.append((other, moved))
    return out


def moved_page(other, font):
    """Where a family went when its two publishers disagree about its name.

    Google calls SIL's Charis "Charis SIL" and its Gentium "Gentium Plus". Once
    the foundry's release became the primary record the page moved to the
    foundry's own name, and `/font/charis-sil/` — a URL that worked yesterday and
    that people have — started 404ing. `check_site.py` could not catch it: no
    page links to the old slug, so nothing was broken *inside* the site.

    A real page rather than a redirect, saying which name belongs to whom, since
    the disagreement is itself worth knowing. The canonical link and the refresh
    take a reader on.
    """
    name, to = other.get("name") or "", font["name"]
    where = link(f"/font/{font['slug']}/")
    return page(
        f"{name} is {to}",
        f'''    <section class="entity-head">
      <h1>{esc(name)}</h1>
      <p class="quiet">{esc(FOUNDRIES.get(other.get("source"), "This distributor"))} calls this
         family <strong>{esc(name)}</strong>. Its publisher calls it
         <strong>{esc(to)}</strong>, and that is the name the font's own tables
         carry — so the family lives at <a href="{where}">{esc(to)}</a>, with both
         releases compared on that page.</p>
      <p class="quiet">Taking you there now.</p>
    </section>''',
        kind="font", code=slug(name),
        description=f"{name} is this site's page for {to}.",
        extra_head=f'  <link rel="canonical" href="{where}">\n'
                   f'  <meta http-equiv="refresh" content="2; url={where}">')


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

    # Can the reader's browser get this face at all? Google's CDN, the foundry's
    # own stylesheet, or our copy of their release build where they publish
    # neither. Where the answer is no, nothing on this page is set in the family
    # — a specimen the browser substituted is a picture of the wrong font under
    # the right name, and the verdicts beside it would read as measurements of it.
    face_css = can_draw(font)

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
        header += [f'      <p class="specimen" data-face="{esc(name)}">{esc(line)}</p>',
                   f'      <p class="specimen-small" data-face="{esc(name)}">'
                   f'{esc(second)}</p>']
    if facts:
        header += ['      <div class="facts">'] + facts + ['      </div>']
    if measured and not face_css:
        header.append('      <p class="quiet">No specimen here: ' + esc(why_not_drawn(font))
                      + '. Everything below was read from the family’s own font file, '
                        'and none of it depends on your browser drawing it.</p>')
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
    # The snippet is the one thing on this page a reader takes away with them,
    # and selecting a <pre> by hand on a phone is a fight.
    right = ['      <h2 class="eyebrow">Use it</h2>\n'
             '      <div class="snippet-wrap">\n'
             f'        <pre class="snippet mono">{highlight(snippet)}</pre>\n'
             f'        <button class="copy" data-copy="{esc(snippet)}" '
             'title="Copy this snippet">copy</button>\n'
             '      </div>\n'
             f'      <p class="quiet">{esc(note)}</p>']
    links = []
    if font.get("tables"):
        links.append(f'<a href="{font_href(font)}lookups/">Lookups</a>')
    if font.get("glyphs"):
        links.append(f'<a href="{font_href(font)}glyphs/">Glyphs</a>')
    if font.get("url"):
        links.append(f'<a href="{esc(font["url"])}">Download {esc(name)} ↗</a>')
    links.append(f'<a href="{link("/compare/")}">Compare with another family</a>')
    # A list, because it is one. Four destinations joined by a plain space read
    # as a sentence — "Download Anek Malayalam ↗ Compare with another family" —
    # and a screen reader announced it as one too. Now it says "list, 4 items".
    right.append('      <ul class="links">'
                 + "".join(f"<li>{item}</li>" for item in links)
                 + '</ul>')
    right.append(try_it(font, name))

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
        # `release` is a URL only for foundries we read a stylesheet from. For a
        # GitHub or GitLab release it is a tag — "v4.100" — and linking it
        # produced `href="v4.100"`, a relative link to nothing, on every SIL, RIT
        # and libre family page, labelled "external". The checker found it.
        release = source.get("release") or ""
        where = release if release.startswith("http") else font.get("url") or ""
        named = ("" if release.startswith("http")
                 else f' release <span class="mono">{esc(release)}</span>')
        link_text = (f'<a href="{esc(where)}">the release the foundry publishes ↗ — external</a>'
                     if where else "the release the foundry publishes")
        right.append('      <h2 class="eyebrow">Provenance</h2>\n'
                     '      <p class="quiet">Read from <span class="mono">'
                     f'{esc(source.get("file"))}</span>{named} on {esc(source.get("read"))}, '
                     f'via {link_text}.<br>'
                     f'<span class="mono break">{esc(font.get("checksum"))}</span></p>')

    # The evidence gets the full width. It was in a third of it, beside two
    # other columns, and a matrix of four engine columns plus an hb-shape line
    # does not fit in 300px — the verdicts wrapped into each other and the
    # command ran under the panel to its right.
    # Before the evidence, because it names which release the evidence is of.
    releases = two_releases(font)
    if releases:
        body.append(releases)

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


def rule_row(rule, drawn=True):
    """One rule, in the script first and the font's glyph names second.

    Glyph names are the font developer's private business: nobody should have to
    learn that Manjari calls chillu n `n1cil` to read what a lookup does. Where
    the cmap reaches a glyph we show the character; a ligature glyph has no
    codepoint of its own, so the output is drawn by letting the browser shape
    the input — which is the same substitution, performed rather than described.
    """
    # With no face to load, every one of these spans would be some other font
    # drawing this font's rules. The glyph names beside them are the font's own
    # and stand without it, so that is all the row becomes.
    if not drawn:
        return (f'<div class="rule"><span class="names mono">'
                f'{esc(rule["in"])} → {esc(rule["out"])}</span></div>')
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


def unloadable_cell(glyph, why, chars_built=()):
    """What stands where the drawing would be for a family we cannot load.

    Not a blank, and not the character set in the page font: an encoded glyph
    still has a codepoint worth naming, and everything the layout builds has
    nothing honest to show at all.

    `chars_built` is not optional in practice, whatever the default says. Without
    it this linked every codepoint it found — including private use and control
    characters, which have no page — and put 99 dead links on Junicode's glyphs
    page alone. `glyph_cell()` has always checked; this was written later and did
    not, which is what `check_site.py` was built to catch.
    """
    if glyph.get("cp"):
        code = f'U+{glyph["cp"]:04X}'
        return (f'<a class="mono quiet" href="{link(f"/char/{glyph["cp"]:04X}/")}">{code}</a>'
                if glyph["cp"] in chars_built else f'<span class="mono quiet">{code}</span>')
    return ('<span class="faint" title="nothing here can draw this: '
            + esc(why) + '">not loadable</span>')


def glyphs_page(font, chars_built=()):
    """Every glyph in the family, and what the layout does with each one."""
    inventory = font.get("glyphs") or []
    name = font["name"]
    # Every cell here is the browser drawing this family. With no face to load,
    # nine hundred cells would be nine hundred pictures of some other font,
    # captioned with this font's glyph names — the whole page a fabrication.
    drawn = can_draw(font)
    why = why_not_drawn(font)
    # The inventory is capped in the generator, and until now the page showed the
    # capped number twice and read as complete. Every other cap on this site is
    # disclosed; this was the exception. `glyph_count` is absent only for a
    # measurement taken before it was recorded — say nothing rather than guess.
    counted = font.get("glyph_count")
    dropped = (counted - len(inventory)) if counted else 0
    cap_note = (f" This page lists the first {len(inventory):,} of the "
                f"{counted:,} glyphs the font carries; {dropped:,} are not shown."
                if dropped > 0 else "")
    drawn_note = (
        "Glyphs are drawn by your browser from the family's own distribution. An "
        "unencoded glyph is shown by setting the input that produces it, so what you "
        "see is the shaper doing the substitution rather than a picture of it."
        if drawn else
        "Nothing here is drawn: " + why_not_drawn(font) + ", so your browser has nothing "
        "to set these glyphs in — and a cell filled by some other font would be a picture "
        "of the wrong typeface under this one’s glyph names. Everything else on this "
        "page was read from the family’s own tables and stands.")

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
            + f'<td>{glyph_cell(glyph, chars_built) if drawn else unloadable_cell(glyph, why, chars_built)}</td>'
            + f'<th scope="row" class="mono">{esc(glyph["name"])}</th>'
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
           of {counted or len(inventory):,}</p>
      </div>
      <p class="quiet">A font is not its codepoints. {len(built):,} of these
         {len(inventory):,} glyphs have no codepoint at all — they are the conjuncts, half
         forms and positional variants the layout rules build — and
         {len(orphans):,} are reachable by nothing: no codepoint, and no rule that produces
         them. However well drawn, those cannot appear in text.{cap_note}</p>
      <p class="quiet">{drawn_note}</p>
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


# How many faces one block's entry lists. Enough to see that families differ,
# few enough that a page loading them is still a page.
BLOCK_FACES = 10


def block_faces(fonts, blocks, assigned):
    """{block: [faces that cover all of it]} — what Inspect draws a string in.

    Per block rather than per string: shipping every family's ranges so the
    browser could work it out itself is megabytes, and the useful answer for
    "why do these two render differently" is a handful of families that all
    cover the script, not an exhaustive list.
    """
    out = {}
    for first, last, name in blocks:
        total = len(assigned.get(name) or [])
        if not total:
            continue
        faces = [font for font in fonts
                 if font.get("tier") == "measured"
                 and (font.get("_blocks") or {}).get(name, 0) >= total
                 and (font.get("source") == "google" or font.get("css"))]
        if not faces:
            continue
        # Families drawn for this script first: they are the ones whose
        # differences are about the writing system rather than incidental.
        faces.sort(key=lambda font: ((font.get("_dominant") or ("", 0, 0))[0] != name,
                                     font["name"].lower()))
        # The cap stays — uncapped this file is megabytes, and the docstring above
        # says why — but the total ships with it so Inspect can say what it is not
        # showing and point at the page that lists every one. Basic Latin is
        # covered by 1,879 families; showing eight and saying nothing was the bug.
        out[name] = {
            "of": len(faces),
            "faces": [{"name": font["name"], "slug": font["slug"],
                       "source": font.get("source", ""), "css": font.get("css") or "",
                       "for": (font.get("_dominant") or ("", 0, 0))[0] == name}
                      for font in faces[:BLOCK_FACES]],
        }
    return out


def inspect_page():
    """Paste anything and read what it is.

    A tool page: it answers a question the reader brings, so the shell is served
    and the answer is computed in the browser from the same Unicode tables the
    build uses. Nothing is sent anywhere — there is no server to send it to, and
    that is the point rather than a policy.
    """
    body = """    <section class="entity-head">
      <h1>Inspect</h1>
      <p class="quiet">Paste or type anything — text, a codepoint in any notation,
         a range. It is read in your browser, against the same Unicode tables the
         rest of the site is built from. Nothing you type leaves the page.</p>
    </section>

    <section>
      <label class="field">
        <span class="eyebrow-inline">text or codepoints</span>
        <input type="search" id="inspect-input" autocomplete="off" autofocus
               placeholder="paste anything, or try 0D15, U+0D15, \u0D15, &amp;#x0D15;"
               aria-label="Text or codepoints to inspect">
      </label>
      <p class="quiet" id="inspect-reading"></p>
      <noscript>
        <p class="quiet">This page reads what you type in the browser, so it needs
           JavaScript. Everything else on the site is plain HTML and does not —
           and a character's own page carries the same facts without it:
           <a href="{chars}">browse a block</a> to reach one.</p>
      </noscript>
      <div id="inspect-out"></div>
      <div id="inspect-faces" hidden></div>
    </section>
"""
    return page("Inspect", body.replace("{chars}", link("/block/basic-latin/")),
                kind="tool", code="inspect",
                description="Paste text or a codepoint in any notation and read what it is: "
                            "clusters, codepoints, names, blocks, normalisation and "
                            "encodings — computed in your browser.")


def lookup_rows(rows, drawn=True):
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
        rules = "".join(rule_row(rule, drawn) for rule in row["rules"])
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
    # This page draws every rule in the family's own face — and never loaded it,
    # for any family, so even a Google face drew its rules in the page font.
    drawn = can_draw(font)
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
        rows = lookup_rows(tables.get(key) or [], drawn)
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
                            f"rules behind them.",
                extra_head=face_head(font, name))


# How many faces one page will load to draw a character in. A grid of nine
# hundred webfonts is not a page; what is dropped is stated, as everywhere else.
DRAWN_LIMIT = 24

# How many family cards a language page sets. Each loads a face.
CARDS_LIMIT = 36


def capped(rows, limit, noun, because=""):
    """Truncate a table and say so, in one call so the two cannot drift apart.

    Five caps on this site were undisclosed at one time or another, found one at
    a time and mostly after shipping — the glyph inventory, the character grid,
    the language cards, the block families, the script families. Each was written
    as a bare `[:N]` slice, and each read as complete.

    Returns (shown, attributes for the table, the note). The attributes let
    `check_site.py` find a truncated table and demand the note; passing through
    here is what makes the note exist at all.
    """
    shown = rows[:limit]
    if len(rows) <= limit:
        return shown, "", ""
    attrs = f' data-showing="{len(shown)}" data-of="{len(rows)}"'
    note = (f'      <p class="quiet cap-note">Showing {len(shown):,} of '
            f'{len(rows):,} {esc(noun)}'
            + (f" — {esc(because)}" if because else "") + ".</p>")
    return shown, attrs, note


def face_attrs(font, eager):
    """The attributes that either claim a face or ask for one later.

    `data-face` is a claim: this family drew this text. It is only true once the
    face is really here, so a panel that loads faces on scroll emits
    `data-family` plus what a face needs, and lazyfaces.js swaps one for the
    other after the face lands. Backwards, it marks every waiting tile as a
    failure the moment the page loads.

    Shared by the character grid and the language cards because they had the same
    cap and want the same fix — and writing it twice is how one of them gets
    fixed and the other does not, which is exactly what happened the first time.
    """
    if eager:
        return f' data-face="{esc(font["name"])}"'
    css = face_css_of(font)
    rule = "" if css else face_rule(font)
    return (f' data-family="{esc(font["name"])}"'
            + (f' data-css="{esc(css)}"' if css else "")
            + (f' data-rule="{esc(rule)}"' if rule else ""))


def lazy_face_styles(fonts):
    """The `.f-<slug>` rules for tiles whose faces have not arrived yet.

    The class has to exist in the markup or the tile would jump from the page
    font to the family's the instant its face loads. What is absent is the face
    itself — no stylesheet link, no @font-face — so until `lazyfaces.js` injects
    one these tiles are the page font, marked pending, and claim nothing.
    """
    if not fonts:
        return ""
    rules = "\n".join(
        f'    .f-{esc(font.get("slug") or slug(font["name"]))} '
        f'{{ font-family: "{esc(font["name"])}", serif; }}'
        for font in fonts)
    return "  <style>\n" + rules + "\n  </style>"


def face_styles(fonts):
    """Load these families, and give each a class that sets it.

    Google's CDN takes every family in one request, which is the difference
    between one stylesheet and twenty-four. Foundry families each bring their
    own stylesheet, or — where they publish none — an @font-face pointing at the
    copy we serve of their own release build.
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

    ours = "\n".join(f"    {face_rule(font)}" for font in fonts
                     if not face_css_of(font) and face_rule(font))
    rules = (ours + "\n" if ours else "") + "\n".join(
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

    # Supporting evidence rather than the answer to "which fonts do this", so a
    # stated cap is right here where removing it would not be. It is bounded by
    # how many font files we have read — 194 today — so it climbs whenever the
    # tier-2 gate widens, and would have passed 200 with nobody touching this.
    shown_implementers, implementers_attrs, implementers_note = capped(
        implementers, 200, "families that run it",
        "ordered by how many rules they give it")
    listed = "\n".join(
        f'      <tr><th scope="row"><a href="{font_href(font)}lookups/">'
        f'{esc(font["name"])}</a></th>'
        f'<td class="mono">{rules:,}</td><td class="mono">{lookups}</td>'
        f'<td class="quiet">{esc(FOUNDRIES.get(font.get("source"), ""))}</td></tr>'
        for font, rules, lookups in shown_implementers)
    # This page already said what it dropped, in better words than the generic
    # note — so it keeps its own sentence and takes only the marker, which is
    # what lets check_site.py notice if the sentence ever goes away. The
    # `cap-note` class is the contract between the two.
    who = ('    <section>\n      <h2 class="eyebrow">Implemented by</h2>\n'
           f'      <table class="index"{implementers_attrs}>\n'
           '        <thead><tr><th>Family</th><th>Rules</th>'
           '<th>Lookups</th><th>Foundry</th></tr></thead>\n'
           f'      <tbody>\n{listed}\n      </tbody>\n      </table>\n'
           f'      <p class="quiet cap-note">{len(implementers):,} of the families whose '
           f'tables we have read run this feature'
           + (f", the {len(shown_implementers)} largest shown."
              if len(implementers) > len(shown_implementers) else ".")
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
    # Only families the browser can actually fetch — from Google, from the
    # foundry's stylesheet, or from the copy of their own release build that we
    # publish where they host none. Before any of that, eleven RIT families were
    # drawn here in whatever the browser fell back to, under their own names: the
    # page asserting a drawing it could not make. A browser test caught it.
    drawable = [font for font in covering if can_draw(font)]
    ordered = sorted(drawable, key=lambda f: (f.get("tier") != "measured",
                                              f["name"].lower()))
    # Every family that covers this codepoint gets a tile. The first
    # DRAWN_LIMIT arrive with their faces in the markup, so a reader with
    # JavaScript off sees those drawn and the rest listed by name — the same
    # thing they saw before, plus everything they could not reach.
    #
    # The rest carry what a face needs and are drawn as they are scrolled to.
    # Deliberately *not* their `data-face`: until a face is injected the tile has
    # not been drawn by this family, and the fallback marking in app.js would
    # otherwise mark every one of them as failed the moment the page loaded.
    # lazyfaces.js sets `data-face` after the face lands, which is the whole
    # safety argument and is why #2 shipped first.
    drawn = ordered[:DRAWN_LIMIT]
    later = ordered[DRAWN_LIMIT:]
    undrawable = len(covering) - len(drawable)

    def tile(font, eager):
        face = face_attrs(font, eager)
        return (f'        <a class="draws" href="{font_href(font)}">'
                f'<span class="tile-glyph f-{esc(font.get("slug") or slug(font["name"]))}"'
                f'{face}>{esc(ch)}</span>'
                f'<span class="draws-name">{esc(font["name"])}</span></a>')

    tiles = "\n".join([tile(font, True) for font in drawn]
                      + [tile(font, False) for font in later])
    faces = face_styles(drawn) + "\n" + lazy_face_styles(later)
    # What the grid dropped, said out loud: twenty-four tiles where nine hundred
    # families have the character would otherwise read as "twenty-four have it".
    # Every drawable family is now on the page, so the note is no longer about
    # what was dropped — nothing is — but about what has been *drawn* so far.
    # A tile still in the page font is not a drawing by the family it names, and
    # lazyfaces.js rewrites this line while the faces arrive.
    drawn_note = (f"All {len(drawable):,} indexed families that cover this codepoint and "
                  "can be loaded, measured ones first."
                  + (f" The first {len(drawn)} are drawn as this page loads; the rest arrive "
                     "as you scroll, because each one is a webfont."
                     if later else ""))
    if undrawable:
        drawn_note += (f" A further {undrawable:,} cover it but publish no webfont we can "
                       "load or re-serve, so they cannot be drawn here — their coverage "
                       "still comes from their own font tables.")

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
        <p class="quiet" data-drawn-note="{esc(drawn_note)}">{drawn_note}
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
        for font, n in covering)

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


# What the characters of a script divide into, for a reader who wants to see the
# alphabet rather than a codepoint range. Unicode's own general categories, not
# a grouping of ours — a linguistic one would be ours to defend and could not be
# checked against anything.
CHAR_GROUPS = [
    ("Letters", ("Lo", "Lu", "Ll", "Lt", "Lm")),
    ("Marks", ("Mn", "Mc", "Me")),
    ("Digits", ("Nd", "Nl", "No")),
    ("Signs and punctuation", ("Po", "Pd", "Ps", "Pe", "Pi", "Pf", "Pc", "Sk", "So", "Sm")),
]


def script_alphabet(script, chars_built, faces=""):
    """The script's own characters, grouped, on the script's own page.

    Reaching these used to mean language, then script, then a font, then that
    font's glyph list — four clicks to see an alphabet, ending in one long list
    of a single family's glyphs. They belong here.
    """
    import unicodedata

    found = {label: [] for label, _cats in CHAR_GROUPS}
    for block in script["blocks"]:
        for first, last in block["ranges"]:
            for cp in range(first, last + 1):
                try:
                    unicodedata.name(chr(cp))
                except ValueError:
                    continue
                category = unicodedata.category(chr(cp))
                for label, categories in CHAR_GROUPS:
                    if category in categories:
                        found[label].append(cp)
                        break

    sections = []
    for label, _categories in CHAR_GROUPS:
        cps = found[label]
        if not cps:
            continue
        # A mark drawn on its own is a mark floating in space, so it is shown on
        # a dotted circle — which is what the shaper does with it anyway.
        base = "◌" if label == "Marks" else ""
        tiles = "".join(
            '<span class="tile">'
            + (f'<a href="{link(f"/char/{cp:04X}/")}">{esc(base + chr(cp))}</a>'
               if cp in chars_built else esc(base + chr(cp)))
            + "</span>"
            for cp in cps)
        sections.append(f'      <h3 class="group">{esc(label)} '
                        f'<span class="quiet mono">{len(cps)}</span></h3>\n'
                        f'      <div class="tiles alphabet">{tiles}</div>')

    if not sections:
        return ""
    return ('    <section>\n      <h2 class="eyebrow">The characters</h2>\n'
            + "\n".join(sections)
            + '\n      <p class="quiet">Every assigned character of the script, in Unicode\'s '
              'own categories rather than a grouping of ours — ours could not be checked '
              'against anything. Combining marks are shown on a dotted circle, which is what '
              'a shaper does with a mark that has no base. Each links to the character, where '
              'every indexed family draws it.</p>\n    </section>')


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
    shown_langs, _langs_attrs, langs_note = capped(
        sorted(written_by, key=lambda l: l["name"].lower()), 60,
        "languages written in it", "alphabetical")
    langs_html = "".join(
        f'<li><a href="{link("/lang/" + lang["id"] + "/")}">{esc(lang["name"])}</a></li>'
        for lang in shown_langs)

    families = "\n".join(
        f'      <tr><th scope="row"><a href="{font_href(font)}">{esc(font["name"])}</a></th>'
        f'<td class="mono">{cov["covered"]}/{cov["chars"]}</td>'
        f'<td class="quiet">{esc(" · ".join(font.get("tags") or []) or "not read")}</td>'
        f'<td class="quiet">{esc(FOUNDRIES.get(font.get("source"), ""))}</td></tr>'
        for font, cov in ranked)

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

{script_alphabet(script, chars_built)}

    <section>
      <h2 class="eyebrow">Written by</h2>
      {f'<ul class="links">{langs_html}</ul>' if langs_html
        else '<p class="quiet">No language in the index is recorded as using it.</p>'}
{langs_note}
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


def made_for(font, script, blocks):
    """Is this face built for this script, or does it merely also cover it?

    A family whose own dominant block belongs to the script was drawn for it. A
    pan-Unicode workhorse that happens to include the block is a different
    answer to "what should I set this in", and ranking them together is what
    made the old list useless.
    """
    if not script:
        return False
    dominant = dominant_block(font, blocks)
    return bool(dominant and dominant[0] in {b["name"] for b in script["blocks"]})


def specimen_for(language, exemplars):
    """A few real words of the language, for a card to be set in.

    The UDHR sample is actual prose in the language, which is what a reader
    wants to judge — better than the alphabet, and far better than lorem.
    """
    sample = (language.get("sample") or "").replace("\n", " ").strip()
    words = [word for word in sample.split(" ") if word][:3]
    if words:
        return " ".join(words)
    letters = [ch for ch in exemplars if not ch.isspace()][:8]
    return "".join(letters)


def lang_page(language, fonts, scripts, chars_built, blocks=(), coverage=None):
    """One language: what it needs written down, and what can write it."""
    exemplars = language.get("exemplars") or ""
    sample = (language.get("sample") or "").strip()

    # The scripts in the language's own order. SIL marks the default by giving
    # the bare tag its script, so the first is the one the language is normally
    # written in — sorting these alphabetically is how Hindi ended up "written
    # in Braille, Devanagari, Latin".
    by_code = {script["code"]: script for script in scripts}
    used = [by_code[code] for code in (language.get("scripts") or []) if code in by_code]
    main = used[0] if used else None

    fits, partial = [], []
    if exemplars:
        needs = exemplar_needs(exemplars)
        wanted = {cp for cp, _pieces in needs}
        for font in fonts:
            if not font.get("ranges"):
                continue
            covered = (coverage or {}).get(id(font))
            if covered is None:
                covered = covered_subset(font, wanted)
            gaps = language_fit(needs, covered)
            (fits if not gaps else partial).append((font, gaps))

    # Faces drawn for the script first, then by name. "Which font should I use"
    # is answered by a family built for the writing system, not by whichever
    # pan-Unicode face sorts earliest.
    fits.sort(key=lambda row: (not made_for(row[0], main, blocks),
                               row[0]["tier"] != "measured",
                               row[0]["name"].lower()))

    # Near misses only. A Latin face missing all 67 Devanagari exemplars is not
    # a near miss, and listing it above the families that work — which is what
    # sorting purely by gap count did — is worse than not listing it at all.
    needed = len([ch for ch in exemplars if not ch.isspace()])
    threshold = max(1, round(needed * 0.25))
    near = sorted((row for row in partial if len(row[1]) <= threshold),
                  key=lambda row: (len(row[1]), row[0]["name"].lower()))
    unsuitable = len(partial) - len(near)

    specimen = specimen_for(language, exemplars)
    # Same cap and the same fix as the character grid: every family that covers
    # the exemplars gets a card, the first CARDS_LIMIT arrive with their faces in
    # the markup, and the rest load as they are scrolled to. "Showing 36 of 59
    # families" is not an answer to "what can I set Hindi in".
    shown = fits[:CARDS_LIMIT]
    later_cards = fits[CARDS_LIMIT:]
    cards = "\n".join(
        f'        <a class="card" href="{font_href(font)}">'
        f'<span class="card-specimen f-{esc(font.get("slug") or slug(font["name"]))}"'
        f'{face_attrs(font, at < CARDS_LIMIT)}>{esc(specimen)}</span>'
        f'<span class="card-name">{esc(font["name"])}</span>'
        f'<span class="card-note quiet">'
        + ("built for " + esc(main["name"]) if made_for(font, main, blocks)
           else esc(FOUNDRIES.get(font.get("source"), "")))
        + "</span></a>"
        for at, (font, _gaps) in enumerate(fits))
    faces = (face_styles([font for font, _gaps in shown]) + "\n"
             + lazy_face_styles([font for font, _gaps in later_cards]))

    cards_note = (
        f"All {len(fits):,} families that cover every exemplar character, the ones drawn "
        f"for {main['name'] if main else 'the script'} first."
        + (f" The first {len(shown)} are drawn as this page loads; the rest arrive as you "
           "scroll, because each one is a webfont." if later_cards else "")
        + " Each is set in real words of the language, drawn by your browser from that "
          "family's own distribution. Covering the characters is not the same as shaping "
          "them correctly — the family's own page carries that.")

    tiles = "".join(
        f'<span class="tile">' +
        (f'<a href="{link(f"/char/{ord(ch):04X}/")}">{esc(ch)}</a>'
         if ord(ch) in chars_built else esc(ch)) + "</span>"
        for ch in exemplars if not ch.isspace())

    script_links = " ".join(
        f'<a href="{link("/script/" + s["code"] + "/")}">{esc(s["name"])}</a>' for s in used)

    # Near misses are context for the families that do fit, not the answer, so
    # this table keeps its cap and says so.
    shown_near, near_attrs, near_note = capped(near, 40, "near misses", "closest first")
    nearly = "\n".join(
        f'      <tr><th scope="row"><a href="{font_href(font)}">{esc(font["name"])}</a></th>'
        f'<td class="mono">{len(gaps)}</td>'
        f'<td class="glyph-small">{esc("".join(gaps[:12]))}</td></tr>'
        for font, gaps in shown_near)

    body = f"""    <section class="entity-head">
      <h1>{esc(language["name"])}</h1>
      <p class="byline">{esc(language.get("tag") or "")} ·
         ISO 639-3 <span class="mono">{esc(language.get("iso") or "")}</span></p>
      <div class="facts">
{fact(needed, "exemplar characters")}
{fact(f"{len(fits):,}", "families that fit")}
{fact(f"{sum(1 for font, _g in fits if made_for(font, main, blocks)):,}",
      f"built for {main['name'] if main else 'the script'}")}
{fact(len(used), "scripts it is written in")}
      </div>
      <p class="quiet">Written in {script_links or "a script not in the index"} — the first is
         the one SIL records as the default, and the rest are real alternatives rather than
         curiosities. A language is not a script: several may write the same one, and one
         language may be written in several.</p>
    </section>

    <section>
      <h2 class="eyebrow">Set in the families that fit</h2>
      <div class="cards">
{cards or '        <p class="quiet">No indexed family covers this exemplar set.</p>'}
      </div>
      <p class="quiet" data-drawn-note="{esc(cards_note)}">{esc(cards_note)}</p>
    </section>

    <section>
      <h2 class="eyebrow">What it needs</h2>
      <div class="tiles">{tiles or '<span class="quiet">No exemplar set in SLDR for this language yet.</span>'}</div>
      <p class="quiet">The exemplar characters SIL's SLDR records for this language — what
         ordinary text in it actually requires, rather than a whole block.</p>
    </section>

    {'<section><h2 class="eyebrow">A line of it</h2><p class="specimen-small">'
     + esc(sample.split(chr(10))[0][:200]) + '</p>'
     '<p class="quiet">From the Universal Declaration of Human Rights.</p></section>'
     if sample else ''}

    <section>
      <h2 class="eyebrow">Nearly fits</h2>
      <table class="index"{near_attrs}>
        <thead><tr><th>Family</th><th>Missing</th><th>Which characters</th></tr></thead>
      <tbody>
{nearly or '      <tr><td colspan="3" class="quiet">Nothing came close without fitting.</td></tr>'}
      </tbody>
      </table>
{near_note}
      <p class="quiet">Families missing no more than {threshold} of the {needed} exemplar
         characters, and which ones they drop to a fallback face. Naming them is the useful
         part: one absent letter is a different problem from twenty.
         {f"{unsuitable:,} further families cover some of the set but not enough of it to be "
          "a near miss — a Latin face missing every Devanagari letter is not a candidate."
          if unsuitable else ""}</p>
    </section>
"""
    return page(language["name"], body, kind="language",
                code=language.get("tag") or language.get("iso"),
                description=f"{language['name']}: the families that can set it, its exemplar "
                            f"characters, and the scripts it is written in.",
                extra_head=faces)


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

# Writing a page is a millisecond of work and nineteen of waiting on the disk,
# and there are 33,000 of them. Threads do nothing for CPU-bound Python, but each
# of these releases the GIL inside the write: eight workers turned six minutes of
# writing into fifty seconds, and this was the longest step in the build.
WRITE_WORKERS = 16
BATCH = 2000


def write_many(pages, label):
    """Write (path, markup) pairs in parallel, in batches.

    Batched so the whole site — 144 MB of HTML — is never held in memory at once
    just to hand it to a pool.
    """
    written = 0
    batch = []

    def flush():
        nonlocal written
        if not batch:
            return
        with ThreadPoolExecutor(max_workers=WRITE_WORKERS) as pool:
            list(pool.map(lambda pair: write(*pair), batch))
        written += len(batch)
        batch.clear()

    for pair in pages:
        batch.append(pair)
        if len(batch) >= BATCH:
            flush()
    flush()
    print(f"  wrote {written:,} {label}")
    return written


def write_json(name, payload):
    """A data file the browser reads, beside the pages."""
    out = os.path.join(OUT_SITE, "data")
    os.makedirs(out, exist_ok=True)
    with io.open(os.path.join(out, name), "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))


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
    prepare_fonts(fonts["fonts"], blocks)

    # core.js goes out too: Inspect imports it at runtime to read the same
    # Unicode tables the build reads, so a codepoint's facts there and on its
    # own page come from one place.
    for asset in ("style.css", "app.js", "copy.js", "core.js", "inspect.js", "tryit.js",
                  "lazyfaces.js", "facecheck.js"):
        shutil.copyfile(os.path.join(ROOT, "web", asset), os.path.join(OUT_SITE, asset))

    # The one thing we serve that we did not write: a foundry's own woff2 build,
    # copied unmodified, with the licence that permits it beside it. gen_index
    # decides what may be here; this only moves it.
    source = os.path.join(ROOT, "web", "webfonts")
    if os.path.isdir(source):
        shutil.copytree(source, os.path.join(OUT_SITE, "webfonts"), dirs_exist_ok=True)

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

    def family_pages():
        for font in fonts["fonts"]:
            yield (f"/font/{font['slug']}/", font_page(font, blocks))
            if font.get("tables"):
                yield (f"/font/{font['slug']}/lookups/", lookups_page(font))
            if font.get("glyphs"):
                yield (f"/font/{font['slug']}/glyphs/", glyphs_page(font, chars_built))
            # A family the foundry and Google name differently lives at the
            # foundry's name, because the font's own tables outrank a
            # distributor's rename — that is the argument this whole site makes.
            # But /font/charis-sil/ was a real URL yesterday, so it stays one.
            for other, moved in moved_slugs(font):
                yield (f"/font/{moved}/", moved_page(other, font))

    write_many(family_pages(), "family pages, with lookups and glyphs where measured")
    write("/fonts/", fonts_index(fonts["fonts"], blocks))

    # Features: one page each for every tag any indexed family runs, plus the
    # ones we have written about.
    content = feature_content()
    tags = {row["feature"] for font in fonts["fonts"]
            for table in ("gsub", "gpos")
            for row in (font.get("tables") or {}).get(table, [])}
    tags |= set(content.get("features") or {})
    tags |= set(content.get("stages") or [])
    write_many(((f"/feature/{tag}/", feature_page(tag, content, fonts["fonts"]))
                for tag in sorted(tags)), "feature pages")

    import bisect
    import unicodedata

    # Bisected, not scanned: "which block is this codepoint in" asked 33,000
    # times against 327 blocks is ten million comparisons for no reason.
    starts = [block[0] for block in blocks]

    def char_pages():
        for cp in sorted(chars_built):
            at = bisect.bisect_right(starts, cp) - 1
            block = blocks[at] if at >= 0 and blocks[at][1] >= cp else None
            yield (f"/char/{cp:04X}/",
                   char_page(cp, unicodedata.name(chr(cp)), block,
                             covering_fonts.get(cp, []), chars_built))

    write_many(char_pages(), "character pages")

    write_many(((f"/block/{slug(block[2])}/",
                 block_page(block, fonts["fonts"], chars_built)) for block in blocks),
               "block pages")

    write_many(((f"/script/{script['code']}/",
                 script_page(script, fonts["fonts"], languages, chars_built))
                for script in scripts), "script pages")
    write("/scripts/", scripts_index(scripts, fonts["fonts"]))

    # Every codepoint any exemplar set needs, and which fonts have them —
    # computed once for all languages rather than re-walking every font's
    # ranges for every exemplar of every language.
    wanted = set()
    for language in languages:
        wanted |= {cp for cp, _pieces in exemplar_needs(language.get("exemplars") or "")}
    coverage = {id(font): covered_subset(font, wanted) for font in fonts["fonts"]}

    write_many(((f"/lang/{language['id']}/",
                 lang_page(language, fonts["fonts"], scripts, chars_built, blocks, coverage))
                for language in languages), "language pages")
    write("/languages/", languages_index(languages))
    write("/compare/", compare_page(fonts["fonts"]))
    write("/inspect/", inspect_page())

    # Inspect reads the same Unicode tables the build does, so they are
    # served: the block ranges, the formulaic name ranges, and the name
    # table itself, which is 1.4 MB and fetched only when a name is asked
    # for.
    # What Inspect needs beyond the Unicode tables: which families cover each
    # block, and the sequences we have authored notes and verdicts for.
    write_json("block-faces.json", block_faces(fonts["fonts"], blocks, assigned))
    shutil.copyfile(os.path.join(ROOT, "web", "content", "sequences.json"),
                    os.path.join(OUT_SITE, "data", "sequences.json"))
    for table in ("blocks.json", "names.txt", "names-formulaic.json", "props.json"):
        source = os.path.join(ROOT, "web", "data", table)
        if os.path.exists(source):
            os.makedirs(os.path.join(OUT_SITE, "data"), exist_ok=True)
            shutil.copyfile(source, os.path.join(OUT_SITE, "data", table))

    # One small file per measured family, for Compare and for the Try it panel's
    # coverage marking. It was written only for families with lookup tables,
    # which left Try it fetching a 404 on every other family and falling back to
    # "we could not load the coverage list" — for families whose ranges we had
    # all along. The site checker found it. A family with no tables carries only
    # its ranges here, which is a few hundred bytes.
    out = os.path.join(OUT_SITE, "data", "font")
    os.makedirs(out, exist_ok=True)
    written = 0
    for font in fonts["fonts"]:
        if font.get("tier") != "measured":
            continue
        with io.open(os.path.join(out, f"{font['slug']}.json"), "w", encoding="utf-8") as handle:
            json.dump(font_data(font), handle, ensure_ascii=False, separators=(",", ":"))
        written += 1
    print(f"  wrote per-family data for {written} families")
    measured = sum(1 for f in fonts["fonts"] if f.get("tier") == "measured")
    print(f"  {len(fonts['fonts']):,} families — {measured:,} measured, "
          f"{len(fonts['fonts']) - measured:,} not yet")


if __name__ == "__main__":
    main()
