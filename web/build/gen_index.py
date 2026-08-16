"""Build the site's data files: which public font covers what, and sample text.

    python web/build/gen_index.py             # everything, ~10 minutes
    python web/build/gen_index.py --limit 40  # a slice, for development

Writes web/data/*.json. It reads JSON, XML and CSS, and **never a font file**:
Google publishes each family's coverage as codepoint ranges, so the whole Google
corpus costs small metadata fetches and no downloads at all. Every other foundry
is indexed by name, licence and where to get it — its coverage stays unmeasured
until someone runs the desktop companion against a font they already have, which
is the only place a font binary is ever opened.

An unmeasured family says so on the page. That is the honest state; a guessed
range would not be.
"""
import argparse
import collections
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "shared"))
import langs  # noqa: E402

GF_LIST = "https://fonts.google.com/metadata/fonts"
GF_FAMILY = "https://fonts.google.com/metadata/fonts/{family}"
GF_SPECIMEN = "https://fonts.google.com/specimen/{slug}"
UDHR_INDEX = "https://raw.githubusercontent.com/unicode-org/udhr/main/data/udhr/index.xml"
UDHR_TEXT = "https://raw.githubusercontent.com/unicode-org/udhr/main/data/udhr/udhr_{f}.xml"
GITHUB_REPOS = "https://api.github.com/orgs/{org}/repos?per_page=100&page={page}"
GITLAB_PROJECTS = "https://gitlab.com/api/v4/groups/{group}/projects?per_page=100&page={page}"

# The foundries worth indexing beside Google. Google is handled separately —
# it publishes coverage directly. These four are listed by name and licence so
# the family is findable and its "Use it" snippet can point at a stylesheet the
# foundry actually serves; the numbers come later, from the companion.
#
# Deliberately not here, and the reasons are the point: Last Resort has a glyph
# for every codepoint in Unicode, all of them placeholder boxes, so indexing it
# would put a font that draws nothing at the top of every answer. STIX is
# already carried by Google as STIX Two. Liberation publishes no built
# binaries. Source Han is an 80 MB .ttc for CJK that Noto already covers.
SOURCES = [
    {"id": "sil", "host": "github", "org": "silnrsi", "prefix": "font-",
     "page": "https://github.com/silnrsi/{project}/releases/latest",
     # silnrsi/font-* is mostly fonts, but not entirely — these are tooling,
     # tests and proposals.
     "skip": {"font-ttf", "font-ttf-scripts", "font-arab-tools", "font-keymanweb-osk",
              "font-lcg", "font-line-spacing-test", "font-stroke-test", "font-symchar",
              "font-sympub", "font-bloom-show-inv", "font-leke-proposal"}},
    # Swathanthra Malayalam Computing — Manjari, Gayathri, Meera, Rachana.
    # Their own site lists every family as a stylesheet, which is both more
    # complete than their GitLab releases and, now, the only thing we need.
    {"id": "smc", "host": "css", "index": "https://smc.org.in/css/fonts.css",
     "base": "https://smc.org.in", "page": "https://smc.org.in/fonts/#/{project}",
     "skip": set()},
    # Rachana Institute of Typography — RIT Rachana, Panmana.
    {"id": "rit", "host": "gitlab", "group": "rit-fonts",
     "page": "https://gitlab.com/rit-fonts/{project}",
     "skip": {"malayalam-shaping", "texbook-inside-out", "texsynhl", "tnjoy",
              "arsenal-math", "Sayahna-font"}},
    # Long-running libre families with no Google Fonts entry: broad Latin and
    # symbol coverage (DejaVu), scholarly and medieval Latin (Junicode), and the
    # maths faces a typesetter reaches for (Libertinus, XITS).
    {"id": "libre", "host": "github-repos", "skip": set(),
     "page": "https://github.com/{project}/releases/latest",
     "repos": ["dejavu-fonts/dejavu-fonts", "psb1558/Junicode-font",
               "alerque/libertinus", "aliftype/xits", "rastikerdar/vazirmatn"]},
]

OUT_DATA = os.path.join(ROOT, "web", "data")
HEADERS = {"User-Agent": "glyph-sleuth-index/1.0 (+https://github.com/beniza/glyph-sleuth)"}


def fetch(url, token=None):
    request = urllib.request.Request(url, headers=dict(HEADERS))
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def fetch_text(url, token=None):
    return fetch(url, token).decode("utf-8", "replace")


def loads(body):
    """JSON, minus Google's anti-hijacking guard: )]}'

    Without this every family fetch fails with "Expecting value: line 1".
    """
    return json.loads(body.lstrip(")]}'\n "))


def fetch_json(url, token=None):
    return loads(fetch_text(url, token))


def in_parallel(items, work, label):
    """Map work over items, keeping going when one item fails."""
    results = []
    with ThreadPoolExecutor(max_workers=16) as pool:
        for done, result in enumerate(pool.map(work, items), 1):
            if result is not None:
                results.append(result)
            if done % 50 == 0 or done == len(items):
                print(f"  {label}: {done}/{len(items)}", end="\r", flush=True)
    print(f"  {label}: {len(results)}/{len(items)} ok    ")
    return results


# ------------------------------------------------------------------- ranges

def ranges_from(codepoints):
    """Sorted codepoints -> [[first, last], ...], the form the client bisects."""
    out = []
    for cp in sorted(codepoints):
        if out and cp == out[-1][1] + 1:
            out[-1][1] = cp
        else:
            out.append([cp, cp])
    return out


def parse_google_ranges(coverage):
    """Google's "32-126,160-255,8470" per subset -> merged [[first, last], ...]."""
    codepoints = set()
    for spec in coverage.values():
        for part in spec.split(","):
            if not part:
                continue
            first, _, last = part.partition("-")
            codepoints.update(range(int(first), int(last or first) + 1))
    return ranges_from(codepoints)


# ------------------------------------------------------------------- google

# What Google calls a licence, and what a designer would call it.
GOOGLE_LICENCES = {"ofl": "OFL", "apache2": "Apache 2.0", "ufl": "UFL"}


def google_families(limit=None):
    families = fetch_json(GF_LIST)["familyMetadataList"]
    families.sort(key=lambda f: f["family"])
    return families[:limit] if limit else families


def google_record(meta, detail):
    """One family, from Google's list entry and its metadata detail.

    Split from the fetch so the record's shape is testable without a network.
    """
    coverage = detail.get("coverage")
    if not coverage:
        return None
    name = meta["family"]
    slug = name.replace(" ", "+")
    licence = detail.get("license") or ""
    return {
        "name": name,
        "ranges": parse_google_ranges(coverage),
        "source": "google",
        "licence": GOOGLE_LICENCES.get(licence, licence.upper()),
        "category": meta.get("category") or "",
        "designers": meta.get("designers") or [],
        # Weights and styles, so a specimen can be set in more than one face.
        "faces": [f.replace(name, "").strip() or "Regular" for f in (detail.get("fonts") or {})],
        "url": GF_SPECIMEN.format(slug=slug),
        "css": f"https://fonts.googleapis.com/css2?family={slug}",
        "tier": "measured",
    }


def google_font(meta):
    try:
        detail = fetch_json(GF_FAMILY.format(family=urllib.parse.quote(meta["family"])))
    except Exception as error:
        print(f"  !! {meta['family']}: {error}")
        return None
    return google_record(meta, detail)


# ------------------------------------------------------------- the foundries

def squash(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


# Suffixes a foundry adds to a name Google spells shorter (or the reverse):
# Charis / Charis SIL, Gentium Book / Gentium Book Plus. Anything else that
# merely shares a prefix is a different family — Meera and Meera Inimai are not
# the same font, and hiding one behind the other would be a wrong answer.
FAMILY_SUFFIXES = {"sil", "plus", "lolo", "alu", "wsp", "vf"}


def same_family(a, b):
    if a == b:
        return True
    long, short = (a, b) if len(a) > len(b) else (b, a)
    return long.startswith(short) and long[len(short):] in FAMILY_SUFFIXES


CSS_URL = re.compile(r"""url\(\s*["']?([^"')]+)""")
CSS_FAMILY = re.compile(r"""font-family\s*:\s*["']?([^"';}]+)""")


def family_from_stylesheet(sheet):
    """The family name a foundry's own @font-face declares, or None.

    Read from the stylesheet rather than guessed from the filename: smc's
    `manjari.css` declares "Manjari", but the two do not always agree, and the
    name is what every link, search and CSS snippet is keyed on.
    """
    found = CSS_FAMILY.search(sheet)
    return found.group(1).strip() if found else None


def foundry_record(name, source, page, css=None, licence=""):
    """A family we know exists but have not measured.

    No ranges, and `tier` says why: opening the font is the companion's job, on
    a contributor's own machine. Until then the page says "not measured yet"
    rather than implying a coverage we never computed.
    """
    return {
        "name": name,
        "ranges": [],
        "source": source,
        "licence": licence,
        "category": "",
        "designers": [],
        "faces": [],
        "url": page,
        "css": css,
        "tier": "stub",
    }


def projects(source, token=None):
    """Every font project a foundry publishes, so new releases need no edit."""
    if source["host"] == "github-repos":
        return sorted(source["repos"])

    if source["host"] == "css":
        sheet = fetch_text(source["index"])
        found = [os.path.basename(u).rsplit(".css", 1)[0]
                 for u in CSS_URL.findall(sheet) if u.endswith(".css")]
        return sorted(p for p in found if p not in source["skip"])

    found = []
    for page in (1, 2, 3):
        if source["host"] == "github":
            batch = fetch_json(GITHUB_REPOS.format(org=source["org"], page=page), token)
            found += [r["name"] for r in batch]
        else:
            group = urllib.parse.quote(source["group"], safe="")
            batch = fetch_json(GITLAB_PROJECTS.format(group=group, page=page))
            found += [p["path"] for p in batch]
        if len(batch) < 100:
            break
    prefix = source.get("prefix", "")
    return sorted(p for p in found if p.startswith(prefix) and p not in source["skip"])


def foundry_family(source, project):
    """One indexed family from a foundry project — metadata only.

    For a foundry that publishes its own stylesheet we read the family name out
    of it, which also gives the "Use it" snippet a real URL to point at. For the
    rest, the repository name is the best handle we have without opening a font,
    and the companion will correct it when it measures the family.
    """
    page = source["page"].format(project=project)
    if source["host"] == "css":
        css = f"{source['base']}/fonts/{project}.css"
        try:
            name = family_from_stylesheet(fetch_text(css))
        except Exception:
            return None
        if not name:
            return None
        return foundry_record(name, source["id"], page, css=css)

    name = project.split("/")[-1].replace("font-", "").replace("-", " ").title()
    return foundry_record(name, source["id"], page)


# ----------------------------------------------------------------- languages

# Where UDHR ships several translations of one language and only one is the
# right sample, name the file to keep. Malayalam: the chillu-encoded text, which
# uses the atomic chillu characters a modern font is expected to have.
PREFERRED = {"mal": "mal_chillus"}


def udhr_languages(limit=None):
    """The UDHR translation list: our language menu, and our sample text."""
    root = ET.fromstring(fetch(UDHR_INDEX))
    entries = []
    for node in root:
        if node.get("stage") not in ("4", "5") or not node.get("iso639-3"):
            continue
        iso = node.get("iso639-3")
        if iso in PREFERRED and node.get("f") != PREFERRED[iso]:
            continue
        # Some entries carry bcp47='und'; the ISO 639-3 code is the real handle.
        bcp47 = node.get("bcp47")
        entries.append({
            # Several translations share a language tag (two Catalans, two
            # Crioulos), so the UDHR file id is the stable key.
            "id": node.get("f"),
            "tag": bcp47 if bcp47 and bcp47 != "und" else node.get("iso639-3"),
            "iso": node.get("iso639-3"),
            "script": node.get("iso15924") or "",
            "name": re.sub(r"\s*\(\d+\)$", "", node.get("n") or ""),
            "dir": node.get("dir") or "ltr",
        })
    entries.sort(key=lambda e: e["name"])
    return entries[:limit] if limit else entries


def strip_tags(tag):
    return re.sub(r"\{[^}]*\}", "", tag)


def udhr_sample(entry, paragraphs=3):
    """Article 1 and its neighbours — enough text to judge a face, not a book."""
    try:
        root = ET.fromstring(fetch(UDHR_TEXT.format(f=entry["id"])))
    except Exception:
        return None
    text = [node.text.strip() for node in root.iter()
            if strip_tags(node.tag) == "para" and node.text and node.text.strip()]
    return "\n\n".join(text[:paragraphs]) or None


def language(entry):
    entry = dict(entry)
    entry["sample"] = udhr_sample(entry)
    try:
        # Exemplars are what the language actually needs; the sample is only prose.
        entry["exemplars"] = "".join(sorted(langs.required(entry["tag"])))
    except Exception:
        entry["exemplars"] = ""
    if not entry["sample"] and not entry["exemplars"]:
        return None
    return entry


def disambiguate(languages):
    """UDHR ships more than one translation for some languages, and two rows
    reading "Malayalam" is a puzzle, not a choice.

    Identical texts are dropped. Ones that genuinely differ are kept and
    qualified from their UDHR file id — Malayalam has a chillu-encoded variant,
    German has both orthographies — because for a coverage tool that difference
    is the whole point: the chillu text needs characters the other doesn't.
    """
    kept, seen = [], set()
    for lang in sorted(languages, key=lambda l: (l["name"], len(l["id"]))):
        key = (lang["iso"], lang["script"], lang.get("sample"), lang.get("exemplars"))
        if key in seen:
            continue
        seen.add(key)
        kept.append(lang)

    # Sorted by shortest id first, so the canonical translation keeps the plain
    # name and only the variants carry a qualifier.
    seen_name = collections.Counter()
    for lang in kept:
        seen_name[lang["name"]] += 1
        if seen_name[lang["name"]] == 1:
            continue
        _, _, suffix = lang["id"].partition("_")
        named = suffix and (len(suffix) > 2 or not suffix.isdigit())
        lang["name"] += f" ({suffix.replace('_', ' ') if named else seen_name[lang['name']]})"
    return sorted(kept, key=lambda l: l["name"])


# ------------------------------------------------------------------ scripts

# Scripts nobody writes a living language in still belong in the index — they are
# exactly what a font hunt for a historic text needs — but these are not scripts
# at all in the sense the app means.
NOT_SCRIPTS = {"Zyyy", "Zinh", "Zzzz", "Zsym", "Zxxx", "Qaai"}


def ucd_module():
    import ucd
    return ucd


def script_names():
    """ISO 15924 code -> the name the regex engine knows it by (Mlym -> Malayalam)."""
    names = {}
    for (kind, value), label in ucd_module().VALUE_NAMES.items():
        if kind == "sc" and len(value) == 4:
            names[value.title()] = label
    return names


def script_blocks(engine_name):
    """[(block, ranges, chars)] for every UCD block this script appears in.

    A script is not one block: Devanagari takes three, Tamil two, Arabic nine —
    which is exactly the thing a font can cover half of. The ranges travel to the
    client so it can measure any font against any block without another download.
    """
    import regex

    matcher = regex.compile(r"\p{Script=%s}" % engine_name)
    out = []
    for lo, hi, name in ucd_module().BLOCKS:
        if lo > 0x2FFFF:
            break
        found = [cp for cp in range(lo, hi + 1) if matcher.fullmatch(chr(cp))]
        if found:
            out.append((name, ranges_from(found), len(found)))
    return out


def script_index(languages):
    """Every script SIL records a language for, with where it lives in Unicode.

    ponytail: the codespace scan is the slow part (a minute or so for ~150
    scripts). It runs once per build, not once per visitor.
    """
    names = script_names()
    used = collections.defaultdict(list)
    for lang in languages:
        for code in lang.get("scripts", ()):
            used[code].append(lang["id"])

    out = []
    for code in sorted(used):
        engine_name = names.get(code)
        if not engine_name:
            continue
        blocks = script_blocks(engine_name)
        if not blocks:
            continue
        out.append({
            "code": code,
            "name": engine_name.replace("_", " "),
            "blocks": [{"name": name, "ranges": ranges, "chars": chars}
                       for name, ranges, chars in blocks],
            "chars": sum(count for _name, _ranges, count in blocks),
            "languages": sorted(used[code]),
        })
    return out


def scripts_for(tags):
    """{language: [script codes]} from SIL langtags, the default script first.

    langtags marks the default by giving the bare tag its script: `ml` is Mlym,
    and `ml-Arab` is the other way Malayalam is written. Alphabetical order would
    open Malayalam on Arabic, which is a true fact told in the wrong order.
    """
    found = collections.defaultdict(set)
    primary = {}
    for tag in tags:
        if not tag.script or tag.script in NOT_SCRIPTS:
            continue
        base = tag.tag.split("-")[0]
        found[base].add(tag.script)
        if tag.tag == base:
            primary[base] = tag.script
    return {base: ([primary[base]] if base in primary else [])
                  + sorted(codes - {primary.get(base)})
            for base, codes in found.items()}


# ------------------------------------------------------- names and blocks

def write_blocks():
    """The UCD blocks, straight out of the vendored table the companion uses."""
    ucd = ucd_module()
    write(os.path.join(OUT_DATA, "blocks.json"),
          {"unicode": ucd.UNICODE_VERSION,
           "blocks": [[lo, hi, name] for lo, hi, name in ucd.BLOCKS]})


def write_names():
    """cp<TAB>NAME per line, minus the ~100k characters whose name is a formula.

    CJK ideographs and their kin are named PREFIX-<hex>, so the client can derive
    those from a range list and we keep the download to the names that are real.
    """
    import unicodedata
    lines, formulaic, run = [], [], None
    for cp in range(0x110000):
        try:
            name = unicodedata.name(chr(cp))
        except ValueError:
            run = None
            continue
        prefix, _, suffix = name.rpartition("-")
        if prefix and suffix == f"{cp:04X}":
            if run and run[0] == prefix and run[2] == cp - 1:
                run[2] = cp
            else:
                run = [prefix, cp, cp]
                formulaic.append(run)
            continue
        run = None
        lines.append(f"{cp:X}\t{name}")
    path = os.path.join(OUT_DATA, "names.txt")
    with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines))
    print(f"  wrote {path} — {os.path.getsize(path) / 1e6:.1f} MB, {len(lines)} names")
    write(os.path.join(OUT_DATA, "names-formulaic.json"),
          [[p, lo, hi] for p, lo, hi in formulaic])


def write(path, payload):
    with io.open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
    print(f"  wrote {path} — {os.path.getsize(path) / 1e6:.1f} MB")


# --------------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, help="only this many families and languages")
    parser.add_argument("--google-only", action="store_true", help="skip the foundry listings")
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    os.makedirs(OUT_DATA, exist_ok=True)

    print("Google Fonts")
    families = google_families(args.limit)
    fonts = in_parallel(families, google_font, "coverage")

    for source in [] if args.google_only else SOURCES:
        print(f"{source['id'].upper()} — families Google doesn't carry")
        found = projects(source, token)
        found = found[:args.limit] if args.limit else found
        have = [squash(f["name"]) for f in fonts]
        for font in in_parallel(found, lambda p: foundry_family(source, p), "families"):
            # Already indexed — by Google, or by another project of this family.
            if any(same_family(squash(font["name"]), name) for name in have):
                continue
            fonts.append(font)
            have.append(squash(font["name"]))

    fonts.sort(key=lambda f: f["name"])
    measured = sum(1 for f in fonts if f["tier"] == "measured")
    print(f"  {len(fonts)} families, {measured} measured, {len(fonts) - measured} not yet")
    write(os.path.join(OUT_DATA, "fonts.json"), {"fonts": fonts, "count": len(fonts)})

    print("Unicode tables")
    write_blocks()
    write_names()

    print("Languages (UDHR text + SLDR exemplars)")
    entries = udhr_languages(args.limit)
    languages = disambiguate(in_parallel(entries, language, "languages"))

    # SIL records which scripts each language is written in: Malayalam is not
    # only Mlym but also Arab (Arabi-Malayalam) and Brai.
    by_tag = scripts_for(langs.languages())
    for lang in languages:
        lang["scripts"] = (by_tag.get(lang["tag"].split("-")[0])
                           or by_tag.get(lang["iso"]) or [])
    write(os.path.join(OUT_DATA, "languages.json"),
          {"languages": languages, "count": len(languages)})

    print("Scripts (Unicode blocks each one spans)")
    scripts = script_index(languages)
    print(f"  scripts: {len(scripts)} with "
          f"{sum(len(s['blocks']) for s in scripts)} blocks between them")
    write(os.path.join(OUT_DATA, "scripts.json"),
          {"scripts": scripts, "count": len(scripts)})


if __name__ == "__main__":
    main()
