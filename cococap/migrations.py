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


# --------------------------------------------------------------------------------------------
# MongoDB -> SQLite import (one-off, see scripts/import_mongo.py)
# --------------------------------------------------------------------------------------------
import re  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402

from cococap.id_rename import ITEMS  # noqa: E402
from cococap.models.skills.base import Skill  # noqa: E402

# Item ids that were renamed when the item registry was introduced (docs/AUDIT.md).
ITEM_ID_ALIASES = {
    "sanity": "sanity_gemstone",
    "rage": "rage_gemstone",
    "peace": "peace_gemstone",
    "balance": "balance_gemstone",
    "implosion_gem": "implosion_gemstone",
}
_SKILL_COLUMNS = {"xp", "equipped_instance_id"}
_VALID_ID = re.compile(r"^[a-z][a-z0-9_]*$")


def normalize_item_id(item_id: str) -> str:
    """Old id -> registry id: apply renames and turn 'apple.seed' into 'apple_seed'."""
    item_id = ITEM_ID_ALIASES.get(item_id, item_id).replace(".", "_")
    item_id = ITEM_ID_ALIASES.get(item_id, item_id)
    return ITEMS.get(item_id, item_id)  # then the prefixed-ids rename (cococap/id_rename.py)


@dataclass
class ConvertedUser:
    discord_id: int
    columns: dict
    stats: dict[str, int] = field(default_factory=dict)
    skills: dict[str, dict] = field(default_factory=dict)  # name -> {xp, data}
    instances: list[str] = field(default_factory=list)  # template ids of unique items to create
    equipped: dict[str, str] = field(default_factory=dict)  # skill -> template id of its tool
    items: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _number(value, default, cast, warnings: list[str], label: str):
    try:
        return cast(value) if value is not None else default
    except (TypeError, ValueError):
        warnings.append(f"{label} unreadable ({value!r}); using {default}")
        return default


def convert_mongo_user(doc: dict) -> ConvertedUser:
    """Turn one document of the old ``users`` collection (legacy flat or new nested shape) into
    rows for the SQL schema. Never raises on odd data; problems become ``warnings``."""
    from cococap.registry import get_registry
    from cococap.user import SKILL_MODELS  # local import: user.py imports the db layer

    out = ConvertedUser(
        discord_id=int(doc["discord_id"]),
        columns={"name": str(doc.get("name") or "unnamed user")},
    )
    for column in ("purse", "bank", "tokens", "luckbucks"):
        value = _number(doc.get(column), 1000 if column == "purse" else 0, int, out.warnings, column)
        if value < 0:
            out.warnings.append(f"{column} was negative ({value}); set to 0")
            value = 0
        out.columns[column] = value
    out.columns["rank"] = _number(doc.get("rank"), 0, int, out.warnings, "rank")

    cooldowns = doc.get("cooldowns") if isinstance(doc.get("cooldowns"), dict) else {}
    for name in ("work", "daily", "weekly"):
        out.columns[f"{name}_cooldown"] = _number(
            cooldowns.get(name), 0.0, float, out.warnings, f"{name} cooldown"
        )
    out.columns["settings"] = {
        k: v for k, v in (doc.get("settings") or {}).items() if k in {"auto_deposit"}
    }

    for key, value in (doc.get("statistics") or {}).items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            out.stats[key] = int(value)

    doc = {**doc, **migrate_legacy_user(doc)}  # legacy skill dicts -> nested shape
    for name, model in SKILL_MODELS.items():
        raw = doc.get(name)
        if not isinstance(raw, dict):
            continue
        if raw.get("equipped_tool"):  # a template id in the old data
            out.equipped[name] = normalize_item_id(str(raw["equipped_tool"]))
        try:
            skill: Skill = model.model_validate(raw)
        except Exception as e:  # keep the player; drop only the unreadable skill
            out.warnings.append(f"{name} skill unreadable ({e.__class__.__name__}); skipped")
            continue
        out.skills[name] = {
            "xp": skill.xp,
            "data": skill.model_dump(exclude=_SKILL_COLUMNS),
        }

    for item_id, stack in (doc.get("items") or {}).items():
        raw = stack.get("quantity", 0) if isinstance(stack, dict) else stack
        quantity = _number(raw, 0, int, out.warnings, f"item {item_id!r} quantity")
        new_id = normalize_item_id(item_id)
        if quantity <= 0:
            continue
        if not _VALID_ID.match(new_id):
            out.warnings.append(f"item {item_id!r} has an invalid id; skipped ({quantity} lost)")
            continue
        if new_id != item_id:
            out.warnings.append(f"item {item_id!r} renamed to {new_id!r}")
        template = get_registry().find_item(new_id)
        if template is not None and template.is_instance:
            out.instances.extend([new_id] * quantity)  # tools are unique objects now
        else:
            out.items[new_id] = out.items.get(new_id, 0) + quantity

    for skill, template_id in list(out.equipped.items()):
        template = get_registry().find_item(template_id)
        if template is None or not template.is_instance:
            out.warnings.append(f"equipped {skill} tool {template_id!r} is not a known tool; unequipped")
            del out.equipped[skill]
        elif template_id not in out.instances:
            out.instances.append(template_id)  # they were using it, so they own it

    if doc.get("pets"):
        out.warnings.append("legacy 'pets' data not imported (pets are being redesigned)")
    return out
