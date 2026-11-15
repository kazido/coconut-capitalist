"""Shipments: crates filled with materials from several skills, shipped for xp and bits, plus a weekly one the whole server fills."""

import asyncio
from random import Random

import pytest

from cococap.registry import get_registry
from cococap.services import shipments as sh
from cococap.user import User
from tests.test_hub import all_text, buttons, choose, click, find_button, hub, select_named

REG = get_registry()
P = REG.shipments.personal
C = REG.shipments.community
LEVELS = lambda n: {s: n for s in sh.SKILLS}  # noqa: E731


# ---- making a crate --------------------------------------------------------------------------------------------------------------------------
def test_a_crate_has_the_right_number_of_different_materials_worth_about_the_same_whatever_they_are():
    for level in (1, 10, 40):
        for theme in (*sh.SKILLS, "mixed"):
            for seed in range(20):
                ship = sh.make_shipment(Random(seed), theme, LEVELS(level), REG)
                assert len(ship.need) == P.kinds and all(q >= 1 for q in ship.need.values())
                target = P.value_base + P.value_per_level * level
                assert 0.6 * target <= sh.worth(ship.need, REG) <= 2 * target, (level, theme, seed)
                assert all(q <= sh.MAX_QUANTITY * 1.2 or REG.item(i).sell_price * q <= target for i, q in ship.need.items())  # (nobody is asked for 5,000 of something)


def test_a_themed_crate_favours_its_skill_and_a_mixed_one_spreads_across_skills():
    for seed in range(30):
        themed = sh.make_shipment(Random(seed), "mining", LEVELS(15), REG)
        skills = [REG.item(i).skill for i in themed.need]
        assert skills.count("mining") >= P.theme_kinds and len(set(skills)) >= 2  # mostly mining, but something else as well
        mixed = sh.make_shipment(Random(seed), "mixed", LEVELS(15), REG)
        assert len({REG.item(i).skill for i in mixed.need}) >= 3


def test_low_levels_are_not_asked_for_rare_finds_and_the_same_seed_makes_the_same_crate():
    for seed in range(30):
        ship = sh.make_shipment(Random(seed), "mixed", LEVELS(1), REG)
        for item_id in ship.need:
            item = REG.item(item_id)
            assert item.category == "crop" or item.drop.rate <= 5 + P.rate_per_level * 1 or REG.item(item_id).sell_price > 0
    assert sh.make_shipment(Random(7), "fishing", LEVELS(9), REG) == sh.make_shipment(Random(7), "fishing", LEVELS(9), REG)


def test_shipping_pays_more_than_selling_the_materials_and_gives_xp_to_the_skills_involved():
    ship = sh.make_shipment(Random(2), "mixed", LEVELS(10), REG)
    bits, xp = sh.reward(ship, REG)
    assert bits == round(sh.worth(ship.need, REG) * P.bits_factor) > sh.worth(ship.need, REG)
    assert set(xp) == {REG.item(i).skill for i in ship.need} and all(v > 0 for v in xp.values())


def test_wedges_and_things_you_cannot_sell_are_never_asked_for():
    wedges = {w.item for w in REG.foraging.rotate.wedges}
    for skill in sh.SKILLS:
        for item in sh.pool(skill, 100, REG, 10**9):
            assert item.id not in wedges and item.sell_price > 0 and not item.is_instance


# ---- your crates ------------------------------------------------------------------------------------------------------------------------------
async def test_you_always_have_your_slots_two_themed_and_one_mixed_and_looking_twice_changes_nothing(db):
    user = await User.get(1)
    first = await sh.mine(user)
    assert len(first) == P.slots and [s.theme == "mixed" for s in first] == [False, False, True]
    assert first[0].theme != first[1].theme and first == await sh.mine(user)
    other = await sh.mine(await User.get(2))
    assert other != first  # (everyone's crates differ)


async def total_xp(user):
    return sum([(await user.skill(s)).xp for s in sh.SKILLS])


async def fill_it(user, index):
    """Give the player everything crate `index` asks for."""
    ship = (await sh.mine(user))[index]
    for item_id, need in ship.need.items():
        await user.add_item(item_id, need)
    return ship


async def test_fill_moves_what_you_hold_into_the_crate_and_ship_pays_and_replaces_it(db):
    user = await User.get(1)
    ship = (await sh.mine(user))[0]
    item = next(iter(ship.need))
    with pytest.raises(sh.ShipmentError, match="nothing it still needs"):
        await sh.fill(user, 0)
    await user.add_item(item, ship.need[item] + 5)
    moved = await sh.fill(user, 0)
    assert moved == {item: ship.need[item]} and await user.item_quantity(item) == 5  # only what it needs: the rest stays
    assert (await sh.mine(user))[0].have == {item: ship.need[item]}
    with pytest.raises(sh.ShipmentError, match="not full"):
        await sh.ship(user, 0)
    for other, need in ship.need.items():
        await user.add_item(other, need)
    await sh.fill(user, 0)
    assert (await sh.mine(user))[0].done()
    await user.refresh()
    before, xp_before = user.purse, {s: (await user.skill(s)).xp for s in sh.SKILLS}
    sent = await sh.ship(user, 0)
    await user.refresh()
    bits, xp = sh.reward(ship, REG)
    assert sent.bits == bits and user.purse == before + bits
    for s, x in xp.items():
        assert (await user.skill(s)).xp - xp_before[s] >= x
    crates = await sh.mine(user)
    assert len(crates) == P.slots and crates[0] != ship and not crates[0].have  # a new, empty crate took its place
    assert [c.theme == "mixed" for c in crates] == [False, False, True]


async def test_two_ships_at_once_pay_once(db):
    user = await User.get(1)
    ship = await fill_it(user, 0)
    await sh.fill(user, 0)
    a, b = await asyncio.gather(sh.ship(user, 0), sh.ship(user, 0), return_exceptions=True)
    assert sum(isinstance(r, sh.Shipped) for r in (a, b)) == 1 and ship


async def test_a_bad_slot_number_is_refused(db):
    user = await User.get(1)
    for call in (sh.fill(user, 9), sh.ship(user, 9)):
        with pytest.raises(sh.ShipmentError, match="no such"):
            await call


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
async def test_shipments_sit_on_the_home_page_between_skills_and_minigames_and_open_one_at_a_time(db):
    nav, inter = await hub("home")
    text = all_text(nav)
    assert text.index("Skills") < text.index("Shipments") < text.index("Minigames")
    nav, inter = await hub("shipments")
    assert find_button(nav, "Home") and "shipment" in all_text(nav).lower()
    assert all_text(nav).count("Ships for") == 1 and "Community shipment" not in all_text(nav).split("Pick a shipment")[-1]
    assert len([b for b in buttons(nav) if b.label in ("Fill", "Ship")]) == 2


async def test_the_dropdown_lists_every_crate_and_the_community_one_and_each_has_its_own_page(db):
    nav, inter = await hub("shipments")
    menu = select_named(nav, "Pick a shipment")
    assert len(menu.options) == P.slots + 1 and menu.options[-1].label == "Community shipment"
    seen = set()
    for option in menu.options:
        await choose(nav, inter, select_named(nav, "Pick a shipment"), option.value)
        seen.add(all_text(nav))
    assert len(seen) == len(menu.options)
    assert find_button(nav, "Give what it needs")  # (the last page is the community one)
    first = all_text(nav)
    assert "Community shipment" in first and "Ships for" not in first


async def test_filling_and_shipping_from_the_page(db):
    user = await User.get(1)
    ship = await fill_it(user, 0)
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
    nav, _ = await hub("shipments")
    assert all(b.disabled for b in buttons(nav) if b.label in ("Fill", "Ship"))


async def test_the_page_pays_a_finished_community_shipment_on_a_page_of_its_own(db, monkeypatch):
    import time as _time

    monkeypatch.setattr(sh, "time", type("T", (), {"time": staticmethod(lambda: NOW)}))
    monkeypatch.setattr(_time, "time", lambda: NOW)
    users = [await User.get(i) for i in (1, 2)]
    view = await sh.community_now(users[0], NOW)
    for item_id, need in view.need.items():
        await users[0].add_item(item_id, need)
    await sh.donate(users[0], NOW)
    nav, _ = await hub("shipments", user_id=1)
    assert nav.screen.id == "result" and "community shipment is out" in all_text(nav).lower() and "bits" in all_text(nav)


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
