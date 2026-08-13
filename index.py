"""The font index: every installed face and the exact set of codepoints it maps.

Built once, cached to disk, and refreshed per-file so only fonts you actually
installed or changed get re-read.
"""
import array
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from fontTools.ttLib import TTCollection, TTFont

import store

CACHE_FILE = "index.pkl"
CACHE_VERSION = 2
EXTENSIONS = (".ttf", ".otf", ".ttc", ".otc")


def font_dirs():
    dirs = []
    if sys.platform == "win32":
        win = os.environ.get("SystemRoot", r"C:\Windows")
        dirs += [Path(win) / "Fonts"]
        local = os.environ.get("LOCALAPPDATA")
        if local:
            dirs.append(Path(local) / "Microsoft" / "Windows" / "Fonts")
    elif sys.platform == "darwin":
        dirs += [Path("/System/Library/Fonts"), Path("/Library/Fonts"),
                 Path.home() / "Library" / "Fonts"]
    else:
        dirs += [Path("/usr/share/fonts"), Path("/usr/local/share/fonts"),
                 Path.home() / ".local" / "share" / "fonts", Path.home() / ".fonts"]
    return [d for d in dirs if d.is_dir()]


def font_files():
    seen, out = set(), []
    for d in font_dirs():
        for path in sorted(d.rglob("*")):
            if path.suffix.lower() in EXTENSIONS and path.is_file():
                key = str(path).lower()
                if key not in seen:
                    seen.add(key)
                    out.append(path)
    return out


@dataclass
class Face:
    family: str
    style: str
    path: str
    ttc_index: int
    glyphs: int
    format: str
    codepoints: frozenset = field(repr=False, default=frozenset())

    @property
    def label(self):
        return f"{self.family} {self.style}".strip()

    @property
    def filename(self):
        return os.path.basename(self.path)

    def has(self, cp):
        return cp in self.codepoints


def _unicode_codepoints(font):
    cps = set()
    for table in font["cmap"].tables:
        if table.isUnicode():
            cps.update(table.cmap)
    return cps


def _read_font(font, path, ttc_index):
    names = font["name"]
    family = names.getDebugName(16) or names.getDebugName(1) or os.path.basename(path)
    style = names.getDebugName(17) or names.getDebugName(2) or ""
    cps = _unicode_codepoints(font)
    return Face(
        family=family.strip(),
        style=style.strip(),
        path=str(path),
        ttc_index=ttc_index,
        glyphs=len(cps),
        format="OpenType/CFF" if "CFF " in font or "CFF2" in font else "TrueType",
        codepoints=frozenset(cps),
    )


def read_file(path):
    """All faces in one font file. Collections contribute every face they hold."""
    faces = []
    if path.suffix.lower() in (".ttc", ".otc"):
        collection = TTCollection(str(path), lazy=True)
        try:
            for i, font in enumerate(collection.fonts):
                try:
                    faces.append(_read_font(font, path, i))
                except Exception:
                    continue
        finally:
            collection.close()
    else:
        font = TTFont(str(path), lazy=True, fontNumber=0)
        try:
            faces.append(_read_font(font, path, 0))
        finally:
            font.close()
    return faces


def _pack(faces):
    """Codepoint sets are stored as sorted 32-bit arrays; ~4x smaller than pickled sets."""
    out = []
    for f in faces:
        d = f.__dict__.copy()
        d["codepoints"] = array.array("I", sorted(f.codepoints))
        out.append(d)
    return out


def _unpack(records):
    faces = []
    for d in records:
        d = dict(d)
        d["codepoints"] = frozenset(d["codepoints"])
        faces.append(Face(**d))
    return faces


class FontIndex:
    def __init__(self):
        self.faces = []
        self.errors = []
        self.cold = True

    # ---------------------------------------------------------------- build

    def build(self, progress=None):
        """Scan every font file, reusing cached results for unchanged files."""
        cached = store.load(CACHE_FILE) or {}
        by_key = {} if cached.get("version") != CACHE_VERSION else cached.get("files", {})

        files = font_files()
        fresh, faces, errors, reused = {}, [], [], 0
        for i, path in enumerate(files):
            if progress:
                progress(i / max(len(files), 1), path.name)
            try:
                stat = path.stat()
                key = (str(path).lower(), int(stat.st_mtime), stat.st_size)
            except OSError as exc:
                errors.append((str(path), str(exc)))
                continue

            hit = by_key.get(key[0])
            if hit and hit["key"] == key:
                fresh[key[0]] = hit
                faces.extend(_unpack(hit["faces"]))
                reused += 1
                continue
            try:
                found = read_file(path)
            except Exception as exc:
                errors.append((str(path), f"{type(exc).__name__}: {exc}"))
                continue
            fresh[key[0]] = {"key": key, "faces": _pack(found)}
            faces.extend(found)

        faces.sort(key=lambda f: (f.family.lower(), f.style.lower()))
        self.faces = faces
        self.errors = errors
        self.cold = reused < len(files) / 2
        store.save(CACHE_FILE, {"version": CACHE_VERSION, "files": fresh})
        return self

    # ---------------------------------------------------------------- queries

    @property
    def families(self):
        seen = {}
        for f in self.faces:
            seen.setdefault(f.family, f)
        return seen

    def with_codepoint(self, cp):
        """Faces that map this codepoint, widest coverage first."""
        return sorted(
            (f for f in self.faces if cp in f.codepoints),
            key=lambda f: (-f.glyphs, f.family.lower()),
        )

    def coverage(self, needed):
        """[(face, have, missing)] over a set of codepoints, best coverage first."""
        needed = set(needed)
        rows = []
        for f in self.faces:
            have = needed & f.codepoints
            rows.append((f, len(have), sorted(needed - have)))
        rows.sort(key=lambda r: (-r[1], -r[0].glyphs, r[0].family.lower()))
        return rows

    def count_faces_with(self, cp):
        return sum(1 for f in self.faces if cp in f.codepoints)

    def coverage_counts(self, needed):
        """[(face, have)] best first, skipping the missing sets.

        coverage() builds a sorted list of what each face lacks, which is wasted
        work when all you want is a ranking — and expensive on a 20,000
        codepoint block like CJK.
        """
        needed = frozenset(needed)
        rows = [(f, len(needed & f.codepoints)) for f in self.faces]
        rows.sort(key=lambda r: (-r[1], -r[0].glyphs, r[0].family.lower()))
        return rows

    def find_face(self, family, style=None):
        """One face from a family — the plainest one, not the alphabetically first."""
        matches = [
            f for f in self.faces
            if f.family.lower() == family.lower() and (style is None or f.style == style)
        ]
        if not matches:
            return None
        plain = ("regular", "book", "roman", "normal", "")
        matches.sort(key=lambda f: (f.style.lower() not in plain, f.style.lower()))
        return matches[0]

    def styles_of(self, family):
        return [f for f in self.faces if f.family.lower() == family.lower()]

    def block_coverage(self, face):
        """[(block, have, total)] over every block the face touches, best first."""
        out = []
        for name, assigned in assigned_by_block().items():
            have = sum(1 for cp in assigned if cp in face.codepoints)
            if have:
                out.append((name, have, len(assigned)))
        out.sort(key=lambda r: (-(r[1] / r[2]), -r[2]))
        return out


def best_per_family(rows, face_of=lambda row: row[0]):
    """Collapse an already-sorted ranking to one row per family.

    Six Nirmala faces covering Hindi is one useful fact, not six rows.
    """
    seen, out = set(), []
    for row in rows:
        family = face_of(row).family
        if family not in seen:
            seen.add(family)
            out.append(row)
    return out


_assigned = None


def assigned_by_block():
    """{block name: [assigned codepoints]}, computed once for the whole session."""
    global _assigned
    if _assigned is None:
        import unicodedata

        import ucd

        _assigned = {}
        for lo, hi, name in ucd.BLOCKS:
            cps = [cp for cp in range(lo, hi + 1)
                   if unicodedata.category(chr(cp)) != "Cn"]
            if cps:
                _assigned[name] = cps
    return _assigned
