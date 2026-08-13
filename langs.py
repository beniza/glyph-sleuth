"""Language coverage from SIL data: langtags for the language list, SLDR for the
characters each language actually needs.

langtags.json is fetched once. Each language's exemplar characters are fetched the
first time you ask for that language and then cached, so there's no bulk download.
"""
import re
import unicodedata
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import store

LANGTAGS_URL = "https://ldml.api.sil.org/langtags.json"
SLDR_RAW = "https://raw.githubusercontent.com/silnrsi/sldr/master/sldr/{d}/{f}.xml"
SLDR_API = "https://ldml.api.sil.org/{tag}"
LANGTAGS_FILE = "langtags.pkl"
EXEMPLAR_FILE = "exemplars.pkl"
TIMEOUT = 45


@dataclass(frozen=True)
class Lang:
    tag: str
    name: str
    full: str
    script: str
    region: str
    has_sldr: bool

    @property
    def label(self):
        return f"{self.name} ({self.tag})"


def _fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "glyph-sleuth"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read()


# ---------------------------------------------------------------- language list

def languages(refresh=False):
    """Every language tag SIL knows about. Downloads langtags.json on first use."""
    if not refresh:
        cached = store.load(LANGTAGS_FILE)
        if cached:
            return cached

    import json

    data = json.loads(_fetch(LANGTAGS_URL).decode("utf-8"))
    out = []
    for entry in data:
        if not isinstance(entry, dict) or "tag" not in entry:
            continue
        name = entry.get("name") or (entry.get("iana") or [entry["tag"]])[0]
        out.append(
            Lang(
                tag=entry["tag"],
                name=name,
                full=entry.get("full", entry["tag"]),
                script=entry.get("script", ""),
                region=entry.get("region", ""),
                has_sldr=bool(entry.get("sldr")),
            )
        )
    out.sort(key=lambda l: l.name.lower())
    store.save(LANGTAGS_FILE, out)
    return out


def is_cached():
    return store.load(LANGTAGS_FILE) is not None


# ---------------------------------------------------------------- exemplars

def _sldr_candidates(tag):
    """File names to try, most specific first. SLDR uses underscores."""
    under = tag.replace("-", "_")
    base = tag.split("-")[0]
    names = [under]
    if base != under:
        names.append(base)
    return [(n[0].lower(), n) for n in names]


def _exemplar_xml(tag):
    for directory, name in _sldr_candidates(tag):
        try:
            return _fetch(SLDR_RAW.format(d=directory, f=name)).decode("utf-8")
        except (urllib.error.HTTPError, urllib.error.URLError):
            continue
    return _fetch(SLDR_API.format(tag=tag)).decode("utf-8")


def _parse_exemplars(xml):
    root = ET.fromstring(xml)
    out = {}
    for element in root.iter("exemplarCharacters"):
        kind = element.get("type") or "main"
        if element.text:
            out.setdefault(kind, element.text)
    return out


def exemplars(tag, refresh=False):
    """{'main': {chars}, 'auxiliary': {chars}, ...} for one language tag."""
    cache = store.load(EXEMPLAR_FILE) or {}
    if tag in cache and not refresh:
        return cache[tag]
    raw = _parse_exemplars(_exemplar_xml(tag))
    parsed = {kind: expand_unicode_set(text) for kind, text in raw.items()}
    cache[tag] = parsed
    store.save(EXEMPLAR_FILE, cache)
    return parsed


def required(tag, include_auxiliary=False, include_punctuation=False):
    """The characters a font must have to set this language."""
    sets = exemplars(tag)
    chars = set(sets.get("main", ()))
    if include_auxiliary:
        chars |= set(sets.get("auxiliary", ()))
    if include_punctuation:
        chars |= set(sets.get("punctuation", ()))
    return chars


# ---------------------------------------------------------------- UnicodeSet

_TOKEN = re.compile(r"\\u\{[0-9A-Fa-f ]+\}|\\u[0-9A-Fa-f]{4}|\\U[0-9A-Fa-f]{8}|\\.|\{[^}]*\}|.", re.S)


def expand_unicode_set(text):
    """`[a b c-e {ch} \\u0301]` -> the set of characters it names.

    ponytail: handles the shapes CLDR/SLDR exemplars actually use — literals,
    ranges, multi-character sequences, escapes, and nesting flattened to a union.
    It does not implement set difference, intersection, or \\p{...} inside a set;
    those don't appear in exemplarCharacters. Upgrade path is PyICU's UnicodeSet
    if that ever changes.
    """
    if not text:
        return set()
    tokens = [t for t in _TOKEN.findall(text.strip()) if not t.isspace()]
    chars, i, pending = set(), 0, None

    def literal(token):
        if token.startswith("\\u{") or token.startswith("\\U{"):
            return "".join(chr(int(p, 16)) for p in token[3:-1].split())
        if token.startswith("\\u") or token.startswith("\\U"):
            return chr(int(token[2:], 16))
        if token.startswith("\\"):
            return token[1:]
        return token

    while i < len(tokens):
        token = tokens[i]
        if token in "[]":
            pending = None
        elif token.startswith("{"):
            chars.update(token[1:-1])
            pending = None
        elif token == "-" and pending and i + 1 < len(tokens) and tokens[i + 1] not in "[]":
            end = literal(tokens[i + 1])
            if len(pending) == 1 and len(end) == 1 and ord(pending) <= ord(end):
                chars.update(chr(c) for c in range(ord(pending), ord(end) + 1))
            i += 1
            pending = None
        else:
            value = literal(token)
            chars.update(value)
            pending = value if len(value) == 1 else None
        i += 1

    return {c for c in chars if c and not c.isspace()}


# ---------------------------------------------------------------- coverage

def missing_from(codepoints, chars):
    """Characters a face can't produce, either directly or by composition.

    A precomposed character counts as covered when the face has every piece of
    its decomposition — that's how the renderer will build it anyway.
    """
    missing = set()
    for ch in chars:
        if ord(ch) in codepoints:
            continue
        pieces = unicodedata.normalize("NFD", ch)
        if pieces != ch and all(ord(p) in codepoints for p in pieces):
            continue
        missing.add(ch)
    return missing


def rank_faces(faces, chars, limit=None):
    """[(face, missing_set)] over the given characters, best coverage first."""
    rows = [(face, missing_from(face.codepoints, chars)) for face in faces]
    rows.sort(key=lambda r: (len(r[1]), -r[0].glyphs, r[0].family.lower()))
    return rows[:limit] if limit else rows
