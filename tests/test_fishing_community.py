import asyncio
import datetime
from random import Random

import pytest

from cococap.registry import get_registry
from cococap.services import fishing as f
from cococap.services import fishing_community as c
from cococap.user import User
from tests.test_fishing import cast_of
from tests.test_hub import all_text, choose, click, find_button, hub, select_named

REG = get_registry()
RULES = REG.fishing
CB = RULES.community.book
T0 = datetime.datetime(2026, 3, 10, 12, tzinfo=datetime.timezone.utc).timestamp()


async def angler(user_id=1, level=None, fish=None):
    user = await User.get(user_id)
    await user.add_xp("fishing", User.level_to_xp(level or RULES.book.min_level) + 1)
    for fish_id, quantity in (fish or {}).items():
        await user.add_item(fish_id, quantity)
    return user


def full_book(level=1, scale=1):
    return {i.id: c.book_need(level, i, RULES) * scale for i in c.book_fish(REG)}


async def fill_book(users, level=1):
    """Donate everything the book needs, spread over the given players; returns the last donation."""
    last = None
    for i, fish in enumerate(c.book_fish(REG)):
        last = await c.donate(users[i % len(users)], fish.id, REG)
    return last


# ---- months and goals ---------------------------------------------------------------------------------------------
def test_months_count_from_the_clock_and_end_on_the_first():
    march, april = c.month_of(T0), c.month_of(datetime.datetime(2026, 4, 1, tzinfo=datetime.timezone.utc).timestamp())
    assert april == march + 1
    assert c.month_ends_at(march) == datetime.datetime(2026, 4, 1, tzinfo=datetime.timezone.utc).timestamp()
    assert c.month_of(c.month_ends_at(march) - 1) == march  # the last second of the month is still March
    assert c.month_ends_at(c.month_of(datetime.datetime(2026, 12, 15, tzinfo=datetime.timezone.utc).timestamp())) == \
        datetime.datetime(2027, 1, 1, tzinfo=datetime.timezone.utc).timestamp()  # December rolls into the next year


def test_the_months_goals_are_the_same_for_everybody_and_change_from_month_to_month():
    period = c.month_of(T0)
    first = c.goals(period, REG)
    assert [g.text for g in first] == [g.text for g in c.goals(period, REG)]
    assert len(first) == len(RULES.community.monthly) == 3
    fish_goal = next(g for g in first if g.slot.kind == "fish")
    assert fish_goal.fish.rarity == fish_goal.slot.rarity and fish_goal.fish.display in fish_goal.text
    seen = {next(g for g in c.goals(p, REG) if g.slot.kind == "fish").fish.id for p in range(period, period + 24)}
    assert len(seen) > 1


def test_goals_count_the_right_fish():
    any_goal, rarity_goal, fish_goal = c.goals(c.month_of(T0), REG)
    cod, salmon = REG.item("fish_cod"), REG.item("fish_salmon")
    assert any_goal.counts(cod) and any_goal.counts(salmon)
    assert not rarity_goal.counts(cod) and rarity_goal.counts(salmon)
    assert fish_goal.counts(fish_goal.fish) and not fish_goal.counts(cod)


# ---- the community book -------------------------------------------------------------------------------------------
def test_the_community_book_holds_two_legendary_two_premium_and_a_mythical_fish():
    rarities = sorted(i.rarity for i in c.book_fish(REG))
    assert rarities == [5, 5, 6, 6, 7]
    for level in range(1, 10):
        for fish in c.book_fish(REG):
            assert c.book_need(level + 1, fish, RULES) >= c.book_need(level, fish, RULES)
    assert [c.book_need(1, i, RULES) for i in c.book_fish(REG)] == [3, 3, 2, 2, 1]


async def test_you_must_be_a_good_enough_angler_to_donate(db):
    user = await angler(level=RULES.book.min_level - 1, fish={"fish_marlin": 1})
    with pytest.raises(c.CommunityError, match="opens to anglers"):
        await c.donate(user, "fish_marlin", REG)
    assert await user.item_quantity("fish_marlin") == 1


async def test_donating_pays_the_donor_and_fills_the_page_only_as_far_as_it_needs(db):
    user = await angler(fish={"fish_marlin": 5})
    before = user.purse
    done = await c.donate(user, "fish_marlin", REG)
    assert done.quantity == 3 and done.finished_level is None  # level 1 wants 3 marlin
    assert done.bits == round(REG.item("fish_marlin").sell_price * CB.donor_bits_per_sell * 3)
    await user.refresh()
    assert user.purse == before + done.bits and await user.item_quantity("fish_marlin") == 2
    view = await c.book(user, REG)
    page = next(p for p in view.pages if p.fish.id == "fish_marlin")
    assert page.given == 3 and page.done and view.donated_by_you == 3
    with pytest.raises(c.CommunityError, match="already has"):
        await c.donate(user, "fish_marlin", REG)


async def test_you_cannot_donate_what_the_book_does_not_hold_or_you_do_not_have(db):
    user = await angler(fish={"fish_cod": 1})
    with pytest.raises(c.CommunityError, match="no page"):
        await c.donate(user, "fish_cod", REG)
    with pytest.raises(c.CommunityError, match="don't have any"):
        await c.donate(user, "fish_marlin", REG)


async def test_a_stale_second_donation_gets_its_fish_back(db, monkeypatch):
    user = await angler(fish={"fish_marlin": 6})
    stale = await c.book(user, REG)
    await c.donate(user, "fish_marlin", REG)  # fills the page

    async def old(*_a, **_k):
        return stale

    monkeypatch.setattr(c, "book", old)
    before = await user.item_quantity("fish_marlin")
    with pytest.raises(c.CommunityError, match="already has"):
        await c.donate(user, "fish_marlin", REG)
    assert await user.item_quantity("fish_marlin") == before


async def test_finishing_the_book_happens_once_levels_it_up_and_pays_everyone_once(db):
    alice = await angler(1, fish=full_book())
    bob = await angler(2, fish=full_book())
    carol = await angler(3, level=RULES.book.min_level)  # never donates
    results = [await c.donate(alice, i.id, REG) for i in c.book_fish(REG)[:3]]
    results += [await c.donate(bob, i.id, REG) for i in c.book_fish(REG)[3:]]
    assert [r.finished_level for r in results[:-1]] == [None] * 4 and results[-1].finished_level == 1
    view = await c.book(alice, REG)
    assert view.level == 2 and view.completed == 1 and all(p.given == 0 for p in view.pages)
    assert view.donated_by_you == 0  # a fresh page
    expected = CB.completion_bits * 1
    for who in (alice, bob, carol):  # everyone is owed it, donors or not
        before = who.purse
        paid = await c.claim_book_rewards(who, REG)
        await who.refresh()
        assert paid.levels == (1,) and paid.bits == expected and who.purse == before + expected
        assert await c.claim_book_rewards(who, REG) is None  # once only
    assert (await carol.skill("fishing")).community_claimed == 1


async def test_two_players_giving_the_last_fish_at_the_same_moment_finish_it_once(db):
    users = [await angler(i, fish=full_book(scale=2)) for i in (1, 2)]
    for fish in c.book_fish(REG)[:-1]:
        await c.donate(users[0], fish.id, REG)
    last = c.book_fish(REG)[-1].id
    results = await asyncio.gather(c.donate(users[0], last, REG), c.donate(users[1], last, REG), return_exceptions=True)
    assert sum(isinstance(r, c.Donation) and r.finished_level == 1 for r in results) == 1
    view = await c.book(users[0], REG)
    assert view.level == 2 and view.completed == 1


async def test_a_player_who_was_away_collects_every_level_they_missed(db):
    donors = [await angler(i, fish={**full_book(1), **{k: v + 20 for k, v in full_book(2).items()}}) for i in (1, 2)]
    away = await angler(3, level=RULES.book.min_level)
    for level in (1, 2):
        for fish in c.book_fish(REG):
            await c.donate(donors[level % 2], fish.id, REG)
    paid = await c.claim_book_rewards(away, REG)
    assert paid.levels == (1, 2) and paid.bits == CB.completion_bits * (1 + 2)


async def test_players_below_the_level_are_not_paid_until_they_reach_it(db):
    donor = await angler(1, fish=full_book())
    await fill_book([donor])
    newbie = await angler(2, level=RULES.quests.min_level)
    assert RULES.quests.min_level < RULES.book.min_level
    assert await c.claim_book_rewards(newbie, REG) is None
    await newbie.add_xp("fishing", User.level_to_xp(RULES.book.min_level) + 1)
    assert (await c.claim_book_rewards(newbie, REG)).levels == (1,)


async def test_the_book_stops_levelling_at_its_top(db):
    from cococap.services import community

    donor = await angler(fish=full_book(CB.max_level))
    await community.update(c.BOOK_KEY, c.BOOK_DEFAULT, lambda s: s.update(level=CB.max_level))
    last = await fill_book([donor])
    assert last.finished_level is None and (await c.book(donor, REG)).level == CB.max_level


# ---- monthly goals ------------------------------------------------------------------------------------------------
async def land_fish(user, fish_id, now=T0):
    cast = cast_of(fish_id)
    for arrow in cast.pattern:
        cast.press(arrow, 11_000_000)
    return await f.land(user, cast, REG, now=now)


async def test_a_landed_fish_adds_to_every_goal_it_fits(db):
    user = await angler(level=RULES.quests.min_level)
    fish_goal = c.goals(c.month_of(T0), REG)[2].fish.id
    await land_fish(user, "fish_cod")
    await land_fish(user, "fish_salmon")
    await land_fish(user, fish_goal)
    any_goal, rare_goal, specific = await c.monthly(user, T0, REG)
    assert (any_goal.progress, rare_goal.progress, specific.progress) == (3, 2, 1)  # cod: only the first; salmon: two
    assert (any_goal.yours, specific.yours) == (3, 1)


async def test_catches_before_the_unlock_level_do_not_count(db):
    user = await User.get(1)
    await land_fish(user, "fish_cod")
    assert (await c.monthly(user, T0, REG))[0].progress == 0


async def test_everybody_adds_to_the_same_goal(db):
    one, two = await angler(1, level=3), await angler(2, level=3)
    await land_fish(one, "fish_cod")
    await land_fish(two, "fish_cod")
    await land_fish(two, "fish_cod")
    seen_by_one = await c.monthly(one, T0, REG)
    assert seen_by_one[0].progress == 3 and seen_by_one[0].yours == 1
    assert (await c.monthly(two, T0, REG))[0].yours == 2


async def test_a_new_month_starts_the_goals_over(db):
    user = await angler(level=3)
    await land_fish(user, "fish_cod")
    april = datetime.datetime(2026, 4, 2, tzinfo=datetime.timezone.utc).timestamp()
    assert (await c.monthly(user, april, REG))[0].progress == 0 and (await c.monthly(user, T0, REG))[0].progress == 1


async def reach_goal(users_shares, index=0, now=T0):
    """Push a goal over the line by adding progress directly, as {user: how_many_they_did}."""
    from cococap.services import community

    period = c.month_of(now)

    def add(state):
        for user, n in users_shares.items():
            mine = state["mine"].setdefault(str(user.id), [0] * len(state["progress"]))
            mine[index] += n
            state["progress"][index] += n

    await community.update(f"fishing_monthly:{period}", {"progress": [0, 0, 0], "mine": {}}, add)


async def test_a_finished_goal_pays_everyone_who_did_enough_once(db):
    goal = RULES.community.monthly[0]
    big, small, idle = await angler(1, level=3), await angler(2, level=3), await angler(3, level=3)
    await reach_goal({big: goal.count - 1, small: 1})  # small did 1 of 1,500: well under 5%
    paid = await c.claim_monthly(big, T0, REG)
    assert paid.bits == goal.bits and [g.index for g in paid.goals] == [0]
    assert await c.claim_monthly(big, T0, REG) is None  # not twice
    assert await c.claim_monthly(small, T0, REG) is None  # didn't do enough
    assert await c.claim_monthly(idle, T0, REG) is None  # did nothing
    assert (await big.skill("fishing")).xp >= goal.xp


async def test_you_can_still_collect_last_months_goal_but_not_forever(db):
    goal = RULES.community.monthly[0]
    user = await angler(level=3)
    march = T0
    await reach_goal({user: goal.count}, now=march)
    in_april = datetime.datetime(2026, 4, 5, tzinfo=datetime.timezone.utc).timestamp()
    assert (await c.claim_monthly(user, in_april, REG)).bits == goal.bits
    other = await angler(2, level=3)
    await reach_goal({other: goal.count}, now=march)
    in_june = datetime.datetime(2026, 6, 5, tzinfo=datetime.timezone.utc).timestamp()
    assert await c.claim_monthly(other, in_june, REG) is None


async def test_an_unfinished_goal_pays_nothing(db):
    goal = RULES.community.monthly[0]
    user = await angler(level=3)
    await reach_goal({user: goal.count - 1})
    assert await c.claim_monthly(user, T0, REG) is None


# ---- the screen ---------------------------------------------------------------------------------------------------
async def test_the_community_page_shows_the_book_and_goals_and_you_donate_from_a_menu(db, monkeypatch):
    user = await angler(fish={"fish_marlin": 4, "fish_giant_squid": 1})
    nav, inter = await hub("fishcommunity")
    text = all_text(nav)
    assert "Community Book" in text and "This month's goals" in text and "Blue Marlin" in text
    assert nav.screen.refresh_every  # redraws itself so you see everyone's progress
    await choose(nav, inter, select_named(nav, "Donate a fish"), "fish_marlin")
    assert "You gave 3" in all_text(nav) and await user.item_quantity("fish_marlin") == 1


async def test_the_page_pays_what_you_are_owed_when_you_open_it(db):
    donor = await angler(1, fish=full_book())
    await fill_book([donor])
    watcher = await angler(2, level=RULES.book.min_level)
    nav, _ = await hub("fishcommunity", user_id=2)
    assert "community finished its book" in all_text(nav)
    assert (await watcher.skill("fishing")).community_claimed == 1


async def test_the_fishing_page_links_to_the_community_once_unlocked(db):
    user = await User.get(1)
    nav, inter = await hub("fish")
    assert find_button(nav, "Community").disabled
    await user.add_xp("fishing", User.level_to_xp(RULES.quests.min_level) + 1)
    nav, inter = await hub("fish")
    await click(nav, inter, "Community")
    assert nav.screen.id == "fishcommunity"
    await click(nav, inter, "Back to fishing")
    assert nav.screen.id == "fish"


async def test_below_the_level_the_community_page_says_when_it_opens(db):
    nav, _ = await hub("fishcommunity")
    assert "opens at fishing level" in all_text(nav)
