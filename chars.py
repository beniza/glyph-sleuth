"""Characters, codepoints and Unicode properties. Knows nothing about fonts or Qt.

Property data comes from the `regex` engine's own tables, so a "does \\p{X} match"
answer here is the same answer a real regex would give.
"""
import bisect
import re
import unicodedata
from collections import namedtuple
from functools import lru_cache

import regex
from regex import _regex_core as _rc

import store
import ucd

MAX_CP = 0x110000

# ---------------------------------------------------------------- property tables

def _property_values():
    """{CANONICAL_PROPERTY: [value names]} straight out of the regex engine."""
    out = {}
    for _id, entry in _rc.PROPERTY_NAMES.items():
        try:
            name, values = entry
            out[name] = sorted(set(values.values()))
        except Exception:
            continue
    return out


PROPERTY_VALUES = _property_values()
BOOLEAN_PROPS = sorted(
    p for p, v in PROPERTY_VALUES.items() if set(v) == {"FALSE", "TRUE"}
)
# Enumerated properties worth reporting for a single character, in reading order.
# The engine's names carry no separators: GENERALCATEGORY, not GENERAL_CATEGORY.
ENUM_PROPS = [
    p
    for p in (
        "SCRIPT", "BLOCK", "BIDICLASS", "EASTASIANWIDTH", "LINEBREAK",
        "WORDBREAK", "GRAPHEMECLUSTERBREAK", "NUMERICTYPE",
        "DECOMPOSITIONTYPE", "JOININGTYPE", "INDICSYLLABICCATEGORY",
        "INDICPOSITIONALCATEGORY", "HANGULSYLLABLETYPE",
    )
    if p in PROPERTY_VALUES
]
# GENERALCATEGORY is deliberately absent: probing it in value order matches a
# supercategory alias ("Assigned") before the real one, so it comes from
# unicodedata instead. Values that mean "doesn't apply" are dropped as noise.
_NOT_APPLICABLE = {"none", "other", "notapplicable", "na", "notapplicable"}
PROPERTY_COUNT = len(PROPERTY_VALUES)

# Block names and ranges come from the UCD, so they read as Unicode writes them.
BLOCKS = [name for _lo, _hi, name in ucd.BLOCKS]
_BLOCK_STARTS = [lo for lo, _hi, _name in ucd.BLOCKS]
SCRIPTS = sorted(
    {
        ucd.VALUE_NAMES.get(("sc", value), value.title())
        for value in PROPERTY_VALUES.get("SCRIPT", ())
    }
)

# regex's canonical property name -> the UCD's short name, for looking up labels.
_UCD_SHORT = {
    "BLOCK": "blk", "SCRIPT": "sc", "SCRIPTEXTENSIONS": "scx",
    "GENERALCATEGORY": "gc", "BIDICLASS": "bc", "EASTASIANWIDTH": "ea",
    "LINEBREAK": "lb", "WORDBREAK": "WB", "SENTENCEBREAK": "SB",
    "GRAPHEMECLUSTERBREAK": "GCB", "NUMERICTYPE": "nt",
    "DECOMPOSITIONTYPE": "dt", "JOININGTYPE": "jt", "JOININGGROUP": "jg",
    "HANGULSYLLABLETYPE": "hst", "INDICSYLLABICCATEGORY": "InSC",
    "INDICPOSITIONALCATEGORY": "InPC", "CANONICALCOMBININGCLASS": "ccc",
}


def property_label(prop):
    """GRAPHEMEBASE -> Grapheme_Base"""
    return ucd.PROP_NAMES.get(prop, prop.title())


def value_label(prop, value):
    """(BLOCK, 'DINGBATS') -> 'Dingbats'. Falls back to title case."""
    short = _UCD_SHORT.get(prop)
    if short:
        for key in (short, short.lower(), short.upper()):
            label = ucd.VALUE_NAMES.get((key, value))
            if label:
                return label
    return value.title()


def block_of(cp):
    """The UCD block containing a codepoint, or None."""
    i = bisect.bisect_right(_BLOCK_STARTS, cp) - 1
    if i >= 0:
        lo, hi, name = ucd.BLOCKS[i]
        if lo <= cp <= hi:
            return name
    return None


def block_range(name):
    """(first, last) for a block name, or None."""
    wanted = name.lower().replace("_", " ")
    for lo, hi, block in ucd.BLOCKS:
        if block.lower() == wanted:
            return lo, hi
    return None


@lru_cache(maxsize=8192)
def _matcher(expr):
    """Compile \\p{...}; None if the engine rejects it."""
    try:
        return regex.compile(r"\p{%s}" % expr)
    except Exception:
        return None


def matches_property(ch, expr):
    m = _matcher(expr)
    return bool(m and m.fullmatch(ch))


@lru_cache(maxsize=4096)
def enum_value(ch, prop):
    """The value of an enumerated property for one character, e.g. BLOCK -> 'Dingbats'."""
    for value in PROPERTY_VALUES.get(prop, ()):
        if matches_property(ch, f"{prop}={value}"):
            return value
    return None


@lru_cache(maxsize=2048)
def properties_of(ch):
    """(matched, unmatched) \\p{...} expressions for one character.

    Every string returned is valid inside a real \\p{...}, so it can be copied
    straight into a regex.
    """
    matched, unmatched = [], []
    for prop in BOOLEAN_PROPS:
        label = property_label(prop)
        (matched if matches_property(ch, prop) else unmatched).append(label)

    category = unicodedata.category(ch)
    matched.append(f"General_Category={value_label('GENERALCATEGORY', category.upper())}")
    matched.append(category)

    for prop in ENUM_PROPS:
        value = enum_value(ch, prop)
        if not value:
            continue
        label = value_label(prop, value)
        if label.lower().replace("_", "") in _NOT_APPLICABLE:
            continue
        matched.append(f"{property_label(prop)}={label}")
    # De-duplicate aliases (ALPHA and ALPHABETIC share one label) while keeping order.
    return _unique(matched), _unique(unmatched)


def _unique(items):
    seen, out = set(), []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


# ---------------------------------------------------------------- character facts

CharInfo = namedtuple(
    "CharInfo",
    "cp ch name category block script bidi combining decimal utf8 utf16 "
    "html escape decomposition numeric",
)

_CONTROL_NAMES = {
    0x00: "NULL", 0x09: "TAB", 0x0A: "LINE FEED", 0x0D: "CARRIAGE RETURN",
    0x1B: "ESCAPE", 0x7F: "DELETE",
}


def char_name(ch):
    try:
        return unicodedata.name(ch)
    except ValueError:
        cp = ord(ch)
        if cp in _CONTROL_NAMES:
            return f"<control> {_CONTROL_NAMES[cp]}"
        if unicodedata.category(ch) == "Cc":
            return "<control>"
        if 0xE000 <= cp <= 0xF8FF or 0xF0000 <= cp <= 0x10FFFD:
            return "<private use>"
        if 0xD800 <= cp <= 0xDFFF:
            return "<surrogate>"
        return "<unassigned>"


def describe(cp):
    ch = chr(cp)
    num = None
    try:
        num = unicodedata.numeric(ch)
    except (ValueError, TypeError):
        pass
    return CharInfo(
        cp=cp,
        ch=ch,
        name=char_name(ch),
        category=unicodedata.category(ch),
        block=block_of(cp),
        script=value_label("SCRIPT", enum_value(ch, "SCRIPT") or ""),
        bidi=unicodedata.bidirectional(ch) or None,
        combining=unicodedata.combining(ch),
        decimal=cp,
        utf8=" ".join(f"{b:02X}" for b in ch.encode("utf-8")),
        utf16=" ".join(f"{b:04X}" for b in _utf16_units(cp)),
        html=html_entity(cp),
        escape=escape_of(cp),
        decomposition=unicodedata.decomposition(ch) or None,
        numeric=num,
    )


def _utf16_units(cp):
    if cp <= 0xFFFF:
        return [cp]
    v = cp - 0x10000
    return [0xD800 + (v >> 10), 0xDC00 + (v & 0x3FF)]


def html_entity(cp):
    import html.entities

    name = html.entities.codepoint2name.get(cp)
    return f"&{name};" if name else f"&#{cp};"


def escape_of(cp):
    return f"\\u{cp:04x}" if cp <= 0xFFFF else f"\\U{cp:08x}"


CATEGORY_NAMES = {
    "Lu": "Letter, uppercase", "Ll": "Letter, lowercase", "Lt": "Letter, titlecase",
    "Lm": "Letter, modifier", "Lo": "Letter, other",
    "Mn": "Mark, non-spacing", "Mc": "Mark, spacing combining", "Me": "Mark, enclosing",
    "Nd": "Number, decimal digit", "Nl": "Number, letter", "No": "Number, other",
    "Pc": "Punctuation, connector", "Pd": "Punctuation, dash",
    "Ps": "Punctuation, open", "Pe": "Punctuation, close",
    "Pi": "Punctuation, initial quote", "Pf": "Punctuation, final quote",
    "Po": "Punctuation, other",
    "Sm": "Symbol, math", "Sc": "Symbol, currency", "Sk": "Symbol, modifier",
    "So": "Symbol, other",
    "Zs": "Separator, space", "Zl": "Separator, line", "Zp": "Separator, paragraph",
    "Cc": "Other, control", "Cf": "Other, format", "Cs": "Other, surrogate",
    "Co": "Other, private use", "Cn": "Other, unassigned",
}

BIDI_NAMES = {
    "L": "Left-to-right", "R": "Right-to-left", "AL": "Arabic letter",
    "EN": "European number", "ES": "European separator", "ET": "European terminator",
    "AN": "Arabic number", "CS": "Common separator", "NSM": "Non-spacing mark",
    "BN": "Boundary neutral", "B": "Paragraph separator", "S": "Segment separator",
    "WS": "Whitespace", "ON": "Other neutral", "LRE": "LTR embedding",
    "RLE": "RTL embedding", "LRO": "LTR override", "RLO": "RTL override",
    "PDF": "Pop directional format", "LRI": "LTR isolate", "RLI": "RTL isolate",
    "FSI": "First-strong isolate", "PDI": "Pop directional isolate",
}

# Characters with no ink of their own get a visible stand-in.
_STANDIN = {0x20: "SP", 0x09: "TAB", 0x0A: "LF", 0x0D: "CR", 0xA0: "NBSP",
            0x200B: "ZWSP", 0x200C: "ZWNJ", 0x200D: "ZWJ", 0xFEFF: "BOM"}


def standin(cp):
    """Short label to show instead of the glyph, or None if the glyph is fine."""
    if cp in _STANDIN:
        return _STANDIN[cp]
    cat = unicodedata.category(chr(cp))
    if cat in ("Cc", "Cf", "Zl", "Zp", "Zs", "Cs", "Cn"):
        return f"{cat}"
    return None


# ---------------------------------------------------------------- name index

_STOPWORDS = {
    "LETTER", "CAPITAL", "SMALL", "WITH", "AND", "SIGN", "MARK", "SYMBOL",
    "COMBINING", "MODIFIER", "CHARACTER", "FORM", "ABOVE", "BELOW", "OVERLAY",
    "LEFT", "RIGHT", "UPPER", "LOWER", "MIDDLE", "CENTRE", "CENTER", "OPEN",
    "HEAVY", "LIGHT", "MEDIUM", "BOLD", "VERY", "EXTREMELY", "OF", "THE",
    "DIGIT", "NUMBER", "SPACING", "NON", "FINAL", "INITIAL", "ISOLATED",
    "MEDIAL", "TURNED", "REVERSED", "ROTATED", "INVERTED",
}
_NAME_INDEX_FILE = "names.pkl"


def build_name_index(progress=None):
    """{keyword: (codepoints...)} over every named character. ~2 s cold."""
    index = {}
    for cp in range(MAX_CP):
        if progress and cp % 0x10000 == 0:
            progress(cp / MAX_CP)
        try:
            name = unicodedata.name(chr(cp))
        except ValueError:
            continue
        for word in name.replace("-", " ").split():
            index.setdefault(word, []).append(cp)
    return {k: tuple(v) for k, v in index.items()}


_name_index = None


def name_index(progress=None):
    global _name_index
    if _name_index is None:
        cached = store.load(_NAME_INDEX_FILE)
        if cached and cached.get("unicode") == unicodedata.unidata_version:
            _name_index = cached["index"]
        else:
            _name_index = build_name_index(progress)
            store.save(
                _NAME_INDEX_FILE,
                {"unicode": unicodedata.unidata_version, "index": _name_index},
            )
    return _name_index


def keywords(name):
    words = {w for w in name.replace("-", " ").split() if len(w) > 1}
    return words - _STOPWORDS or words


def variants(cp, limit=400):
    """Codepoints whose name shares a keyword, rarest keyword first.

    Score is 1/frequency summed over shared keywords, so a rare word like
    ASTERISK outranks a common one like LATIN without a special case for either.
    """
    idx = name_index()
    name = char_name(chr(cp))
    if name.startswith("<"):
        return []
    words = keywords(name) & idx.keys()
    scores = {}
    for word in words:
        weight = 1.0 / len(idx[word])
        for other in idx[word]:
            scores[other] = scores.get(other, 0.0) + weight
    scores.pop(cp, None)
    ranked = sorted(scores, key=lambda c: (-scores[c], c))
    return [cp] + ranked[:limit]


def normalization_variants(text):
    """[(form, text)] for the four normal forms, skipping ones equal to the input."""
    out = []
    for form in ("NFC", "NFD", "NFKC", "NFKD"):
        value = unicodedata.normalize(form, text)
        out.append((form, value))
    return out


def case_variants(ch):
    out = {}
    for label, value in (("upper", ch.upper()), ("lower", ch.lower()),
                         ("title", ch.title()), ("casefold", ch.casefold())):
        if value != ch and value:
            out[label] = value
    return out


# ---------------------------------------------------------------- query parsing

Query = namedtuple("Query", "kind value label alternates")

_CP_PREFIXED = re.compile(
    r"^(?:U\+|u\+|0x|0X|\\u|\\U|&#x|&#X)([0-9A-Fa-f]{1,6})[;]?$"
)
_CP_DECIMAL = re.compile(r"^(?:&#)?([0-9]{2,7})[;]?$")
_CP_HEX = re.compile(r"^([0-9A-Fa-f]{4,6})$")
_PROP = re.compile(r"^\\?p\{(.+)\}$|^\\?p\{?([A-Za-z_]+(?:=[\w \-]+)?)\}?$")
_RANGE = re.compile(
    r"^(?:U\+|0x|)([0-9A-Fa-f]{2,6})\s*(?:\.\.|-|…|…)\s*(?:U\+|0x|)([0-9A-Fa-f]{2,6})$",
    re.I,
)


def _valid(cp):
    return 0 <= cp < MAX_CP


def parse(text, font_families=(), lang_names=()):
    """Work out what the user meant. Returns a Query; alternates are other readings."""
    raw = text.strip()
    if not raw:
        return Query("empty", None, "nothing yet", [])

    alts = []

    # \p{...} property
    m = _PROP.match(raw)
    if m and (raw.startswith("\\p") or raw.startswith("p{")):
        expr = (m.group(1) or m.group(2) or "").strip()
        return Query("prop", expr, f"\\p{{{expr}}}", [])

    # explicit codepoint, e.g. U+2731 / 0x2731 / ✱
    m = _CP_PREFIXED.match(raw)
    if m and _valid(int(m.group(1), 16)):
        return Query("char", int(m.group(1), 16), "codepoint", [])

    # range, e.g. U+2700..U+27BF
    m = _RANGE.match(raw)
    if m:
        lo, hi = int(m.group(1), 16), int(m.group(2), 16)
        if _valid(lo) and _valid(hi) and lo <= hi:
            return Query("range", (lo, hi), "codepoint range", [])

    # one character: almost always the character itself
    if len(raw) == 1:
        cp = ord(raw)
        alt = []
        if raw in "0123456789abcdefABCDEF":
            alt.append(Query("char", int(raw, 16), "codepoint", []))
        return Query("char", cp, "character", alt)

    # a bare number. In a Unicode tool "2731" means U+2731, but decimal is a real
    # reading too, so it goes in the alternates where the parse echo will show it.
    if re.fullmatch(r"[0-9A-Fa-f]{2,7}", raw):
        readings = []
        try:
            as_hex = int(raw, 16)
            if _valid(as_hex):
                readings.append(Query("char", as_hex, "hex codepoint", []))
        except ValueError:
            pass
        if raw.isdigit() and _valid(int(raw)):
            readings.append(Query("char", int(raw), "decimal codepoint", []))
        if readings:
            head, tail = readings[0], readings[1:]
            tail.append(Query("name", raw, "name search", []))
            return head._replace(alternates=tail)

    lowered = raw.lower()

    # exact block name
    for block in BLOCKS:
        if block.lower().replace("_", " ") == lowered.replace("_", " "):
            return Query("block", block, "unicode block", [])

    # installed font family
    for family in font_families:
        if family.lower() == lowered:
            return Query("font", family, "installed font", [])

    # language tag or name
    for tag, name in lang_names:
        if lowered in (tag.lower(), name.lower()):
            return Query("lang", tag, "language", [])

    # a list of codepoints
    parts = raw.replace(",", " ").split()
    if len(parts) > 1:
        cps = codepoints_from_tokens(parts)
        if cps is not None:
            alts.append(Query("text", raw, "literal text", []))
            return Query("codepoints", cps, f"{len(cps)} codepoints", alts)

    # letters and spaces -> search Unicode names; otherwise treat as text to cover
    if re.fullmatch(r"[A-Za-z][A-Za-z \-']*", raw):
        alts.append(Query("text", raw, "text to cover", []))
        return Query("name", raw, "name search", alts)

    return Query("text", raw, f"text · {len(raw)} chars", [])


def codepoints_from_tokens(tokens):
    """['U+41','0x42','67'] -> [65,66,67]; None if any token isn't a codepoint."""
    out = []
    for tok in tokens:
        tok = tok.strip().rstrip(";")
        if not tok:
            continue
        m = _CP_PREFIXED.match(tok)
        if m:
            cp = int(m.group(1), 16)
        elif re.fullmatch(r"[0-9]+", tok):
            cp = int(tok)
        elif re.fullmatch(r"[0-9A-Fa-f]{2,6}", tok):
            cp = int(tok, 16)
        else:
            return None
        if not _valid(cp):
            return None
        out.append(cp)
    return out or None


def text_from_codepoints(text):
    """Free-form codepoint notation -> the string it denotes, plus how it was read."""
    tokens = text.replace(",", " ").split()
    cps = codepoints_from_tokens(tokens)
    if cps is None:
        return None, None
    hexish = [t for t in tokens if re.fullmatch(r"[0-9A-Fa-f]{2}", t.strip())]
    if len(hexish) == len(tokens) and len(tokens) > 1:
        try:
            decoded = bytes(int(t, 16) for t in tokens).decode("utf-8")
            return decoded, "utf-8 bytes"
        except (ValueError, UnicodeDecodeError):
            pass
    return "".join(chr(c) for c in cps), "codepoints"


def search_names(needle, limit=300):
    """Codepoints whose Unicode name contains every word given."""
    idx = name_index()
    words = [w.upper() for w in needle.replace("-", " ").split() if w]
    if not words:
        return []
    exact = [idx.get(w) for w in words]
    if all(exact):
        hits = set(exact[0])
        for group in exact[1:]:
            hits &= set(group)
        if hits:
            return sorted(hits)[:limit]
    # fall back to substring matching over keys
    candidates = None
    for word in words:
        matching = set()
        for key, cps in idx.items():
            if word in key:
                matching.update(cps)
        candidates = matching if candidates is None else candidates & matching
        if not candidates:
            return []
    return sorted(candidates)[:limit]


def property_members(expr, limit=20000):
    """Every codepoint matching \\p{expr}. None if the engine rejects the property."""
    m = _matcher(expr)
    if m is None:
        return None
    out = []
    for cp in range(MAX_CP):
        if m.fullmatch(chr(cp)):
            out.append(cp)
            if len(out) >= limit:
                break
    return out
