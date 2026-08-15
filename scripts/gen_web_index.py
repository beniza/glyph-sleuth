"""Build the web app's data files: which public fonts cover what, and sample text.

    python scripts/gen_web_index.py            # everything, ~10 minutes
    python scripts/gen_web_index.py --limit 40 # a slice, for development

Writes web/data/fonts.json and web/data/languages.json, plus web/fonts/*.woff2 for
the SIL faces Google Fonts doesn't carry. Nothing here reads your machine — the
desktop app answers "which of *my* fonts", this answers "which public font".

ponytail: Google publishes each family's coverage as codepoint ranges, so the
whole Google corpus costs ~2000 small JSON fetches and no font downloads. Only
the handful of SIL-only faces get downloaded and read with fontTools.
"""
import argparse
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
SIL_REPOS = "https://api.github.com/orgs/silnrsi/repos?per_page=100&page={page}"
SIL_RELEASE = "https://api.github.com/repos/silnrsi/{repo}/releases/latest"

# silnrsi/font-* is mostly fonts, but not entirely — these are tooling, tests and
# proposals. Everything else is taken as a face; the 27 families Google already
# carries (Charis, Gentium, Andika, Scheherazade New, Padauk, ...) are dropped
# later by name, so this list only has to catch what isn't a font at all.
NOT_FONTS = {"font-ttf", "font-ttf-scripts", "font-arab-tools", "font-keymanweb-osk",
             "font-lcg", "font-line-spacing-test", "font-stroke-test", "font-symchar",
             "font-sympub", "font-bloom-show-inv", "font-leke-proposal"}

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


def google_font(meta):
    name = meta["family"]
    try:
        coverage = fetch_json(GF_FAMILY.format(family=urllib.parse.quote(name))).get("coverage")
    except Exception as error:
        print(f"  !! {name}: {error}")
        return None
    if not coverage:
        return None
    slug = name.replace(" ", "+")
    return {
        "name": name,
        "ranges": parse_google_ranges(coverage),
        "source": "google",
        "category": meta.get("category") or "",
        "designers": meta.get("designers") or [],
        "url": GF_SPECIMEN.format(slug=slug),
        "css": f"https://fonts.googleapis.com/css2?family={slug}",
    }


# ---------------------------------------------------------------------- sil

def squash(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def same_family(a, b):
    """SIL and Google name the same face differently — Charis vs Charis SIL,
    Gentium Book vs Gentium Book Plus. One being a prefix of the other is the
    cheap test that catches those without matching unrelated families.

    ponytail: prefix, not a similarity score. If it ever mismerges two real
    families, an explicit alias table is the upgrade.
    """
    return a.startswith(b) or b.startswith(a)


def sil_repos(token=None):
    """Every silnrsi font repo, so a new SIL release turns up without an edit."""
    found = []
    for page in (1, 2, 3):
        batch = fetch_json(SIL_REPOS.format(page=page), token)
        found += [r["name"] for r in batch]
        if len(batch) < 100:
            break
    return sorted(r for r in found if r.startswith("font-") and r not in NOT_FONTS)


def sil_font(repo, token=None):
    """Download a silnrsi release, read the cmap, and re-emit the face as woff2."""
    from fontTools.ttLib import TTFont

    try:
        release = fetch_json(SIL_RELEASE.format(repo=repo), token)
        assets = [a for a in release.get("assets", []) if a["name"].endswith((".zip", ".tar.xz"))]
        if not assets:
            return None
        blob = fetch(sorted(assets, key=lambda a: a["name"].endswith(".zip"))[-1]["browser_download_url"])
        members = extract_fonts(blob)
        regular = pick_regular(members)
        if not regular:
            return None
        font = TTFont(io.BytesIO(regular[1]), fontNumber=0, lazy=True)
        codepoints = set()
        for table in font["cmap"].tables:
            codepoints.update(table.cmap)
        name = family_name(font)
        font.flavor = "woff2"
        out = io.BytesIO()
        font.save(out)
    except Exception as error:
        print(f"  !! {repo}: {error}")
        return None

    filename = re.sub(r"[^A-Za-z0-9]", "", name) + ".woff2"
    os.makedirs(OUT_FONTS, exist_ok=True)
    with open(os.path.join(OUT_FONTS, filename), "wb") as handle:
        handle.write(out.getvalue())
    return {
        "name": name,
        "ranges": ranges_from(codepoints),
        "source": "sil",
        "category": "",
        "designers": ["SIL International"],
        "url": f"https://github.com/silnrsi/{repo}/releases/latest",
        "file": f"fonts/{filename}",
    }


def extract_fonts(blob):
    """(name, bytes) for every ttf/otf inside a zip or tar.xz release asset."""
    if blob[:2] == b"PK":
        archive = zipfile.ZipFile(io.BytesIO(blob))
        names = [n for n in archive.namelist() if n.lower().endswith((".ttf", ".otf"))]
        return [(n, archive.read(n)) for n in names]
    archive = tarfile.open(fileobj=io.BytesIO(blob), mode="r:xz")
    return [(m.name, archive.extractfile(m).read())
            for m in archive.getmembers()
            if m.isfile() and m.name.lower().endswith((".ttf", ".otf"))]


def pick_regular(members):
    """The plain upright face — never Bold or Italic, which cover the same set."""
    for name, data in members:
        stem = os.path.basename(name).lower()
        if "bold" in stem or "italic" in stem or "compact" in stem:
            continue
        return name, data
    return members[0] if members else None


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
    parser.add_argument("--skip-sil", action="store_true", help="Google Fonts only")
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    os.makedirs(OUT_DATA, exist_ok=True)

    print("Google Fonts")
    families = google_families(args.limit)
    fonts = in_parallel(families, google_font, "coverage")

    if not args.skip_sil:
        print("SIL fonts Google doesn't carry")
        repos = sil_repos(token)
        repos = repos[:args.limit] if args.limit else repos
        have = [squash(f["name"]) for f in fonts]
        for font in in_parallel(repos, lambda r: sil_font(r, token), "faces"):
            if any(same_family(squash(font["name"]), name) for name in have):
                os.remove(os.path.join("web", font["file"]))  # Google serves it
            else:
                fonts.append(font)

    fonts.sort(key=lambda f: f["name"])
    write(os.path.join(OUT_DATA, "fonts.json"),
          {"fonts": fonts, "count": len(fonts)})

    print("Unicode tables")
    write_blocks()
    write_names()

    print("Languages (UDHR text + SLDR exemplars)")
    entries = udhr_languages(args.limit)
    languages = in_parallel(entries, language, "languages")
    write(os.path.join(OUT_DATA, "languages.json"),
          {"languages": languages, "count": len(languages)})


def write(path, payload):
    with io.open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
    print(f"  wrote {path} — {os.path.getsize(path) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
