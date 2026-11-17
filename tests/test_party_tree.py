import asyncio
from random import Random

import pytest

from cococap.registry import get_registry
from cococap.services import foraging as f
from cococap.services import party_tree as pt
from cococap.services.equipment import equip
from cococap.services.party import Party
from cococap.user import User
from tests.test_hub import all_text, chop, click, find_button, hub

REG = get_registry()
RULES = REG.foraging


@pytest.fixture(autouse=True)
def chopping_pays_bits():
    """Chopping itself pays no bits in the shipped data, but the rules for sharing a tree's pay still work on them: these tests turn it on so bits can stand for the pay."""
    old = RULES.bits_per_hp
    RULES.__dict__["bits_per_hp"] = 60
    yield
    RULES.__dict__["bits_per_hp"] = old
P = RULES.party_tree
T0 = 1_000_000.0


async def player(user_id, level=None, axe=True):
    user = await User.get(user_id)
    if level:
        await user.add_xp("foraging", User.level_to_xp(level) + 1)
    if axe:
        inst = await user.give_instance("starter_axe")
        await equip(user, "foraging", inst.id)
    return user


async def team(size=3, **kw):
    users = [await player(i, **kw) for i in range(1, size + 1)]
    party = await Party.create(1)
    for i in range(2, size + 1):
        await party.add_member(i)
    return users


# ---- the rules -----------------------------------------------------------------------------------------------------------------------
def test_a_party_tree_pays_a_little_better_than_the_community_tree_for_the_same_work():
    chops = {1: 400, 2: 300, 3: 300}
    args = (1000, True, chops)
    community = f.community_shares(*args, RULES, Random(1), REG, 1)
    party = f.community_shares(*args, pt.party_rules(RULES), Random(1), REG, 1)
    assert sum(s.bits for s in party.values()) > sum(s.bits for s in community.values())
    assert sum(s.bits for s in party.values()) < 1.6 * sum(s.bits for s in community.values())  # "a little" better


def test_the_group_bonus_grows_with_each_member_who_did_their_share_up_to_a_cap():
    def bits(n):
        chops = {i: 1000 // n for i in range(n)}
        return sum(s.bits for s in f.community_shares(1000, True, chops, pt.party_rules(RULES), Random(1), REG, 1).values())

    totals = [bits(n) for n in (1, 2, 3, 4, 5, 6, 8)]
    assert totals == sorted(totals) and totals[-1] > totals[0]
    assert bits(8) / bits(1) <= 1 + P.max_group_bonus + 0.01  # capped


def test_trees_get_bigger_with_the_party():
    assert pt.tree_hp(3, 4, RULES) == pytest.approx(2 * pt.tree_hp(3, 2, RULES), abs=2)
    assert pt.tree_hp(5, 3, RULES) > pt.tree_hp(2, 3, RULES)


# ---- starting one ---------------------------------------------------------------------------------------------------------------------
async def test_you_need_a_party_of_two_and_an_axe_to_start(db):
    solo = await player(1)
    with pytest.raises(pt.PartyTreeError, match="party of two or more"):
        await pt.start(solo, 1, T0, REG)
    await Party.create(1)
    with pytest.raises(pt.PartyTreeError, match="party of two or more"):
        await pt.start(solo, 1, T0, REG)  # a party of one is not enough
    assert await pt.view(solo, T0, REG) is None


async def test_the_zone_is_limited_by_the_member_who_has_unlocked_the_least(db):
    boss = await player(1, level=f.zone_level(5, RULES))
    await player(2, level=f.zone_level(2, RULES))
    party = await Party.create(1)
    await party.add_member(2)
    assert await pt.unlocked_zone(party, REG) == 2
    with pytest.raises(pt.PartyTreeError, match="up to forest 2"):
        await pt.start(boss, 3, T0, REG)
    started = await pt.start(boss, 2, T0, REG)
    assert started.zone == 2 and started.standing and started.max_hp == pt.tree_hp(2, 2, RULES)


async def test_one_tree_at_a_time_and_a_new_one_after_it_ends(db):
    one, _, _ = await team(3)
    tree = await pt.start(one, 1, T0, REG)
    assert tree.number == 1 and tree.max_hp == pt.tree_hp(1, 3, RULES)
    with pytest.raises(pt.PartyTreeError, match="already has a tree"):
        await pt.start(one, 1, T0 + 10, REG)
    after = T0 + P.open_minutes * 60 + 1
    assert (await pt.view(one, after, REG)).status == "expired"
    again = await pt.start(one, 1, after, REG)
    assert again.number == 2 and again.standing


async def test_without_an_axe_you_cannot_start_a_tree(db):
    await player(1, axe=False)
    await player(2)
    party = await Party.create(1)
    await party.add_member(2)
    with pytest.raises(f.ForagingError, match="need an axe"):
        await pt.start(await User.get(1), 1, T0, REG)
    assert party


# ---- chopping together ---------------------------------------------------------------------------------------------------------------
async def test_every_members_chops_add_up_and_non_members_cannot_chop(db):
    one, two, three = await team(3)
    await pt.start(one, 1, T0, REG)
    await pt.chop(one, 30, T0 + 1, REG)
    await pt.chop(two, 20, T0 + 2, REG)
    seen = await pt.view(three, T0 + 3, REG)
    assert seen.hp == seen.max_hp - 50 and seen.chops == {1: 30, 2: 20} and seen.yours == 0
    outsider = await player(9)
    with pytest.raises(pt.PartyTreeError, match="party of two or more"):
        await pt.chop(outsider, 10, T0 + 4, REG)
    assert await pt.view(outsider, T0 + 4, REG) is None  # it is not their tree


async def test_there_is_nothing_to_chop_before_one_is_started_or_after_it_fell_over(db):
    one, two = (await team(2))[:2]
    with pytest.raises(pt.PartyTreeError, match="no tree standing"):
        await pt.chop(one, 5, T0, REG)
    await pt.start(one, 1, T0, REG)
    with pytest.raises(pt.PartyTreeError, match="no tree standing"):
        await pt.chop(two, 5, T0 + P.open_minutes * 60 + 5, REG)


async def test_a_chop_never_takes_more_than_is_left_and_the_last_one_fells_it_once(db):
    one, two = (await team(2))[:2]
    tree = await pt.start(one, 1, T0, REG)
    first = await pt.chop(one, tree.max_hp - 5, T0 + 1, REG)
    assert not first.felled_now
    last = await pt.chop(two, 1000, T0 + 2, REG)
    assert last.applied == 5 and last.felled_now and last.tree.hp == 0 and last.tree.status == "felled"
    with pytest.raises(pt.PartyTreeError):
        await pt.chop(one, 1, T0 + 3, REG)


async def test_many_members_chopping_at_the_same_moment_lose_nothing_and_it_falls_once(db):
    users = await team(4)
    tree = await pt.start(users[0], 1, T0, REG)
    each = tree.max_hp // 4 + 3  # together a little more than the tree has
    results = await asyncio.gather(*[pt.chop(u, each, T0 + 1, REG) for u in users])
    assert sum(r.applied for r in results) == tree.max_hp
    assert sum(r.felled_now for r in results) == 1
    final = await pt.view(users[0], T0 + 2, REG)
    assert final.hp == 0 and sum(final.chops.values()) == tree.max_hp


# ---- rewards -------------------------------------------------------------------------------------------------------------------------------
async def fell(users, shares, now=T0, effort=1.0):
    tree = await pt.start(users[0], 1, now, REG)
    for user, fraction in zip(users, shares, strict=False):
        await pt.chop(user, round(tree.max_hp * fraction), now + 1, REG, effort=effort)
    left = (await pt.view(users[0], now + 1, REG)).hp
    if left:  # rounding left a sliver: the last chopper finishes it, so the tree really falls
        await pt.chop(users[len(shares) - 1], left, now + 1, REG, effort=0.0)  # (finishing the sliver is not extra work)
    return tree


async def test_a_felled_tree_pays_each_member_by_their_share_and_only_once(db):
    users = await team(3)
    await fell(users, [0.6, 0.3, 0.1])
    paid = {}
    for user in users:
        before = user.purse
        rewards = await pt.claim(user, T0 + 10, REG)
        await user.refresh()
        assert len(rewards) == 1 and rewards[0].party and rewards[0].felled
        paid[user.id] = user.purse - before
        assert await pt.claim(user, T0 + 11, REG) == []  # collected: nothing more
    assert paid[1] > paid[2] > paid[3] > 0
    assert (await users[0].skill("foraging")).stats.trees_chopped == 1


async def test_someone_below_the_minimum_share_gets_xp_but_no_bits_or_drops(db):
    users = await team(3)
    await fell(users, [0.6, 0.35, 0.05])
    small = (await pt.claim(users[2], T0 + 10, REG))[0]
    assert small.bits == 0 and not small.drops and small.xp > 0 and P.min_share > 0.05


async def test_a_member_who_did_not_chop_is_owed_nothing(db):
    users = await team(3)
    await fell(users[:2], [0.5, 0.5])
    assert await pt.claim(users[2], T0 + 10, REG) == []


async def test_a_tree_that_fell_over_pays_a_consolation_and_the_old_rewards_survive_a_new_tree(db):
    users = await team(2)
    tree = await pt.start(users[0], 1, T0, REG)
    await pt.chop(users[0], tree.max_hp // 2, T0 + 5, REG)
    await pt.chop(users[1], tree.max_hp // 3, T0 + 6, REG)
    late = T0 + P.open_minutes * 60 + 30
    await pt.start(users[0], 1, late, REG)  # the next tree starts before anyone collected the first
    rewards = await pt.claim(users[0], late + 1, REG)
    assert len(rewards) == 1 and not rewards[0].felled and rewards[0].xp > 0  # the fallen-over tree is still owed
    felled_pay = (await fell_later(users, T0 + 99_999)).bits
    assert rewards[0].bits < felled_pay


async def fell_later(users, now):
    await pt.start(users[0], 1, now, REG)
    tree = await pt.view(users[0], now, REG)
    await pt.chop(users[0], tree.max_hp // 2 + 1, now + 1, REG)
    await pt.chop(users[1], tree.max_hp, now + 2, REG)
    return (await pt.claim(users[0], now + 3, REG))[0]


async def test_two_claims_at_once_pay_once(db):
    users = await team(2)
    await fell(users, [0.5, 0.5])
    a, b = await asyncio.gather(pt.claim(users[0], T0 + 10, REG), pt.claim(users[0], T0 + 10, REG))
    assert len(a) + len(b) == 1


async def test_a_pets_xp_bonus_is_added_to_the_xp_you_collect(db):
    from cococap.models.pethouse import OwnedPet
    from cococap.services import pets

    users = await team(2)
    await fell(users, [0.5, 0.5], effort=40.0)  # (enough xp that a percentage bonus shows through the rounding)
    await users[0].update_pethouse(lambda h: (h.pets.update({"koala": OwnedPet(xp=pets.level_xp(20, REG.pets["koala"].rarity, REG))}), setattr(h, "active", "koala")))
    with_pet, without = (await pt.claim(users[0], T0 + 10, REG))[0], (await pt.claim(users[1], T0 + 10, REG))[0]
    assert with_pet.xp > without.xp > 0  # the same work, but the koala adds its bonus (and both get the party's)


# ---- the screens -------------------------------------------------------------------------------------------------------------------------------
@pytest.fixture
def clock(monkeypatch):
    from types import SimpleNamespace

    for target in ("cococap.screens.forage.time", "cococap.services.foraging.time", "cococap.services.party_tree.time"):
        monkeypatch.setattr(target, SimpleNamespace(time=lambda: T0 + 5))
    monkeypatch.setattr("cococap.screens.forage.new_rng", lambda: Random(1))


async def test_the_foraging_page_hints_at_party_trees_until_you_have_a_party(db, clock):
    await player(1)
    nav, _ = await hub("forage")
    assert "party tree" in all_text(nav) and not [b for b in nav.walk_children() if getattr(b, "label", "") == "Start a party tree"]


async def test_a_party_can_start_and_chop_a_tree_from_the_foraging_page(db, clock):
    await team(2)
    nav, inter = await hub("forage")
    assert "Party tree" in all_text(nav)
    await click(nav, inter, "Start a party tree")
    assert nav.screen.id == "partygrove" and "Forest 1" in all_text(nav) and "Nobody has chopped yet" in all_text(nav)
    for label in ("Overhead", "Sidecut", "Undercut", "Grain notes", "Leave"):
        assert find_button(nav, label)
    await chop(nav, inter)
    assert "you" in all_text(nav) and "hp (" in all_text(nav)
    other, other_inter = await hub("partygrove", user_id=2)
    await chop(other, other_inter)
    assert "(you)" in all_text(other) and "hp (" in all_text(other)
    await click(nav, inter, "Leave")
    assert nav.screen.id == "forage" and find_button(nav, "Join the party tree")


async def test_the_rewards_arrive_on_a_result_page_when_a_member_looks(db, clock):
    users = await team(2)
    await fell(users, [0.5, 0.5], now=T0 + 1)
    nav, _ = await hub("forage", user_id=2)
    assert nav.screen.id == "result" and "(party tree)" in all_text(nav) and "TIMBER" in all_text(nav)
    assert (await User.get(2)).purse > 1000


async def test_the_foraging_page_updates_by_itself_when_a_teammate_starts_a_party_tree(db, clock):
    users = await team(2)
    nav, inter = await hub("forage")
    assert nav.screen.refresh_every  # in a party: it redraws on its own
    assert "No tree is up" in all_text(nav) and find_button(nav, "Start a party tree")
    await pt.start(users[1], 1, T0 + 5, REG)  # the teammate starts one while she is looking at the page
    await nav.screen.nav.refresh(inter)  # (what the self-refresh does)
    assert "falls over" in all_text(nav) and find_button(nav, "Join the party tree")
    solo = await player(9)
    nav2, _ = await hub("forage", user_id=9)
    assert solo and nav2.screen.refresh_every is None  # nobody to wait for: no needless redraws


async def test_party_tree_xp_follows_the_number_of_chops_not_the_axe_behind_them(db):
    users = await team(2)
    tree = await pt.start(users[0], 1, T0, REG)
    big = tree.max_hp // 2
    await pt.chop(users[0], big, T0 + 1, REG, effort=3.0)  # one huge chop from a strong axe
    for _ in range(10):  # ten small ones from a weak axe, each as good a chop as the huge one
        await pt.chop(users[1], big // 10, T0 + 1, REG, effort=3.0)
    left = (await pt.view(users[0], T0 + 1, REG)).hp
    if left:
        await pt.chop(users[1], left, T0 + 1, REG, effort=0.0)
    strong, weak = (await pt.claim(users[0], T0 + 10, REG))[0], (await pt.claim(users[1], T0 + 10, REG))[0]
    assert strong.xp > 0 and weak.xp == pytest.approx(10 * strong.xp, rel=0.15)


async def test_a_party_chop_that_overshoots_only_counts_the_part_that_was_needed(db):
    users = await team(2)
    tree = await pt.start(users[0], 1, T0, REG)
    await pt.chop(users[0], tree.max_hp - 10, T0 + 1, REG, effort=1.0)
    await pt.chop(users[0], 1000, T0 + 1, REG, effort=100.0)  # only 10 of its 1000 were needed
    reward = (await pt.claim(users[0], T0 + 10, REG))[0]
    expected_effort = (tree.max_hp - 10) / (tree.max_hp - 10) + 100.0 * 10 / 1000
    assert reward.xp == round(round(expected_effort * RULES.xp_per_swing) * (1 + REG.economy.party_xp_bonus_by_size[0]))


# ---- a teammate fells the tree while your panel is old ----------------------------------------------------------------------------------------
async def stale_panel():
    """Two players; player 2 is looking at the standing tree when player 1 fells it (after player 2 did their share)."""
    users = await team(2)
    tree = await pt.start(users[0], 1, T0, REG)
    mine, mine_inter = await hub("partygrove", user_id=2)
    assert "hp" in all_text(mine)
    await pt.chop(users[1], tree.max_hp // 2, T0 + 2, REG)
    await pt.chop(users[0], tree.max_hp, T0 + 3, REG)  # a teammate fells it: your panel is now out of date
    return users, mine, mine_inter


async def test_chopping_a_tree_a_teammate_already_felled_shows_your_rewards_instead_of_an_error(db, clock):
    users, mine, mine_inter = await stale_panel()
    before = (await User.get(2)).purse
    mine_inter.response.send_message.reset_mock()
    await chop(mine, mine_inter)  # you press a chop button on the old panel
    assert mine.screen.id == "result" and "TIMBER" in all_text(mine)  # your rewards, on a page of their own
    mine_inter.response.send_message.assert_not_called()  # not an ephemeral "no party tree" error
    assert (await User.get(2)).purse > before and await pt.claim(users[1], T0 + 10, REG) == []  # paid, and only once


async def test_a_result_that_never_reached_you_is_shown_on_your_next_click(db, clock):
    users, mine, mine_inter = await stale_panel()
    before = (await User.get(2)).purse
    # the self-refresh builds the result page (and pays you), but the message can no longer be edited...
    await mine._render()
    assert mine.screen.id == "result" and mine._unsent is not None and (await User.get(2)).purse > before
    mine.screen = mine.screen.origin  # (the player's panel is still the old one: the edit failed)
    # ...so your next click still shows what you were paid
    await mine.refresh(mine_inter)
    assert mine.screen.id == "result" and "TIMBER" in all_text(mine)
    assert mine._unsent is None  # delivered: nothing left to repeat
    await mine.refresh(mine_inter)
    assert mine.screen.id != "result" or "TIMBER" not in all_text(mine) or mine._unsent is None
    assert users


async def test_leaving_a_felled_tree_still_shows_what_you_are_owed(db, clock):
    users, mine, mine_inter = await stale_panel()
    await click(mine, mine_inter, "Leave")
    assert mine.screen.id == "result" and "TIMBER" in all_text(mine)  # (the Leave button takes you to the foraging page, which collects and shows it)


# ---- tree species ----------------------------------------------------------------------------------------------------------------------
async def test_a_party_tree_has_a_species_of_its_zone_and_pays_its_signature_drops(db):
    one, two = (await team(2))[:2]
    tree = await pt.start(one, 1, T0, REG, Random(1))
    assert tree.species and RULES.species_of(tree.species).grows_in(1)
    assert (await pt.view(two, T0 + 1, REG)).species == tree.species  # the whole party sees the same one
    shares = f.community_shares(1_000_000, True, {1: 500_000, 2: 500_000}, pt.party_rules(RULES), Random(2), REG, 1, species=tree.species)
    sig = {d.item for d in RULES.species_of(tree.species).drops}
    assert all(set(s.drops) & sig for s in shares.values())
    await pt.chop(one, tree.max_hp, T0 + 2, REG)
    rewards = await pt.claim(one, T0 + 3, REG)
    assert rewards and rewards[0].party
