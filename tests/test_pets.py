import asyncio
from random import Random

import pytest

from cococap.models.pethouse import OwnedPet
from cococap.registry import get_registry
from cococap.services import economy, farming, mining, pets
from cococap.services import fishing as f
from cococap.services.equipment import EffectiveStats, equip
from cococap.services.party import Party, xp_multiplier
from cococap.user import User
from tests.conftest import set_columns
from tests.test_hub import all_text, buttons, choose, click, find_button, hub, select_named

REG = get_registry()
RULES = REG.economy.pets


async def with_pet(pet_id, user_id=1, stars=1, xp=None, active=True):
    """A player who owns this pet, at the top level unless told otherwise (so bonuses are the full configured values)."""
    user = await User.get(user_id)
    top = pets.level_xp(RULES.max_level, REG) if xp is None else xp

    def give(house):
        house.pets[pet_id] = OwnedPet(stars=stars, xp=top)
        if active:
            house.active = pet_id

    await user.update_pethouse(give)
    return user


def rod(power=3):
    return EffectiveStats(power=power, requirement=0, stats={"power": float(power)})


# ---- the data ---------------------------------------------------------------------------------------------------------
def test_every_pet_has_a_bonus_and_every_bonus_is_something_the_game_uses():
    used = {b.stat for p in REG.pets.values() for b in p.bonuses}
    assert used <= pets.KNOWN_STATS, used - pets.KNOWN_STATS
    assert all(p.bonuses and p.rarity in RULES.orb_weights for p in REG.pets.values())
    assert pets.KNOWN_STATS <= used, pets.KNOWN_STATS - used  # ...and every kind of bonus has a pet that gives it


def test_pets_cover_every_part_of_the_game():
    stats = {b.stat for p in REG.pets.values() for b in p.bonuses}
    assert {"bite_speed", "rare_luck", "pot_speed", "pot_luck"} <= stats  # fishing and crab pots
    assert {"danger_reduction", "ore_yield"} <= stats  # mining
    assert {"good_chop"} <= stats and {"grow_chance", "crop_yield"} <= stats  # foraging, farming
    assert {"work_bonus", "xp_all"} <= stats  # the economy


# ---- strength, levels and stars --------------------------------------------------------------------------------------------
def test_levels_come_from_xp_and_stop_at_the_cap():
    assert pets.pet_level(0, REG) == 1 and pets.pet_level(RULES.xp_scale, REG) == 2
    assert pets.pet_level(8_000, REG) == 5 and pets.pet_level(10**12, REG) == RULES.max_level
    assert pets.level_xp(2, REG) == RULES.xp_scale and pets.pet_level(pets.level_xp(7, REG), REG) == 7


def test_stars_and_levels_make_a_pet_stronger_up_to_the_full_bonus():
    fresh = pets.strength(OwnedPet(), REG)
    top = pets.strength(OwnedPet(xp=pets.level_xp(RULES.max_level, REG)), REG)
    five = pets.strength(OwnedPet(stars=5, xp=pets.level_xp(RULES.max_level, REG)), REG)
    assert fresh < top < five
    assert top == pytest.approx(1.0) and fresh == pytest.approx(RULES.level_floor + (1 - RULES.level_floor) / RULES.max_level)
    assert five == pytest.approx(1 + 4 * RULES.star_bonus)


async def test_a_pets_bonus_is_its_configured_value_times_its_strength(db):
    user = await with_pet("cat")
    assert (await pets.bonuses(user, REG))["bite_speed"] == pytest.approx(REG.pets["cat"].bonuses[0].value)
    star3 = await with_pet("cat", user_id=2, stars=3)
    assert (await pets.bonuses(star3, REG))["bite_speed"] == pytest.approx(REG.pets["cat"].bonuses[0].value * (1 + 2 * RULES.star_bonus))
    young = await with_pet("cat", user_id=3, xp=0)
    assert 0 < (await pets.bonuses(young, REG))["bite_speed"] < REG.pets["cat"].bonuses[0].value
    assert await pets.bonuses(await User.get(4), REG) == {}  # no pet, no bonuses
    inactive = await with_pet("cat", user_id=5, active=False)
    assert await pets.bonuses(inactive, REG) == {}


# ---- orbs ---------------------------------------------------------------------------------------------------------------------
def test_orbs_give_common_pets_often_and_rare_ones_rarely():
    seen = {}
    rng = Random(1)
    for _ in range(8000):
        pet = pets.roll_pet(rng, REG)
        seen[pet.rarity] = seen.get(pet.rarity, 0) + 1
    assert set(seen) == set(RULES.orb_weights) and seen[1] > seen[2] > seen[3] > seen[4] > seen[5] > 0
    total = sum(seen.values())
    assert seen[5] / total == pytest.approx(RULES.orb_weights[5] / sum(RULES.orb_weights.values()), abs=0.01)


async def test_opening_an_orb_spends_it_gives_a_pet_and_the_first_one_starts_working(db):
    user = await User.get(1)
    with pytest.raises(pets.PetError, match="don't have a Familiar Orb"):
        await pets.open_orb(user, Random(1), REG)
    await user.add_item(pets.ORB, 2)
    got = await pets.open_orb(user, Random(1), REG)
    assert got.is_new and got.stars == 1 and not got.maxed
    assert await user.item_quantity(pets.ORB) == 1
    house = user.pethouse
    assert house.active == got.pet.id and set(house.pets) == {got.pet.id}


async def test_a_duplicate_adds_a_star_and_a_maxed_one_gives_xp_instead(db, monkeypatch):
    user = await User.get(1)
    monkeypatch.setattr(pets, "roll_pet", lambda rng, reg: REG.pets["dog"])
    await user.add_item(pets.ORB, 8)
    stars = [(await pets.open_orb(user, Random(1), REG)).stars for _ in range(RULES.max_stars)]
    assert stars == [1, 2, 3, 4, 5]
    last = await pets.open_orb(user, Random(1), REG)
    assert last.maxed and last.stars == RULES.max_stars and not last.is_new
    assert user.pethouse.pets["dog"].xp == RULES.maxed_xp and user.pethouse.pets["dog"].stars == RULES.max_stars


async def test_the_orb_comes_back_if_the_pet_cannot_be_added(db, monkeypatch):
    user = await User.get(1)
    await user.add_item(pets.ORB, 1)

    async def broken(*_a, **_k):
        raise RuntimeError("database hiccup")

    monkeypatch.setattr(user, "update_pethouse", broken)
    with pytest.raises(RuntimeError):
        await pets.open_orb(user, Random(1), REG)
    assert await user.item_quantity(pets.ORB) == 1


async def test_switching_pets_only_works_for_pets_you_own(db):
    user = await with_pet("dog")
    await with_pet("cat", active=False)
    assert user.pethouse.active == "dog"
    assert (await pets.set_active(user, "cat", REG)).id == "cat" and user.pethouse.active == "cat"
    with pytest.raises(pets.PetError, match="don't have that pet"):
        await pets.set_active(user, "dragon", REG)
    assert user.pethouse.active == "cat"


# ---- feeding and spirits ------------------------------------------------------------------------------------------------------
async def test_feeding_crops_levels_the_active_pet_up(db):
    user = await with_pet("dog", xp=0)
    await user.add_item("hot_pepper", 3)  # 1,450 pet xp each
    fed = await pets.feed(user, "hot_pepper", 2, REG)
    assert fed.xp == 2 * 1450 and fed.level_before == 1 and fed.level_after == pets.pet_level(2900, REG) > 1
    assert user.pethouse.pets["dog"].xp == 2900 and await user.item_quantity("hot_pepper") == 1


async def test_feeding_refuses_nonsense_and_keeps_your_crops(db):
    user = await User.get(1)
    await user.add_item("lemon", 5)
    with pytest.raises(pets.PetError, match="active pet"):
        await pets.feed(user, "lemon", 1, REG)
    user = await with_pet("dog", xp=0)
    with pytest.raises(pets.PetError, match="eat crops"):
        await pets.feed(user, "cod", 1, REG)
    with pytest.raises(pets.PetError, match="don't have 9"):
        await pets.feed(user, "lemon", 9, REG)
    with pytest.raises(pets.PetError, match="at least one"):
        await pets.feed(user, "lemon", 0, REG)
    assert await user.item_quantity("lemon") == 5 and user.pethouse.pets["dog"].xp == 0


async def test_every_crop_is_worth_something_to_a_pet():
    crops = [i for i in REG.items.values() if i.crop]
    assert crops and all(i.crop.pet_xp > 0 for i in crops)
    assert sorted(i.crop.pet_xp for i in crops) == [i.crop.pet_xp for i in sorted(crops, key=lambda c: c.sell_price)]  # dearer crops feed more


async def test_a_spirit_adds_xp_for_its_skill_only_while_that_pet_is_active_and_only_once(db):
    user = await with_pet("dog")
    await user.add_item("spirit_of_the_sea", 2)
    pet, skill = await pets.give_spirit(user, "spirit_of_the_sea", REG)
    assert pet.id == "dog" and skill == "fishing" and await user.item_quantity("spirit_of_the_sea") == 1
    assert await pets.xp_bonus(user, "fishing", REG) == pytest.approx(RULES.spirit_bonus)
    assert await pets.xp_bonus(user, "mining", REG) == 0
    with pytest.raises(pets.PetError, match="already carries"):
        await pets.give_spirit(user, "spirit_of_the_sea", REG)
    assert await user.item_quantity("spirit_of_the_sea") == 1  # not wasted
    await with_pet("cat", active=False)
    await pets.set_active(user, "cat", REG)
    assert await pets.xp_bonus(user, "fishing", REG) == 0  # the Spirit stays with the dog
    with pytest.raises(pets.PetError, match="isn't a Spirit"):
        await pets.give_spirit(user, "cod", REG)


# ---- the bonuses really do things -----------------------------------------------------------------------------------------------
async def test_the_dog_pays_more_work_wages(db):
    plain = await User.get(1)
    base = (await economy.claim_work(plain)).wage
    user = await with_pet("dog", user_id=2)
    paid = (await economy.claim_work(user)).wage
    assert paid == round(base * (1 + REG.pets["dog"].bonuses[0].value))


async def test_the_koala_and_spirits_raise_skill_xp(db):
    user = await with_pet("koala")
    assert await xp_multiplier(user.id, REG, "fishing") == pytest.approx(1 + REG.pets["koala"].bonuses[0].value)
    await user.add_item("spirit_of_the_mines", 1)
    await pets.give_spirit(user, "spirit_of_the_mines", REG)
    mine = await xp_multiplier(user.id, REG, "mining")
    assert mine == pytest.approx(1 + REG.pets["koala"].bonuses[0].value + RULES.spirit_bonus)
    assert await xp_multiplier(user.id, REG, "fishing") < mine  # the Spirit is for mining only


async def test_pet_xp_stacks_with_the_party_bonus(db):
    user = await with_pet("koala")
    party = await Party.create(1)
    await party.add_member(2)
    expected = (1 + REG.economy.party_xp_bonus_by_size[0]) * (1 + REG.pets["koala"].bonuses[0].value)
    assert await xp_multiplier(1, REG, "farming") == pytest.approx(expected)
    assert user


def test_the_cat_makes_fish_bite_sooner_and_the_eagle_finds_rare_ones():
    water = f.water_by_id(REG, "river")

    def mean_wait(pet):
        return sum(f.cast_line(rod(), Random(i), 0, REG, water=water, pet=pet).bite_at for i in range(500)) / 500

    assert mean_wait({"bite_speed": 0.3}) == pytest.approx(mean_wait({}) * 0.7, rel=0.05)

    def rare_share(luck):
        rng = Random(5)
        return sum(f.roll_fish(rng, REG, water, luck).rarity >= 4 for _ in range(20000)) / 20000

    assert rare_share(0.5) > rare_share(0.0) * 1.35
    assert rare_share(0.0) > 0


def test_the_dragon_makes_chests_and_hallucinations_more_likely():
    def chests(luck):
        return sum(bool(f.cast_line(rod(), Random(i), 0, REG, armed=True, pet={"treasure_luck": luck}).chest) for i in range(6000))

    assert chests(0.5) > chests(0.0) * 1.3 > 0


async def test_the_dragon_also_brings_on_hallucinations_sooner(db):
    class Rolls(Random):
        """Hits the 1-in-N roll only if N is at most 25."""

        def randint(self, a, b):
            return 1 if b <= cutoff else b

    base_odds = REG.fishing.treasure.hallucination_odds
    cutoff = round(base_odds / (1 + REG.pets["dragon"].bonuses[0].value))
    assert cutoff < base_odds
    plain, dragon = await with_pet("cat"), await with_pet("dragon", user_id=2)

    async def catch(user):
        cast = f.Cast(REG.item("cod"), 0, 10, [f.LEFT], 0, hooked=True, progress=1)
        return await f.land(user, cast, REG, now=1.0, rng=Rolls(1))

    assert (await catch(plain)).hallucination is None and (await catch(dragon)).hallucination is not None


async def test_the_turtle_steadies_the_mine_and_brings_up_more_ore(db):
    plain = await User.get(1)
    steady = await with_pet("turtle", user_id=2)
    for user in (plain, steady):
        inst = await user.give_instance("rookiepickaxe")
        await equip(user, "mining", inst.id)
    a, b = await mining.start_run(plain, Random(1)), await mining.start_run(steady, Random(1))
    pet = REG.pets["turtle"].bonuses
    assert b.growth_factor == pytest.approx(a.growth_factor - pet[0].value)
    assert b.yield_factor == pytest.approx(a.yield_factor * (1 + pet[1].value))


async def test_the_frog_makes_crops_grow_more_often_and_the_bee_makes_harvests_bigger(db):
    user = await User.get(1)

    def grown(bonus):
        total = 0
        for uid in range(1, 400):
            m = type("M", (), {})()
            from cococap.models.skills.farming import Farming

            farm = Farming()
            plot = farm.farm.plot_1
            plot.crop_id, plot.since = "coconut_seed", 100  # (a slow grower, so every extra growth shows up)
            farming.apply_rain(farm, uid, 3600 * 160, REG, bonus)
            total += plot.cycle
            assert m
        return total

    assert grown(0.3) > grown(0.0)
    bee = await with_pet("bee", user_id=2)
    await bee.add_item("apple_seed", 1)
    await farming.plant(bee, 1, "apple_seed", now=0)
    await bee.update_skill("farming", lambda m: setattr(m.farm.plot_1, "can_harvest", True))
    amount = (await farming.harvest(bee, 1, Random(1), now=0)).amount
    plain = await User.get(3)
    await plain.add_item("apple_seed", 1)
    await farming.plant(plain, 1, "apple_seed", now=0)
    await plain.update_skill("farming", lambda m: setattr(m.farm.plot_1, "can_harvest", True))
    assert amount >= (await farming.harvest(plain, 1, Random(1), now=0)).amount and user


# ---- the Pet House -----------------------------------------------------------------------------------------------------------------------
async def test_the_pet_house_for_someone_with_no_pets_explains_orbs(db):
    nav, _ = await hub("pets")
    assert "no pets yet" in all_text(nav) and "Familiar Orb" in all_text(nav)
    assert find_button(nav, "Open a Familiar Orb (0)").disabled


async def test_opening_an_orb_from_the_pet_house_shows_a_result_page(db, monkeypatch):
    monkeypatch.setattr(pets, "roll_pet", lambda rng, reg: REG.pets["cat"])
    user = await User.get(1)
    await user.add_item(pets.ORB, 2)
    nav, inter = await hub("pets")
    await click(nav, inter, "Open a Familiar Orb (2)")
    assert nav.screen.id == "result" and "Cat" in all_text(nav) and "A new friend" in all_text(nav) and "waiting for a bite" in all_text(nav)
    await click(nav, inter, "Another orb")
    assert "Another Cat" in all_text(nav) and "2" in all_text(nav)
    await click(nav, inter, "To the Pet House")
    assert nav.screen.id == "pets" and "Cat" in all_text(nav) and "⭐⭐" in all_text(nav)


async def test_the_pet_house_switches_pets_feeds_crops_and_hands_over_spirits(db):
    user = await with_pet("dog", xp=0)
    await with_pet("cat", active=False)
    await user.add_item("lemon", 4)
    await user.add_item("spirit_of_the_forest", 1)
    nav, inter = await hub("pets")
    assert "Dog" in all_text(nav) and "work" in all_text(nav).lower()
    await choose(nav, inter, select_named(nav, "Switch active pet"), "cat")
    await user.refresh()
    assert user.pethouse.active == "cat" and "Cat" in all_text(nav)
    before = user.pethouse.pets["cat"].xp
    await choose(nav, inter, select_named(nav, "Feed your pet"), "lemon")
    modal = inter.response.send_modal.await_args.args[0]
    await modal._handler(inter, "3")
    await user.refresh()
    assert user.pethouse.pets["cat"].xp == before + 3 * REG.item("lemon").crop.pet_xp and await user.item_quantity("lemon") == 1
    await choose(nav, inter, select_named(nav, "Give a Spirit"), "spirit_of_the_forest")
    await user.refresh()
    assert user.pethouse.pets["cat"].spirits == ["foraging"] and "Spirit" in all_text(nav)
    assert not [s for s in nav.walk_children() if getattr(s, "placeholder", "").startswith("Give a Spirit")]  # none left to give


async def test_the_home_page_links_to_the_pet_house(db):
    nav, inter = await hub("home")
    await click(nav, inter, "Pets")
    assert nav.screen.id == "pets"
    assert asyncio and buttons and set_columns
