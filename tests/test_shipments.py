"""Shipments: a basic and a harder crate per skill (unlocked by that skill's level), filled with materials and shipped for xp and bits. The weekly community one is off by default."""

import asyncio
from random import Random

import pytest

from cococap.registry import get_registry
from cococap.services import shipments as sh
from cococap.user import User
from tests.test_hub import all_text, buttons, choose, find_button, hub, select_named

REG = get_registry()
P = REG.shipments.personal
BASIC, HARD = P.tiers["basic"], P.tiers["hard"]
C = REG.shipments.community
LEVELS = lambda n: {s: n for s in sh.SKILLS}  # noqa: E731


XP10, XP30 = 20_000, 180_000  # about level 10 and level 30


async def level_up(user, skill="mining", xp=XP10):
    await user.add_xp(skill, xp)
    return user


# ---- making a crate --------------------------------------------------------------------------------------------------------------------------
def test_a_crate_has_the_right_number_of_different_materials_worth_about_what_its_tier_says():
    for tier in P.tiers:
        t = P.tiers[tier]
        for level in (t.unlock_level, 40, 80):
            for skill in sh.SKILLS:
                for seed in range(15):
                    ship = sh.make_shipment(Random(seed), skill, LEVELS(level), REG, tier)
                    assert len(ship.need) == t.kinds and all(q >= 1 for q in ship.need.values()) and ship.id == f"{skill}:{tier}"
                    target = t.value_base + t.value_per_level * level
                    assert 0.6 * target <= sh.worth(ship.need, REG) <= 3 * target, (tier, level, skill, seed)  # (one piece of a dear, rare find can overshoot a small crate)


def test_a_crate_is_mostly_its_own_skill_with_something_from_another():
    for tier, t in P.tiers.items():
        for seed in range(30):
            ship = sh.make_shipment(Random(seed), "mining", LEVELS(40), REG, tier)
            skills = [REG.item(i).skill for i in ship.need]
            assert skills.count("mining") >= t.theme_kinds - 1 and len(set(skills)) >= 2  # (a skill with few materials can fall short by one)


def test_the_harder_crate_is_worth_much_more_than_the_basic_one_and_pays_a_better_rate():
    assert HARD.value_base > 3 * BASIC.value_base and HARD.unlock_level > BASIC.unlock_level and HARD.bits_factor > BASIC.bits_factor
    easy, hard = (sh.make_shipment(Random(3), "fishing", LEVELS(40), REG, t) for t in ("basic", "hard"))
    assert sh.worth(hard.need, REG) > 2.5 * sh.worth(easy.need, REG)


def test_the_same_seed_makes_the_same_crate():
    assert sh.make_shipment(Random(7), "fishing", LEVELS(9), REG) == sh.make_shipment(Random(7), "fishing", LEVELS(9), REG)


def test_shipping_pays_more_than_selling_the_materials_and_gives_xp_to_the_skills_involved():
    for tier in P.tiers:
        ship = sh.make_shipment(Random(2), "farming", LEVELS(35), REG, tier)
        bits, xp = sh.reward(ship, REG)
        assert bits == round(sh.worth(ship.need, REG) * P.tiers[tier].bits_factor) > sh.worth(ship.need, REG)
        assert set(xp) == {REG.item(i).skill for i in ship.need} and all(v > 0 for v in xp.values())


def test_wedges_and_things_you_cannot_sell_are_never_asked_for():
    wedges = {w.item for w in REG.foraging.rotate.wedges}
    for skill in sh.SKILLS:
        for item in sh.pool(skill, 100, REG, 10**9):
            assert item.id not in wedges and item.sell_price > 0 and not item.is_instance


# ---- your crates ------------------------------------------------------------------------------------------------------------------------------
async def test_a_skill_unlocks_its_basic_crate_at_its_own_level_and_the_hard_one_later(db):
    user = await User.get(1)
    assert await sh.mine(user) == []  # (nothing is open at level 1)
    assert {(s, t) for s, t, _ in await sh.locked(user)} == set(sh.slot_ids(REG))
    await level_up(user, "mining")
    mine = await sh.mine(user)
    assert [c.id for c in mine] == ["mining:basic"]  # (only mining is high enough)
    await level_up(user, "fishing", XP30)
    assert [c.id for c in await sh.mine(user)] == ["mining:basic", "fishing:basic", "fishing:hard"]
    assert ("mining", "hard", HARD.unlock_level) in await sh.locked(user)
    first = await sh.mine(user)
    assert first == await sh.mine(user)  # (looking twice changes nothing)
    other = await level_up(await User.get(2), "mining")
    assert (await sh.mine(other))[0] != first[0]  # (everyone's crates differ)


async def total_xp(user):
    return sum([(await user.skill(s)).xp for s in sh.SKILLS])


async def fill_it(user, slot_id="mining:basic"):
    """Give the player everything the crate asks for."""
    await level_up(user, slot_id.split(":")[0], XP30)
    ship = next(c for c in await sh.mine(user) if c.id == slot_id)
    for item_id, need in ship.need.items():
        await user.add_item(item_id, need)
    return ship


async def test_fill_moves_what_you_hold_into_the_crate_and_ship_pays_and_replaces_it(db):
    user = await level_up(await User.get(1), "mining", XP10)
    ship = (await sh.mine(user))[0]
    item = next(iter(ship.need))
    with pytest.raises(sh.ShipmentError, match="nothing it still needs"):
        await sh.fill(user, "mining:basic")
    await user.add_item(item, ship.need[item] + 5)
    moved = await sh.fill(user, "mining:basic")
    assert moved == {item: ship.need[item]} and await user.item_quantity(item) == 5  # only what it needs: the rest stays
    assert (await sh.mine(user))[0].have == {item: ship.need[item]}
    with pytest.raises(sh.ShipmentError, match="not full"):
        await sh.ship(user, "mining:basic")
    for other, need in ship.need.items():
        await user.add_item(other, need)
    await sh.fill(user, "mining:basic")
    assert (await sh.mine(user))[0].done()
    await user.refresh()
    before, xp_before = user.purse, {s: (await user.skill(s)).xp for s in sh.SKILLS}
    sent = await sh.ship(user, "mining:basic")
    await user.refresh()
    bits, xp = sh.reward(ship, REG)
    assert sent.bits == bits and user.purse == before + bits
    for s, x in xp.items():
        assert (await user.skill(s)).xp - xp_before[s] >= x
    crates = await sh.mine(user)
    assert [c.id for c in crates] == ["mining:basic"] and crates[0] != ship and not crates[0].have  # a new, empty crate took its place


async def test_two_ships_at_once_pay_once(db):
    user = await User.get(1)
    ship = await fill_it(user)
    await sh.fill(user, "mining:basic")
    a, b = await asyncio.gather(sh.ship(user, "mining:basic"), sh.ship(user, "mining:basic"), return_exceptions=True)
    assert sum(isinstance(r, sh.Shipped) for r in (a, b)) == 1 and ship


async def test_a_locked_or_unknown_crate_is_refused(db):
    user = await User.get(1)
    for call in (sh.fill(user, "mining:hard"), sh.ship(user, "nothing:basic")):
        with pytest.raises(sh.ShipmentError, match="no such"):
            await call


async def test_crates_from_the_old_layout_are_cleared_and_what_was_inside_is_handed_back(db):
    from cococap.services import community

    user = await User.get(1)
    old = {"made": 5, "slots": [{"theme": "mining", "need": {"material_copper_ore": 100}, "have": {"material_copper_ore": 40, "material_tin_ore": 3}}, {"theme": "mixed", "need": {"material_coal": 5}, "have": {}}]}
    await community.update(sh._key(user.id), sh.DEFAULT, lambda d: d.update(old))
    assert await sh.mine(user) == []
    assert await user.item_quantity("material_copper_ore") == 40 and await user.item_quantity("material_tin_ore") == 3
    await sh.mine(user)
    assert await user.item_quantity("material_copper_ore") == 40  # (handed back once)



# ---- the community shipment --------------------------------------------------------------------------------------------------------------------
NOW = 1_800_000_000.0  # some Monday-ish time: only the week matters


async def fill_community(users, now=NOW):
    view = await sh.community_now(users[0], now)
    for n, user in enumerate(users):
        for item_id, need in view.need.items():
            await user.add_item(item_id, need // len(users) + (need % len(users) if n == 0 else 0))
        await sh.donate(user, now)
    return view


async def test_the_community_shipment_is_the_same_for_everyone_and_changes_each_week(db):
    a, b = await User.get(1), await User.get(2)
    assert (await sh.community_now(a, NOW)).need == (await sh.community_now(b, NOW)).need
    assert (await sh.community_now(a, NOW + 8 * 86400)).need != (await sh.community_now(a, NOW)).need
    assert len((await sh.community_now(a, NOW)).need) == C.kinds


async def test_giving_takes_only_what_it_needs_and_finishing_pays_each_giver_more_than_they_gave(db):
    users = [await User.get(i) for i in (1, 2)]
    view = await sh.community_now(users[0], NOW)
    mats = next(iter(view.need))
    with pytest.raises(sh.ShipmentError, match="nothing it still needs"):
        await sh.donate(users[0], NOW)
    await users[0].add_item(mats, view.need[mats] + 9)
    gave = await sh.donate(users[0], NOW)
    assert gave == {mats: view.need[mats]} and await users[0].item_quantity(mats) == 9
    await fill_community(users)
    done = await sh.community_now(users[0], NOW)
    assert done.done and done.fraction == 1.0
    with pytest.raises(sh.ShipmentError, match="already full"):
        await sh.donate(users[0], NOW + 5)
    for user in users:
        await user.refresh()
        before, xp_before = user.purse, await total_xp(user)
        paid = await sh.claim_community(user, NOW + 10)
        assert len(paid) == 1 and paid[0].bits > 0 and paid[0].xp >= C.xp
        await user.refresh()
        assert user.purse - before == paid[0].bits and await total_xp(user) - xp_before >= C.xp
        assert paid[0].bits >= (await sh.community_now(user, NOW + 10)).yours  # worth more than what they gave
        assert await sh.claim_community(user, NOW + 11) == []  # once only


async def test_someone_who_barely_helped_is_not_paid_and_a_new_week_starts_a_new_shipment(db):
    users = [await User.get(i) for i in (1, 2)]
    view = await sh.community_now(users[0], NOW)
    first = next(iter(view.need))
    await users[1].add_item(first, 1)  # a token gift
    await sh.donate(users[1], NOW)
    for item_id, need in view.need.items():
        await users[0].add_item(item_id, need)
    await sh.donate(users[0], NOW)
    assert (await sh.community_now(users[0], NOW)).done
    assert len(await sh.claim_community(users[0], NOW + 1)) == 1 and await sh.claim_community(users[1], NOW + 1) == []
    fresh = await sh.community_now(users[0], NOW + 8 * 86400)
    assert not fresh.done and fresh.yours == 0 and not fresh.have


# ---- the screen --------------------------------------------------------------------------------------------------------------------------------
async def test_shipments_sit_on_the_home_page_between_skills_and_shop_and_say_when_they_unlock(db):
    nav, inter = await hub("home")
    text = all_text(nav)
    assert text.index("Skills") < text.index("Crates") < text.index("Shop")
    nav, inter = await hub("shipments")
    assert f"level **{BASIC.unlock_level}**" in all_text(nav) and not [b for b in buttons(nav) if b.label in ("Fill", "Ship")]


async def test_the_dropdown_lists_the_unlocked_crates_one_page_each_and_mentions_what_is_locked(db):
    user = await User.get(1)
    await level_up(user, "mining")
    await level_up(user, "fishing", XP30)
    nav, inter = await hub("shipments")
    menu = select_named(nav, "Pick a shipment")
    assert [o.value for o in menu.options] == ["mining:basic", "fishing:basic", "fishing:hard"] and "Community" not in all_text(nav)
    seen = set()
    for option in menu.options:
        await choose(nav, inter, select_named(nav, "Pick a shipment"), option.value)
        seen.add(all_text(nav))
        assert all_text(nav).count("Ships for") == 1
    assert len(seen) == 3 and "Locked:" in all_text(nav)


async def test_filling_and_shipping_from_the_page(db):
    user = await User.get(1)
    ship = await fill_it(user)
    nav, inter = await hub("shipments")
    fills = [b for b in buttons(nav) if b.label == "Fill"]
    assert not fills[0].disabled
    await fills[0].callback(inter)
    assert "Added" in all_text(nav)
    ship_button = [b for b in buttons(nav) if b.label == "Ship"][0]
    assert not ship_button.disabled
    start = (await User.get(1)).purse
    await ship_button.callback(inter)
    assert nav.screen.id == "result" and "Shipped" in all_text(nav) and "bits" in all_text(nav)
    assert (await User.get(1)).purse == start + sh.reward(ship, REG)[0]


async def test_fill_is_off_when_you_have_nothing_useful_and_ship_is_off_until_full(db):
    await level_up(await User.get(1), "mining")
    nav, _ = await hub("shipments")
    assert all(b.disabled for b in buttons(nav) if b.label in ("Fill", "Ship"))


async def test_the_community_shipment_is_off_but_comes_back_when_the_flag_is_on(db):
    assert C.enabled is False
    await level_up(await User.get(1), "mining")
    object.__setattr__(C, "enabled", True)  # (the rules are frozen: flip it for this test only)
    try:
        nav, inter = await hub("shipments")
        menu = select_named(nav, "Pick a shipment")
        assert menu.options[-1].label == "Community shipment"
        await choose(nav, inter, menu, "community")
        assert find_button(nav, "Give what it needs")
    finally:
        object.__setattr__(C, "enabled", False)


# ---- the community goal is sized by who is playing -------------------------------------------------------------------------------------------
async def test_the_goal_grows_with_the_number_of_recently_active_players_and_their_levels_and_ignores_idle_ones(db):
    from tests.conftest import set_columns

    users = [await User.get(i) for i in range(1, 7)]
    for user in users[:2]:
        await set_columns(user, last_active=NOW - 86400)  # active
    for user in users[2:]:
        await set_columns(user, last_active=NOW - 30 * 86400)  # idle for a month
    view = await sh.community_now(users[0], NOW)
    assert view.players == C.min_players  # (only 2 are active: the floor applies)
    for user in users[2:5]:
        await set_columns(user, last_active=NOW - 100)
    later = await sh.community_now(users[0], NOW + 14 * 86400)  # a new week counts the crowd again... and these are idle by then
    assert later.players == C.min_players
    assert sh.community_target(10, 1, REG) > sh.community_target(5, 1, REG) > sh.community_target(1, 1, REG) == sh.community_target(C.min_players, 1, REG)
    assert sh.community_target(5, 40, REG) > sh.community_target(5, 1, REG)


async def test_five_active_players_set_the_goal_and_it_stays_fixed_for_the_week(db):
    from tests.conftest import set_columns

    users = [await User.get(i) for i in range(1, 6)]
    for user in users:
        await set_columns(user, last_active=NOW - 3600)
    first = await sh.community_now(users[0], NOW)
    assert first.players == 5 and first.value == sh.community_target(5, 1, REG)
    assert 0.5 * first.value <= sh.worth(first.need, REG) <= 1.6 * first.value
    for extra in range(6, 12):
        await set_columns(await User.get(extra), last_active=NOW)
    assert (await sh.community_now(users[1], NOW + 86400)).need == first.need  # more players joining mid-week change nothing


async def test_higher_level_players_are_asked_for_more(db):
    from cococap.services import activity
    from tests.conftest import set_columns

    user = await User.get(1)
    await set_columns(user, last_active=NOW)
    low = await activity.recent_players(sh.SKILLS, 7, NOW)
    for skill in sh.SKILLS:
        await user.add_xp(skill, 50_000)
    high = await activity.recent_players(sh.SKILLS, 7, NOW)
    assert low == (1, 1.0) and high[0] == 1 and high[1] > 5
    assert await activity.recent_players(sh.SKILLS, 7, NOW + 30 * 86400) == (0, 0.0)


def test_the_home_skills_materials_are_the_bulk_of_every_crate_and_the_rest_is_small_and_varied():
    """A foraging crate is mostly foraging finds; other skills add a small, varied slice (never a pile of the same cheap ore)."""
    for tier in P.tiers:
        for skill in sh.SKILLS:
            foreign_seen = set()
            for seed in range(120):
                crate = sh.make_shipment(Random(seed), skill, LEVELS(unlock := P.tiers[tier].unlock_level), REG, tier)
                total = sh.worth(crate.need, REG)
                home = sum(REG.item(i).sell_price * q for i, q in crate.need.items() if REG.item(i).skill == skill)
                assert home / total >= 0.5, (skill, tier, seed, crate.need)  # (a single rare foreign find is worth a lot now)
                for i, q in crate.need.items():
                    if REG.item(i).skill != skill:
                        foreign_seen.add(i)
                        assert q <= P.foreign_max_quantity, (skill, tier, i, q)
            assert len(foreign_seen) >= 6, (skill, tier, foreign_seen)  # varied: not the same one or two materials every time
