"""Generate ucd.py: block ranges plus display names for every property value."""
import re, unicodedata, urllib.request

V = unicodedata.unidata_version
BASE = f"https://www.unicode.org/Public/{V}/ucd/"


def get(name):
    return urllib.request.urlopen(BASE + name, timeout=60).read().decode("utf-8")


blocks = []
for line in get("Blocks.txt").splitlines():
    line = line.split("#")[0].strip()
    if not line:
        continue
    rng, name = line.split(";")
    lo, hi = rng.strip().split("..")
    blocks.append((int(lo, 16), int(hi, 16), name.strip()))

def canon(text):
    return re.sub(r"[^A-Za-z0-9]", "", text).upper()


# PropertyValueAliases: canonical (uppercase, no separators) -> long name.
# Underscores are kept so every label pastes straight into a real \p{...}.
display = {}
for line in get("PropertyValueAliases.txt").splitlines():
    line = line.split("#")[0].strip()
    if not line:
        continue
    parts = [p.strip() for p in line.split(";")]
    if len(parts) < 3:
        continue
    prop, long_name = parts[0], parts[2]
    for alias in parts[1:]:
        display.setdefault((prop, canon(alias)), long_name)

# PropertyAliases: canonical property name -> long name, e.g. GRAPHEMEBASE -> Grapheme_Base
prop_names = {}
for line in get("PropertyAliases.txt").splitlines():
    line = line.split("#")[0].strip()
    if not line:
        continue
    parts = [p.strip() for p in line.split(";")]
    if len(parts) < 2:
        continue
    for alias in parts:
        prop_names.setdefault(canon(alias), parts[1])

with open("ucd.py", "w", encoding="utf-8") as fh:
    fh.write('"""Generated from the Unicode Character Database — do not edit by hand.\n\n')
    fh.write(f'Unicode {V}. Regenerate with scripts/gen_ucd.py when Python\'s UCD moves.\n"""\n')
    fh.write(f'UNICODE_VERSION = "{V}"\n\n')
    fh.write("# (first, last, name), sorted, non-overlapping — bisect on the first field.\n")
    fh.write("BLOCKS = [\n")
    for lo, hi, name in blocks:
        fh.write(f'    (0x{lo:04X}, 0x{hi:04X}, "{name}"),\n')
    fh.write("]\n\n")
    fh.write("# (property, canonical value) -> long name, e.g. ('sc','DEVA') -> 'Devanagari'\n")
    fh.write("VALUE_NAMES = {\n")
    for (prop, key), long_name in sorted(display.items()):
        fh.write(f'    ("{prop}", "{key}"): "{long_name}",\n')
    fh.write("}\n\n")
    fh.write("# canonical property name -> long name, e.g. 'GRAPHEMEBASE' -> 'Grapheme_Base'\n")
    fh.write("PROP_NAMES = {\n")
    for key, long_name in sorted(prop_names.items()):
        fh.write(f'    "{key}": "{long_name}",\n')
    fh.write("}\n")

print(f"blocks={len(blocks)} value_names={len(display)} prop_names={len(prop_names)} unicode={V}")
