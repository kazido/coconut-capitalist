import asyncio
from collections import Counter
from random import Random

import pytest
from discord import ui

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
    assert pets.pet_level(pets.level_xp(5, REG), REG) == 5 and pets.pet_level(10**12, REG) == RULES.max_level == 100
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
    monkeypatch.setattr(pets, "roll_pet", lambda rng, reg, target=None, misses=0: REG.pets["dog"])
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
    user = await with_pet("frog", xp=0)  # a farming pet: crops are its own skill's food
    await user.add_item("hot_pepper", 3)  # 1,450 pet xp each, x3 for a farming pet
    fed = await pets.feed(user, "hot_pepper", 2, REG)
    assert fed.xp == 2 * 1450 * 3 and fed.level_before == 1 and fed.level_after == pets.pet_level(8700, REG) > 1
    assert user.pethouse.pets["frog"].xp == 8700 and await user.item_quantity("hot_pepper") == 1


async def test_feeding_refuses_nonsense_and_keeps_your_crops(db):
    user = await User.get(1)
    await user.add_item("lemon", 5)
    with pytest.raises(pets.PetError, match="need a pet"):
        await pets.feed(user, "lemon", 1, REG)
    user = await with_pet("dog", xp=0)
    with pytest.raises(pets.PetError, match="eat crops and"):
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
    nav, inter = await hub("pets")
    assert "No pets yet" in all_text(nav) and "Familiar Orb" in all_text(nav)
    await click(nav, inter, "Familiar Orbs")
    assert nav.screen.id == "orbs" and find_button(nav, "Open a Familiar Orb (0)").disabled


async def test_opening_an_orb_from_the_orbs_page_shows_a_result_page(db, monkeypatch):
    monkeypatch.setattr(pets, "roll_pet", lambda rng, reg, target=None, misses=0: REG.pets["cat"])
    user = await User.get(1)
    await user.add_item(pets.ORB, 2)
    nav, inter = await hub("orbs")
    await click(nav, inter, "Open a Familiar Orb (2)")
    assert nav.screen.id == "result" and "Cat" in all_text(nav) and "A new friend" in all_text(nav) and "waiting for a bite" in all_text(nav)
    await click(nav, inter, "Another orb")
    assert "Another Cat" in all_text(nav) and "2" in all_text(nav)
    await click(nav, inter, "Back to the orbs")
    assert nav.screen.id == "orbs"
    await click(nav, inter, "Your pets")
    assert nav.screen.id == "pets" and "Cat" in all_text(nav) and "⭐⭐" in all_text(nav)


async def test_the_pet_house_switches_pets_feeds_crops_and_hands_over_spirits(db):
    user = await with_pet("dog", xp=0)
    await with_pet("cat", active=False)
    await user.add_item("lemon", 4)
    await user.add_item("spirit_of_the_forest", 1)
    nav, inter = await hub("pets")
    assert "Dog" in all_text(nav) and "work" in all_text(nav).lower()
    await choose(nav, inter, select_named(nav, "Look at a pet"), "cat")
    assert user.pethouse.active == "dog" and "Cat" in all_text(nav)  # looking is not switching
    await click(nav, inter, "Make active")
    await user.refresh()
    assert user.pethouse.active == "cat"
    before = user.pethouse.pets["cat"].xp
    feed = select_named(nav, "Feed Cat")  # the menu names the pet it is for
    hint = next(o.description for o in feed.options if o.value == "lemon")
    assert f"{REG.item('lemon').crop.pet_xp:,} xp each" in hint and "Cat" in hint
    await choose(nav, inter, feed, "lemon")
    modal = inter.response.send_modal.await_args.args[0]
    assert "xp each" in modal.children[0].description
    await modal._handler(inter, "3")
    await user.refresh()
    assert user.pethouse.pets["cat"].xp == before + 3 * REG.item("lemon").crop.pet_xp and await user.item_quantity("lemon") == 1  # (a fishing cat: x1)
    await choose(nav, inter, select_named(nav, "Give a Spirit"), "spirit_of_the_forest")
    await user.refresh()
    assert user.pethouse.pets["cat"].spirits == ["foraging"] and "Spirit" in all_text(nav)
    assert not [s for s in nav.walk_children() if getattr(s, "placeholder", "").startswith("Give a Spirit")]  # none left to give


async def test_the_home_page_links_to_the_pet_house(db):
    nav, inter = await hub("home")
    await click(nav, inter, "Pets")
    assert nav.screen.id == "pets"
    assert asyncio and buttons and set_columns


# ---- focused xp pets ---------------------------------------------------------------------------------------------------------------
def test_every_skill_has_a_pet_that_boosts_just_its_xp_and_a_better_one_is_rarer():
    for skill in ("fishing", "mining", "foraging", "farming", "combat"):
        focused = sorted((p for p in REG.pets.values() if any(b.stat == f"xp_{skill}" for b in p.bonuses)), key=lambda p: p.rarity)
        assert len(focused) >= 2, skill
        values = [next(b.value for b in p.bonuses if b.stat == f"xp_{skill}") for p in focused]
        assert values == sorted(values) and values[-1] > values[0], skill  # the rarer pet gives more
        koala = REG.pets["koala"].bonuses[0].value
        assert values[-1] > koala  # a specialist beats the all-rounder at its own skill
    assert len(REG.pets) >= 20


async def test_a_specialist_pet_boosts_only_its_own_skill(db):
    user = await with_pet("otter")
    assert await xp_multiplier(user.id, REG, "fishing") == pytest.approx(1 + REG.pets["otter"].bonuses[0].value)
    for other in ("mining", "foraging", "farming"):
        assert await xp_multiplier(user.id, REG, other) == 1.0
    phoenix = await with_pet("phoenix", user_id=2)
    assert await xp_multiplier(phoenix.id, REG, "mining") == pytest.approx(1 + REG.pets["phoenix"].bonuses[0].value)


# ---- the target system ----------------------------------------------------------------------------------------------------------------
def test_the_odds_add_up_and_a_target_is_much_likelier_with_every_miss_making_it_more_so():
    plain = pets.orb_odds(REG)
    assert sum(plain.values()) == pytest.approx(1.0) and set(plain) == set(REG.pets)
    aimed = pets.orb_odds(REG, "dragon")
    assert aimed["dragon"] == pytest.approx(plain["dragon"] * RULES.target_boost / (1 + plain["dragon"] * (RULES.target_boost - 1)), rel=0.01)
    assert aimed["dragon"] > 5 * plain["dragon"] and sum(aimed.values()) == pytest.approx(1.0)
    chances = [pets.orb_odds(REG, "dragon", misses)["dragon"] for misses in (0, 5, 10, 20, 100)]
    assert chances == sorted(chances) and chances[-1] > chances[0] * 2
    assert pets.target_boost(10**6, REG) == RULES.max_boost  # there is a ceiling
    assert all(aimed[p] < plain[p] for p in plain if p != "dragon")  # everything else is a little less likely


def test_aiming_really_does_get_you_the_pet_more_often():
    def hits(target, misses=0, n=20000):
        rng = Random(2)
        return sum(pets.roll_pet(rng, REG, target, misses).id == "dragon" for _ in range(n))

    assert hits("dragon") > 5 * hits(None) > 0
    assert hits("dragon", misses=15) > hits("dragon")


async def test_misses_pile_up_a_hit_resets_them_and_a_maxed_target_is_dropped(db, monkeypatch):
    user = await User.get(1)
    await user.add_item(pets.ORB, 12)
    await pets.set_target(user, "dragon", REG)
    seen = []
    monkeypatch.setattr(pets, "roll_pet", lambda rng, reg, target=None, misses=0: (seen.append((target, misses)) or REG.pets["dog"]))
    for _ in range(3):
        got = await pets.open_orb(user, Random(1), REG)
        assert not got.target_hit
    assert seen == [("dragon", 0), ("dragon", 1), ("dragon", 2)] and user.pethouse.misses == 3
    monkeypatch.setattr(pets, "roll_pet", lambda rng, reg, target=None, misses=0: REG.pets["dragon"])
    hit = await pets.open_orb(user, Random(1), REG)
    assert hit.target_hit and user.pethouse.misses == 0 and user.pethouse.target == "dragon" and user.pethouse.pets["dragon"].stars == 1
    for _ in range(RULES.max_stars - 1):
        await pets.open_orb(user, Random(1), REG)
    assert user.pethouse.pets["dragon"].stars == RULES.max_stars
    assert user.pethouse.target is None  # you have every star: nothing left to hunt


async def test_choosing_a_new_target_starts_the_count_again_and_nonsense_is_refused(db):
    user = await User.get(1)
    await pets.set_target(user, "dragon", REG)
    await user.update_pethouse(lambda h: setattr(h, "misses", 7))
    await pets.set_target(user, "dragon", REG)  # same one: keep the misses
    assert user.pethouse.misses == 7
    await pets.set_target(user, "cat", REG)
    assert user.pethouse.target == "cat" and user.pethouse.misses == 0
    assert await pets.set_target(user, None, REG) is None and user.pethouse.target is None
    with pytest.raises(pets.PetError, match="no such pet"):
        await pets.set_target(user, "unicorn", REG)
    await with_pet("dog", stars=RULES.max_stars)
    with pytest.raises(pets.PetError, match="every star"):
        await pets.set_target(user, "dog", REG)


async def test_the_pet_house_lets_you_aim_and_shows_your_chances(db):
    user = await User.get(1)
    await user.add_item(pets.ORB, 1)
    nav, inter = await hub("orbs")
    await choose(nav, inter, select_named(nav, "Hunt a pet"), "dragon")
    await user.refresh()
    assert user.pethouse.target == "dragon"
    page = all_text(nav)
    assert "Dragon" in page and "Hunting" in page and "%" in page
    await choose(nav, inter, select_named(nav, "Hunt a pet"), "none")
    await user.refresh()
    assert user.pethouse.target is None and "Hunting" not in all_text(nav)


# ---- skill food and pet skills --------------------------------------------------------------------------------------------------------
FEASTS = {"burger"}  # rare finds worth a multiple of a tier's pet xp (not one of a skill's three everyday foods)
FOODS = {"foraging": ("acorn_mix", "honeycomb", "golden_sap"), "mining": ("stone_biscuit", "crystal_chew", "geode_feast"),
         "fishing": ("fish_flakes", "dried_squid", "sea_feast")}


def test_every_food_skill_has_three_tiers_that_are_worth_more_and_drop_less_often():
    for skill, ids in FOODS.items():
        items = [REG.item(i) for i in ids]
        assert [i.pet_food.tier for i in items] == [1, 2, 3] and all(i.skill == skill and i.category == "pet_food" for i in items)
        assert [i.drop.rate for i in items] == sorted(i.drop.rate for i in items) and len({i.drop.rate for i in items}) == 3
        assert [pets.food_xp(i, REG) for i in items] == list(REG.economy.pets.food_xp) and all(i.sell_price == 0 for i in items)
    assert {i.id for i in REG.items.values() if i.category == "pet_food"} == {f for ids in FOODS.values() for f in ids} | FEASTS


def test_every_pet_has_one_fixed_skill_that_matches_what_it_does():
    for pet in REG.pets.values():
        assert pet.skill == pets.default_skill(pet), pet.id  # the data and the bonuses agree
        assert pet.skill in pets.SKILL_EMOJI
    assert {p.id for p in REG.pets.values() if p.skill == "global"} == {"dog", "koala", "phoenix"}  # work wage and every-skill xp
    assert REG.pets["cat"].skill == "fishing" and REG.pets["frog"].skill == "farming" and REG.pets["otter"].skill == "fishing"
    assert {p.skill for p in REG.pets.values()} >= {"fishing", "mining", "farming", "foraging", "global"}
    assert not hasattr(pets, "set_skill")  # a pet's skill is not something you change


async def test_food_of_a_pets_own_skill_is_worth_triple_a_global_pet_gets_double_and_the_rest_the_plain_amount(db):
    rules = REG.economy.pets
    user = await with_pet("cat", xp=0)  # a fishing pet
    await with_pet("dog", active=False)  # a global one
    await user.add_item("fish_flakes", 10)
    await user.add_item("acorn_mix", 10)
    base = rules.food_xp[0]
    own = await pets.feed(user, "fish_flakes", 2, REG)
    assert own.xp == 2 * base * rules.matched_food_multiplier and own.multiplier == rules.matched_food_multiplier
    other = await pets.feed(user, "acorn_mix", 2, REG)
    assert other.xp == 2 * base and other.multiplier == 1.0  # foraging food for a fishing pet: the plain amount
    glob = await pets.feed(user, "acorn_mix", 2, REG, pet_id="dog")  # any food, whatever it is
    assert glob.xp == 2 * base * rules.global_food_multiplier and glob.pet.id == "dog"
    again = await pets.feed(user, "fish_flakes", 1, REG, pet_id="dog")
    assert again.xp == base * rules.global_food_multiplier
    assert rules.matched_food_multiplier > rules.global_food_multiplier > 1  # a specialist does best, a generalist still gains
    assert await user.item_quantity("fish_flakes") == 10 - 2 - 1 and user.pethouse.active == "cat"  # (feeding a pet does not make it active)


async def test_crops_are_farming_food_so_a_farming_pet_gets_triple_for_them(db):
    user = await with_pet("frog", xp=0)
    await user.add_item("lemon", 2)
    assert (await pets.feed(user, "lemon", 2, REG)).xp == 2 * REG.item("lemon").crop.pet_xp * REG.economy.pets.matched_food_multiplier


async def test_feeding_can_name_a_pet_you_do_not_have_and_gives_the_food_back_when_it_fails(db):
    user = await with_pet("dog", xp=0)
    await user.add_item("acorn_mix", 3)
    with pytest.raises(pets.PetError, match="don't have that pet"):
        await pets.feed(user, "acorn_mix", 1, REG, pet_id="wolf")
    assert await user.item_quantity("acorn_mix") == 3 and user.pethouse.pets["dog"].xp == 0


async def test_skills_turn_up_their_own_food_at_about_the_intended_rates(db):
    from random import Random

    rng = Random(5)
    for skill, ids in FOODS.items():
        got = Counter()
        for _ in range(120):
            got.update(await pets.roll_food(skill, 1000, rng, REG))
        rolls = 120_000
        for item_id in ids:
            rate = REG.item(item_id).drop.rate
            assert got[item_id] == pytest.approx(rolls / rate, rel=0.35), item_id
        assert set(got) <= set(ids) | FEASTS  # a skill only drops its own food (and the rare feast)
    assert await pets.roll_food("combat", 5, rng, REG) == {}  # (no combat food yet)


async def test_a_mine_run_can_turn_up_stone_biscuits(db):
    from random import Random

    from cococap.services import mining as m

    class Lucky(Random):
        def randint(self, a, b):
            return 1

        def random(self):
            return 0.0

    user = await User.get(1)
    run = m.MineRun(REG.mining, REG, Lucky(1), cursors=[2], braces=1)
    run.dig()
    run.leave()
    summary = await m.settle_run(user, run, REG)
    assert summary.haul["stone_biscuit"] >= 1 and await user.item_quantity("stone_biscuit") == summary.haul["stone_biscuit"]


async def test_the_pet_house_lets_you_look_after_a_pet_that_is_not_active_and_pick_its_skill(db):
    user = await with_pet("dog", xp=0)
    await with_pet("cat", xp=0, active=False)
    await user.add_item("fish_flakes", 5)
    nav, inter = await hub("pets")
    await choose(nav, inter, select_named(nav, "Look at a pet"), "cat")
    assert "Fishing 🎣" in all_text(nav) and "Looks after" not in all_text(nav)
    hint = next(o.description for o in select_named(nav, "Feed Cat").options if o.value == "fish_flakes")
    assert f"x{REG.economy.pets.matched_food_multiplier:g}" in hint  # its own skill's food: the boosted rate is shown
    await choose(nav, inter, select_named(nav, "Feed Cat"), "fish_flakes")
    modal = inter.response.send_modal.await_args.args[0]
    await modal._handler(inter, "2")
    await user.refresh()
    assert user.pethouse.pets["cat"].xp == 2 * REG.economy.pets.food_xp[0] * REG.economy.pets.matched_food_multiplier
    assert user.pethouse.pets["dog"].xp == 0  # the cat got it, not the active dog
    assert "Fishing 🎣" in all_text(nav)
    assert not [x for x in nav.walk_children() if getattr(x, "placeholder", "").startswith("Skill for this pet")]  # (it cannot be changed)


# ---- the simplified pet page ---------------------------------------------------------------------------------------------------------
async def test_the_pet_page_puts_the_description_under_the_name_and_stars_only_on_the_page(db):
    user = await with_pet("koala", stars=3)
    await with_pet("cat", stars=2, active=False)
    nav, _ = await hub("pets")
    head = next(c.content for c in nav.walk_children() if isinstance(c, ui.TextDisplay) and "Koala" in c.content and "###" in c.content)
    lines = head.splitlines()
    assert "Koala" in lines[0] and "⭐⭐⭐" in lines[0]
    assert lines[1] == f"-# {REG.pets['koala'].description}"  # right under the name, above the xp bar
    assert "Global 🌐" in head and "Looks after" not in head and "any food" not in head
    menu = select_named(nav, "Look at a pet")
    assert all("⭐" not in (o.label + (o.description or "")) for o in menu.options)  # no stars in the dropdown
    assert [o.label for o in menu.options] == ["Cat", "Koala"]
    assert user


async def test_the_orbs_and_pet_pages_link_to_each_other(db):
    await with_pet("cat")
    nav, inter = await hub("pets")
    await click(nav, inter, "Familiar Orbs")
    assert nav.screen.id == "orbs"
    await click(nav, inter, "Your pets")
    assert nav.screen.id == "pets"


# ---- pets level as you play, and a much wider range of strength -----------------------------------------------------------------------
def test_a_pet_grows_about_ten_times_stronger_from_a_new_one_to_a_five_star_level_100():
    fresh = pets.strength(OwnedPet(), REG)
    top = pets.strength(OwnedPet(stars=RULES.max_stars, xp=pets.level_xp(RULES.max_level, REG)), REG)
    assert RULES.max_level == 100 and top / fresh > 15  # 3-5% at level 20 used to be the whole range
    assert fresh == pytest.approx(RULES.level_floor + (1 - RULES.level_floor) / RULES.max_level)


def test_a_koala_is_worth_real_xp_at_the_top():
    koala = REG.pets["koala"]
    best = pets.effects(koala, OwnedPet(stars=RULES.max_stars, xp=pets.level_xp(RULES.max_level, REG)), REG)["xp_all"]
    assert best >= 0.15  # a five-star level-100 Koala: 20%
    newborn = pets.effects(koala, OwnedPet(), REG)["xp_all"]
    assert newborn < 0.02


def test_play_xp_shares_depend_on_the_pets_skill():
    assert pets.play_share(REG.pets["otter"], "fishing", REG) == RULES.play_xp_share  # its own skill
    assert pets.play_share(REG.pets["otter"], "mining", REG) == 0.0  # a pet for another skill gains nothing from it
    assert pets.play_share(REG.pets["koala"], "mining", REG) == RULES.play_xp_global  # a global pet from anything
    assert RULES.play_xp_global < RULES.play_xp_share


async def test_the_active_pet_levels_as_you_earn_xp_in_its_skill(db):
    user = await with_pet("otter", xp=0)  # a fishing pet
    await user.add_xp("fishing", 1000)
    await user.refresh()
    assert user.pethouse.pets["otter"].xp == round(1000 * RULES.play_xp_share)
    await user.update_skill("fishing", lambda s: setattr(s, "xp", s.xp + 400))  # the other way xp is earned
    await user.refresh()
    assert user.pethouse.pets["otter"].xp == round(1000 * RULES.play_xp_share) + round(400 * RULES.play_xp_share)


async def test_a_pet_for_another_skill_does_not_level_from_play_but_a_global_one_does(db):
    user = await with_pet("otter", xp=0)
    await user.add_xp("mining", 1000)
    await user.refresh()
    assert user.pethouse.pets["otter"].xp == 0
    koala = await with_pet("koala", xp=0, user_id=2)
    await koala.add_xp("mining", 1000)
    await koala.refresh()
    assert koala.pethouse.pets["koala"].xp == round(1000 * RULES.play_xp_global)


async def test_only_the_active_pet_levels_from_play_and_nothing_happens_without_one(db):
    user = await with_pet("otter", xp=0)
    await with_pet("cat", xp=0, active=False)  # also a fishing pet, but resting
    await user.add_xp("fishing", 1000)
    await user.refresh()
    assert user.pethouse.pets["cat"].xp == 0 and user.pethouse.pets["otter"].xp > 0
    plain = await User.get(3)
    await plain.add_xp("fishing", 1000)  # no pet at all: no error
    assert (await plain.skill("fishing")).xp == 1000


async def test_play_xp_includes_the_real_skill_xp_you_were_paid_for_a_catch(db):
    from cococap.services import fishing as f

    user = await with_pet("otter", xp=0)
    inst = await user.give_instance("starter_rod")
    from cococap.services.equipment import equip

    await equip(user, "fishing", inst.id)
    cast = f.Cast(REG.item("cod"), 0, 10, [f.LEFT], 0, hooked=True, progress=1)
    caught = await f.land(user, cast, REG)
    await user.refresh()
    assert user.pethouse.pets["otter"].xp == round(caught.xp * RULES.play_xp_share) > 0
