"""Drop tables (bits or any item, by weight), enemy loot, and the key that opens the boss fight."""

import random
from collections import Counter

import pytest
from pydantic import ValidationError

from cococap.registry import DropTable, get_registry, load_registry
from cococap.registry.models import DropEntry
from cococap.services import combat, loot
from cococap.services.combat import CombatError
from cococap.user import User

REG = get_registry()


class Script(random.Random):
    """choices() / random() / randint() with scripted answers."""

    def __init__(self, pick=0, roll=0.0):
        super().__init__(0)
        self.pick, self.roll = pick, roll

    def choices(self, population, weights=None, **kw):
        return [population[self.pick]]

    def random(self):
        return self.roll


# ---- the data -------------------------------------------------------------------------------------------------------------------
def test_shipped_tables_only_use_real_items_and_mix_bits_with_items():
    for table in REG.drop_tables.values():
        assert any(e.item is None for e in table.entries) and any(e.item for e in table.entries), table.id
        assert all(e.item in REG.items for e in table.entries if e.item)
    rare = [e for e in REG.drop_tables["graveyard"].entries if e.item in {"key_orb_familiar", "key_land_deed"}]
    total = sum(e.weight for e in REG.drop_tables["graveyard"].entries)
    assert rare and all(e.weight / total < 0.01 + 0.01 for e in rare)  # rare things are rare


def test_an_entry_is_either_an_item_or_bits_and_ranges_must_be_ordered():
    with pytest.raises(ValidationError):
        DropEntry(weight=1)
    with pytest.raises(ValidationError):
        DropEntry(weight=1, item="material_iron_ore", bits_max=5)
    with pytest.raises(ValidationError):
        DropEntry(weight=1, item="material_iron_ore", min=5, max=2)
    with pytest.raises(ValidationError):
        DropEntry(weight=1, bits_min=10, bits_max=5)
    assert DropEntry(weight=1, bits_min=1, bits_max=5).item is None


def test_unknown_items_tables_and_keys_are_rejected_when_the_data_loads(tmp_path):
    import shutil

    from cococap.registry import RegistryError
    from cococap.registry.loader import CONFIG_DIR

    def broken(name, edit, message):
        d = tmp_path / name
        shutil.copytree(CONFIG_DIR, d)
        edit(d)
        with pytest.raises(RegistryError, match=message):
            load_registry(d)

    def swap(file, old, new):
        return lambda d: (d / file).write_text((d / file).read_text().replace(old, new, 1))

    broken("item", lambda d: (d / "drops.toml").write_text('[graveyard]\nentries = [{ weight = 1, item = "nope" }]\n'), "unknown item 'nope'")
    broken("table", swap("enemies.toml", 'drops = "graveyard"', 'drops = "nope"'), "unknown drop table 'nope'")
    broken("key", swap("combat.toml", 'key = "key_graveyard"', 'key = "material_iron_ore"'), "not a key_item")


# ---- rolling -----------------------------------------------------------------------------------------------------------------------
def test_an_item_entry_gives_a_quantity_in_range_and_a_bits_entry_gives_bits_in_range():
    table = DropTable(id="t", entries=[DropEntry(weight=1, item="material_iron_ore", min=2, max=6), DropEntry(weight=1, bits_min=100, bits_max=200)])
    got = loot.roll_drop_table(table, Script(pick=0))
    assert got.item_id == "material_iron_ore" and 2 <= got.quantity <= 6 and got.bits == 0
    got = loot.roll_drop_table(table, Script(pick=1))
    assert got.item_id is None and 100 <= got.bits <= 200


def test_weights_decide_how_often_things_drop():
    table = DropTable(id="t", entries=[DropEntry(weight=90, item="material_iron_ore"), DropEntry(weight=10, item="material_gold_ore")])
    rng = random.Random(1)
    counts = Counter(loot.roll_drop_table(table, rng).item_id for _ in range(4000))
    assert 0.85 < counts["material_iron_ore"] / 4000 < 0.95 and counts["material_gold_ore"] > 200


def test_drop_chance_is_the_percent_a_kill_drops_anything():
    assert loot.roll_kill("graveyard", 60, REG, Script(roll=0.59)) is not None
    assert loot.roll_kill("graveyard", 60, REG, Script(roll=0.61)) is None
    assert loot.roll_kill(None, 100, REG, Script()) is None
    assert loot.roll_kill("graveyard", 0, REG, Script()) is None


def test_the_graveyard_gives_keys_and_now_and_then_the_rare_things():
    rng = random.Random(5)
    seen = Counter()
    for _ in range(20000):
        drop = loot.roll_drop_table(REG.drop_tables["graveyard"], rng)
        seen[drop.item_id or "bits"] += 1
    assert seen["key_graveyard"] > 100 and 0 < seen["key_orb_familiar"] < seen["key_graveyard"] and seen["bits"] > seen["material_iron_ore"]


# ---- keys --------------------------------------------------------------------------------------------------------------------------
async def level_up(user, level=20):
    await user.add_xp("combat", User.level_to_xp(level) + 1)


async def test_the_boss_needs_a_key_which_is_spent_when_you_walk_in(db):
    user = await User.get(1)
    await level_up(user)
    with pytest.raises(CombatError, match="Graveyard Key"):
        await combat.start_fight(user, "gravewarden")
    await user.add_item("key_graveyard", 2)
    battle = await combat.start_fight(user, "gravewarden")
    assert battle.living("enemy")[0].name == "The Gravewarden" and await user.item_quantity("key_graveyard") == 1


async def test_a_missing_level_does_not_cost_a_key(db):
    user = await User.get(1)
    await user.add_item("key_graveyard", 1)
    with pytest.raises(CombatError, match="combat level 20"):
        await combat.start_fight(user, "gravewarden")
    assert await user.item_quantity("key_graveyard") == 1


async def test_ordinary_fights_need_no_key(db):
    user = await User.get(1)
    battle = await combat.explore(user, "graveyard")
    assert battle.living("enemy") and await user.item_quantity("key_graveyard") == 0


# ---- settling ----------------------------------------------------------------------------------------------------------------------
def won_battle(drops="graveyard", chance=100):
    from tests.test_combat import hero, foe

    foe_unit = foe(max_hp=10, xp=40)
    foe_unit.drops, foe_unit.drop_chance = drops, chance
    battle = combat.Battle(REG.combat, [hero(attack=500), foe_unit], random.Random(0))
    battle.start()
    battle.play("slash", "e1")
    assert battle.outcome == "win"
    return battle


async def test_a_win_pays_xp_and_the_drop_in_items_and_bits(db):
    user = await User.get(1)
    bits_before = await user.get_bits() if hasattr(user, "get_bits") else None
    paid = await combat.settle(user, won_battle(), REG, Script(pick=1, roll=0.0))  # entry 1 of the graveyard table: iron ore
    assert paid.xp == 40 and paid.kills == 1 and list(paid.items) == ["material_iron_ore"]
    assert await user.item_quantity("material_iron_ore") == paid.items["material_iron_ore"]
    paid = await combat.settle(user, won_battle(), REG, Script(pick=0, roll=0.0))  # entry 0: bits
    assert paid.bits > 0 and not paid.items
    assert bits_before is None or await user.get_bits() >= bits_before + paid.bits


async def test_a_kill_that_drops_nothing_still_pays_xp(db):
    user = await User.get(1)
    paid = await combat.settle(user, won_battle(chance=0), REG, Script())
    assert paid.xp == 40 and not paid.items and paid.bits == 0
    assert (await user.skill("combat")).xp == 40


async def test_a_loss_pays_nothing_at_all(db):
    from tests.test_combat import hero, foe

    user = await User.get(1)
    battle = combat.Battle(REG.combat, [hero(max_hp=1), foe(attack=900, speed=300)], random.Random(0))
    battle.start()
    paid = await combat.settle(user, battle, REG, Script())
    assert battle.outcome == "loss" and (paid.xp, paid.bits, paid.items) == (0, 0, {})


async def test_the_boss_always_drops_something(db):
    user = await User.get(1)
    boss = combat.enemy_unit(REG.enemies["gravewarden"], "e1")
    assert boss.drops == "gravewarden" and boss.drop_chance == 100 and boss.xp == 8000


async def test_a_loss_after_killing_one_of_two_enemies_still_pays_nothing(db):
    from tests.test_combat import hero, foe

    user = await User.get(1)
    weak, tough = foe("e1", max_hp=10, xp=40), foe("e2", max_hp=10**6, attack=900, speed=50, xp=40)
    weak.drops = tough.drops = "graveyard"
    weak.drop_chance = tough.drop_chance = 100
    battle = combat.Battle(REG.combat, [hero(attack=500, max_hp=5, speed=300), weak, tough], random.Random(0))
    battle.start()
    battle.play("slash", "e1")
    while not battle.outcome:
        battle.play("slash", "e2")
    assert battle.outcome == "loss" and not weak.alive
    paid = await combat.settle(user, battle, REG, Script())
    assert (paid.xp, paid.bits, paid.items) == (0, 0, {})
    assert (await user.skill("combat")).stats.monsters_slain == 0 and (await user.skill("combat")).xp == 0
