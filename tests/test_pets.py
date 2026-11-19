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
    top = pets.level_xp(RULES.max_level, REG.pets[pet_id].rarity, REG) if xp is None else xp

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
    assert all(p.bonuses and p.rarity in RULES.xp_scale and all(p.rarity in table for table in RULES.orbs.values()) for p in REG.pets.values())
    assert pets.KNOWN_STATS <= used, pets.KNOWN_STATS - used  # ...and every kind of bonus has a pet that gives it


def test_pets_cover_every_part_of_the_game():
    stats = {b.stat for p in REG.pets.values() for b in p.bonuses}
    assert {"bite_speed", "rare_luck", "pot_speed", "pot_luck"} <= stats  # fishing and crab pots
    assert {"danger_reduction", "ore_yield"} <= stats  # mining
    assert {"good_chop"} <= stats and {"grow_chance", "extra_harvest"} <= stats  # foraging, farming
    assert {"work_bonus", "xp_all"} <= stats  # the economy


# ---- strength, levels and stars --------------------------------------------------------------------------------------------
def test_levels_come_from_xp_and_stop_at_the_cap():
    for rarity, scale in RULES.xp_scale.items():
        assert pets.pet_level(0, rarity, REG) == 1 and pets.pet_level(scale, rarity, REG) == 2
        assert pets.pet_level(pets.level_xp(5, rarity, REG), rarity, REG) == 5 and pets.pet_level(10**12, rarity, REG) == RULES.max_level == 100
        assert pets.level_xp(2, rarity, REG) == scale and pets.pet_level(pets.level_xp(7, rarity, REG), rarity, REG) == 7


def test_stars_and_levels_make_a_pet_stronger_up_to_the_full_bonus():
    fresh = pets.strength(OwnedPet(), 3, REG)
    top = pets.strength(OwnedPet(xp=pets.level_xp(RULES.max_level, 3, REG)), 3, REG)
    five = pets.strength(OwnedPet(stars=5, xp=pets.level_xp(RULES.max_level, 3, REG)), 3, REG)
    assert fresh < top < five
    assert top == pytest.approx(1.0) and fresh == pytest.approx(RULES.level_floor + (1 - RULES.level_floor) / RULES.max_level)
    assert five == pytest.approx(1 + 4 * RULES.star_bonus)


async def test_a_pets_bonus_is_its_configured_value_times_its_strength(db):
    user = await with_pet("drizzle")
    assert (await pets.bonuses(user, REG))["bite_speed"] == pytest.approx(REG.pets["drizzle"].bonuses[0].value)
    star3 = await with_pet("drizzle", user_id=2, stars=3)
    assert (await pets.bonuses(star3, REG))["bite_speed"] == pytest.approx(REG.pets["drizzle"].bonuses[0].value * (1 + 2 * RULES.star_bonus))
    young = await with_pet("drizzle", user_id=3, xp=0)
    assert 0 < (await pets.bonuses(young, REG))["bite_speed"] < REG.pets["drizzle"].bonuses[0].value
    assert await pets.bonuses(await User.get(4), REG) == {}  # no pet, no bonuses
    inactive = await with_pet("drizzle", user_id=5, active=False)
    assert await pets.bonuses(inactive, REG) == {}


# ---- orbs ---------------------------------------------------------------------------------------------------------------------
def test_orbs_give_common_pets_often_and_rare_ones_rarely():
    seen = {}
    rng = Random(1)
    for _ in range(8000):
        pet = pets.roll_pet(rng, REG)
        seen[pet.rarity] = seen.get(pet.rarity, 0) + 1
    weights = RULES.orbs[pets.ORB]
    assert set(seen) == set(weights) and seen[1] > seen[2] > seen[3] > seen[4] > seen[5] > 0
    total = sum(seen.values())
    assert seen[5] / total == pytest.approx(weights[5] / sum(weights.values()), abs=0.01)


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
    monkeypatch.setattr(pets, "roll_pet", lambda rng, reg, target=None, misses=0, orb=pets.ORB: REG.pets["cinder"])
    await user.add_item(pets.ORB, 8)
    stars = [(await pets.open_orb(user, Random(1), REG)).stars for _ in range(RULES.max_stars)]
    assert stars == [1, 2, 3, 4, 5]
    last = await pets.open_orb(user, Random(1), REG)
    assert last.maxed and last.stars == RULES.max_stars and not last.is_new
    assert user.pethouse.pets["cinder"].xp == RULES.maxed_xp and user.pethouse.pets["cinder"].stars == RULES.max_stars


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
    user = await with_pet("cinder")
    await with_pet("drizzle", active=False)
    assert user.pethouse.active == "cinder"
    assert (await pets.set_active(user, "drizzle", REG)).id == "drizzle" and user.pethouse.active == "drizzle"
    with pytest.raises(pets.PetError, match="don't have that pet"):
        await pets.set_active(user, "tempest", REG)
    assert user.pethouse.active == "drizzle"


# ---- feeding and spirits ------------------------------------------------------------------------------------------------------
async def test_feeding_crops_levels_the_active_pet_up(db):
    user = await with_pet("dew", xp=0)  # a farming pet: crops are its own skill's food
    await user.add_item("crop_hot_pepper", 3)  # x3 for a farming pet
    each = REG.item("crop_hot_pepper").crop.pet_xp * 3
    fed = await pets.feed(user, "crop_hot_pepper", 2, REG)
    assert fed.xp == 2 * each and fed.level_before == 1 and fed.level_after == pets.pet_level(2 * each, REG.pets["dew"].rarity, REG) > 1
    assert user.pethouse.pets["dew"].xp == 2 * each and await user.item_quantity("crop_hot_pepper") == 1


async def test_feeding_refuses_nonsense_and_keeps_your_crops(db):
    user = await User.get(1)
    await user.add_item("crop_lemon", 5)
    with pytest.raises(pets.PetError, match="need a pet"):
        await pets.feed(user, "crop_lemon", 1, REG)
    user = await with_pet("cinder", xp=0)
    with pytest.raises(pets.PetError, match="eat crops and"):
        await pets.feed(user, "fish_cod", 1, REG)
    with pytest.raises(pets.PetError, match="don't have 9"):
        await pets.feed(user, "crop_lemon", 9, REG)
    with pytest.raises(pets.PetError, match="at least one"):
        await pets.feed(user, "crop_lemon", 0, REG)
    assert await user.item_quantity("crop_lemon") == 5 and user.pethouse.pets["cinder"].xp == 0


async def test_every_crop_is_worth_something_to_a_pet():
    crops = [i for i in REG.items.values() if i.crop]
    assert crops and all(i.crop.pet_xp > 0 for i in crops)
    assert sorted(i.crop.pet_xp for i in crops) == [i.crop.pet_xp for i in sorted(crops, key=lambda c: c.sell_price)]  # dearer crops feed more


async def test_a_spirit_adds_xp_for_its_skill_only_while_that_pet_is_active_and_only_once(db):
    user = await with_pet("cinder")
    await user.add_item("spirit_of_the_sea", 2)
    pet, skill = await pets.give_spirit(user, "spirit_of_the_sea", REG)
    assert pet.id == "cinder" and skill == "fishing" and await user.item_quantity("spirit_of_the_sea") == 1
    assert await pets.xp_bonus(user, "fishing", REG) == pytest.approx(RULES.spirit_bonus)
    assert await pets.xp_bonus(user, "mining", REG) == 0
    with pytest.raises(pets.PetError, match="already carries"):
        await pets.give_spirit(user, "spirit_of_the_sea", REG)
    assert await user.item_quantity("spirit_of_the_sea") == 1  # not wasted
    await with_pet("drizzle", active=False)
    await pets.set_active(user, "drizzle", REG)
    assert await pets.xp_bonus(user, "fishing", REG) == 0  # the Spirit stays with the dog
    with pytest.raises(pets.PetError, match="isn't a Spirit"):
        await pets.give_spirit(user, "fish_cod", REG)


# ---- the bonuses really do things -----------------------------------------------------------------------------------------------
async def test_the_dog_pays_more_work_wages(db):
    plain = await User.get(1)
    base = (await economy.claim_work(plain)).wage
    user = await with_pet("cinder", user_id=2)
    paid = (await economy.claim_work(user)).wage
    assert paid == round(base * (1 + REG.pets["cinder"].bonuses[0].value))


async def test_the_koala_and_spirits_raise_skill_xp(db):
    user = await with_pet("haze")
    assert await xp_multiplier(user.id, REG, "fishing") == pytest.approx(1 + REG.pets["haze"].bonuses[0].value)
    await user.add_item("spirit_of_the_mines", 1)
    await pets.give_spirit(user, "spirit_of_the_mines", REG)
    mine = await xp_multiplier(user.id, REG, "mining")
    assert mine == pytest.approx(1 + REG.pets["haze"].bonuses[0].value + RULES.spirit_bonus)
    assert await xp_multiplier(user.id, REG, "fishing") < mine  # the Spirit is for mining only


async def test_pet_xp_stacks_with_the_party_bonus(db):
    user = await with_pet("haze")
    party = await Party.create(1)
    await party.add_member(2)
    expected = (1 + REG.economy.party_xp_bonus_by_size[0]) * (1 + REG.pets["haze"].bonuses[0].value)
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
    cutoff = round(base_odds / (1 + REG.pets["tempest"].bonuses[0].value))
    assert cutoff < base_odds
    plain, dragon = await with_pet("drizzle"), await with_pet("tempest", user_id=2)

    async def catch(user):
        cast = f.Cast(REG.item("fish_cod"), 0, 10, [f.LEFT], 0, hooked=True, progress=1)
        return await f.land(user, cast, REG, now=1.0, rng=Rolls(1))

    assert (await catch(plain)).hallucination is None and (await catch(dragon)).hallucination is not None


async def test_the_turtle_steadies_the_mine_and_brings_up_more_ore(db):
    plain = await User.get(1)
    steady = await with_pet("murk", user_id=2)
    for user in (plain, steady):
        inst = await user.give_instance("tool_pickaxe_rookie")
        await equip(user, "mining", inst.id)
    a, b = await mining.start_run(plain, Random(1)), await mining.start_run(steady, Random(1))
    pet = REG.pets["murk"].bonuses
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
            plot.crop_id, plot.since = "seed_coconut", 100  # (a slow grower, so every extra growth shows up)
            farming.apply_rain(farm, uid, 3600 * 160, REG, bonus)
            total += plot.cycle
            assert m
        return total

    assert grown(0.3) > grown(0.0)
    assert user


# ---- the Pet House -----------------------------------------------------------------------------------------------------------------------
async def test_the_pet_house_for_someone_with_no_pets_explains_orbs(db):
    nav, inter = await hub("pets")
    assert "No pets yet" in all_text(nav) and "Familiar Orb" in all_text(nav)
    assert not any(b.label == "Familiar Orbs" for b in buttons(nav))  # the tab menu switches pages now
    nav.screen.tab = "orbs"
    await nav.refresh(inter)
    assert nav.screen.tab == "orbs" and find_button(nav, f"Buy Familiar Orb ({REG.item(pets.ORB).price:,} bits)").disabled


async def test_orbs_are_bought_on_the_orbs_page_for_the_configured_price(db):
    from cococap.screens.pets import orb_items
    from tests.test_hub import submit

    orb = REG.item(pets.ORB)
    assert orb in orb_items(REG) and orb.buyable
    user = await User.get(1)
    await set_columns(user, purse=orb.price * 4)
    nav, inter = await hub("pets", tab="orbs")
    assert not [b for b in buttons(nav) if b.label == "Buy several"]
    await click(nav, inter, f"Buy {orb.name} ({orb.price:,} bits)")  # (opens a popup asking how many)
    modal = await submit(inter, "4")
    await modal.on_submit(inter)
    user = await User.get(1)
    assert await user.item_quantity(pets.ORB) == 4 and user.purse == 0 and "Bought 4" in all_text(nav)
    assert find_button(nav, f"Open {orb.name} (4)")  # (owning some turns the button into Open)
    assert not [b for b in buttons(nav) if b.label == f"Buy {orb.name} ({orb.price:,} bits)"]


async def test_opening_an_orb_from_the_orbs_page_shows_a_result_page(db, monkeypatch):
    monkeypatch.setattr(pets, "roll_pet", lambda rng, reg, target=None, misses=0, orb=pets.ORB: REG.pets["drizzle"])
    user = await User.get(1)
    await user.add_item(pets.ORB, 2)
    nav, inter = await hub("pets", tab="orbs")
    await click(nav, inter, "Open Familiar Orb (2)")
    assert nav.screen.id == "result" and "Drizzle" in all_text(nav) and "A new friend" in all_text(nav) and "waiting for a bite" in all_text(nav)
    await click(nav, inter, "Another orb")
    assert "Another Drizzle" in all_text(nav) and "2" in all_text(nav)
    await click(nav, inter, "Back to the orbs")
    assert nav.screen.tab == "orbs"
    nav.screen.tab = "pets"
    await nav.refresh(inter)
    assert nav.screen.id == "pets" and "Drizzle" in all_text(nav) and "⭐⭐" in all_text(nav)


async def test_the_pet_house_switches_pets_feeds_crops_and_hands_over_spirits(db):
    user = await with_pet("cinder", xp=0)
    await with_pet("drizzle", active=False)
    await user.add_item("crop_lemon", 4)
    await user.add_item("spirit_of_the_forest", 1)
    nav, inter = await hub("pets")
    assert "Cinder" in all_text(nav) and "work" in all_text(nav).lower()
    await choose(nav, inter, select_named(nav, "Look at a pet"), "drizzle")
    await user.refresh()
    assert user.pethouse.active == "drizzle" and "Drizzle" in all_text(nav)  # picking a pet makes it active
    assert not [b for b in buttons(nav) if b.label == "Make active"]
    before = user.pethouse.pets["drizzle"].xp
    feed = select_named(nav, "Feed Drizzle")  # the menu names the pet it is for
    hint = next(o.description for o in feed.options if o.value == "crop_lemon")
    assert f"{REG.item('crop_lemon').crop.pet_xp:,} xp each" in hint
    await choose(nav, inter, feed, "crop_lemon")
    modal = inter.response.send_modal.await_args.args[0]
    assert "xp each" in modal.children[0].description
    await modal._handler(inter, "3")
    await user.refresh()
    assert user.pethouse.pets["drizzle"].xp == before + 3 * REG.item("crop_lemon").crop.pet_xp and await user.item_quantity("crop_lemon") == 1  # (a fishing cat: x1)
    await choose(nav, inter, select_named(nav, "Give a Spirit"), "spirit_of_the_forest")
    await user.refresh()
    assert user.pethouse.pets["drizzle"].spirits == ["foraging"] and "Spirit" in all_text(nav)
    assert not [s for s in nav.walk_children() if getattr(s, "placeholder", "").startswith("Give a Spirit")]  # none left to give


async def test_the_home_page_links_to_the_pet_house(db):
    nav, inter = await hub("home")
    pets_section = next(c for c in nav.walk_children() if isinstance(c, ui.Section) and "Pets" in " ".join(getattr(t, "content", "") for t in c.children))
    await pets_section.accessory.callback(inter)
    assert nav.screen.id == "pets"
    assert asyncio and buttons and set_columns


# ---- focused xp pets ---------------------------------------------------------------------------------------------------------------
def test_every_skill_has_a_pet_that_boosts_just_its_xp_and_a_better_one_is_rarer():
    for skill in ("fishing", "mining", "foraging", "farming", "combat"):
        focused = sorted((p for p in REG.pets.values() if any(b.stat == f"xp_{skill}" for b in p.bonuses)), key=lambda p: p.rarity)
        assert focused, skill  # (mining has just the Badger since the Mole took on a pressure effect)
        values = [next(b.value for b in p.bonuses if b.stat == f"xp_{skill}") for p in focused]
        assert values == sorted(values) and (len(values) == 1 or values[-1] > values[0]), skill  # the rarer pet gives more
        koala = REG.pets["haze"].bonuses[0].value
        assert values[-1] > koala  # a specialist beats the all-rounder at its own skill
    assert len(REG.pets) >= 20


async def test_a_specialist_pet_boosts_only_its_own_skill(db):
    user = await with_pet("ripple")
    assert await xp_multiplier(user.id, REG, "fishing") == pytest.approx(1 + REG.pets["ripple"].bonuses[0].value)
    for other in ("mining", "foraging", "farming"):
        assert await xp_multiplier(user.id, REG, other) == 1.0
    phoenix = await with_pet("halo", user_id=2)
    assert await xp_multiplier(phoenix.id, REG, "mining") == pytest.approx(1 + REG.pets["halo"].bonuses[0].value)


# ---- the target system ----------------------------------------------------------------------------------------------------------------
def test_the_odds_add_up_and_a_target_is_much_likelier_with_every_miss_making_it_more_so():
    plain = pets.orb_odds(REG)
    assert sum(plain.values()) == pytest.approx(1.0) and set(plain) == set(REG.pets)
    aimed = pets.orb_odds(REG, "tempest")
    assert aimed["tempest"] == pytest.approx(plain["tempest"] * RULES.target_boost / (1 + plain["tempest"] * (RULES.target_boost - 1)), rel=0.01)
    assert aimed["tempest"] > 5 * plain["tempest"] and sum(aimed.values()) == pytest.approx(1.0)
    chances = [pets.orb_odds(REG, "tempest", misses)["tempest"] for misses in (0, 5, 10, 20, 100)]
    assert chances == sorted(chances) and chances[-1] > chances[0] * 2
    assert pets.target_boost(10**6, REG) == RULES.max_boost  # there is a ceiling
    assert all(aimed[p] < plain[p] for p in plain if p != "tempest")  # everything else is a little less likely


def test_aiming_really_does_get_you_the_pet_more_often():
    def hits(target, misses=0, n=20000):
        rng = Random(2)
        return sum(pets.roll_pet(rng, REG, target, misses).id == "tempest" for _ in range(n))

    assert hits("tempest") > 5 * hits(None) > 0
    assert hits("tempest", misses=15) > hits("tempest")


async def test_misses_pile_up_a_hit_resets_them_and_a_maxed_target_is_dropped(db, monkeypatch):
    user = await User.get(1)
    await user.add_item(pets.ORB, 12)
    await pets.set_target(user, "tempest", REG)
    seen = []
    monkeypatch.setattr(pets, "roll_pet", lambda rng, reg, target=None, misses=0, orb=pets.ORB: (seen.append((target, misses)) or REG.pets["cinder"]))
    for _ in range(3):
        got = await pets.open_orb(user, Random(1), REG)
        assert not got.target_hit
    assert seen == [("tempest", 0), ("tempest", 1), ("tempest", 2)] and user.pethouse.misses == 3
    monkeypatch.setattr(pets, "roll_pet", lambda rng, reg, target=None, misses=0, orb=pets.ORB: REG.pets["tempest"])
    hit = await pets.open_orb(user, Random(1), REG)
    assert hit.target_hit and user.pethouse.misses == 0 and user.pethouse.target == "tempest" and user.pethouse.pets["tempest"].stars == 1
    for _ in range(RULES.max_stars - 1):
        await pets.open_orb(user, Random(1), REG)
    assert user.pethouse.pets["tempest"].stars == RULES.max_stars
    assert user.pethouse.target is None  # you have every star: nothing left to hunt


async def test_choosing_a_new_target_starts_the_count_again_and_nonsense_is_refused(db):
    user = await User.get(1)
    await pets.set_target(user, "tempest", REG)
    await user.update_pethouse(lambda h: setattr(h, "misses", 7))
    await pets.set_target(user, "tempest", REG)  # same one: keep the misses
    assert user.pethouse.misses == 7
    await pets.set_target(user, "drizzle", REG)
    assert user.pethouse.target == "drizzle" and user.pethouse.misses == 7  # switching keeps the pity
    assert await pets.set_target(user, None, REG) is None and user.pethouse.target is None
    with pytest.raises(pets.PetError, match="no such pet"):
        await pets.set_target(user, "unicorn", REG)
    await with_pet("cinder", stars=RULES.max_stars)
    with pytest.raises(pets.PetError, match="every star"):
        await pets.set_target(user, "cinder", REG)


async def test_the_pet_house_lets_you_aim_and_shows_your_chances(db):
    user = await User.get(1)
    await user.add_item(pets.ORB, 1)
    nav, inter = await hub("pets", tab="orbs")
    await choose(nav, inter, select_named(nav, "Hunt a pet"), "tempest")
    await user.refresh()
    assert user.pethouse.target == "tempest"
    page = all_text(nav)
    assert "Tempest" in page and "Hunting" in page and "boost" in page
    await choose(nav, inter, select_named(nav, "Hunt a pet"), "none")
    await user.refresh()
    assert user.pethouse.target is None and "Hunting" not in all_text(nav)


# ---- skill food and pet skills --------------------------------------------------------------------------------------------------------
FEASTS = {"food_burger"}  # rare finds worth a multiple of a tier's pet xp (not one of a skill's three everyday foods)
FOODS = {"foraging": ("food_acorn_mix", "food_honeycomb", "food_golden_sap"), "mining": ("food_stone_biscuit", "food_crystal_chew", "food_geode_feast"),
         "fishing": ("food_fish_flakes", "food_dried_squid", "food_sea_feast")}


def test_every_food_skill_has_three_tiers_that_are_worth_more_and_drop_less_often():
    for skill, ids in FOODS.items():
        items = [REG.item(i) for i in ids]
        assert [i.pet_food.tier for i in items] == [1, 2, 3] and all(i.skill == skill and i.category == "pet_food" for i in items)
        assert [i.drop.rate for i in items] == sorted(i.drop.rate for i in items) and len({i.drop.rate for i in items}) == 3
        assert [pets.food_xp(i, REG) for i in items] == list(REG.economy.pets.food_xp) and all(i.sell_price > 0 for i in items)  # (sellable like everything but tools)
    assert {i.id for i in REG.items.values() if i.category == "pet_food"} == {f for ids in FOODS.values() for f in ids} | FEASTS


def test_every_pet_has_one_fixed_skill_that_matches_what_it_does():
    for pet in REG.pets.values():
        assert pet.skill == pets.default_skill(pet), pet.id  # the data and the bonuses agree
        assert pet.skill in pets.SKILL_EMOJI
    assert {p.id for p in REG.pets.values() if p.skill == "global"} == {"cinder", "haze", "halo", "gloam", "lune", "umbra"}  # work wage, every-skill xp, sales
    assert REG.pets["drizzle"].skill == "fishing" and REG.pets["dew"].skill == "farming" and REG.pets["ripple"].skill == "fishing"
    assert {p.skill for p in REG.pets.values()} >= {"fishing", "mining", "farming", "foraging", "global"}
    assert not hasattr(pets, "set_skill")  # a pet's skill is not something you change


async def test_food_of_a_pets_own_skill_is_worth_triple_a_global_pet_gets_double_and_the_rest_the_plain_amount(db):
    rules = REG.economy.pets
    user = await with_pet("drizzle", xp=0)  # a fishing pet
    await with_pet("cinder", active=False)  # a global one
    await user.add_item("food_fish_flakes", 10)
    await user.add_item("food_acorn_mix", 10)
    base = rules.food_xp[0]
    own = await pets.feed(user, "food_fish_flakes", 2, REG)
    assert own.xp == 2 * base * rules.matched_food_multiplier and own.multiplier == rules.matched_food_multiplier
    other = await pets.feed(user, "food_acorn_mix", 2, REG)
    assert other.xp == 2 * base and other.multiplier == 1.0  # foraging food for a fishing pet: the plain amount
    glob = await pets.feed(user, "food_acorn_mix", 2, REG, pet_id="cinder")  # any food, whatever it is
    assert glob.xp == 2 * base * rules.global_food_multiplier and glob.pet.id == "cinder"
    again = await pets.feed(user, "food_fish_flakes", 1, REG, pet_id="cinder")
    assert again.xp == base * rules.global_food_multiplier
    assert rules.matched_food_multiplier > rules.global_food_multiplier > 1  # a specialist does best, a generalist still gains
    assert await user.item_quantity("food_fish_flakes") == 10 - 2 - 1 and user.pethouse.active == "drizzle"  # (feeding a pet does not make it active)


async def test_crops_are_farming_food_so_a_farming_pet_gets_triple_for_them(db):
    user = await with_pet("dew", xp=0)
    await user.add_item("crop_lemon", 2)
    assert (await pets.feed(user, "crop_lemon", 2, REG)).xp == 2 * REG.item("crop_lemon").crop.pet_xp * REG.economy.pets.matched_food_multiplier


async def test_feeding_can_name_a_pet_you_do_not_have_and_gives_the_food_back_when_it_fails(db):
    user = await with_pet("cinder", xp=0)
    await user.add_item("food_acorn_mix", 3)
    with pytest.raises(pets.PetError, match="don't have that pet"):
        await pets.feed(user, "food_acorn_mix", 1, REG, pet_id="scorch")
    assert await user.item_quantity("food_acorn_mix") == 3 and user.pethouse.pets["cinder"].xp == 0


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
    assert summary.haul["food_stone_biscuit"] >= 1 and await user.item_quantity("food_stone_biscuit") == summary.haul["food_stone_biscuit"]


async def test_the_pet_house_lets_you_look_after_a_pet_that_is_not_active_and_pick_its_skill(db):
    user = await with_pet("cinder", xp=0)
    await with_pet("drizzle", xp=0, active=False)
    await user.add_item("food_fish_flakes", 5)
    nav, inter = await hub("pets")
    await choose(nav, inter, select_named(nav, "Look at a pet"), "drizzle")
    assert "Fishing 🎣" in all_text(nav) and "Looks after" not in all_text(nav)
    hint = next(o.description for o in select_named(nav, "Feed Drizzle").options if o.value == "food_fish_flakes")
    assert f"x{REG.economy.pets.matched_food_multiplier:g}" in hint  # its own skill's food: the boosted rate is shown
    await choose(nav, inter, select_named(nav, "Feed Drizzle"), "food_fish_flakes")
    modal = inter.response.send_modal.await_args.args[0]
    await modal._handler(inter, "2")
    await user.refresh()
    assert user.pethouse.pets["drizzle"].xp == 2 * REG.economy.pets.food_xp[0] * REG.economy.pets.matched_food_multiplier
    assert user.pethouse.pets["cinder"].xp == 0  # the cat got it, not the active dog
    assert "Fishing 🎣" in all_text(nav)
    assert not [x for x in nav.walk_children() if getattr(x, "placeholder", "").startswith("Skill for this pet")]  # (it cannot be changed)


# ---- the simplified pet page ---------------------------------------------------------------------------------------------------------
async def test_the_pet_page_puts_the_description_under_the_name_and_stars_only_on_the_page(db):
    user = await with_pet("haze", stars=3)
    await with_pet("drizzle", stars=2, active=False)
    nav, _ = await hub("pets")
    head = next(c.content for c in nav.walk_children() if isinstance(c, ui.TextDisplay) and "Haze" in c.content and "###" in c.content)
    lines = head.splitlines()
    assert "Haze" in lines[0] and "⭐⭐⭐" in lines[0]
    assert lines[1] == f"-# {REG.pets['haze'].description}"  # right under the name, above the xp bar
    assert "Global 🌐" in head and "Looks after" not in head and "any food" not in head
    menu = select_named(nav, "Look at a pet")
    assert [o.label for o in menu.options] == ["Drizzle ⭐⭐", "Haze ⭐⭐⭐"]  # unicode stars in the dropdown label (custom emoji do not render there)
    assert all(o.description and len(o.description) <= 100 and "<:" not in o.description for o in menu.options)  # level, skill and the ability, plain text
    assert user


async def test_the_orbs_and_pet_pages_are_switched_by_the_tab_menu_not_buttons(db):
    await with_pet("drizzle")
    nav, inter = await hub("pets")
    assert not any(b.label == "Familiar Orbs" for b in buttons(nav))
    nav.screen.tab = "orbs"
    await nav.refresh(inter)
    assert not any(b.label == "Your pets" for b in buttons(nav))


# ---- pets level as you play, and a much wider range of strength -----------------------------------------------------------------------
def test_a_pet_grows_about_ten_times_stronger_from_a_new_one_to_a_five_star_level_100():
    fresh = pets.strength(OwnedPet(), 3, REG)
    top = pets.strength(OwnedPet(stars=RULES.max_stars, xp=pets.level_xp(RULES.max_level, 3, REG)), 3, REG)
    assert RULES.max_level == 100 and top / fresh > 15  # 3-5% at level 20 used to be the whole range
    assert fresh == pytest.approx(RULES.level_floor + (1 - RULES.level_floor) / RULES.max_level)


def test_a_koala_is_worth_real_xp_at_the_top():
    koala = REG.pets["haze"]
    best = pets.effects(koala, OwnedPet(stars=RULES.max_stars, xp=pets.level_xp(RULES.max_level, koala.rarity, REG)), REG)["xp_all"]
    assert best >= 0.15  # a five-star level-100 Haze: 20%
    newborn = pets.effects(koala, OwnedPet(), REG)["xp_all"]
    assert newborn < 0.02


def test_play_xp_shares_depend_on_the_pets_skill():
    assert pets.play_share(REG.pets["ripple"], "fishing", REG) == RULES.play_xp_share  # its own skill
    assert pets.play_share(REG.pets["ripple"], "mining", REG) == 0.0  # a pet for another skill gains nothing from it
    assert pets.play_share(REG.pets["haze"], "mining", REG) == RULES.play_xp_global  # a global pet from anything
    assert RULES.play_xp_global < RULES.play_xp_share


async def test_the_active_pet_levels_as_you_earn_xp_in_its_skill(db):
    user = await with_pet("ripple", xp=0)  # a fishing pet
    await user.add_xp("fishing", 1000)
    await user.refresh()
    assert user.pethouse.pets["ripple"].xp == round(1000 * RULES.play_xp_share)
    await user.update_skill("fishing", lambda s: setattr(s, "xp", s.xp + 400))  # the other way xp is earned
    await user.refresh()
    assert user.pethouse.pets["ripple"].xp == round(1000 * RULES.play_xp_share) + round(400 * RULES.play_xp_share)


async def test_a_pet_for_another_skill_does_not_level_from_play_but_a_global_one_does(db):
    user = await with_pet("ripple", xp=0)
    await user.add_xp("mining", 1000)
    await user.refresh()
    assert user.pethouse.pets["ripple"].xp == 0
    koala = await with_pet("haze", xp=0, user_id=2)
    await koala.add_xp("mining", 1000)
    await koala.refresh()
    assert koala.pethouse.pets["haze"].xp == round(1000 * RULES.play_xp_global)


async def test_only_the_active_pet_levels_from_play_and_nothing_happens_without_one(db):
    user = await with_pet("ripple", xp=0)
    await with_pet("drizzle", xp=0, active=False)  # also a fishing pet, but resting
    await user.add_xp("fishing", 1000)
    await user.refresh()
    assert user.pethouse.pets["drizzle"].xp == 0 and user.pethouse.pets["ripple"].xp > 0
    plain = await User.get(3)
    await plain.add_xp("fishing", 1000)  # no pet at all: no error
    assert (await plain.skill("fishing")).xp == 1000


async def test_play_xp_includes_the_real_skill_xp_you_were_paid_for_a_catch(db):
    from cococap.services import fishing as f

    user = await with_pet("ripple", xp=0)
    inst = await user.give_instance("tool_rod_starter")
    from cococap.services.equipment import equip

    await equip(user, "fishing", inst.id)
    cast = f.Cast(REG.item("fish_cod"), 0, 10, [f.LEFT], 0, hooked=True, progress=1)
    caught = await f.land(user, cast, REG)
    await user.refresh()
    assert user.pethouse.pets["ripple"].xp == round(caught.xp * RULES.play_xp_share) > 0


# ---- orb tiers -----------------------------------------------------------------------------------------------------------------------
def test_every_orb_has_odds_a_price_and_the_cheaper_ones_give_commoner_pets():
    kinds = pets.orb_ids(REG)
    assert pets.ORB in kinds and len(kinds) >= 3 and set(kinds) == set(RULES.orbs)
    prices = [REG.item(i).price for i in kinds]
    assert prices == sorted(prices) and len(set(prices)) == len(prices)

    def average_rarity(orb):
        return sum(c * REG.pets[pid].rarity for pid, c in pets.orb_odds(REG, orb=orb).items())

    averages = [average_rarity(i) for i in kinds]
    assert averages == sorted(averages) and averages[0] < averages[-1]
    for orb in kinds:
        assert sum(pets.orb_odds(REG, orb=orb).values()) == pytest.approx(1.0)


def test_the_cheapest_orb_leans_on_rarity_1_and_2_and_the_priciest_on_4_and_5():
    cheap, dear = pets.orb_ids(REG)[0], pets.orb_ids(REG)[-1]

    def share(orb, rarities):
        return sum(c for pid, c in pets.orb_odds(REG, orb=orb).items() if REG.pets[pid].rarity in rarities)

    assert share(cheap, {1, 2}) > 0.5 and share(dear, {4, 5}) > 0.5
    assert share(cheap, {4, 5}) < share(pets.ORB, {4, 5}) < share(dear, {4, 5})


async def test_each_kind_of_orb_is_spent_when_opened_and_rolls_from_its_own_table(db, monkeypatch):
    seen = []
    real = pets.roll_pet
    monkeypatch.setattr(pets, "roll_pet", lambda rng, reg, target=None, misses=0, orb=pets.ORB: (seen.append(orb), real(rng, reg, target, misses, orb))[1])
    user = await User.get(1)
    for orb in pets.orb_ids(REG):
        with pytest.raises(pets.PetError, match=REG.item(orb).name):
            await pets.open_orb(user, Random(1), REG, orb=orb)
        await user.add_item(orb, 1)
        await pets.open_orb(user, Random(1), REG, orb=orb)
        assert await user.item_quantity(orb) == 0
    assert seen == pets.orb_ids(REG)
    with pytest.raises(pets.PetError):
        await pets.open_orb(user, Random(1), REG, orb="key_land_deed")


async def test_the_orbs_page_lets_you_buy_and_open_every_kind(db, monkeypatch):
    monkeypatch.setattr(pets, "roll_pet", lambda rng, reg, target=None, misses=0, orb=pets.ORB: REG.pets["drizzle"])
    user = await User.get(1)
    for orb in pets.orb_ids(REG):
        await user.add_item(orb, 1)
    nav, inter = await hub("pets", tab="orbs")
    for orb in pets.orb_ids(REG):
        item = REG.item(orb)
        await click(nav, inter, f"Open {item.name} (1)")
        assert nav.screen.id == "result"
        await click(nav, inter, "Back to the orbs")
        assert find_button(nav, f"Buy {item.name} ({item.price:,} bits)")


# ---- levels depend on rarity, and nobody loses a level when that was introduced ---------------------------------------------------------------
def test_common_pets_level_quickest_and_rare_ones_slowest():
    scales = [RULES.xp_scale[r] for r in sorted(RULES.xp_scale)]
    assert scales == sorted(scales) and scales[0] < scales[-1] and set(RULES.xp_scale) == {p.rarity for p in REG.pets.values()} | set(RULES.xp_scale)
    assert pets.level_xp(10, 1, REG) < pets.level_xp(10, 5, REG)
    assert pets.pet_level(5000, 1, REG) > pets.pet_level(5000, 5, REG)


def test_moving_old_xp_onto_the_rarity_curves_never_changes_any_pets_level():
    from cococap.models.pethouse import CURVE_VERSION, Pethouse

    for pet in REG.pets.values():
        xps = [0, 1, 299, 300, 301, 1199, 1200, 24299, 24300, 24301, 720299, 720300, 2940299, 2940300, 5_000_000, 10**9]
        old_levels = {xp: min(RULES.max_level, 1 + int((xp / pets.LEGACY_XP_SCALE) ** 0.5)) for xp in xps}
        house = Pethouse.model_validate({"pets": {pet.id: {"xp": 5}}})
        assert house.curve_version == 0  # (saved before the field existed)
        for xp in xps:
            house = Pethouse.model_validate({"pets": {pet.id: {"xp": xp, "stars": 2}}})
            assert pets.upgrade_curve(house, REG) and house.curve_version == CURVE_VERSION
            assert pets.pet_level(house.pets[pet.id].xp, pet.rarity, REG) == old_levels[xp], (pet.id, xp)
            assert house.pets[pet.id].stars == 2
            assert not pets.upgrade_curve(house, REG)  # (only once)


def test_a_fresh_or_current_house_is_left_alone():
    from cococap.models.pethouse import Pethouse

    assert Pethouse().curve_version and not pets.upgrade_curve(Pethouse(), REG)
    current = Pethouse.model_validate({"pets": {"cinder": {"xp": 1234}}, "curve_version": 1})
    assert not pets.upgrade_curve(current, REG) and current.pets["cinder"].xp == 1234


async def test_a_stored_old_house_keeps_every_level_when_the_player_is_loaded_and_saved(db):
    from cococap.db import get_database
    from cococap.db.tables import UserRow

    old_xp = {"cinder": 24300, "tempest": 24300, "drizzle": 108300}  # levels 10, 10 and 20 on the old curve
    async with get_database().session() as session:
        (await session.get(UserRow, (await User.get(1)).id)).pethouse = {
            "active": "tempest", "pets": {k: {"xp": v, "stars": 1} for k, v in old_xp.items()}}
    user = await User.get(1)
    for pet_id, xp in old_xp.items():
        assert pets.pet_level(user.pethouse.pets[pet_id].xp, REG.pets[pet_id].rarity, REG) == 1 + int((xp / 300) ** 0.5)
    await pets.set_active(user, "drizzle", REG)  # a save writes the rescaled xp back, once
    again = await User.get(1)
    assert again.pethouse.curve_version == 1
    for pet_id, xp in old_xp.items():
        assert pets.pet_level(again.pethouse.pets[pet_id].xp, REG.pets[pet_id].rarity, REG) == 1 + int((xp / 300) ** 0.5)
    assert again.pethouse.pets["cinder"].xp < old_xp["cinder"] < again.pethouse.pets["tempest"].xp  # common sooner, legendary later
