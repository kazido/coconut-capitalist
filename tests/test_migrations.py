from cococap.migrations import migrate_legacy_user
from cococap.models.models import UserDocument

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


def test_legacy_document_converts_to_the_new_models(db):
    updates = migrate_legacy_user(LEGACY)
    doc = UserDocument.model_validate({**LEGACY, **updates})  # must satisfy the real model

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


def test_migration_is_idempotent_and_never_removes_fields(db):
    first = migrate_legacy_user(LEGACY)
    assert set(first) == {"farming", "mining", "fishing", "foraging", "combat"}
    migrated_doc = {**LEGACY, **first}
    assert migrate_legacy_user(migrated_doc) == {}  # already new shape
    assert "pets" in migrated_doc  # untouched legacy-only data survives


def test_fresh_documents_are_left_alone(db):
    fresh = UserDocument(name="n", discord_id=1).model_dump(mode="json")
    assert migrate_legacy_user(fresh) == {}
