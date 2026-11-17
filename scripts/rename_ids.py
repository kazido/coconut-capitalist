"""Build (and later apply) the old-id -> new-id map for the prefixed-ids rename (see docs/plans/prefixed-ids.md).

    .venv/Scripts/python.exe -m scripts.rename_ids        # writes scripts/rename_map.toml for review; changes nothing else

Edit the TOML by hand if a name is wrong; the apply step reads that file, not the rules below.
"""
from __future__ import annotations

import re
import sys
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


def main() -> int:
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
