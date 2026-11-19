"""The Magpie, Mole, Fox, Bee and Raven: pets with small effects that are not xp and never forgive a mistake."""

import pytest

from cococap.models.pethouse import OwnedPet
from cococap.registry import get_registry
from cococap.services import pets, shop
from cococap.user import User
from tests.test_pets import with_pet

REG = get_registry()
RULES = REG.economy.pets

NEW_PETS = {"gloam": "sell_bonus", "lode": "dig_shave", "lune": "rare_reroll", "pollen": "extra_harvest", "umbra": "payout_bonus"}


def built() -> dict[str, str]:
    """The new pets that exist so far (pet id -> its stat)."""
    return {p: stat for p, stat in NEW_PETS.items() if p in REG.pets and any(b.stat == stat for b in REG.pets[p].bonuses)}


def value(pet_id: str) -> float:
    """What the pet gives at max level with one star, read from the registry."""
    return next(b.value for b in REG.pets[pet_id].bonuses if b.stat == NEW_PETS[pet_id])


def test_the_new_pets_are_small_and_of_a_similar_size():
    for pet_id, stat in built().items():
        assert [b.stat for b in REG.pets[pet_id].bonuses] == [stat], pet_id  # one effect each, and it is not an xp one
        assert not stat.startswith("xp_")
        assert 0.04 <= value(pet_id) <= 0.16, pet_id  # modest at max level...
        assert value(pet_id) * (1 + RULES.star_bonus * (RULES.max_stars - 1)) <= 0.32, pet_id  # ...and still modest at five stars
    values = [value(p) for p in built()]
    assert max(values) / min(values) <= 3  # the five sit in one band


def test_the_new_pets_have_the_rarity_and_skill_they_were_given():
    wanted = {"gloam": (3, "global"), "lode": (3, "mining"), "lune": (4, "global"), "pollen": (2, "farming"), "umbra": (5, "global")}
    assert {p: (REG.pets[p].rarity, REG.pets[p].skill) for p in built()} == {p: wanted[p] for p in built()}


# ---- Magpie -------------------------------------------------------------------------------------------------------
async def test_a_magpie_makes_every_sale_pay_more_and_more_with_strength(db):
    ore = REG.item("material_gold_ore")
    plain = await User.get(1)
    await plain.add_item(ore.id, 100)
    base = await shop.sell(plain, ore.id, 100, REG)
    assert base == ore.sell_price * 100

    user = await with_pet("gloam", user_id=2)
    await user.add_item(ore.id, 100)
    paid = await shop.sell(user, ore.id, 100, REG)
    assert paid == round(base * (1 + value("gloam"))) and paid > base

    young = await with_pet("gloam", user_id=3, xp=0)
    star3 = await with_pet("gloam", user_id=4, stars=3)
    assert 0 < await shop.haggle(young, ore, REG) < value("gloam") < await shop.haggle(star3, ore, REG)
    assert await shop.haggle(star3, ore, REG) == pytest.approx(value("gloam") * (1 + 2 * RULES.star_bonus))


# ---- Mole ---------------------------------------------------------------------------------------------------------
async def _run_for(user):
    from random import Random

    from cococap.services import mining
    from cococap.services.equipment import equip

    inst = await user.give_instance("tool_pickaxe_rookie")
    await equip(user, "mining", inst.id)
    return await mining.start_run(user, Random(1), REG)


async def test_a_mole_takes_pressure_off_every_row_and_more_with_strength(db):
    plain, mole = await _run_for(await User.get(1)), await _run_for(await with_pet("lode", user_id=2))
    assert mole.growth_factor == pytest.approx(plain.growth_factor * (1 - value("lode")))
    young = await _run_for(await with_pet("lode", user_id=3, xp=0))
    star3 = await _run_for(await with_pet("lode", user_id=4, stars=3))
    assert plain.growth_factor > young.growth_factor > mole.growth_factor > star3.growth_factor
    assert star3.growth_factor == pytest.approx(plain.growth_factor * (1 - value("lode") * (1 + 2 * RULES.star_bonus)))
    # ...and it is the pressure itself that grows slower, not a softer collapse
    assert mole.rules.descent.max_risk == plain.rules.descent.max_risk


async def test_a_moles_shave_is_a_modest_slice_of_the_pressure():
    assert 0.05 <= value("lode") <= 0.10


# ---- Fox ----------------------------------------------------------------------------------------------------------
def test_a_fox_gives_rare_forest_drops_a_free_second_roll_and_more_with_strength():
    from random import Random

    from cococap.services import foraging

    rares = {i.id for i in foraging.drop_pool(REG) if i.rarity >= pets.RARE_FROM}
    assert rares  # (the forest has rare drops for the Fox to look after)

    def found(chance: float, seed: int) -> int:
        rng = Random(seed)
        return sum(q for item, q in foraging.roll_drops(60_000, rng, REG, chance).items() if item in rares)

    base, small, big = found(0.0, 1), found(value("lune") / 2, 1), found(value("lune"), 1)
    assert base < small < big


def test_a_fox_never_rerolls_common_forest_drops(monkeypatch):
    from collections import Counter
    from random import Random

    from cococap.services import foraging

    calls: Counter[str] = Counter()
    real = foraging.roll_drop
    monkeypatch.setattr(foraging, "roll_drop", lambda item, rng: calls.update([item.id]) or real(item, rng))
    foraging.roll_drops(500, Random(5), REG, 1.0)  # (a Fox that always looks twice)
    for item in foraging.drop_pool(REG):
        assert calls[item.id] >= 500 and (calls[item.id] > 500 if item.rarity >= pets.RARE_FROM else calls[item.id] == 500), item.id


def test_a_fox_makes_rare_fish_likelier():
    from random import Random

    from cococap.services import fishing as fishing_service
    from cococap.services.equipment import EffectiveStats

    water = REG.fishing.waters[2]
    stats = EffectiveStats(power=3, requirement=0, stats={"power": 3.0})

    def rare(chance: float) -> int:
        rng = Random(7)
        return sum(fishing_service.cast_line(stats, rng, 0.0, REG, water=water, pet={"rare_reroll": chance}).fish.rarity >= pets.RARE_FROM for _ in range(6000))

    assert rare(0.0) < rare(value("lune") / 2) < rare(value("lune"))


def test_a_fox_makes_rare_ore_likelier_in_the_mine():
    from random import Random

    from cococap.services import mining

    def rare(chance: float) -> int:
        total = 0
        for seed in range(400):
            run = mining.MineRun(REG.mining, REG, Random(seed), cursors=[2], rare_reroll=chance)
            for depth in range(40, 60):
                total += sum(1 for cell in run.row(depth) if cell and REG.item(cell[0]).rarity >= pets.RARE_FROM)
        return total

    assert rare(0.0) < rare(value("lune") / 2) < rare(value("lune"))


async def test_the_fox_pet_hands_its_chance_to_the_game_and_scales_with_strength(db):
    user, young = await with_pet("lune", user_id=1), await with_pet("lune", user_id=2, xp=0)
    star3 = await with_pet("lune", user_id=3, stars=3)
    assert (await pets.bonuses(user, REG))["rare_reroll"] == pytest.approx(value("lune"))
    assert (await pets.bonuses(young, REG))["rare_reroll"] < value("lune") < (await pets.bonuses(star3, REG))["rare_reroll"]


# ---- Bee ----------------------------------------------------------------------------------------------------------
async def _harvests(user, plots: int, seed: int) -> int:
    from random import Random

    from cococap.services import farming

    rng, total = Random(seed), 0
    for _ in range(plots):
        await user.add_item("seed_apple", 1)
        await farming.plant(user, 1, "seed_apple", now=0)
        await user.update_skill("farming", lambda m: setattr(m.farm.plot_1, "can_harvest", True))
        total += (await farming.harvest(user, 1, rng, now=0)).amount
    return total


async def test_a_bee_gives_free_extra_harvests_and_more_often_with_strength(db):
    plain = await _harvests(await User.get(1), 300, 1)
    young = await _harvests(await with_pet("pollen", user_id=2, xp=0), 300, 1)
    bee = await _harvests(await with_pet("pollen", user_id=3), 300, 1)
    star3 = await _harvests(await with_pet("pollen", user_id=4, stars=3), 300, 1)
    assert abs(young - plain) / plain < 0.05  # a young pet gives no real bonus (300 plots of noise)
    assert plain < bee < star3
    assert bee / plain == pytest.approx(1 + value("pollen"), abs=0.06)  # about one plot in ten gives a second harvest


async def test_a_bee_always_giving_an_extra_harvest_doubles_the_crop(db, monkeypatch):
    from cococap.services import farming

    monkeypatch.setattr(farming.pets, "bonuses", lambda user, reg=None: _constant({"extra_harvest": 1.0}))
    twice = await _harvests(await User.get(1), 50, 3)
    monkeypatch.undo()
    assert twice > await _harvests(await User.get(2), 50, 3) * 1.6


async def _constant(value_):
    return value_


# ---- Raven --------------------------------------------------------------------------------------------------------
async def test_a_raven_makes_the_daily_interest_pay_more_and_more_with_strength(db):
    from cococap.services import economy
    from tests.conftest import set_columns

    paid = {}
    for uid, kwargs in {1: None, 2: {"xp": 0}, 3: {}, 4: {"stars": 3}}.items():
        user = await with_pet("umbra", user_id=uid, **kwargs) if kwargs is not None else await User.get(uid)
        await set_columns(user, purse=1_000_000)
        paid[uid] = (await economy.claim_daily(user)).interest
    assert paid[1] == economy.daily_interest(1_000_000)
    assert paid[1] < paid[2] < paid[3] < paid[4]
    assert paid[3] == round(paid[1] * (1 + value("umbra")))
    assert paid[4] == round(paid[1] * (1 + value("umbra") * (1 + 2 * RULES.star_bonus)))


async def test_a_raven_makes_shipments_pay_more_bits(db):
    from cococap.services import shipments as sh
    from tests.test_shipments import fill_it

    async def shipped(user):
        crate = await fill_it(user)
        await sh.fill(user, "mining:basic")
        return (await sh.ship(user, "mining:basic")).bits, sh.reward(crate, REG)[0]

    plain_paid, plain_base = await shipped(await User.get(1))
    bits, base = await shipped(await with_pet("umbra", user_id=2))
    assert plain_paid == plain_base and bits == round(base * (1 + value("umbra"))) > base
    star3, star3_base = await shipped(await with_pet("umbra", user_id=3, stars=3))
    assert star3 == round(star3_base * (1 + value("umbra") * (1 + 2 * RULES.star_bonus)))
    assert star3 / star3_base > bits / base  # (each player's crate is rolled on their own, so compare the bonus, not the bits)
