"""Build (and later apply) the old-id -> new-id map for the prefixed-ids rename (see docs/plans/prefixed-ids.md).

    .venv/Scripts/python.exe -m scripts.rename_ids        # writes scripts/rename_map.toml for review; changes nothing else

Edit the TOML by hand if a name is wrong; the apply step reads that file, not the rules below.
"""
from __future__ import annotations

import argparse
import re
import sys
import tomllib
from collections import Counter
from pathlib import Path

from cococap.registry.loader import get_registry

MAP_FILE = Path(__file__).with_name("rename_map.toml")
MAX_LEN = 32  # Discord's cap on emoji names
TOOL_KINDS = ("pickaxe", "rod", "axe", "hatchet", "can")
PREFIX = {"material": "material_", "fish": "fish_", "crop": "crop_", "bait": "bait_", "pet_food": "food_"}
# Hand-picked names the rules cannot guess.
EXCEPT = {
    "bastards_broadaxe": "tool_broadaxe_bastards", "graveyard_key": "key_graveyard", "land_deed": "key_land_deed",
    "lesser_orb": "key_orb_lesser", "familiar_orb": "key_orb_familiar", "greater_orb": "key_orb_greater",
}


def new_item_id(old: str, category: str) -> str:
    if old in EXCEPT:
        return EXCEPT[old]
    if category in ("scroll", "pet_item"):
        return old
    if category == "seed":
        return "seed_" + old.removesuffix("_seed")
    if category == "key_item" and old.endswith("_gemstone"):
        return "key_gemstone_" + old.removesuffix("_gemstone")
    if category == "tool":
        for kind in TOOL_KINDS:
            if old.endswith(kind):
                return f"tool_{kind}_{old.removesuffix(kind).rstrip('_')}"
        return "tool_" + old  # combat weapons and the scarab bomb: no kind to group by
    return PREFIX.get(category, "") + old


def build() -> tuple[dict[str, str], dict[str, str]]:
    reg = get_registry()
    items = {i: new_item_id(i, it.category) for i, it in reg.items.items()}
    pets = {pid: re.sub(r"[^a-z0-9]+", "_", p.name.lower()).strip("_") for pid, p in reg.pets.items()}
    return {k: v for k, v in items.items() if k != v}, pets


def problems(items: dict[str, str], pets: dict[str, str]) -> list[str]:
    reg = get_registry()
    out = []
    final_items = {items.get(i, i) for i in reg.items}
    if len(final_items) != len(reg.items):
        out.append("item id collision")
    for name in [*final_items, *(f"pet_{p}" for p in pets.values())]:
        if len(name) > MAX_LEN or not re.fullmatch(r"[a-z0-9_]{2,32}", name):
            out.append(f"bad emoji name: {name!r} ({len(name)})")
    if len(set(pets.values())) != len(pets):
        out.append("pet id collision")
    return out


ROOT = Path(__file__).resolve().parent.parent
TOML_GLOBS = ["configs/**/*.toml", "art/**/*.toml"]
PY_GLOBS = ["cococap/**/*.py", "tests/**/*.py", "utils/**/*.py", "art/*.py", "scripts/*.py"]
DOC_GLOBS = ["docs/**/*.md", "CLAUDE.md", "README.md", ".claude/**/*.md"]
NEVER = {"scripts/rename_ids.py", "scripts/rename_map.toml", "tests/test_rename_ids.py"}
NL = chr(10)
BS = chr(92)  # a backslash, spelled out so no tool mangles it
_TOKEN = re.compile('("(?:[^"' + BS + BS + ']|' + BS + BS + '.)*")|(#.*$)|(' + BS + 'b[A-Za-z_][A-Za-z0-9_]*' + BS + 'b)')


def load_map() -> dict[str, str]:
    data = tomllib.loads(MAP_FILE.read_text(encoding="utf-8"))
    both = {**data["items"], **data["pets"]}
    if len(both) != len(data["items"]) + len(data["pets"]):
        raise SystemExit("an old id is both an item and a pet; rename by hand")
    both.update({f"pet_{o}": f"pet_{n}" for o, n in data["pets"].items()})  # emoji/sprite names
    return both


def rewrite_toml(text: str, m: dict[str, str], hits: Counter) -> str:
    """Quoted strings that ARE an id, and bare words (table headers, keys); never prose, never comments."""
    def sub(match):
        string, comment, word = match.groups()
        if comment:
            return comment
        if string:
            inner = string[1:-1]
            if inner in m:
                hits[inner] += 1
                return f'"{m[inner]}"'
            return string
        if word in m:
            hits[word] += 1
            return m[word]
        return word
    return NL.join(_TOKEN.sub(sub, line) for line in text.split(NL))


def rewrite_py(text: str, m: dict[str, str], hits: Counter) -> str:
    def sub(match):
        q, inner = match.group(1), match.group(2)
        if inner in m:
            hits[inner] += 1
            return f"{q}{m[inner]}{q}"
        return match.group(0)
    return re.sub(r"([\"'])([a-z0-9_]+)\1", sub, text)


def rewrite_md(text: str, m: dict[str, str], hits: Counter) -> str:
    def sub(match):
        if match.group(1) in m:
            hits[match.group(1)] += 1
            return f"`{m[match.group(1)]}`"
        return match.group(0)
    return re.sub(r"`([a-z0-9_]+)`", sub, text)


def apply() -> int:
    m = load_map()
    jobs = [(TOML_GLOBS, rewrite_toml), (PY_GLOBS, rewrite_py), (DOC_GLOBS, rewrite_md)]
    total = Counter()
    for globs, fn in jobs:
        for g in globs:
            for path in sorted(ROOT.glob(g)):
                rel = path.relative_to(ROOT).as_posix()
                if rel in NEVER or "migrations" in rel or ".venv" in rel or "/local/" in rel or "__pycache__" in rel:
                    continue
                old = path.read_text(encoding="utf-8")
                hits: Counter = Counter()
                new = fn(old, m, hits)
                if new != old:
                    path.write_text(new, encoding="utf-8", newline="")
                    total.update(hits)
                    print(f"{rel}: {sum(hits.values())}")
    unused = sorted(set(m) - set(total))
    print(f"{NL}rewrote {sum(total.values())} occurrences of {len(total)} ids; never seen: {', '.join(unused) or 'none'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="rewrite the repo using scripts/rename_map.toml")
    if ap.parse_args().apply:
        return apply()
    items, pets = build()
    bad = problems(items, pets)
    lines = ["# old id -> new id. Review and edit; scripts/rename_ids.py applies THIS file.", "", "[items]"]
    lines += [f'{o} = "{n}"' for o, n in sorted(items.items())]
    lines += ["", "[pets]"] + [f'{o} = "{n}"' for o, n in pets.items()]
    MAP_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(items)} items and {len(pets)} pets -> {MAP_FILE}")
    for b in bad:
        print("PROBLEM:", b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
