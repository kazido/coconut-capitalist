"""Convert user documents from the pre-Pydantic flat-dict schema (<= 2025-09-09) to the nested
models in ``cococap.models``.

The old ``UserDocument`` stored skills as plain dicts (``farming.plot1``, ``mining.core_slot1``,
``fishing.skiff_level`` ...). The new models renamed/nested many of those keys, so an old document
loaded with the new model silently falls back to defaults for every renamed field (player progress
appears reset, and the next write of that sub-document would make it permanent).

``migrate_legacy_user`` is pure (dict in, dict out) so it can be unit-tested and dry-run against
production data before anything is written. It only produces ``$set`` values for skills that are
still in the legacy shape, so running it twice is a no-op.
"""

from typing import Any

PLOT_COUNT = 9
RARITY_FLAGS = {  # old quest_book.found["<rarity id>"] -> new <name>_donated flag
    "1": "common_donated",
    "2": "uncommon_donated",
    "3": "rare_donated",
    "4": "super_rare_donated",
    "5": "legendary_donated",
}


def _farming(old: dict) -> dict:
    unlocked = int(old.get("plots_unlocked", 3))
    farm = {}
    for n in range(1, PLOT_COUNT + 1):
        plot = old.get(f"plot{n}") or {}
        farm[f"plot_{n}"] = {
            "crop_id": plot.get("crop_id"),
            "cycle": plot.get("cycle", 0),
            "imbued": plot.get("imbued", False),
            "unlocked": n <= unlocked,
            "can_harvest": False,
        }
    return {
        "xp": old.get("xp", 0),
        "equipped_tool": old.get("equipped_tool"),
        "farm": farm,
        "stats": {"crops_grown": old.get("crops_grown", 0)},
        "applied_fertilizer": old.get("fertilizer"),
        "rain_god_blessings": old.get("rain_god_blessings", 0),
    }


def _foraging(old: dict) -> dict:
    return {
        "xp": old.get("xp", 0),
        "equipped_tool": old.get("equipped_tool"),
        "stats": {
            "trees_chopped": old.get("trees_chopped", 0),
            "double_trees_chopped": old.get("double_trees_chopped", 0),
            "releaf_donations": old.get("releaf_donations", 0),
        },
        "releaf_meter": old.get("releaf_meter", 0),
        "donations_made_today": old.get("donations_made_today", 0),
    }


def _fishing(old: dict) -> dict:
    book = old.get("quest_book") or {}
    found = book.get("found") or {}
    quest_book = {"level": book.get("level", 1)}
    for rarity, flag in RARITY_FLAGS.items():
        quest_book[flag] = bool(found.get(rarity, 0))  # ASSUMPTION: >0 found == donated
    return {
        "xp": old.get("xp", 0),
        "equipped_tool": old.get("equipped_tool"),
        "quest_book": quest_book,
        "skiff": {"level": old.get("skiff_level", 1)},
        "stats": {
            "quests_completed": old.get("quests_completed", 0),
            "treasures_found": old.get("treasures_found", 0),
            "fish_caught": old.get("fish_caught", 0),
            "community_book_entries": old.get("community_book_entries", 0),
        },
    }


def _mining(old: dict) -> dict:
    reactor = {
        "level": old.get("prestige_level", 1),
        "lodes_available": old.get("lodes_available", 0),
        "last_auto_mine": old.get("last_auto_mine", 0),
    }
    for n in range(1, 5):
        reactor[f"core_{n}"] = {"gem_id": old.get(f"core_slot{n}")}
    return {
        "xp": old.get("xp", 0),
        "equipped_tool": old.get("equipped_tool"),
        "reactor": reactor,
        "stats": {
            "lodes_mined": old.get("lodes_mined", 0),
            "lodes_auto_mined": old.get("lodes_auto_mined", 0),
        },
        "magnet_meter": old.get("magnet_meter", 0),
    }


def _combat(old: dict) -> dict:
    return {
        "xp": old.get("xp", 0),
        "equipped_tool": old.get("equipped_tool"),
        "stats": {
            "monsters_slain": old.get("monsters_slain", 0),
            "bosses_slain": old.get("bosses_slain", 0),
        },
    }


# skill -> (marker key that only exists in the legacy shape, converter)
_SKILLS = {
    "farming": ("plot1", _farming),
    "foraging": ("trees_chopped", _foraging),
    "fishing": ("skiff_level", _fishing),
    "mining": ("core_slot1", _mining),
    "combat": ("monsters_slain", _combat),
}


def migrate_legacy_user(doc: dict[str, Any]) -> dict[str, Any]:
    """Return ``{field: new_value}`` for every skill in ``doc`` that is still in the legacy shape.

    Fields that are absent, already migrated, or unknown are left alone (nothing is ever unset;
    legacy-only keys such as ``pets`` stay in the document).
    """
    updates: dict[str, Any] = {}
    for skill, (marker, convert) in _SKILLS.items():
        old = doc.get(skill)
        if isinstance(old, dict) and marker in old:
            updates[skill] = convert(old)
    return updates
