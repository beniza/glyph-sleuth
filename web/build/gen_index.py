"""Build the site's data files: which public font covers what, and sample text.

    python web/build/gen_index.py             # everything, ~10 minutes
    python web/build/gen_index.py --limit 40  # a slice, for development

Writes web/data/*.json, and **no font file, ever**. Reading a font is fine and is
what every font QA tool does; redistributing one is not. So a release is fetched,
parsed in memory and dropped: nothing is written to disk, cached into the site,
or committed, and nothing we publish points at a font URL of ours.

Google publishes each family's coverage as codepoint ranges in its metadata, so
those ~1,900 families cost small JSON fetches and no downloads at all. The other
foundries are measured from their own latest release — cmap for coverage,
GSUB/GPOS for the script tags and lookup counts, fvar for axes, silf for
Graphite.

A family whose release cannot be read is still indexed, as a stub, and says
"not measured yet" on the page. That is the honest state; a guessed range would
not be.
"""
import argparse
import collections
import datetime
import hashlib
import io
import json
import os
import re
import sys
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
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

NEWLINE = chr(10)   # written explicitly, so a build on Windows still emits LF
OUT_DATA = os.path.join(ROOT, "web", "data")
# The only place a font file is ever written. Build output, like site/: render
# copies it, git ignores it, and nothing lands here whose licence was not read
# out of the same release — see `find_licence`.
OUT_WEBFONTS = os.path.join(ROOT, "web", "webfonts")
# Stamped onto every measurement: a verdict is about the release it was read
# from, on the day it was read, not a permanent property of the family.
TODAY = datetime.date.today().isoformat()
HEADERS = {"User-Agent": "glyph-sleuth-index/1.0 (+https://github.com/beniza/glyph-sleuth)"}


# Derived facts from a previous run, keyed on the exact font file we read them
# from. A warm cache skips the download, the parse and the shaping — most of the
# build — and re-reads nothing that has not changed.
#
# Facts, never bytes: gstatic and foundry URLs carry a version, so a new release
# is a new key rather than a stale hit. No font file is written to disk here, in
# a cache or anywhere else.
CACHE = os.path.join(OUT_DATA, "cache")


def cache_key(url):
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def cached(url):
    path = os.path.join(CACHE, cache_key(url) + ".json")
    if not os.path.exists(path):
        return None
    try:
        with io.open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def remember(url, facts):
    # The day the file was actually read, kept with the facts. A cached
    # measurement re-stamped with today's date would claim we looked at a
    # release we have not opened since — provenance has to survive the cache.
    if isinstance(facts, dict) and "ranges" in facts:
        facts["read"] = TODAY
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, cache_key(url) + ".json")
    with io.open(path, "w", encoding="utf-8") as handle:
        json.dump(facts, handle, ensure_ascii=False, separators=(",", ":"))
    return facts


def measure_and_shape(blob, url, label, ranges=None):
    """Everything we read from one font file, cached against that file's URL."""
    hit = cached(url)
    if hit is not None:
        return hit
    facts = measure(blob)
    for script, script_blocks in SHAPED_SCRIPTS.items():
        against = ranges if ranges is not None else facts["ranges"]
        if any(countInRange(against, first, last) for first, last in script_blocks):
            facts.setdefault("results", {})[script] = shape_all(blob, label, script)
    return remember(url, facts)


# Hosts our GitHub token belongs to. Anywhere else it is at best useless and at
# worst a credential handed to a third party: CI sent it to gitlab.com with
# every RIT download, and GitLab answered 401, which is the polite version of
# what could have happened.
GITHUB_HOSTS = ("github.com", "api.github.com", "objects.githubusercontent.com",
                "codeload.github.com", "release-assets.githubusercontent.com")


def for_github(url):
    host = urllib.parse.urlsplit(url).hostname or ""
    return host in GITHUB_HOSTS or host.endswith(".githubusercontent.com")


# A host saying "not now" rather than "no". GitLab answers 401 for a throttled
# anonymous job-artifact download rather than 429, which is why 401 is in here:
# it cost RIT Rachana its webfont in an otherwise green build, one family of
# twelve, nothing else wrong. 5xx and a dropped connection are the ordinary
# transient failures.
#
# 404 is deliberately absent. It is an answer, and the seven SIL projects with no
# release must stay fast rather than being asked three times.
RETRY_STATUS = frozenset({401, 408, 429, 500, 502, 503, 504})
RETRIES = 3
BACKOFF = 1.5          # seconds, then doubled


def retriable(error):
    if isinstance(error, urllib.error.HTTPError):
        return error.code in RETRY_STATUS
    return isinstance(error, urllib.error.URLError)


def fetch(url, token=None, attempts=RETRIES, sleep=time.sleep):
    """The bytes at `url`, retrying only what a retry can fix.

    `attempts` is bounded and asserted in the tests: an unbounded retry does not
    fail a build, it hangs one, which is worse.
    """
    request = urllib.request.Request(url, headers=dict(HEADERS))
    if token and for_github(url):
        request.add_header("Authorization", f"Bearer {token}")
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except Exception as error:
            if attempt == attempts or not retriable(error):
                raise
            sleep(BACKOFF * (2 ** (attempt - 1)))


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


CSS_SRC = re.compile(r"src:\s*url\(([^)]+)\)")


def face_url_from_stylesheet(sheet):
    """The actual font file behind a css2 stylesheet, or None.

    Google's metadata stops at coverage, so tiers 2 and 3 need the file itself
    — and Google serves it publicly, like any other foundry.
    """
    found = CSS_SRC.search(sheet)
    return found.group(1).strip("'\" ") if found else None


def worth_parsing(font):
    """Is this family worth opening?

    Only if it covers a script we have authored sequences for. Downloading
    every family to answer a question about Malayalam would be rude to the CDN
    and slow, and tiers 2 and 3 say nothing about a face the script never
    reaches.
    """
    return any(countInRange(font.get("ranges") or [], first, last)
               for blocks in SHAPED_SCRIPTS.values() for first, last in blocks)


def measure_google_face(font):
    """Open a Google family's real font file and fill in what metadata cannot.

    Coverage stays as published — it is authoritative and already parsed — but
    the declared tags, lookup counts, Graphite and the shaping verdicts can
    only come from the file.
    """
    try:
        sheet = fetch_text(font["css"] + "&display=swap")
        url = face_url_from_stylesheet(sheet)
        if not url:
            return font
        label = os.path.basename(urllib.parse.urlsplit(url).path)
        # Ask the cache before the network: the stylesheet is a few hundred bytes
        # and names the exact file, so a cache hit costs one cheap fetch.
        facts = cached(url)
        if facts is None:
            facts = measure_and_shape(fetch(url), url, label, font["ranges"])
    except Exception as error:
        print(f"  !! {font['name']}: {error}")
        return font

    facts = dict(facts)
    facts.pop("ranges", None)          # Google's published coverage is the fuller one.
    facts.pop("family", None)
    font.update(facts)
    font["provenance"] = {"file": label, "release": url,
                          "read": facts.get("read", TODAY)}
    return font


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


def foundry_record(name, source, page, css=None, licence="", facts=None):
    """One indexed family from a foundry.

    With `facts` from measure() it is a measured family; without them it is a
    stub — indexed and findable, but the page says "not measured yet" rather
    than implying a coverage nobody computed.
    """
    record = {
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
    if facts:
        record.update({k: v for k, v in facts.items() if k != "family"})
        record["tier"] = "measured"
    return record


# --------------------------------------------------------------- measuring

# We may read any font; we re-serve only what its own licence permits.
#
# This started stricter — nothing written, ever — and that was wrong for the
# families it mattered most for. RIT publishes its Malayalam faces as a GitLab
# job artifact and SIL as a tarball; neither hosts a stylesheet, so no browser
# could reach them and every page that named one drew it in a fallback while
# printing a verdict beside it. Both ship a `woff2` build and their licence in
# the same archive, so what we publish is the foundry's own file, byte for byte,
# with its licence next to it. We convert nothing and rename nothing.
#
# The gate is `find_licence`, and it denies by default: a release whose licence
# we cannot recognise is measured and never re-served.

FONT_SUFFIXES = (".ttf", ".otf")
WEB_SUFFIXES = (".woff2",)

# Licences under which a foundry's own build may be re-served from our site.
# Each is matched against the licence text the release itself ships, not against
# a claim in metadata.
REDISTRIBUTABLE = (
    ("SIL OPEN FONT LICENSE", "OFL-1.1"),
    ("BITSTREAM VERA FONTS COPYRIGHT", "Bitstream Vera"),
    ("UBUNTU FONT LICENCE", "UFL-1.0"),
    ("APACHE LICENSE", "Apache-2.0"),
)

# Where a release keeps that text. Matched on the basename, lowercased.
LICENCE_MEMBERS = ("ofl.txt", "ofl", "license.txt", "licence.txt", "license",
                   "licence", "license.md", "copying")


def archive_members(blob, wanted):
    """{member name: bytes} for the members of a release archive `wanted` picks.

    One reader for zip and tar, because RIT ships one and SIL the other.
    """
    found = {}
    if blob[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            for name in archive.namelist():
                if wanted(name):
                    found[name] = archive.read(name)
        return found
    with tarfile.open(fileobj=io.BytesIO(blob)) as archive:
        for member in archive.getmembers():
            if member.isfile() and wanted(member.name):
                found[member.name] = archive.extractfile(member).read()
    return found


def extract_fonts(blob):
    """{member name: bytes} for the font files in a release archive."""
    return archive_members(blob, is_font_member)


def extract_release(blob):
    """Everything we take from a release: the faces, the webfonts, the licence.

    Read in one pass. The archive is large — Andika's tarball is 11 MB — and
    opening it three times to answer three questions is three downloads' worth
    of decompression for no reason.
    """
    return archive_members(
        blob,
        lambda name: is_font_member(name) or is_web_member(name)
        or is_licence_member(name))


def is_licence_member(name):
    return os.path.basename(name).lower() in LICENCE_MEMBERS


def find_licence(members):
    """(spdx, text) for a licence that permits re-serving, else ("", "").

    Default deny. We are publishing someone else's copyrighted file from our own
    domain; an unrecognised licence is a no, not a guess. `licence` on the record
    still says what we found, so a family we cannot host says why.
    """
    for name, blob in sorted(members.items()):
        if not is_licence_member(name):
            continue
        text = blob.decode("utf-8", "replace")
        upper = text.upper()
        for needle, spdx in REDISTRIBUTABLE:
            if needle in upper:
                return spdx, text
    return "", ""


def is_web_member(name):
    base = os.path.basename(name)
    if base.startswith("._") or "__MACOSX" in name:
        return False
    return name.lower().endswith(WEB_SUFFIXES)


def webfont_for(face, members):
    """The foundry's own woff2 build of the face we measured, or None.

    Matched on the filename stem, so Andika-Regular.ttf finds
    web/Andika-Regular.woff2 and not Andika-Bold.woff2. If the release ships no
    woff2 there is nothing to publish — we do not convert, because a file we
    generated is no longer the file the foundry signed off.
    """
    stem = os.path.basename(face).rsplit(".", 1)[0].lower()
    for name in sorted(members):
        if is_web_member(name) and os.path.basename(name).rsplit(".", 1)[0].lower() == stem:
            return name
    return None


def publish_webfont(source_id, project, member, blob, licence_text):
    """Write the foundry's file where the site can serve it, licence beside it.

    Returns the site-relative path, which is what the font record carries and
    what render.py turns into an @font-face src. Keyed on foundry and project
    rather than on the family slug: those are unique by construction, and the
    page slug is not decided until render resolves collisions.
    """
    slug_ = f"{source_id}/{project.replace('/', '-')}"
    folder = os.path.join(OUT_WEBFONTS, *slug_.split("/"))
    os.makedirs(folder, exist_ok=True)
    file = os.path.basename(member)
    with open(os.path.join(folder, file), "wb") as handle:
        handle.write(blob)
    with io.open(os.path.join(folder, "LICENCE.txt"), "w", encoding="utf-8") as handle:
        handle.write(licence_text)
    return f"webfonts/{slug_}/{file}"


def publish_family(source_id, project, picked, members, licence, text, facts):
    """Serve every face of this family the release ships, not only the regular.

    Coverage, tags and shaping stay the regular's: they are what the family page
    reports, and reporting the Bold's cmap under the family's name would be a
    different font's numbers. What the other faces are for is the weight and
    italic controls, which until now foundry families could not have — we read
    one face, so we did not know a second existed, and offering a weight we had
    not loaded would have been the browser faking a bold.

    A variable face is one file and one @font-face over a weight *range*, so it
    ships alone and carries its axis instead of a list.

    Returns the keys to merge into the record: `faces`, `webfont` (the regular,
    which is what "can we draw this at all" turns on) and `webfonts`.
    """
    empty = {"faces": [], "webfont": None, "webfonts": {}}
    if not licence:
        return empty

    variable = wght_axis(facts)
    if variable:
        web = webfont_for(picked, members)
        if not web:
            return empty
        path = publish_webfont(source_id, project, web, members[web], text)
        low, high = variable
        return {"faces": [str(low), str(high)], "webfont": path,
                "webfonts": {f"{low} {high}": path}}

    faces, webfonts, regular = [], {}, None
    for member, weight, italic in sibling_faces(picked, members):
        web = webfont_for(member, members)
        if not web:
            continue                      # no webfont build for this face
        key = face_key(weight, italic)
        if key in webfonts:
            continue                      # two files claiming one face: first wins
        webfonts[key] = publish_webfont(source_id, project, web, members[web], text)
        faces.append(key)
        if member == picked:
            regular = webfonts[key]

    if not webfonts:
        return empty
    # The face we measured is the one the specimen is set in. If its own build is
    # missing but a sibling's is not, we still have something to draw with.
    return {"faces": sorted(faces, key=lambda k: (k.endswith("i"), int(k.rstrip("i")))),
            "webfont": regular or next(iter(webfonts.values())),
            "webfonts": webfonts}


def webfont_present(facts):
    """Is the file a cached measurement claims we published still on disk?

    The cache holds facts, not bytes, and the webfonts are built output. A warm
    cache on a fresh checkout would otherwise skip the download and leave every
    page pointing at a woff2 that was never written.
    """
    facts = facts or {}
    # Measured before this ran at all: we have never looked for a webfont in
    # that release, so the cache cannot answer for it.
    if "webfont" not in facts:
        return False
    web = facts["webfont"]
    if not web:
        return True
    return os.path.exists(os.path.join(ROOT, "web", *web.split("/")))


def is_font_url(url):
    """Is this stylesheet `src` a font file?

    Split the query off first: SMC cache-busts with "?v=Version2.000", and a
    plain endswith() sees no font there at all.
    """
    path = urllib.parse.urlsplit(url).path
    return path.lower().endswith(FONT_SUFFIXES + (".woff2", ".woff"))


def is_font_member(name):
    base = os.path.basename(name)
    # macOS resource forks are named like the file they shadow and are not fonts.
    if base.startswith("._") or "__MACOSX" in name:
        return False
    return name.lower().endswith(FONT_SUFFIXES)


# Style words that mean this is not the face to measure or set a specimen in.
NOT_REGULAR = ("bold", "italic", "oblique", "thin", "light", "medium", "black",
               "semibold", "extrabold", "heavy", "condensed", "expanded")


def pick_faces(members):
    """One face per family in a release: the upright regular where there is one.

    A specimen set in Bold Italic tells you about the wrong drawing, and a
    release carrying two families (Meera and Meera Inimai) is two answers, not
    one — the same distinction `same_family` protects in the index.
    """
    by_family = collections.defaultdict(list)
    for name in members:
        if not is_font_member(name):
            continue
        stem = os.path.basename(name).rsplit(".", 1)[0]
        by_family[squash(stem.split("-")[0])].append(name)

    picked = []
    for family in sorted(by_family):
        faces = sorted(by_family[family])
        regular = [f for f in faces
                   if not any(word in os.path.basename(f).lower() for word in NOT_REGULAR)]
        picked.append((regular or faces)[0])
    return picked


def face_style(blob):
    """(weight, italic, family) from a face's own tables.

    Read from `OS/2`, not guessed from the filename. A file called
    `Foo-Medium.ttf` is a claim; `usWeightClass` is what the browser will match
    against, and the two disagree often enough that guessing would put a weight
    in the control that never arrives when it is picked.
    """
    from fontTools.ttLib import TTFont

    font = TTFont(io.BytesIO(blob), fontNumber=0, lazy=True)
    os2 = font.get("OS/2")
    weight = int(getattr(os2, "usWeightClass", 400) or 400)
    if os2 is not None:
        italic = bool(getattr(os2, "fsSelection", 0) & 0x01)
    else:
        italic = bool(font["head"].macStyle & 0x02)
    family = str(font["name"].getBestFamilyName() or "")
    font.close()
    return weight, italic, family


def wght_axis(facts):
    """(min, max) of a variable font's weight axis, or None.

    One file covering 100–900 is one @font-face with a weight *range*, not nine
    faces. Missing that would either offer a single weight for a font that has
    every one of them, or ask for eight files that do not exist.
    """
    for axis in facts.get("axes") or []:
        if axis.get("tag") == "wght":
            return int(axis["min"]), int(axis["max"])
    return None


def face_key(weight, italic):
    """Google's own notation for a face — "400", "700i" — so a foundry family
    and a Google family describe their weights the same way and the page needs
    one code path."""
    return f"{weight}{'i' if italic else ''}"


def sibling_faces(picked, members):
    """Every face in the release belonging to the same family as `picked`.

    Grouped on the family name each file declares, not on its filename. RIT's
    archives are the reason: `pick_faces` splits a stem on "-", so every
    RIT-Something face groups under "rit", and a release carrying two families
    would hand back one. Reading the name table costs a parse per face and is
    simply correct.

    Returns [(member, weight, italic)], the picked face included.
    """
    try:
        _weight, _italic, wanted = face_style(members[picked])
    except Exception:
        return []

    found = []
    for name in sorted(members):
        if not is_font_member(name):
            continue
        try:
            weight, italic, family = face_style(members[name])
        except Exception:
            continue                      # an unreadable sibling is not fatal
        if squash(family) == squash(wanted):
            found.append((name, weight, italic))
    return found


def measure(blob):
    """Everything a font file can tell us, read in memory from its own tables.

    Tier 1 is `cmap`: which codepoints exist. Tier 2 is the `GSUB`/`GPOS` script
    list: which OpenType tag the font declares — a face can cover every
    codepoint of a script and still declare only the old tag, which is exactly
    the failure the site exists to show. Tier 3 needs a shaper and is not here.
    """
    from fontTools.ttLib import TTFont

    font = TTFont(io.BytesIO(blob), fontNumber=0, lazy=True)
    facts = {
        "ranges": ranges_from(font.getBestCmap().keys()),
        "tags": [],
        "gsub": 0,
        "gpos": 0,
        "features": [],
        "axes": [],
        # Graphite lives in `silf`. Absent means not applicable, which the
        # matrix says differently from "failed".
        "graphite": "Silf" in font,
        "checksum": "sha256:" + hashlib.sha256(blob).hexdigest(),
        "version": "",
        "family": "",
    }

    tags, features = set(), set()
    for table_tag in ("GSUB", "GPOS"):
        if table_tag not in font:
            continue
        table = font[table_tag].table
        for record in getattr(table.ScriptList, "ScriptRecord", []) or []:
            tags.add(record.ScriptTag.strip())
        for record in getattr(table.FeatureList, "FeatureRecord", []) or []:
            features.add(record.FeatureTag.strip())
        found = getattr(table.LookupList, "Lookup", []) or []
        facts["gsub" if table_tag == "GSUB" else "gpos"] = len(found)
    facts["tags"] = sorted(tags)
    facts["features"] = sorted(features)

    if "fvar" in font:
        facts["axes"] = [{"tag": axis.axisTag, "min": axis.minValue,
                          "default": axis.defaultValue, "max": axis.maxValue}
                         for axis in font["fvar"].axes]

    # The working behind the counts, for the shaping tables page.
    facts["tables"] = lookups(blob)
    # Every glyph, and what the rules do with it — the page that shows a
    # font is more than its codepoints.
    facts["glyphs"] = glyphs(blob)

    name = font["name"]
    facts["family"] = str(name.getBestFamilyName() or "")
    version = name.getDebugName(5) or ""
    facts["version"] = version.replace("Version ", "").strip()
    font.close()
    return facts


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


GITHUB_RELEASE = "https://api.github.com/repos/{org}/{project}/releases/latest"
GITHUB_RELEASE_FULL = "https://api.github.com/repos/{project}/releases/latest"
GITLAB_RELEASES = "https://gitlab.com/api/v4/projects/{project}/releases"


def release_probe(source, project, token=None):
    """What identifies this project's current release, without downloading it.

    Returns (key, extra, faces) where `faces` is a callable that does the
    expensive part. The key comes from something cheap that changes when the
    font changes — a foundry's cache-busted stylesheet URL, or a release tag —
    so a cached measurement can be reused without fetching megabytes to discover
    that nothing moved.
    """
    if source["host"] == "css":
        sheet = fetch_text(f"{source['base']}/fonts/{project}.css")
        # The first @font-face is the upright regular; the rest are weights.
        for url in CSS_URL.findall(sheet):
            if is_font_url(url):
                full = url if url.startswith("http") else source["base"] + url
                label = os.path.basename(urllib.parse.urlsplit(url).path)
                # A foundry that already hosts a stylesheet needs nothing
                # published, so there is no archive to hand back.
                return url, sheet, lambda: ([(label, fetch(full))], {})
        return None, sheet, lambda: ([], {})

    if source["host"] in ("github", "github-repos"):
        url = (GITHUB_RELEASE_FULL.format(project=project) if source["host"] == "github-repos"
               else GITHUB_RELEASE.format(org=source["org"], project=project))
        release = fetch_json(url, token)
        assets = [a for a in release.get("assets", [])
                  if a["name"].endswith((".zip", ".tar.xz"))]
        if not assets:
            return None, None, lambda: ([], {})
        download = assets[0]["browser_download_url"]
        tag = release.get("tag_name")
    else:
        group = urllib.parse.quote(f"{source['group']}/{project}", safe="")
        releases = fetch_json(GITLAB_RELEASES.format(project=group))
        if not releases:
            return None, None, lambda: ([], {})
        # GitLab serves built fonts from a job artifact whose URL ends
        # ".../download?job=build-tag" — no extension to filter on, so take the
        # link and let extract_fonts sniff what it actually is.
        links = [l["url"] for l in releases[0].get("assets", {}).get("links", [])]
        if not links:
            return None, None, lambda: ([], {})
        download = links[0]
        tag = releases[0].get("tag_name")

    def faces():
        members = extract_release(fetch(download, token))
        return [(name, members[name]) for name in pick_faces(members)], members

    return f"{download}#{tag}", tag, faces


def foundry_family(source, project, token=None):
    """One indexed family from a foundry project, measured from its release.

    The release is fetched, parsed in memory and dropped. If anything about it
    fails — no release, a moved URL, an unreadable face — the family is still
    indexed, as a stub, because a family we cannot measure today is still a
    family someone is looking for.
    """
    page = source["page"].format(project=project)
    css = f"{source['base']}/fonts/{project}.css" if source["host"] == "css" else None
    fallback_name = project.split("/")[-1].replace("font-", "").replace("-", " ").title()

    try:
        key, extra, faces = release_probe(source, project, token)
    except Exception as error:
        print(f"  !! {project}: {error}")
        return foundry_record(fallback_name, source["id"], page, css=css)

    if source["host"] == "css" and extra:
        fallback_name = family_from_stylesheet(extra) or fallback_name
    if not key:
        return foundry_record(fallback_name, source["id"], page, css=css)

    key = f"{source['id']}:{project}:{key}"
    label = os.path.basename(urllib.parse.urlsplit(key).path) or project
    licence = ""
    # The probe was cheap; the download only happens on a cache miss — or when
    # the cache remembers a webfont that is no longer on disk.
    facts = cached(key)
    if facts is None or not webfont_present(facts):
        try:
            found, members = faces()
            if not found:
                return foundry_record(fallback_name, source["id"], page, css=css)
            label, blob = found[0]
            fresh = dict(measure_and_shape(blob, key, label))
            licence, text = find_licence(members)
            fresh["licence"] = licence
            # Recorded even when they are empty, so a warm cache can tell "we
            # looked and there was nothing to serve" from "we never looked".
            fresh.update(publish_family(source["id"], project, label, members,
                                        licence, text, fresh))
            remember(key, fresh)
            facts = fresh
        except Exception as error:
            # A download that fails must not cost us a measurement we already
            # have. Twelve RIT families went from measured to "not measured yet"
            # in one build because the fetch 401'd and the whole record was
            # thrown away with it — the coverage, the tags, the shaping, all of
            # it read from the release weeks earlier and still true. What the
            # failure costs is the webfont, and only until the next build.
            print(f"  !! {project}: {error}")
            if facts is None:
                return foundry_record(fallback_name, source["id"], page, css=css)
            facts = dict(facts)
            facts["webfont"] = None
            facts["webfonts"] = {}
    licence = facts.get("licence", licence)

    facts = dict(facts)
    facts["provenance"] = {"file": label,
                           "release": extra if source["host"] != "css" else css,
                           "read": facts.get("read", TODAY)}

    return foundry_record(facts.get("family") or fallback_name, source["id"], page,
                          css=css, licence=licence, facts=facts)


# --------------------------------------------------------- lookup tables

# What the OpenType spec calls each lookup type, so the page can say
# "Ligature" rather than "type 4".
GSUB_TYPES = {1: "Single", 2: "Multiple", 3: "Alternate", 4: "Ligature",
              5: "Context", 6: "Chaining context", 7: "Extension",
              8: "Reverse chaining single"}
GPOS_TYPES = {1: "Single", 2: "Pair", 3: "Cursive", 4: "Mark to base",
              5: "Mark to ligature", 6: "Mark to mark", 7: "Context",
              8: "Chaining context", 9: "Extension"}

# A real family carries thousands of rules. Enough to see the shape of the
# lookup, and the count says how many more there are.
RULE_SAMPLES = 6


def resolve(lookup):
    """Extension lookups wrap the real one; unwrap to what actually runs."""
    subtables = []
    for subtable in lookup.SubTable or []:
        if getattr(subtable, "ExtSubTable", None) is not None:
            subtables.append(subtable.ExtSubTable)
        else:
            subtables.append(subtable)
    return subtables


def glyph_text(names, reverse):
    """The characters these glyphs are encoded as, or None if any is not.

    Glyph names are a font developer's private business — k1cil means nothing to
    a reader. Where a glyph is in the cmap we can show the real character; a
    ligature glyph has no codepoint of its own, and the page draws that by
    letting the browser shape the input instead.
    """
    out = []
    for name in names:
        if name not in reverse:
            return None
        out.append(chr(reverse[name]))
    return "".join(out)


def gsub_rules(subtables, reverse=None):
    """[{in, out}] — a rule reads as what it does: these glyphs become that."""
    rules, total = [], 0
    for subtable in subtables:
        mapping = getattr(subtable, "mapping", None)
        if mapping:                                    # single, alternate
            total += len(mapping)
            for source, target in list(mapping.items())[:RULE_SAMPLES]:
                out = target if isinstance(target, str) else " ".join(target)
                rules.append(with_text({"in": source, "out": out}, reverse))
            continue
        alternates = getattr(subtable, "alternates", None)
        if alternates:                                 # aalt: one glyph, several choices
            total += len(alternates)
            for source, targets in list(alternates.items())[:RULE_SAMPLES]:
                rules.append(with_text({"in": source, "out": " / ".join(targets)}, reverse))
            continue
        ligatures = getattr(subtable, "ligatures", None)
        if ligatures:
            for first, entries in ligatures.items():
                total += len(entries)
                for entry in entries[:RULE_SAMPLES]:
                    rules.append(with_text(
                        {"in": " ".join([first] + list(entry.Component)),
                         "out": entry.LigGlyph}, reverse))
            continue
        # Contextual lookups chain other lookups rather than mapping glyphs;
        # counting their rules is honest, listing them is not readable.
        for attribute in ("SubRuleSet", "ChainSubRuleSet", "SubClassSet",
                          "ChainSubClassSet", "SubstLookupRecord"):
            found = getattr(subtable, attribute, None)
            if found:
                total += len(found)
    return rules[:RULE_SAMPLES], total


def with_text(rule, reverse):
    """Add the characters behind a rule's glyph names, where they have any."""
    if not reverse:
        return rule
    rule["inText"] = glyph_text(rule["in"].split(), reverse)
    rule["outText"] = glyph_text([rule["out"]], reverse)
    return rule


def gpos_rules(subtables):
    """Positioning does not rewrite glyphs, so the interesting number is how
    many marks and bases the lookup attaches — a mark-to-base with no marks is
    a lookup that will never fire."""
    total = 0
    for subtable in subtables:
        for attribute in ("MarkArray", "BaseArray", "Mark1Array", "LigatureArray",
                          "PairSet", "Coverage"):
            found = getattr(subtable, attribute, None)
            count = getattr(found, "MarkCount", None) or getattr(found, "BaseCount", None)
            if count:
                total += count
            elif isinstance(found, list):
                total += len(found)
            elif getattr(found, "glyphs", None):
                total += len(found.glyphs)
    return total


def glyph_roles(sfnt):
    """Which features produce and consume each glyph, across every rule.

    Uncapped on purpose: this is what decides whether a glyph is reachable, and
    a sample cannot answer that.
    """
    from fontTools.ttLib import TTFont

    font = TTFont(io.BytesIO(sfnt), fontNumber=0, lazy=True)
    produced = collections.defaultdict(set)
    consumed = collections.defaultdict(set)
    if "GSUB" not in font:
        font.close()
        return produced, consumed, {}

    # How each produced glyph is made: the input glyph names and the feature
    # that does the producing. That recipe is the only way to *draw* a glyph
    # with no codepoint — set its input, turn its feature on, let the browser's
    # shaper do the substitution.
    recipe = {}

    table = font["GSUB"].table
    all_lookups = getattr(table.LookupList, "Lookup", []) or []
    for record in getattr(table.FeatureList, "FeatureRecord", []) or []:
        feature = record.FeatureTag.strip()
        for index in record.Feature.LookupListIndex:
            if index >= len(all_lookups):
                continue
            for subtable in resolve(all_lookups[index]):
                mapping = getattr(subtable, "mapping", None)
                if mapping:
                    for source, target in mapping.items():
                        consumed[source].add(feature)
                        for name in ([target] if isinstance(target, str) else target):
                            produced[name].add(feature)
                            recipe.setdefault(name, ([source], feature))
                    continue
                alternates = getattr(subtable, "alternates", None)
                if alternates:
                    for source, targets in alternates.items():
                        consumed[source].add(feature)
                        for name in targets:
                            produced[name].add(feature)
                            recipe.setdefault(name, ([source], feature))
                    continue
                ligatures = getattr(subtable, "ligatures", None)
                if ligatures:
                    for first, entries in ligatures.items():
                        consumed[first].add(feature)
                        for entry in entries:
                            for name in entry.Component:
                                consumed[name].add(feature)
                            produced[entry.LigGlyph].add(feature)
                            recipe.setdefault(entry.LigGlyph,
                                              ([first] + list(entry.Component), feature))
                    continue
                # A contextual lookup rewrites nothing itself; what it touches
                # is its coverage, and the lookups it chains are already walked
                # on their own account.
                coverage = getattr(subtable, "Coverage", None)
                for glyph in getattr(coverage, "glyphs", []) or []:
                    consumed[glyph].add(feature)
    # Lookups reached only from a chaining context are in no feature's list, so
    # the walk above never sees what they build. A second pass over every
    # lookup fills in those recipes with no feature attached: the substitution
    # fires from its context, not from a feature you can switch on, and the
    # page says so instead of drawing the unsubstituted input as if it were the
    # result.
    for lookup in all_lookups:
        for subtable in resolve(lookup):
            ligatures = getattr(subtable, "ligatures", None)
            if ligatures:
                for first, entries in ligatures.items():
                    for entry in entries:
                        recipe.setdefault(entry.LigGlyph,
                                          ([first] + list(entry.Component), None))
                continue
            mapping = getattr(subtable, "mapping", None)
            if mapping:
                for source, target in mapping.items():
                    for name in ([target] if isinstance(target, str) else target):
                        recipe.setdefault(name, ([source], None))

    font.close()
    return produced, consumed, recipe


def expand(name, recipe, reverse, depth=0):
    """The characters that produce a glyph, following recipes as deep as needed.

    Ligatures are built from ligatures: Manjari's k1k1r3 takes k1k1 — itself a
    ligature with no codepoint — plus r3. Stopping at the first unencoded
    component left 283 of its 911 glyphs undrawable, so each component is
    expanded through its own recipe until everything is a real character.
    """
    if depth > 6 or name not in recipe:
        return None, []
    sources, feature = recipe[name]
    features = {feature} if feature else set()
    text = []
    for source in sources:
        if source in reverse:
            text.append(chr(reverse[source]))
            continue
        deeper, deeper_features = expand(source, recipe, reverse, depth + 1)
        if not deeper:
            return None, []
        text.append(deeper)
        features.update(deeper_features)
    return "".join(text), sorted(features)


def glyphs(blob, limit=4000):
    """Every glyph in the font, and what the layout rules do with it.

    A font is not its codepoints. The glyphs that carry Indic writing — half
    forms, conjuncts, chillus, positional variants — have no codepoints at all,
    and a glyph no rule ever produces can never appear in text however well it
    is drawn. Both facts are invisible from a coverage table.

    `produced` is the features whose rules output this glyph; `consumed` is the
    features whose rules take it as input. A glyph with neither, and no
    codepoint, is an orphan: unreachable.
    """
    from fontTools.ttLib import TTFont

    sfnt = as_sfnt(blob)
    font = TTFont(io.BytesIO(sfnt), fontNumber=0, lazy=True)
    order = font.getGlyphOrder()[:limit]
    reverse = {}
    for cp, name in font.getBestCmap().items():
        reverse.setdefault(name, cp)
    font.close()

    # From *every* rule, not the handful the page samples. Deriving roles from
    # the samples called 441 of Manjari's 911 glyphs unreachable — everything
    # produced by a seventh rule or later — which would have accused a good
    # font of carrying dead weight in our own confident voice.
    produced, consumed, recipe = glyph_roles(sfnt)

    out = []
    for name in order:
        cp = reverse.get(name)
        # .notdef is the fallback by design, not an unreachable glyph.
        orphan = (cp is None and not produced[name] and not consumed[name]
                  and name != ".notdef")
        entry = {"name": name, "cp": cp,
                 "produced": sorted(produced[name]),
                 "consumed": sorted(consumed[name]),
                 "orphan": orphan}
        # Only an unencoded glyph needs a recipe: an encoded one is reachable
        # by typing its character.
        if cp is None and name in recipe:
            text, features = expand(name, recipe, reverse)
            if text:
                entry["from"] = {"text": text, "features": features}
        out.append(entry)
    return out


def lookups(blob):
    """Every feature's lookups, with the rules behind them.

    This is the working behind the font page's "48 GSUB lookups": which
    lookups a feature runs, of what type, carrying how many rules.
    """
    from fontTools.ttLib import TTFont

    font = TTFont(io.BytesIO(as_sfnt(blob)), fontNumber=0, lazy=True)
    # Glyph name -> the character it is encoded as, so a rule can be shown in
    # the script rather than in one font developer's naming scheme.
    reverse = {}
    for cp, name in font.getBestCmap().items():
        reverse.setdefault(name, cp)
    out = {"gsub": [], "gpos": []}
    for table_tag, key, names in (("GSUB", "gsub", GSUB_TYPES), ("GPOS", "gpos", GPOS_TYPES)):
        if table_tag not in font:
            continue
        table = font[table_tag].table
        all_lookups = getattr(table.LookupList, "Lookup", []) or []
        for record in getattr(table.FeatureList, "FeatureRecord", []) or []:
            tag = record.FeatureTag.strip()
            for index in record.Feature.LookupListIndex:
                if index >= len(all_lookups):
                    continue
                lookup = all_lookups[index]
                subtables = resolve(lookup)
                kind = names.get(lookup.LookupType, f"type {lookup.LookupType}")
                if getattr(lookup.SubTable[0] if lookup.SubTable else None,
                           "ExtSubTable", None) is not None and subtables:
                    kind = names.get(subtables[0].LookupType, kind)
                if key == "gsub":
                    rules, total = gsub_rules(subtables, reverse)
                else:
                    rules, total = [], gpos_rules(subtables)
                out[key].append({"feature": tag, "type": kind, "index": index,
                                 "flag": lookup.LookupFlag, "n": total, "rules": rules})
    font.close()
    return out


# ----------------------------------------------------------------- shaping

CONTENT = os.path.join(ROOT, "web", "content")

# Scripts we have authored sequences for, and the blocks that say a face is
# meant for one. Malayalam is the flagship, not the limit — adding a script is
# a sequences.json entry and a line here.
# Every block each script spans, because a script is rarely one block:
# Devanagari takes three, Arabic nine. Miss one and the families that cover
# only the supplement are never opened.
SHAPED_SCRIPTS = {
    "Mlym": [(0x0D00, 0x0D7F)],
    "Deva": [(0x0900, 0x097F), (0xA8E0, 0xA8FF), (0x11B00, 0x11B5F)],
}


def countInRange(ranges, first, last):
    """How many codepoints of first..last these ranges cover. Mirrors core.js."""
    total = 0
    for lo, hi in ranges:
        if hi < first:
            continue
        if lo > last:
            break
        total += min(hi, last) - max(lo, first) + 1
    return total


def all_sequences():
    """Every script we have authored sequences for."""
    with io.open(os.path.join(CONTENT, "sequences.json"), encoding="utf-8") as handle:
        return [key for key in json.load(handle) if not key.startswith("_")]


def sequences(script="Mlym"):
    """The authored sequences a script's fonts actually disagree on.

    Content, not data: which sequences are worth testing is an editorial
    judgement about a writing system. The companion reads the same file, so
    neither product carries its own copy of what a verdict is about.
    """
    with io.open(os.path.join(CONTENT, "sequences.json"), encoding="utf-8") as handle:
        return json.load(handle).get(script, [])


def codepoints_of(codes):
    return [int(part, 16) for part in codes.split()]


def hb_shape_command(filename, codes, needs, language, script="Mlym"):
    """The `hb-shape` line that reproduces a verdict.

    Shown beside every verdict on the site: a claim nobody can re-run is an
    assertion, not evidence.
    """
    unicodes = ",".join(codes.split())
    line = f"hb-shape --font-file={filename} --unicodes={unicodes}"
    if needs:
        line += f" --features={','.join(needs)}"
    return f"{line} --script={script} --language={language}"


def as_sfnt(blob):
    """Plain sfnt bytes, unwrapping woff2 if that is what a foundry serves.

    HarfBuzz does not read woff2. Handed compressed bytes it finds no glyphs,
    so every sequence comes back .notdef and a perfectly good family reads as
    broken — silently, which is the worst way to be wrong.
    """
    if blob[:4] not in (b"wOF2", b"wOFF"):
        return blob
    from fontTools.ttLib import woff2

    out = io.BytesIO()
    woff2.decompress(io.BytesIO(blob), out)
    return out.getvalue()


def shape(blob, codes, features=None, language="ml", script="Mlym", expected=None):
    """Shape one sequence with HarfBuzz and judge the result.

    Three things count as the font failing, not the text being wrong:
    a .notdef in the run (the font has no glyph for something it was asked to
    draw), a leftover dotted circle (the shaper gave up on the cluster), and a
    run that comes back empty. Everything else is clean — this says nothing
    about whether the shaping is *beautiful*, only that it happened.
    """
    import uharfbuzz as hb

    face = hb.Face(as_sfnt(blob))
    font = hb.Font(face)
    buffer = hb.Buffer()
    buffer.add_codepoints(codepoints_of(codes))
    buffer.guess_segment_properties()
    if language:
        buffer.language = language
    hb.shape(font, buffer, {feature: True for feature in (features or [])})

    names, gids = [], []
    for info in buffer.glyph_infos:
        gids.append(info.codepoint)
        try:
            names.append(font.glyph_to_string(info.codepoint))
        except Exception:
            names.append(f"gid{info.codepoint}")

    verdict, note = "clean", ""
    if not names:
        verdict, note = "fail", "shaping produced no glyphs"
    elif any(name in (".notdef", "gid0") for name in names):
        missing = [f"{cp:04X}" for cp in codepoints_of(codes)
                   if not font.get_nominal_glyph(cp)]
        verdict = "fail"
        note = (".notdef in the output"
                + (f" — the font has no glyph for {', '.join(missing)}" if missing else ""))
    elif any("dotted" in name.lower() or name == "uni25CC" for name in names):
        verdict, note = "fail", "a dotted circle survived: the shaper gave up on the cluster"

    # "It shaped something" is not "it shaped the right thing". Shaping the
    # expected text through the same font and comparing glyph runs is the only
    # font-independent check available: glyph *names* differ per foundry, so
    # k1cil in one family says nothing about another.
    if verdict == "clean" and expected:
        wanted = hb.Buffer()
        wanted.add_str(expected)
        wanted.guess_segment_properties()
        hb.shape(font, wanted, {feature: True for feature in (features or [])})
        wanted_gids = [info.codepoint for info in wanted.glyph_infos]
        if wanted_gids and wanted_gids != gids:
            # Two different glyph ids can draw the same shape, so this is a
            # caveat and not a failure: the run differs from the expected
            # form's, which is worth a look, not proof of a bug.
            wanted_names = []
            for info in wanted.glyph_infos:
                try:
                    wanted_names.append(font.glyph_to_string(info.codepoint))
                except Exception:
                    wanted_names.append(f"gid{info.codepoint}")
            verdict = "caveat"
            note = (f"a different glyph run from the expected form {expected}: "
                    f"{' '.join(names)} against {' '.join(wanted_names)}. Two glyphs "
                    "can draw the same shape, so this is worth looking at rather "
                    "than proof of a fault.")

    return {"verdict": verdict, "glyphs": names, "gids": gids, "note": note,
            "shaper": "hb", "version": hb.version_string()}


LOOKUP_END = re.compile(r"^end lookup (\d+) feature '(\w+)'")


def trace(blob, codes, features=None, language="ml"):
    """Every step where the glyph run actually changed, and what changed it.

    A verdict is a claim; this is the demonstration. HarfBuzz reports each
    lookup it runs, so a reader can watch three glyphs become one and read off
    which lookup of which feature did it.

    Only steps that changed the run are kept. A real font skips dozens of
    lookups per sequence because nothing matched, and listing those is noise
    that hides the two lines that matter.
    """
    import uharfbuzz as hb

    face = hb.Face(as_sfnt(blob))
    font = hb.Font(face)
    buffer = hb.Buffer()
    buffer.add_codepoints(codepoints_of(codes))
    buffer.guess_segment_properties()
    if language:
        buffer.language = language

    def names():
        out = []
        for info in buffer.glyph_infos:
            try:
                out.append(font.glyph_to_string(info.codepoint))
            except Exception:
                out.append(f"gid{info.codepoint}")
        return out

    steps, previous = [], None

    def message(text):
        nonlocal previous
        current = names()
        if previous is None:
            steps.append({"step": "after cmap", "glyphs": current})
            previous = current
            return True
        found = LOOKUP_END.match(text)
        if found and current != previous:
            steps.append({"step": text, "feature": found.group(2),
                          "lookup": int(found.group(1)),
                          "before": previous, "glyphs": current})
            previous = current
        elif "dotted-circle" in text and "skipped" not in text:
            steps.append({"step": "the shaper inserted a dotted circle — it could not "
                                  "make sense of the cluster", "glyphs": current})
            previous = current
        return True

    buffer.set_message_func(message)
    hb.shape(font, buffer, {feature: True for feature in (features or [])})
    if not steps:
        steps.append({"step": "after cmap", "glyphs": names()})
    return steps


def shape_all(blob, filename, script="Mlym"):
    """Every authored sequence for a script, against one face.

    Returns the four-engine shape the matrix wants, with the three engines we
    cannot reach from here left null — "not tested", which the page says in
    those words rather than implying a pass.
    """
    results = {}
    for entry in sequences(script):
        try:
            hb_result = shape(blob, entry["codes"], entry.get("needs"),
                              (entry.get("langs") or "ml").split(",")[0].strip(), script,
                              expected=entry.get("out"))
        except Exception as error:
            hb_result = {"verdict": "fail", "glyphs": [], "note": str(error), "shaper": "hb"}
        try:
            hb_result["trace"] = trace(
                blob, entry["codes"], entry.get("needs"),
                (entry.get("langs") or "ml").split(",")[0].strip())
        except Exception:
            hb_result["trace"] = []
        hb_result["command"] = hb_shape_command(
            filename, entry["codes"], entry.get("needs") or [],
            (entry.get("langs") or "ml").split(",")[0].strip(), script)
        results[entry["id"]] = {"hb": hb_result, "dw": None, "ct": None, "gr": None}
    return results


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
    """One language's sample text and exemplar set.

    Two network fetches per language — the UDHR translation and the SLDR
    exemplar set — times 527 languages, which was five and a half minutes of
    the build. Keyed on the UDHR file id, since that is what identifies the
    translation we picked.
    """
    key = "lang:" + entry["id"]
    hit = cached(key)
    if hit is not None:
        return hit or None
    return remember(key, read_language(entry)) or None


def read_language(entry):
    entry = dict(entry)
    entry["sample"] = udhr_sample(entry)
    try:
        # Exemplars are what the language actually needs; the sample is only prose.
        entry["exemplars"] = "".join(sorted(langs.required(entry["tag"])))
    except Exception:
        entry["exemplars"] = ""
    if not entry["sample"] and not entry["exemplars"]:
        return {}
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

# Indic_Syllabic_Category and Indic_Positional_Category: what a codepoint *does*
# in a cluster, and where it sits. This is the vocabulary a script engineer
# reasons in — that U+093F is a dependent vowel positioned Left is the whole
# explanation for why it is typed after its consonant and drawn before it — and
# general category alone cannot say any of it.
INSC = ["Virama", "Vowel_Dependent", "Vowel_Independent", "Consonant", "Consonant_Dead",
        "Consonant_Medial", "Consonant_Final", "Consonant_Head_Letter", "Consonant_Killer",
        "Consonant_Placeholder", "Consonant_Preceding_Repha", "Consonant_Succeeding_Repha",
        "Consonant_Subjoined", "Consonant_With_Stacker", "Nukta", "Bindu", "Visarga",
        "Avagraha", "Cantillation_Mark", "Tone_Mark", "Gemination_Mark", "Pure_Killer",
        "Invisible_Stacker", "Joiner", "Non_Joiner", "Number", "Number_Joiner",
        "Modifying_Letter", "Syllable_Modifier", "Brahmi_Joining_Number"]
INPC = ["Top", "Bottom", "Left", "Right", "Top_And_Bottom", "Top_And_Right", "Top_And_Left",
        "Bottom_And_Right", "Bottom_And_Left", "Left_And_Right", "Top_And_Left_And_Right",
        "Top_And_Bottom_And_Right", "Top_And_Bottom_And_Left", "Overstruck",
        "Visual_Order_Left"]


def write_props():
    """Per codepoint: category, cluster role, position, combining class.

    Only the codepoints where any of it is interesting — a role, a position, a
    combining class, or a mark or format category. That is 6,054 codepoints and
    190 KB rather than a table of everything, and the rest are plain letters
    whose category the client can read for itself.
    """
    import unicodedata
    import regex

    key = "props:" + ucd_module().UNICODE_VERSION
    hit = cached(key)
    if hit is None:
        insc = [(name, regex.compile(r"\p{InSC=%s}" % name)) for name in INSC]
        inpc = [(name, regex.compile(r"\p{InPC=%s}" % name)) for name in INPC]
        found = {}
        for cp in range(0x110000):
            ch = chr(cp)
            try:
                unicodedata.name(ch)
            except ValueError:
                continue
            category = unicodedata.category(ch)
            combining = unicodedata.combining(ch)
            role = next((name for name, rx in insc if rx.fullmatch(ch)), "")
            position = next((name for name, rx in inpc if rx.fullmatch(ch)), "")
            if role or position or combining or category in ("Mn", "Mc", "Me", "Cf"):
                found[f"{cp:04X}"] = [category, role, position, combining]
        hit = remember(key, {"props": found})
    write(os.path.join(OUT_DATA, "props.json"), hit["props"])


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

    # The same table until the standard moves, and building it means asking
    # unicodedata about 1.1 million codepoints.
    key = "names:" + ucd_module().UNICODE_VERSION
    hit = cached(key)
    if hit is not None:
        path = os.path.join(OUT_DATA, "names.txt")
        with io.open(path, "w", encoding="utf-8", newline=NEWLINE) as handle:
            handle.write(hit["names"])
        print("  wrote %s — from cache, %s names" % (path, hit["count"]))
        write(os.path.join(OUT_DATA, "names-formulaic.json"), hit["formulaic"])
        return

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
    ranges = [[p, lo, hi] for p, lo, hi in formulaic]
    write(os.path.join(OUT_DATA, "names-formulaic.json"), ranges)
    remember(key, {"names": NEWLINE.join(lines), "count": len(lines),
                   "formulaic": ranges})


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

    # Google carries the flagship Malayalam families too, so stopping at its
    # metadata would leave exactly the faces this site is about with coverage
    # and no tags, no lookups and no verdicts. Only the families that reach a
    # script we have sequences for get opened.
    wanted = [font for font in fonts if worth_parsing(font)]
    print(f"  {len(wanted)} of them reach a script we can shape — reading those files")
    in_parallel(wanted, measure_google_face, "tables")

    for source in [] if args.google_only else SOURCES:
        print(f"{source['id'].upper()} — families Google doesn't carry")
        found = projects(source, token)
        found = found[:args.limit] if args.limit else found
        have = [squash(f["name"]) for f in fonts]
        for font in in_parallel(found, lambda p: foundry_family(source, p, token), "families"):
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
    write_props()

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
    # The scan asks the regex engine about every codepoint below 0x30000 for
    # every script — minutes of work that only changes when Unicode or the
    # langtags script list moves, so it is keyed on both.
    codes = ",".join(sorted({code for lang in languages
                             for code in (lang.get("scripts") or [])}))
    key = "scripts:%s:%s" % (ucd_module().UNICODE_VERSION,
                             hashlib.sha1(codes.encode("utf-8")).hexdigest())
    scripts = cached(key)
    if scripts is None:
        scripts = remember(key, script_index(languages))
    print(f"  scripts: {len(scripts)} with "
          f"{sum(len(s['blocks']) for s in scripts)} blocks between them")
    write(os.path.join(OUT_DATA, "scripts.json"),
          {"scripts": scripts, "count": len(scripts)})


if __name__ == "__main__":
    main()
