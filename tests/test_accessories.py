"""Accessories: rolled traits by rarity and skill, 2 slots per skill, stats reaching the tool's stats."""

import random

import pytest

from cococap.errors import GameRuleError
from cococap.registry import get_registry
from cococap.services import accessories
from cococap.services.equipment import effective_stats, equipped_stats
from cococap.user import User

REG = get_registry()
RULES = REG.accessories
SKILLS = ("mining", "foraging", "fishing", "farming")


@pytest.fixture(autouse=True)
async def _real_db(db):
    """Every test here reads and writes the real SQLite fixture."""
    yield


async def player() -> User:
    return await User.get(1)


def template_of(skill: str, rarity: int):
    return next(t for t in RULES.templates if t.skill == skill and t.rarity == rarity)


async def give(user: User, template_id: str, traits: list[str] | None = None):
    return await user.give_instance(template_id, traits=traits or [])


def test_every_skill_has_a_basic_and_a_rare_template():
    for skill in SKILLS:
        rarities = sorted(t.rarity for t in RULES.templates if t.skill == skill)
        assert len(rarities) == 2 and rarities[0] == 1 and rarities[1] > 1, skill
        assert any(t.shop_price > 0 for t in RULES.templates if t.skill == skill)


def test_every_template_has_an_item_entry_in_its_category():
    for template in RULES.templates:
        assert REG.item(template.id).category == "accessory"
        assert REG.item(template.id).is_instance


async def test_roll_takes_traits_only_from_the_skills_pool_and_counts_by_rarity():
    user = await player()
    rng = random.Random(3)
    for skill in SKILLS:
        pool = {t.id for t in RULES.traits_for(skill)}
        for _ in range(30):
            instance = await accessories.roll_accessory(user, skill, rng, registry=REG)
            template = RULES.template(instance.template_id)
            assert template.skill == skill
            assert set(instance.traits) <= pool
            assert len(instance.traits) == min(RULES.trait_count(template.rarity), len(pool))
            assert len(set(instance.traits)) == len(instance.traits)
            await user.delete_instance(instance.id)


async def test_a_rarer_accessory_gets_more_traits():
    basic, rare = (template_of("mining", r) for r in (1, 5))
    assert RULES.trait_count(rare.rarity) > RULES.trait_count(basic.rarity)


async def test_drop_chance_comes_from_the_registry():
    user = await player()
    rng = random.Random(11)
    rolls = 4000
    drops = 0
    for _ in range(rolls):
        instance = await accessories.maybe_drop_accessory(user, "mining", rng, registry=REG)
        if instance is not None:
            drops += 1
            await user.delete_instance(instance.id)
    assert drops / rolls == pytest.approx(RULES.drop_chance, abs=0.004)


async def test_equip_fills_two_slots_and_refuses_a_worn_or_missing_slot():
    user = await player()
    a = await give(user, template_of("mining", 1).id)
    b = await give(user, template_of("mining", 5).id)
    await accessories.equip(user, "mining", a.id, 0, registry=REG)
    await accessories.equip(user, "mining", b.id, 1, registry=REG)
    worn = await accessories.equipped(user, "mining", REG)
    assert [w.id if w else None for w in worn] == [a.id, b.id]
    with pytest.raises(GameRuleError):
        await accessories.equip(user, "mining", a.id, 1, registry=REG)  # already worn
    with pytest.raises(GameRuleError):
        await accessories.equip(user, "mining", a.id, RULES.slots_per_skill, registry=REG)  # no such slot


async def test_equip_refuses_wrong_skill_and_not_owned():
    user = await player()
    mine = await give(user, template_of("mining", 1).id)
    with pytest.raises(GameRuleError):
        await accessories.equip(user, "fishing", mine.id, 0, registry=REG)
    other = await User.get(2)
    theirs = await give(other, template_of("fishing", 1).id)
    with pytest.raises(GameRuleError):
        await accessories.equip(user, "fishing", theirs.id, 0, registry=REG)


async def test_worn_stats_reach_equipped_stats_and_unequip_removes_them():
    user = await player()
    rare = template_of("farming", 5)
    trait = RULES.traits_for("farming")[0]
    instance = await give(user, rare.id, traits=[trait.id])
    await accessories.equip(user, "farming", instance.id, 0, registry=REG)
    expected = dict(rare.stats)
    expected[trait.stat] = expected.get(trait.stat, 0.0) + RULES.value(trait, rare.rarity)
    assert await accessories.bonus(user, "farming", REG) == pytest.approx(expected)

    # equipped_stats needs a tool in hand, so give the player a can and equip it.
    can_id = next(i.id for i in REG.items.values() if i.tool and i.tool.kind == "can")
    tool = await user.give_instance(can_id)
    await user.equip("farming", tool.id)
    stats = await equipped_stats(user, "farming", REG)
    base = effective_stats(tool, REG).stats
    for stat, amount in expected.items():
        assert stats.stats[stat] == pytest.approx(base.get(stat, 0.0) + amount)

    await accessories.unequip(user, "farming", 0, registry=REG)
    assert await accessories.bonus(user, "farming", REG) == {}
    with pytest.raises(GameRuleError):
        await accessories.unequip(user, "farming", 0, registry=REG)


# ---- drops, shop, the Accessories tab ----------------------------------------------------------------------

async def test_a_drop_rides_on_the_result_and_its_line_names_it(db, monkeypatch):
    from collections import Counter

    from cococap.services import farming as farm
    from cococap.services import foraging as fg
    from cococap.services import smithing
    from tests.test_farming import HOUR, SURE, T0 as FARM_T0, ripe_farm
    HARDWOOD = "material_hardwood"

    monkeypatch.setattr(smithing, "maybe_drop_part", _no_part)
    user = await player()
    charm = await give(user, template_of("farming", 5).id, traits=[RULES.traits_for("farming")[0].id])

    async def always(user, skill, rng, registry=None):
        return charm

    monkeypatch.setattr(accessories, "maybe_drop_accessory", always)
    await ripe_farm(user)
    result = await farm.harvest(user, 1, random.Random(1), now=FARM_T0 + 1000 * HOUR, registry=SURE)
    assert result.accessory is charm
    assert "Found a **Golden Trowel**" in accessories.accessory_line(charm, REG)

    monkeypatch.setattr(fg, "roll_drops", lambda *a, **k: Counter({HARDWOOD: 1}))
    tree = fg.Tree(1, 100, 100)
    tree.chop(100, 1.0)
    reward = await fg.fell_private(user, tree, random.Random(3), REG)
    assert reward.accessory is charm


async def _no_part(*args, **kwargs):
    return None


async def test_shop_sells_a_basic_accessory_for_its_price_one_at_a_time(db):
    from cococap.services import shop

    user = await player()
    basic = next(t for t in RULES.templates if t.skill == "mining" and t.shop_price > 0)
    await user.add_bits(basic.shop_price * 3)  # (a new player may not afford one)
    before = await user.get_bits()
    purchase = await shop.buy(user, basic.id)
    assert purchase.total == basic.shop_price
    assert await user.get_bits() == before - basic.shop_price
    assert purchase.instances[0].template_id == basic.id and purchase.instances[0].traits == []
    with pytest.raises(GameRuleError):
        await shop.buy(user, basic.id, 2)


def test_the_shop_price_in_items_toml_matches_accessories_toml():
    for t in RULES.templates:
        assert REG.item(t.id).price == t.shop_price, t.id


async def test_the_tab_toggle_equips_into_slot_one_and_unequips(db):
    from tests.test_hub import choose, click, hub, select_named

    user = await player()
    spare = await give(user, template_of("fishing", 1).id)
    from cococap.registry import get_registry
    from cococap.services import shop
    await shop.claim_starter_tools(user)
    reg = get_registry()
    rod = next(i for i in await user.instances() if (t := reg.find_item(i.template_id)) and t.tool and t.tool.kind == "rod")
    nav, inter = await hub("tools")
    await choose(nav, inter, select_named(nav, "See a tool"), str(rod.id))
    await choose(nav, inter, select_named(nav, "Pick an accessory"), str(spare.id))
    await click(nav, inter, "Equip")
    assert (await user.skill("fishing")).accessory_ids[0] == spare.id

    await click(nav, inter, "Unequip")
    assert (await user.skill("fishing")).accessory_ids[0] is None
