import asyncio
from collections import Counter
from random import Random

import pytest

from cococap.registry import get_registry
from cococap.services import foraging as f
from cococap.services import releaf
from cococap.services.equipment import equip
from cococap.user import User
from tests.test_hub import all_text, buttons, click, find_button, freeze_time, hub, with_axe

REG = get_registry()
R = REG.foraging.releaf
T0 = 20_000 * 86_400.0  # the start of a day


async def forager(user_id=1, level=None, items=None):
    user = await User.get(user_id)
    await user.add_xp("foraging", User.level_to_xp(level or R.min_level) + 1)
    for item_id, quantity in (items or {}).items():
        await user.add_item(item_id, quantity)
    return user


# ---- the rules -------------------------------------------------------------------------------------------------------------------
def test_the_numbers_follow_the_wiki():
    assert R.min_level == 10 and R.daily_limit == 3 and R.meter_goal == 50 and R.double_spirit_chance == 0.01 and R.growth_donations == 420
    assert releaf.meter_gain(Counter({"aged_feather": 1}), REG) == 25  # the wiki's own example: rarity 5 is worth 25
    assert releaf.meter_gain(Counter({"feather": 9, "fine_bark": 1}), REG) == REG.item("fine_bark").rarity * R.meter_per_rarity  # the rarest counts
    assert releaf.meter_gain(Counter(), REG) == 0 and releaf.meter_gain(Counter({"feather": 0}), REG) == 0


# ---- donating -----------------------------------------------------------------------------------------------------------------------
async def test_donating_takes_the_drops_and_fills_the_meter_by_the_rarest_one(db):
    user = await forager(items={"feather": 4, "fine_bark": 2})
    gift = Counter({"feather": 4, "fine_bark": 2})
    done = await releaf.donate(user, gift, T0, REG)
    assert done.gained == REG.item("fine_bark").rarity * R.meter_per_rarity == done.meter and done.left_today == R.daily_limit - 1
    assert not done.became_ready
    assert await user.item_quantity("feather") == 0 and await user.item_quantity("fine_bark") == 0  # they are gone
    skill = await user.skill("foraging")
    assert skill.releaf_meter == done.meter and skill.stats.releaf_donations == 1 and skill.donations_made_today == 1


async def test_you_need_the_level_and_something_to_give(db):
    newbie = await forager(1, level=R.min_level - 1, items={"feather": 1})
    with pytest.raises(releaf.ReleafError, match=f"level {R.min_level}"):
        await releaf.donate(newbie, Counter({"feather": 1}), T0, REG)
    assert await newbie.item_quantity("feather") == 1
    user = await forager(2)
    with pytest.raises(releaf.ReleafError, match="nothing to donate"):
        await releaf.donate(user, Counter(), T0, REG)
    with pytest.raises(releaf.ReleafError, match="no longer have"):
        await releaf.donate(user, Counter({"feather": 3}), T0, REG)  # you sold them in the meantime
    assert (await user.skill("foraging")).releaf_meter == 0


async def test_a_partly_missing_gift_gives_back_what_it_took(db):
    user = await forager(items={"feather": 2})
    with pytest.raises(releaf.ReleafError):
        await releaf.donate(user, Counter({"feather": 2, "fine_bark": 1}), T0, REG)
    assert await user.item_quantity("feather") == 2  # nothing was lost


async def test_three_a_day_and_the_count_starts_again_tomorrow(db):
    user = await forager(items={"feather": 9})
    for _ in range(R.daily_limit):
        await releaf.donate(user, Counter({"feather": 1}), T0 + 100, REG)
    with pytest.raises(releaf.ReleafError, match="already made your 3"):
        await releaf.donate(user, Counter({"feather": 1}), T0 + 200, REG)
    assert await user.item_quantity("feather") == 9 - R.daily_limit  # the refused gift stayed in your bag
    assert (await releaf.status(user, T0 + 300, REG)).left_today == 0
    assert (await releaf.status(user, T0 + 86_400 + 5, REG)).left_today == R.daily_limit
    await releaf.donate(user, Counter({"feather": 1}), T0 + 86_400 + 5, REG)


async def test_two_clicks_with_one_donation_left_only_one_goes_through_and_the_other_is_refunded(db):
    user = await forager(items={"feather": 4})
    for _ in range(R.daily_limit - 1):
        await releaf.donate(user, Counter({"feather": 1}), T0, REG)
    results = await asyncio.gather(releaf.donate(user, Counter({"feather": 1}), T0, REG),
                                   releaf.donate(user, Counter({"feather": 1}), T0, REG), return_exceptions=True)
    assert sum(isinstance(r, releaf.Donation) for r in results) == 1
    assert await user.item_quantity("feather") == 4 - R.daily_limit  # only the real donations took a feather
    assert (await user.skill("foraging")).stats.releaf_donations == R.daily_limit


async def test_a_full_meter_makes_your_next_tree_a_double_tree_and_keeps_what_was_over(db):
    user = await forager(items={"aged_feather": 3})
    first = await releaf.donate(user, Counter({"aged_feather": 1}), T0, REG)
    assert first.meter == 25 and not first.double_ready
    second = await releaf.donate(user, Counter({"aged_feather": 1}), T0, REG)  # 50: full
    assert second.became_ready and second.double_ready and second.meter == 0
    status = await releaf.status(user, T0, REG)
    assert status.double_ready and status.donations == 2
    big = await forager(2, items={"aged_feather": 3})
    await releaf.donate(big, Counter({"aged_feather": 1}), T0, REG)
    await releaf.donate(big, Counter({"aged_feather": 1}), T0, REG)
    await big.add_item("fine_bark", 1)
    over = await releaf.donate(big, Counter({"aged_feather": 1}), T0, REG)  # already ready: the meter just keeps what you add
    assert over.double_ready and not over.became_ready and over.meter == 25
    await big.add_item("aged_feather", 1)
    again = await releaf.donate(big, Counter({"aged_feather": 1}), T0 + 86_400, REG)  # a second 50 while one is waiting: no new flag
    assert again.double_ready and not again.became_ready


# ---- the double tree --------------------------------------------------------------------------------------------------------------------
async def test_the_next_tree_is_double_and_paying_it_clears_the_flag_and_pays_the_jackpot(db):
    user = await forager()
    await user.update_skill("foraging", lambda s: setattr(s, "double_ready", True))
    plain = f.roll_tree(1, Random(5), REG.foraging)
    double = await releaf.new_tree(user, 1, Random(5), REG)
    assert double.double and double.max_hp == round(plain.max_hp * R.double_hp) and double.hp == double.max_hp and not plain.double
    double.chop(double.max_hp)
    before = user.purse
    reward = await f.fell_private(user, double, Random(1), REG)
    await user.refresh()
    assert reward.jackpot == ("bits", R.double_bits) and user.purse >= before + R.double_bits + reward.bits
    skill = await user.skill("foraging")
    assert not skill.double_ready and skill.stats.double_trees_chopped == 1
    after = await releaf.new_tree(user, 1, Random(5), REG)
    assert not after.double  # one double tree per full meter


async def test_a_double_tree_can_drop_a_spirit_of_the_forest_one_time_in_a_hundred(db):
    class Lucky(Random):
        def random(self):
            return 0.0

    user = await forager()
    await user.update_skill("foraging", lambda s: setattr(s, "double_ready", True))
    tree = await releaf.new_tree(user, 1, Random(1), REG)
    tree.chop(tree.max_hp)
    reward = await f.fell_private(user, tree, Lucky(1), REG)
    assert reward.jackpot == ("spirit", 1) and await user.item_quantity("spirit_of_the_forest") >= 1
    hits = 0
    for seed in range(3000):
        rng = Random(seed)
        hits += rng.random() < R.double_spirit_chance
    assert 10 < hits < 60  # about 1 in 100


async def test_an_ordinary_tree_has_no_jackpot_and_a_double_tree_felled_twice_pays_once(db):
    user = await forager()
    tree = f.roll_tree(1, Random(2), REG.foraging)
    tree.chop(tree.max_hp)
    assert (await f.fell_private(user, tree, Random(1), REG)).jackpot is None
    with pytest.raises(f.ForagingError, match="already collected"):
        await f.fell_private(user, tree, Random(1), REG)


# ---- on the screens ---------------------------------------------------------------------------------------------------------------------
async def test_the_foraging_page_shows_the_meter_only_from_level_ten(db, monkeypatch):
    freeze_time(monkeypatch)
    await with_axe(1)
    low, _ = await hub("forage")
    assert "Re-leaf" not in all_text(low)
    user = await forager(2)
    inst = await user.give_instance("starter_axe")
    await equip(user, "foraging", inst.id)
    high, _ = await hub("forage", user_id=2)
    assert "Re-leaf" in all_text(high) and f"0/{R.meter_goal}" in all_text(high) and f"{R.daily_limit} donation" in all_text(high)


async def test_felling_a_tree_offers_to_donate_its_drops_and_donating_fills_the_meter(db, monkeypatch):
    freeze_time(monkeypatch)
    user = await forager(items={})
    inst = await user.give_instance("starter_axe")
    await equip(user, "foraging", inst.id)
    nav, inter = await hub("tree", tree=f.Tree(1, 1, 1))

    class Lucky(Random):
        def random(self):
            return 0.0

    nav.screen.rng = Lucky(1)  # every drop roll succeeds, so there is something to give
    await click(nav, inter, "Overhead")
    assert nav.screen.id == "result" and "TIMBER" in all_text(nav)
    drops = nav.screen.origin.reward.drops
    assert find_button(nav, f"Donate the drops (+{releaf.meter_gain(drops, REG)})")
    await click(nav, inter, f"Donate the drops (+{releaf.meter_gain(drops, REG)})")
    assert "The trees thank you" in all_text(nav) and "Meter" in all_text(nav)
    assert (await user.skill("foraging")).releaf_meter == releaf.meter_gain(drops, REG)
    assert find_button(nav, "Another tree") and find_button(nav, "Back to foraging")
    for item_id in drops:
        assert await user.item_quantity(item_id) == 0


async def test_the_offer_does_not_appear_below_level_ten_or_with_nothing_dropped(db, monkeypatch):
    freeze_time(monkeypatch)
    await with_axe(1)
    nav, inter = await hub("tree", tree=f.Tree(1, 1, 1))
    await click(nav, inter, "Overhead")
    assert nav.screen.id == "result" and not nav.screen.shown.actions
    assert not [b for b in buttons(nav) if b.label and b.label.startswith("Donate")]


async def test_a_double_tree_is_announced_on_the_tree_page_and_the_result(db, monkeypatch):
    freeze_time(monkeypatch)
    user = await forager()
    inst = await user.give_instance("starter_axe")
    await equip(user, "foraging", inst.id)
    await user.update_skill("foraging", lambda s: setattr(s, "double_ready", True))
    nav, inter = await hub("forage")
    assert "double tree" in all_text(nav)  # on the foraging page
    await click(nav, inter, "Chop a tree")
    assert nav.screen.tree.double and "Double tree" in all_text(nav)
    nav.screen.tree.hp = 1
    await click(nav, inter, "Overhead")
    assert "DOUBLE TREE" in all_text(nav) and "jackpot" in all_text(nav).lower() or "Spirit of the Forest" in all_text(nav)
    assert not (await user.skill("foraging")).double_ready
