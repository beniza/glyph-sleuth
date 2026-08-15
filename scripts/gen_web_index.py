"""Build the web app's data files: which public fonts cover what, and sample text.

    python scripts/gen_web_index.py            # everything, ~10 minutes
    python scripts/gen_web_index.py --limit 40 # a slice, for development

Writes web/data/fonts.json and web/data/languages.json, plus web/fonts/*.woff2 for
the faces Google Fonts doesn't carry — SIL, SMC and Rachana. Nothing here reads
your machine: the desktop app answers "which of *my* fonts", this answers "which
freely available font".

ponytail: Google publishes each family's coverage as codepoint ranges, so the
whole Google corpus costs ~2000 small JSON fetches and no font downloads. Only
the other foundries' faces get downloaded and read with fontTools.
"""
import argparse
import collections
import io
import json
import os
import re
import sys
import tarfile
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import langs  # noqa: E402

GF_LIST = "https://fonts.google.com/metadata/fonts"
GF_FAMILY = "https://fonts.google.com/metadata/fonts/{family}"
GF_SPECIMEN = "https://fonts.google.com/specimen/{slug}"
UDHR_INDEX = "https://raw.githubusercontent.com/unicode-org/udhr/main/data/udhr/index.xml"
UDHR_TEXT = "https://raw.githubusercontent.com/unicode-org/udhr/main/data/udhr/udhr_{f}.xml"
GITHUB_REPOS = "https://api.github.com/orgs/{org}/repos?per_page=100&page={page}"
GITHUB_RELEASE = "https://api.github.com/repos/{org}/{project}/releases/latest"
GITHUB_RELEASE_FULL = "https://api.github.com/repos/{project}/releases/latest"
GITLAB_PROJECTS = "https://gitlab.com/api/v4/groups/{group}/projects?per_page=100&page={page}"
GITLAB_RELEASES = "https://gitlab.com/api/v4/projects/{project}/releases"

# The font foundries that publish releases we can read. Google is handled
# separately — it publishes coverage directly, so it needs no downloads at all.
# Everything here ships built fonts in a release archive: take the upright face,
# read its cmap, re-emit it as woff2. All of these licences (OFL, GPL+FE) permit
# that redistribution; nothing else is hosted.
SOURCES = [
    {"id": "sil", "host": "github", "org": "silnrsi", "prefix": "font-",
     "page": "https://github.com/silnrsi/{project}/releases/latest",
     # silnrsi/font-* is mostly fonts, but not entirely — these are tooling,
     # tests and proposals. Families Google already carries are dropped later by
     # name, so this list only has to catch what isn't a font at all.
     "skip": {"font-ttf", "font-ttf-scripts", "font-arab-tools", "font-keymanweb-osk",
              "font-lcg", "font-line-spacing-test", "font-stroke-test", "font-symchar",
              "font-sympub", "font-bloom-show-inv", "font-leke-proposal"}},
    # Swathanthra Malayalam Computing — Manjari, Gayathri, Meera, Rachana.
    # Their own site lists every font as woff2 in a stylesheet, which is both
    # more complete and less work than their GitLab releases (half of which
    # publish no built binary at all).
    {"id": "smc", "host": "css", "index": "https://smc.org.in/css/fonts.css",
     "base": "https://smc.org.in", "page": "https://smc.org.in/fonts/#/{project}",
     "skip": set()},
    # Rachana Institute of Typography (rachana.org.in) — RIT Rachana, Panmana.
    {"id": "rit", "host": "gitlab", "group": "rit-fonts",
     "page": "https://gitlab.com/rit-fonts/{project}",
     "skip": {"malayalam-shaping", "texbook-inside-out", "texsynhl", "tnjoy",
              "arsenal-math", "Sayahna-font"}},
    # Long-running libre families with no Google Fonts entry: broad Latin and
    # symbol coverage (DejaVu), scholarly and medieval Latin (Junicode), and the
    # maths faces a typesetter reaches for (Libertinus, XITS).
    #
    # Deliberately not here: STIX and Liberation (Google carries STIX Two, and
    # Liberation publishes no built binaries), Source Han (an 80 MB .ttc for CJK
    # that Noto already covers), and Last Resort — it has a glyph for every
    # codepoint in Unicode, all of them placeholder boxes, so indexing it would
    # put a font that draws nothing at the top of every single answer.
    {"id": "libre", "host": "github-repos", "skip": set(),
     "page": "https://github.com/{project}/releases/latest",
     "repos": ["dejavu-fonts/dejavu-fonts", "psb1558/Junicode-font",
               "alerque/libertinus", "aliftype/xits", "rastikerdar/vazirmatn"]},
]

OUT_DATA = os.path.join("web", "data")
OUT_FONTS = os.path.join("web", "fonts")
HEADERS = {"User-Agent": "glyph-sleuth-index/1.0 (+https://github.com/beniza/glyph-sleuth)"}


def fetch(url, token=None):
    request = urllib.request.Request(url, headers=dict(HEADERS))
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def fetch_json(url, token=None):
    body = fetch(url, token).decode("utf-8")
    # Google prefixes its JSON with an anti-hijacking guard: )]}'
    return json.loads(body.lstrip(")]}'\n "))


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

def google_families(limit=None):
    families = fetch_json(GF_LIST)["familyMetadataList"]
    families.sort(key=lambda f: f["family"])
    return families[:limit] if limit else families


# What Google calls a licence, and what a designer would call it.
GOOGLE_LICENCES = {"ofl": "OFL", "apache2": "Apache 2.0", "ufl": "UFL"}


def google_font(meta):
    name = meta["family"]
    try:
        detail = fetch_json(GF_FAMILY.format(family=urllib.parse.quote(name)))
    except Exception as error:
        print(f"  !! {name}: {error}")
        return None
    coverage = detail.get("coverage")
    if not coverage:
        return None
    slug = name.replace(" ", "+")
    licence = detail.get("license") or ""
    return {
        "name": name,
        "ranges": parse_google_ranges(coverage),
        "source": "google",
        "licence": GOOGLE_LICENCES.get(licence, licence.upper()),
        "category": meta.get("category") or "",
        "designers": meta.get("designers") or [],
        "url": GF_SPECIMEN.format(slug=slug),
        "css": f"https://fonts.googleapis.com/css2?family={slug}",
    }


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


def projects(source, token=None):
    """Every font project a foundry publishes, so new releases need no edit."""
    if source["host"] == "github-repos":
        return sorted(source["repos"])

    if source["host"] == "css":
        sheet = fetch(source["index"]).decode("utf-8", "replace")
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


def archive(source, project, token=None):
    """The release archive holding built fonts, as bytes."""
    if source["host"] == "css":
        sheet = fetch(f"{source['base']}/fonts/{project}.css").decode("utf-8", "replace")
        for url in CSS_URL.findall(sheet):
            if ".woff2" in url or url.endswith((".ttf", ".otf")):
                return fetch(url if url.startswith("http") else source["base"] + url)
        return None

    if source["host"] in ("github", "github-repos"):
        url = (GITHUB_RELEASE_FULL.format(project=project) if source["host"] == "github-repos"
               else GITHUB_RELEASE.format(org=source["org"], project=project))
        release = fetch_json(url, token)
        assets = [a for a in release.get("assets", []) if a["name"].endswith((".zip", ".tar.xz"))]
        if not assets:
            return None
        # Biggest archive wins: a release often ships both the complete bundle and
        # per-family cuts of it, and dejavu-sans-ttf.zip is not DejaVu.
        best = sorted(assets, key=lambda a: (a["name"].endswith(".zip"), a.get("size", 0)))[-1]
        return fetch(best["browser_download_url"])

    path = urllib.parse.quote(f"{source['group']}/{project}", safe="")
    releases = fetch_json(GITLAB_RELEASES.format(project=path))
    if not releases:
        return None
    assets = releases[0].get("assets", {})
    # Built fonts live in a release zip, in job artifacts, or — SMC does this —
    # as one link per face. The source archive is the git tree, which for these
    # projects holds sources, not binaries, so it is the last resort.
    links = assets.get("links", [])
    for wanted in (".zip", ".ttf", ".otf"):
        for link in links:
            if link["name"].lower().endswith(wanted):
                return fetch(link["url"])
    for link in links:
        if "artifacts" in link["url"]:
            return fetch(link["url"])
    for asset in assets.get("sources", []):
        if asset["format"] == "zip":
            return fetch(asset["url"])
    return None


MAX_PER_PROJECT = 8


def release_fonts(source, project, token=None):
    """Every family in a foundry's latest release: cmap for coverage, woff2 to
    draw with. One release often holds several — DejaVu ships Sans, Serif and
    Mono; Libertinus adds Math — and a serif is not an answer to "I need a mono".
    """
    try:
        blob = archive(source, project, token)
        if not blob:
            return []
        members = extract_fonts(blob)
    except Exception as error:
        print(f"  !! {source['id']}/{project}: {error}")
        return []

    built = []
    for name, regular in pick_faces(members)[:MAX_PER_PROJECT]:
        entry = build_face(source, project, name, regular)
        if entry:
            built.append(entry)
    return built


def build_face(source, project, path, blob):
    from fontTools.ttLib import TTFont

    try:
        font = TTFont(io.BytesIO(blob), fontNumber=0, lazy=True)
        codepoints = set()
        for table in font["cmap"].tables:
            codepoints.update(table.cmap)
        name = family_name(font)
        licence_label, licence_url = licence(font)
        font.flavor = "woff2"
        out = io.BytesIO()
        font.save(out)
    except Exception as error:
        print(f"  !! {source['id']}/{project} [{os.path.basename(path)}]: {error}")
        return None

    # A family can name itself in its own script (RIT Thaara is Malayalam), which
    # leaves nothing to slug — fall back to the file, which is always ASCII.
    filename = (re.sub(r"[^A-Za-z0-9]", "", name)
                or re.sub(r"[^A-Za-z0-9]", "", os.path.basename(path))) + ".woff2"
    os.makedirs(OUT_FONTS, exist_ok=True)
    with open(os.path.join(OUT_FONTS, filename), "wb") as handle:
        handle.write(out.getvalue())
    return {
        "name": name,
        "ranges": ranges_from(codepoints),
        "source": source["id"],
        "licence": licence_label,
        "licenceUrl": licence_url,
        "category": "",
        "designers": [d for d in [designer(font)] if d],
        "url": source["page"].format(project=project),
        "file": f"fonts/{filename}",
    }


def extract_fonts(blob):
    """(name, bytes) for every ttf/otf in a release asset — archive or bare font."""
    if blob[:4] in (bytes.fromhex("00010000"), b"OTTO", b"true", b"ttcf", b"wOFF", b"wOF2"):
        return [("release.ttf", blob)]
    if blob[:2] == b"PK":
        bundle = zipfile.ZipFile(io.BytesIO(blob))
        names = [n for n in bundle.namelist() if n.lower().endswith((".ttf", ".otf"))]
        return [(n, bundle.read(n)) for n in names]
    bundle = tarfile.open(fileobj=io.BytesIO(blob), mode="r:*")
    return [(m.name, bundle.extractfile(m).read())
            for m in bundle.getmembers()
            if m.isfile() and m.name.lower().endswith((".ttf", ".otf"))]


SKIP_STYLES = ("bold", "italic", "oblique", "compact", "thin", "light", "black",
               "medium", "semi", "extra", "condensed", "-vf", "variable")


def pick_faces(members):
    """One upright face per family in the archive, TrueType before CFF.

    Grouped on the filename's stem before the style, which is what a release
    actually names its families by: DejaVuSans-Bold and DejaVuSans-Oblique are
    the same family as DejaVuSans, while DejaVuSerif is another.
    """
    families = {}
    for path, data in members:
        stem = os.path.splitext(os.path.basename(path))[0]
        lowered = stem.lower()
        # Older copies kept for reference are not the release — STIX-style repos
        # carry an archive/ directory of superseded versions.
        if any(part in path.lower().split("/") for part in ("archive", "old", "deprecated")):
            continue
        family = re.split(r"[-_ ]", stem)[0]
        style_free = not any(word in lowered for word in SKIP_STYLES)
        rank = (0 if style_free else 1, 0 if lowered.endswith(("ttf",)) else 1, len(stem))
        best = families.get(family)
        if not best or rank < best[0]:
            families[family] = (rank, (path, data))
    ordered = sorted(families.values(), key=lambda item: item[0])
    return [face for _rank, face in ordered]


def designer(font):
    for record in font["name"].names:
        if record.nameID == 9:
            return str(record)
    return None


# The licence a font states about itself, in name records 13 (description) and
# 14 (URL). Matched on the phrase each licence actually uses, longest first, so
# "GPL with font exception" never reads as plain GPL.
LICENCE_MARKS = [
    ("font exception", "GPL+FE"),
    ("open font license", "OFL"), ("openfontlicense", "OFL"), ("scripts.sil.org/ofl", "OFL"),
    ("apache", "Apache 2.0"),
    ("public domain", "Public domain"), ("unlicense", "Public domain"), ("cc0", "CC0"),
    ("creative commons", "CC"),
    ("mit license", "MIT"),
    ("lesser general public", "LGPL"), ("general public license", "GPL"),
]


def licence(font):
    """(label, url) for what the font says its licence is."""
    text, url = "", ""
    for record in font["name"].names:
        if record.nameID == 13 and not text:
            text = str(record)
        elif record.nameID == 14 and not url:
            url = str(record)
    haystack = f"{text} {url}".lower()
    for mark, label in LICENCE_MARKS:
        if mark in haystack:
            return label, url
    return "", url


def family_name(font):
    for record in font["name"].names:
        if record.nameID == 16:
            return str(record)
    for record in font["name"].names:
        if record.nameID == 1:
            return str(record)
    return "Unknown"


# ----------------------------------------------------------------- language

def udhr_languages(limit=None):
    """The UDHR translation list: our language menu, and our sample text."""
    root = ET.fromstring(fetch(UDHR_INDEX))
    entries = []
    for node in root:
        if node.get("stage") not in ("4", "5") or not node.get("iso639-3"):
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


# ------------------------------------------------------- names and blocks

def write_blocks():
    """The UCD blocks, straight out of the vendored table the desktop app uses."""
    import ucd
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
    for cp in range(MAX_CP := 0x110000):
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


# --------------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, help="only this many families and languages")
    parser.add_argument("--google-only", "--skip-sil", dest="google_only",
                        action="store_true", help="skip the foundry downloads")
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    os.makedirs(OUT_DATA, exist_ok=True)

    print("Google Fonts")
    families = google_families(args.limit)
    fonts = in_parallel(families, google_font, "coverage")

    for source in [] if args.google_only else SOURCES:
        print(f"{source['id'].upper()} — faces Google doesn't carry")
        found = projects(source, token)
        found = found[:args.limit] if args.limit else found
        have = [squash(f["name"]) for f in fonts]
        for batch in in_parallel(found, lambda p: release_fonts(source, p, token), "faces"):
            for font in batch:
                # Already served — by Google, or by another face of this family.
                if any(same_family(squash(font["name"]), name) for name in have):
                    continue
                fonts.append(font)
                have.append(squash(font["name"]))

    prune_fonts(fonts)

    fonts.sort(key=lambda f: f["name"])
    write(os.path.join(OUT_DATA, "fonts.json"),
          {"fonts": fonts, "count": len(fonts), "version": app_version()})

    print("Unicode tables")
    write_blocks()
    write_names()

    print("Languages (UDHR text + SLDR exemplars)")
    entries = udhr_languages(args.limit)
    languages = disambiguate(in_parallel(entries, language, "languages"))
    write(os.path.join(OUT_DATA, "languages.json"),
          {"languages": languages, "count": len(languages)})


def prune_fonts(fonts):
    """Delete every woff2 the index doesn't point at.

    Two faces in one release can share a family name and so a filename, so a
    dropped duplicate must never take the file with it — the kept entry may be
    pointing at exactly that file. Deciding from the finished index instead also
    clears anything left behind by an earlier run.
    """
    if not os.path.isdir(OUT_FONTS):
        return
    wanted = {os.path.basename(f["file"]) for f in fonts if f.get("file")}
    for name in os.listdir(OUT_FONTS):
        if name not in wanted:
            os.remove(os.path.join(OUT_FONTS, name))


def app_version():
    """The same VERSION file the desktop app and the release tag use."""
    try:
        with io.open(os.path.join(os.path.dirname(OUT_DATA), "..", "VERSION"),
                     encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return "dev"


def write(path, payload):
    with io.open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
    print(f"  wrote {path} — {os.path.getsize(path) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
