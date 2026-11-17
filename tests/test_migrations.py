import pytest
from cococap.migrations import migrate_legacy_user
from cococap.models.skills.combat import Combat
from cococap.models.skills.farming import Farming
from cococap.models.skills.fishing import Fishing
from cococap.models.skills.foraging import Foraging
from cococap.models.skills.mining import Mining

# Shape of a document written by the pre-Pydantic UserDocument (git: abb9a68^:cococap/models.py)
LEGACY = {
    "name": "old timer",
    "discord_id": 7,
    "farming": {
        "xp": 500, "equipped_tool": "hoe", "is_farming": True, "crops_grown": 12,
        "fertilizer": "bonemeal", "rain_god_blessings": 2, "plots_unlocked": 4,
        "plot1": {"crop_id": "wheat", "cycle": 3, "imbued": True},
        "plot2": {"crop_id": None, "cycle": 0, "imbued": False},
        "plot3": {"crop_id": None, "cycle": 0, "imbued": False},
        "plot4": {"crop_id": "corn", "cycle": 1, "imbued": False},
        "plot5": {}, "plot6": {}, "plot7": {}, "plot8": {}, "plot9": {},
    },
    "mining": {
        "xp": 900, "equipped_tool": "pick", "lodes_mined": 40, "lodes_auto_mined": 8,
        "core_slot1": "ruby", "core_slot2": None, "core_slot3": None, "core_slot4": "opal",
        "prestige_level": 3, "lodes_available": 5, "last_auto_mine": 1.5e9, "magnet_meter": 9,
    },
    "fishing": {
        "xp": 10, "equipped_tool": None, "skiff_level": 2, "fish_caught": 30,
        "community_book_entries": 4, "quests_completed": 6, "treasures_found": 1,
        "quest_book": {"level": 2, "found": {"1": 3, "2": 0, "3": 1, "4": 0, "5": 0}},
    },
    "foraging": {"xp": 1, "equipped_tool": None, "trees_chopped": 20, "double_trees_chopped": 2,
                 "releaf_donations": 3, "releaf_meter": 7, "donations_made_today": 1},
    "combat": {"xp": 3, "equipped_tool": "sword", "monsters_slain": 50, "bosses_slain": 1},
    "pets": {"rex": {"level": 4}},
}


def test_legacy_document_converts_to_the_new_models():
    updates = migrate_legacy_user(LEGACY)

    class doc:  # each converted skill must satisfy its real model
        farming = Farming.model_validate(updates["farming"])
        mining = Mining.model_validate(updates["mining"])
        fishing = Fishing.model_validate(updates["fishing"])
        foraging = Foraging.model_validate(updates["foraging"])
        combat = Combat.model_validate(updates["combat"])

    assert doc.farming.xp == 500 and doc.farming.stats.crops_grown == 12
    assert doc.farming.applied_fertilizer == "bonemeal"
    assert doc.farming.farm.plot_1.crop_id == "wheat" and doc.farming.farm.plot_1.imbued
    assert doc.farming.farm.plot_4.unlocked and not doc.farming.farm.plot_5.unlocked
    assert doc.mining.reactor.level == 3 and doc.mining.reactor.core_1.gem_id == "ruby"
    assert doc.mining.reactor.core_4.gem_id == "opal" and doc.mining.stats.lodes_mined == 40
    assert doc.fishing.skiff.level == 2 and doc.fishing.stats.fish_caught == 30
    assert doc.fishing.quest_book.common_donated and doc.fishing.quest_book.rare_donated
    assert not doc.fishing.quest_book.uncommon_donated
    assert doc.foraging.stats.trees_chopped == 20 and doc.combat.stats.monsters_slain == 50


def test_migration_is_idempotent_and_never_removes_fields():
    first = migrate_legacy_user(LEGACY)
    assert set(first) == {"farming", "mining", "fishing", "foraging", "combat"}
    migrated_doc = {**LEGACY, **first}
    assert migrate_legacy_user(migrated_doc) == {}  # already new shape
    assert "pets" in migrated_doc  # untouched legacy-only data survives


def test_fresh_documents_are_left_alone():
    fresh = {"farming": Farming().model_dump(), "mining": Mining().model_dump()}
    assert migrate_legacy_user(fresh) == {}


# ---- Mongo -> SQLite import -------------------------------------------------------------------
from cococap.migrations import convert_mongo_user, normalize_item_id  # noqa: E402
from cococap.user import User  # noqa: E402
from scripts.import_mongo import write_sqlite  # noqa: E402


def test_normalize_item_id():
    assert normalize_item_id("apple.seed") == "seed_apple"
    assert normalize_item_id("implosion_gem") == "key_gemstone_implosion"
    assert normalize_item_id("sanity") == "key_gemstone_sanity"
    assert normalize_item_id("fish_cod") == "fish_cod"


def test_convert_legacy_mongo_user():
    doc = {
        **LEGACY, "purse": -50, "bank": 700, "rank": 3, "tokens": 4,
        "cooldowns": {"work": 10.5, "daily": 0, "weekly": 3},
        "statistics": {"hl_wins": 9, "claimed_work": 2, "junk": "x"},
        "settings": {"auto_deposit": True, "mystery": 1},
        "items": {"material_copper_ore": {"quantity": 5}, "tool_axe_starter": {"quantity": 2}, "apple.seed": {"quantity": 2}, "seed_apple": {"quantity": 1},
                  "empty": {"quantity": 0}, "Bad Id!": {"quantity": 1}, "implosion_gem": {"quantity": 1}},
    }
    u = convert_mongo_user(doc)
    assert u.columns["purse"] == 0 and any("negative" in w for w in u.warnings)
    assert (u.columns["bank"], u.columns["rank"], u.columns["work_cooldown"]) == (700, 3, 10.5)
    assert u.columns["settings"] == {"auto_deposit": True}
    assert u.stats == {"hl_wins": 9, "claimed_work": 2}
    assert u.items == {"material_copper_ore": 5, "seed_apple": 3, "key_gemstone_implosion": 1}
    assert u.instances.count("tool_axe_starter") == 2  # tools become unique objects, one per quantity
    assert any("Bad Id!" in w for w in u.warnings) and any("pets" in w for w in u.warnings)
    assert u.skills["mining"]["xp"] == 900
    assert u.skills["mining"]["data"]["reactor"]["core_4"]["gem_id"] == "opal"
    assert set(u.skills) == {"farming", "mining", "fishing", "foraging", "combat"}


def test_convert_survives_garbage():
    u = convert_mongo_user({"discord_id": "12", "mining": {"xp": "lots"}, "items": {"x": "y"}, "cooldowns": None})
    assert u.discord_id == 12 and u.skills == {} and u.items == {}
    assert any("mining" in w for w in u.warnings) and any("item 'x'" in w for w in u.warnings)


async def test_full_import_into_sqlite_then_play(db):
    docs = [
        convert_mongo_user({**LEGACY, "purse": 500, "items": {"fish_cod": {"quantity": 3}}, "statistics": {"hl_wins": 4}}),
        convert_mongo_user({"discord_id": 8, "name": "friend", "purse": 10}),
    ]
    parties = [{"party_id": 1234, "party_owner": 7, "party_members": [7, 8, 999]}]  # 999 doesn't exist
    special = [{"_id": "x", "amount": 123, "total_drops_missed": 4, "times_missed": 1, "counter": 5, "last_winner": 7, "date_started": "01-02-2025"}]
    counts = await write_sqlite(db, docs, parties, special, force=False)
    assert counts["users"] == 2 and counts["parties"] == 1 and counts["megadrop"] == 1

    old = await User.get(7)
    assert old.purse == 500 and await old.items() == {"fish_cod": 3} and await old.get_stat("hl_wins") == 4
    assert (await old.skill("farming")).farm.plot_4.crop_id == "corn"
    assert (await old.skill("mining")).reactor.level == 3
    from cococap.exts.core.party_system import Party

    assert sorted((await Party.load(1234)).members) == [7, 8]

    with pytest.raises(SystemExit):
        await write_sqlite(db, docs, [], [], force=False)  # refuses to overwrite


async def test_import_creates_instances_and_equips_the_old_equipped_tool(db):
    old = {**LEGACY, "mining": {**LEGACY["mining"], "equipped_tool": "tool_pickaxe_rookie"},
           "farming": {**LEGACY["farming"], "equipped_tool": "hoe"}}  # "hoe" isn't a real tool
    converted = convert_mongo_user(old)
    assert converted.equipped == {"mining": "tool_pickaxe_rookie"}
    assert any("hoe" in w for w in converted.warnings)
    await write_sqlite(db, [converted], [], [], force=False)
    user = await User.get(7)
    pick = await user.equipped_instance("mining")
    assert pick.template_id == "tool_pickaxe_rookie" and [i.template_id for i in await user.instances()] == ["tool_pickaxe_rookie"]
