import asyncio
from random import Random

import pytest

from cococap.registry import get_registry
from cococap.services import foraging as f
from cococap.services.equipment import EffectiveStats, add_enchant, effective_stats, equip
from cococap.services.party import Party
from cococap.user import User

REG = get_registry()
RULES = REG.foraging
C = RULES.community
WINDOW = 490_000
T0 = WINDOW * 3600  # the start of an hour
OPEN = T0 + 60  # a minute into the hour: the tree is standing
LATE = T0 + 31 * 60  # after the tree has fallen over (it stands for 30 minutes)


def axe(power=5, flags=()):
    return EffectiveStats(power=power, requirement=0, stats={"power": float(power)}, flags=frozenset(flags))


async def player(user_id, axe_name="starter_axe"):
    user = await User.get(user_id)
    if axe_name:
        inst = await user.give_instance(axe_name)
        await equip(user, "foraging", inst.id)
    return user


# ---- zones and swings -------------------------------------------------------------------------------------------
def test_zones_unlock_with_level():
    assert f.zone_level(1, RULES) == 1 and f.zone_level(7, RULES) == RULES.zone_levels[6]
    assert f.unlocked_zones(1, RULES) == [1]
    assert f.unlocked_zones(f.zone_level(7, RULES), RULES) == list(range(1, 8))
    assert f.unlocked_zones(f.zone_level(7, RULES) - 1, RULES) == list(range(1, 7))
    assert f.unlocked_zones(999, RULES) == list(range(1, RULES.zones + 1))
    assert f.unlocked_zones(7, RULES) == [1, 2, 3]  # level 7 is zone 3: zones are no longer a new one every two levels


def test_every_zone_takes_longer_to_reach_than_the_one_before():
    levels = RULES.zone_levels
    gaps = [b - a for a, b in zip(levels, levels[1:], strict=False)]
    assert len(levels) == RULES.zones == 20 and gaps == sorted(gaps) and gaps[0] >= 3 and gaps[-1] > gaps[0]


def test_a_lone_chopper_is_slowed_on_heavy_trees_unless_soloist():
    heavy, light = RULES.heavy_zone, RULES.heavy_zone - 1
    assert f.swing_power(axe(10), light, RULES) == 10
    assert f.swing_power(axe(10), heavy, RULES) == round(10 * RULES.heavy_solo_power) < 10
    assert f.swing_power(axe(10, {"soloist"}), heavy, RULES) == 10  # Soloist: no penalty
    assert f.swing_power(axe(1), heavy, RULES) == 1  # never below one
    assert f.swing_power(axe(10), heavy, RULES, community=True) == 10  # the community tree is full power for all


def test_trees_get_bigger_deeper_in_the_forest():
    def mean_hp(zone):
        rng = Random(1)
        return sum(f.roll_tree(zone, rng, RULES).max_hp for _ in range(600)) / 600

    assert mean_hp(1) < mean_hp(4) < mean_hp(8)
    assert mean_hp(5) == pytest.approx(f.average_hp(5, RULES), rel=0.15)
    tree = f.roll_tree(3, Random(2), RULES)
    assert tree.hp == tree.max_hp and not tree.felled


def test_chopping_removes_hp_and_stops_at_zero():
    tree = f.Tree(1, 10, 10)
    assert tree.chop(4) == 4 and tree.hp == 6 and not tree.felled
    assert tree.chop(100) == 6 and tree.felled  # the last chop only takes what is left
    with pytest.raises(f.ForagingError, match="already down"):
        tree.chop(1)


# ---- xp is for the work, not for the axe -----------------------------------------------------------------------------
def test_a_stronger_axe_fells_the_tree_faster_but_does_not_earn_more_xp():
    def fell(power):
        tree = f.Tree(1, 100, 100)
        swings = 0
        while not tree.felled:
            tree.chop(power, 1.0)
            swings += 1
        return swings, tree.effort

    slow, fast = fell(5), fell(50)
    assert slow[0] == 20 and fast[0] == 2  # 10x the power: a tenth of the chops
    assert slow[1] == pytest.approx(20.0) and fast[1] == pytest.approx(2.0)  # ...and a tenth of the xp for this tree
    assert slow[1] * 5 == pytest.approx(fast[1] * 50)  # the same xp for the same hour of chopping


def test_the_last_chop_only_counts_for_the_part_that_was_needed():
    tree = f.Tree(1, 10, 10)
    tree.chop(8, 1.0)
    tree.chop(8, 1.0)  # only 2 of its 8 hp were needed
    assert tree.effort == pytest.approx(1.25)


def test_a_swings_effort_is_its_grain_and_good_chop_not_the_axe():
    for power in (1, 50, 500):
        spot = f.Spot("Oak", 1.5, "plain")
        swing = spot.swing(power, RULES, Random(3))
        assert swing.effort in (1.5, 1.5 * (1 + RULES.chopping.good_chop_bonus))


# ---- private trees ------------------------------------------------------------------------------------------------
async def test_felling_a_private_tree_pays_once(db):
    user = await player(1)
    tree = f.Tree(2, 100, 100)
    tree.chop(40, 1.0)
    tree.chop(60, 2.0)  # a good chop on a good grain
    reward = await f.fell_private(user, tree, Random(1))
    assert reward.bits == round(100 * RULES.bits_per_hp * f.zone_reward_factor(2, RULES)) and reward.xp == round(3 * RULES.xp_per_swing)
    await user.refresh()
    assert user.purse == 1000 + reward.bits  # the starting purse plus the tree
    skill = await user.skill("foraging")
    assert skill.xp == reward.xp and skill.stats.trees_chopped == 1
    assert {k: await user.item_quantity(k) for k in reward.drops} == dict(reward.drops)
    with pytest.raises(f.ForagingError, match="already collected"):
        await f.fell_private(user, tree, Random(1))


async def test_a_standing_tree_pays_nothing(db):
    user = await player(1)
    with pytest.raises(f.ForagingError, match="still standing"):
        await f.fell_private(user, f.Tree(1, 10, 10), Random(1))


async def test_you_need_an_axe(db):
    user = await player(1, axe_name=None)
    with pytest.raises(f.ForagingError, match="need an axe"):
        await f.axe_stats(user)
    await equip(user, "foraging", (await user.give_instance("starter_axe")).id)
    assert (await f.axe_stats(user)).power == REG.item("starter_axe").tool.power


async def test_the_soloist_enchant_turns_the_flag_on(db):
    user = await player(1)
    inst = await user.equipped_instance("foraging")
    assert not effective_stats(inst).has("soloist")
    inst = await add_enchant(user, inst.id, "soloist")
    stats = effective_stats(inst)
    assert stats.has("soloist") and f.swing_power(stats, RULES.heavy_zone, RULES) == stats.power


async def test_xp_is_boosted_in_a_party(db):
    user = await player(1)
    plain = f.Tree(1, 100, 100)
    plain.chop(100)
    base = (await f.fell_private(user, plain, Random(1))).xp
    party = await Party.create(1)
    await party.add_member(2)
    boosted = f.Tree(1, 100, 100)
    boosted.chop(100)
    assert (await f.fell_private(user, boosted, Random(1))).xp == round(base * (1 + REG.economy.party_xp_bonus_by_size[0]))


# ---- the community tree: the clock ---------------------------------------------------------------------------------
def test_each_hours_tree_is_fixed_by_the_clock():
    assert f.community_spec(WINDOW, RULES) == f.community_spec(WINDOW, RULES)
    zones = {f.community_spec(WINDOW + n, RULES)[0] for n in range(80)}
    assert zones <= set(range(C.default_zone - C.zone_below, C.default_zone + C.zone_above + 1)) and len(zones) > 2
    zone, hp = f.community_spec(WINDOW, RULES)
    typical = f.average_hp(zone, RULES) * C.hp_per_active * C.min_active
    assert 0.8 * typical <= hp <= 1.2 * typical


def test_the_community_tree_follows_who_has_been_chopping():
    deep = f.zone_level(12, RULES)
    zones = {f.community_spec(WINDOW + n, RULES, [deep] * 5)[0] for n in range(120)}
    assert zones == set(range(12 - C.zone_below, 12 + C.zone_above + 1))
    assert max(f.community_spec(WINDOW + n, RULES, [1] * 5)[0] for n in range(120)) <= 1 + C.zone_above  # beginners get beginner trees
    middle = [1, 1, deep, deep, deep]  # the middle of the crowd decides, not its richest member
    assert max(f.community_spec(WINDOW + n, RULES, middle)[0] for n in range(120)) <= 12 + C.zone_above


def test_a_bigger_crowd_gets_a_bigger_tree_up_to_a_limit():
    def hp_for(people):
        return sum(f.community_spec(WINDOW + n, RULES, [1] * people)[1] / f.average_hp(f.community_spec(WINDOW + n, RULES, [1] * people)[0], RULES)
                   for n in range(60)) / 60
    assert hp_for(1) == pytest.approx(hp_for(C.min_active), rel=0.01)  # a quiet hour still gets a proper tree
    assert hp_for(12) > 3 * hp_for(3) and hp_for(24) > 1.8 * hp_for(12)
    assert hp_for(C.max_active) == pytest.approx(hp_for(C.max_active * 5), rel=0.01)  # ...and a mob does not get an endless one


def test_a_tree_stands_for_open_minutes_each_hour():
    assert f.window_times(WINDOW, RULES) == (T0, T0 + C.open_minutes * 60)
    assert f.next_tree_at(T0 + 100) == T0 + 3600 and f.window_of(T0 + 3599) == WINDOW


async def test_everyone_sees_the_same_tree_and_looking_twice_changes_nothing(db):
    a, b = await player(1), await player(2)
    first = await f.community_tree(a, OPEN)
    again = await f.community_tree(a, OPEN + 100)
    other = await f.community_tree(b, OPEN + 200)
    assert first == again
    assert (other.window, other.zone, other.max_hp, other.hp) == (first.window, first.zone, first.max_hp, first.hp)
    assert first.standing and first.hp == first.max_hp and first.choppers == 0 and first.yours == 0


async def test_no_tree_grows_in_the_quiet_half_of_the_hour_and_the_old_one_has_fallen(db):
    user = await player(1)
    assert await f.community_tree(user, LATE) is None  # nobody looked while it was open: there never was one
    await f.community_tree(user, OPEN)
    fallen = await f.community_tree(user, LATE)
    assert fallen.status == "expired" and not fallen.standing
    with pytest.raises(f.ForagingError, match="no community tree"):
        await f.chop_community(user, 5, LATE)


# ---- the community tree: chopping -----------------------------------------------------------------------------------
async def test_chops_add_up_per_player(db):
    a, b = await player(1), await player(2)
    start = await f.community_tree(a, OPEN)
    await f.chop_community(a, 7, OPEN)
    await f.chop_community(b, 5, OPEN)
    result = await f.chop_community(a, 3, OPEN)
    assert result.applied == 3 and result.tree.hp == start.max_hp - 15 and result.tree.yours == 10
    assert result.tree.choppers == 2 and result.tree.share == pytest.approx(10 / start.max_hp)
    assert (await f.community_tree(b, OPEN)).yours == 5


async def test_many_players_chopping_at_once_lose_nothing(db):
    users = [await player(i) for i in range(1, 7)]
    start = await f.community_tree(users[0], OPEN)
    powers = {u.id: u.id + 1 for u in users}
    jobs = [f.chop_community(u, powers[u.id], OPEN) for u in users for _ in range(15)]
    results = await asyncio.gather(*jobs)
    total = sum(r.applied for r in results)
    assert total == sum(powers[u.id] * 15 for u in users)  # every chop landed (the tree is far bigger than this)
    final = await f.community_tree(users[0], OPEN)
    assert final.hp == start.max_hp - total  # no lost updates
    for u in users:
        assert (await f.community_tree(u, OPEN)).yours == powers[u.id] * 15
    assert final.choppers == 6


async def test_the_last_chop_fells_the_tree_and_only_takes_what_is_left(db):
    user = await player(1)
    tree = await f.community_tree(user, OPEN)
    await f.chop_community(user, tree.max_hp - 3, OPEN)
    last = await f.chop_community(user, 50, OPEN)
    assert last.applied == 3 and last.felled_now and last.tree.hp == 0 and last.tree.status == "felled"
    assert last.tree.yours == tree.max_hp  # contributions add up to exactly the tree's hp
    with pytest.raises(f.ForagingError, match="no community tree"):
        await f.chop_community(user, 1, OPEN)


async def test_two_final_chops_at_the_same_moment_only_fell_it_once(db):
    a, b = await player(1), await player(2)
    tree = await f.community_tree(a, OPEN)
    await f.chop_community(a, tree.max_hp - 5, OPEN)
    results = await asyncio.gather(f.chop_community(a, 5, OPEN), f.chop_community(b, 5, OPEN), return_exceptions=True)
    ok = [r for r in results if isinstance(r, f.CommunityChop)]
    assert len(ok) == 1 and ok[0].felled_now and ok[0].applied == 5
    assert isinstance(next(r for r in results if not isinstance(r, f.CommunityChop)), f.ForagingError)


# ---- the community tree: who gets what -------------------------------------------------------------------------------
def shares(felled, chops, max_hp=1000, seed=1, efforts=None):
    return f.community_shares(max_hp, felled, chops, RULES, Random(seed), REG, efforts=efforts or {u: d / 10 for u, d in chops.items()})


def test_below_the_minimum_share_you_get_xp_but_no_drops_or_bits():
    result = shares(True, {1: 940, 2: 40, 3: 20})  # player 3 chopped 2%: under the 5% minimum
    assert result[3].drops == {} and result[3].bits == 0 and result[3].xp == round(2.0 * RULES.xp_per_swing)
    assert result[1].bits > 0 and result[2].bits == 0  # player 2 chopped 4%: also under it
    assert shares(True, {1: 500, 2: 500})[2].bits > 0


def test_bits_follow_your_share_and_the_group_gets_a_bonus():
    solo = shares(True, {1: 1000})[1]
    pair = shares(True, {1: 500, 2: 500})
    assert solo.bits == 1000 * RULES.bits_per_hp  # no group bonus alone
    bonus = min(C.max_group_bonus, C.group_bonus)
    assert pair[1].bits == round(500 * RULES.bits_per_hp * (1 + bonus)) and pair[1].bits == pair[2].bits
    assert pair[1].bits + pair[2].bits > solo.bits  # working together pays more in total


def test_the_group_bonus_is_capped():
    assert C.group_bonus * 19 > C.max_group_bonus  # twenty choppers would earn more than the cap...
    many = shares(True, {u: 50 for u in range(20)})  # ...each with exactly the 5% minimum
    assert many[0].bits == round(50 * RULES.bits_per_hp * (1 + C.max_group_bonus))
    few = shares(True, {u: 250 for u in range(4)})
    assert few[0].bits == round(250 * RULES.bits_per_hp * (1 + 3 * C.group_bonus))  # below the cap: 5% per extra


def test_a_tree_that_fell_over_pays_a_consolation_only():
    done = shares(True, {1: 600, 2: 400})
    unfinished = shares(False, {1: 300, 2: 200})
    assert unfinished[1].bits == round(300 * RULES.bits_per_hp * C.expired_factor)
    assert unfinished[1].bits < done[1].bits
    assert unfinished[1].xp == round(30.0 * RULES.xp_per_swing)  # but your work still counts for xp


# ---- settling and claiming ----------------------------------------------------------------------------------------
async def test_a_felled_tree_is_settled_once_and_each_player_claims_their_own_share(db):
    a, b = await player(1), await player(2)
    tree = await f.community_tree(a, OPEN)
    await f.chop_community(a, tree.max_hp // 2, OPEN)
    await f.chop_community(b, tree.max_hp - tree.max_hp // 2, OPEN)  # b fells it
    assert (await f.community_tree(a, OPEN)).status == "felled"
    assert await f.settle_due(OPEN, Random(1)) == 1 and await f.settle_due(OPEN, Random(1)) == 0  # exactly once
    mine = await f.claim_rewards(a, OPEN, Random(1))
    assert len(mine) == 1 and mine[0].felled and mine[0].bits > 0 and mine[0].window == WINDOW
    assert await f.claim_rewards(a, OPEN, Random(1)) == []  # claimed: a second click pays nothing
    await a.refresh()
    assert a.purse == 1000 + mine[0].bits
    skill = await a.skill("foraging")
    assert skill.xp == mine[0].xp and skill.stats.trees_chopped == 1
    theirs = await f.claim_rewards(b, LATE + 9999, Random(2))  # b was offline and comes back later: still theirs
    assert len(theirs) == 1 and theirs[0].bits > 0


async def test_two_claims_at_once_pay_once(db):
    user = await player(1)
    tree = await f.community_tree(user, OPEN)
    await f.chop_community(user, tree.max_hp, OPEN)
    results = await asyncio.gather(*(f.claim_rewards(user, OPEN, Random(i)) for i in range(4)))
    assert sum(len(r) for r in results) == 1
    await user.refresh()
    assert user.purse == 1000 + next(r for r in results if r)[0].bits


async def test_an_unfinished_tree_pays_a_consolation_when_it_falls_over(db):
    user = await player(1)
    tree = await f.community_tree(user, OPEN)
    await f.chop_community(user, tree.max_hp // 2, OPEN)
    assert await f.claim_rewards(user, OPEN, Random(1)) == []  # still standing: nothing owed yet
    rewards = await f.claim_rewards(user, LATE, Random(1))
    assert len(rewards) == 1 and not rewards[0].felled
    assert rewards[0].bits == round((tree.max_hp // 2) * RULES.bits_per_hp * f.zone_reward_factor(tree.zone, RULES) * C.expired_factor)
    assert (await user.skill("foraging")).stats.trees_chopped == 0  # nothing was felled


async def test_a_bystander_gets_nothing(db):
    a, b = await player(1), await player(2)
    tree = await f.community_tree(a, OPEN)
    await f.chop_community(a, tree.max_hp, OPEN)
    assert await f.claim_rewards(b, OPEN, Random(1)) == []


async def test_party_xp_applies_to_claimed_community_rewards(db):
    user = await player(1)
    tree = await f.community_tree(user, OPEN)
    await f.chop_community(user, tree.max_hp, OPEN)
    party = await Party.create(1)
    await party.add_member(2)
    reward = (await f.claim_rewards(user, OPEN, Random(1)))[0]
    assert reward.xp == round(1.0 * RULES.xp_per_swing * (1 + REG.economy.party_xp_bonus_by_size[0]))  # one chop of effort 1


# ---- chopping: the spot, its grain and good chops -----------------------------------------------------------------------
CH = RULES.chopping


def test_spots_differ_and_a_new_spot_is_a_random_new_grain():
    kinds = {f.Spot.pick(RULES, Random(i)).name for i in range(300)}
    assert kinds == {g.name for g in CH.grains}
    spot = f.Spot("Knotty", 0.7, "knotty", wear=0.6)
    spot.rotate(RULES, Random(3))
    assert spot.wear == 0 and spot.grain != "knotty" and spot.name == CH.grain(spot.grain).name  # always a different grain, unworn
    assert f.average_spot_multiplier(RULES) == pytest.approx(1.0, abs=0.05)  # on average a new spot is neither a gift nor a curse


def test_the_grain_changes_the_damage_you_deal():
    damage = {g.name: f.Spot(g.name, g.multiplier, g.id).preview(100, RULES) for g in CH.grains}
    assert damage["Knotty"] < damage["Twisted"] < damage["Plain"] == 100 < damage["Clean grain"] < damage["Burl"]
    swing = f.Spot("Clean grain", 1.3).swing(100, RULES, Random(1))
    assert swing.damage == (round(100 * 1.3 * (1 + CH.good_chop_bonus)) if swing.good else 130)


def test_a_swing_always_does_at_least_one_damage():
    assert f.Spot("Knotty", 0.7).swing(1, RULES, Random(1)).damage >= 1 and f.Spot("Knotty", 0.7).preview(1, RULES) == 1


def test_good_chops_happen_about_as_often_as_configured_and_hit_harder():
    good, total = 0, 4000
    rng = Random(3)
    for _ in range(total):
        swing = f.Spot().swing(20, RULES, rng)  # a plain, unworn spot
        good += swing.good
        assert swing.damage == (round(20 * (1 + CH.good_chop_bonus)) if swing.good else 20)
    assert good / total == pytest.approx(CH.good_chop_chance, abs=0.025)


def test_the_starter_axe_chops_a_first_zone_tree_quickly():
    """The complaint: the first tree took too long. With rotating, a typical zone 1 tree is a few dozen clicks at most."""
    power = REG.item("starter_axe").tool.power
    rng, tree, clicks = Random(1), f.roll_tree(1, Random(4), RULES), 0
    spot = f.Spot.pick(RULES, rng)
    while not tree.felled:  # (a master who knows every grain's style)
        tree.chop(spot.swing(power, RULES, rng, 0.0, spot.stance(RULES)).damage)
        clicks += 1
    assert clicks <= 30


# ---- the economy: foraging should not out-earn mining -----------------------------------------------------------------
def test_deeper_zones_pay_more_per_hp():
    assert f.zone_reward_factor(1, RULES) == 1.0 and f.zone_reward_factor(7, RULES) == pytest.approx(1 + 6 * RULES.zone_reward_growth)
    assert f.expected_rolls(100, RULES, 7) > f.expected_rolls(100, RULES, 1)


def test_fractional_drop_rolls_average_out():
    rng = Random(5)
    rolls = [f.whole_rolls(2.3, rng) for _ in range(4000)]
    assert set(rolls) == {2, 3} and sum(rolls) / len(rolls) == pytest.approx(2.3, abs=0.04)


def test_foraging_pays_less_per_click_than_mining_at_starter_gear():
    """A guard against the payouts drifting up again. Both sides are simulated with fixed seeds (so this is exact and
    repeatable); change the numbers and this tells you how the two skills now compare."""
    from cococap.services import loot
    from cococap.services import mining as m

    price = lambda item_id: REG.item(item_id).sell_price

    def mine(seed):
        run = m.MineRun(REG.mining, REG, Random(seed), cursors=[2], braces=1)
        clicks = 0
        while not run.finished:
            if run.risk >= 0.07:
                if run.braces and run.danger > 10:
                    run.brace()
                    clicks += 1
                    continue
                run.leave()
                break
            if run.signs(run.depth)[run.cursors[0]] == "hole":
                run.move(1)
            run.dig()
            clicks += 1
        return sum(price(i) * q for i, q in run.haul.items()), clicks

    runs = [mine(s) for s in range(1500)]
    mining_per_click = sum(v for v, _ in runs) / sum(c for _, c in runs)

    rng = Random(1)
    mean_quantity = {i.id: sum(loot.skewed_roll(rng, i.drop.min, i.drop.max) for _ in range(20000)) / 20000 for i in f.drop_pool(REG)}
    per_roll = sum(price(i.id) * mean_quantity[i.id] / i.drop.rate for i in f.drop_pool(REG))
    power, zone = REG.item("starter_axe").tool.power, 1
    hp = f.average_hp(zone, RULES)
    rng, dealt, clicks = Random(2), 0, 6000
    spot = f.Spot.pick(RULES, rng)
    for _ in range(clicks):  # a master: they know every grain's style (spots wear out and renew by themselves)
        dealt += spot.swing(power, RULES, rng, 0.0, spot.stance(RULES)).damage
    pay_per_hp = RULES.bits_per_hp * f.zone_reward_factor(zone, RULES) + per_roll * f.expected_rolls(1, RULES, zone)
    foraging_per_click = pay_per_hp * dealt / clicks
    assert hp > 0 and foraging_per_click < mining_per_click, (foraging_per_click, mining_per_click)
    assert foraging_per_click > 0.4 * mining_per_click  # ...but it is still worth doing


# ---- one style per grain, wear and wedges ------------------------------------------------------------------------------------------
def right(spot):
    return spot.stance(RULES)


def wrong(spot):
    return next(letter for letter in "osu" if letter != right(spot))


class NoGood(Random):
    def random(self):
        return 0.999  # no good chops


def test_every_grain_likes_one_style_and_every_style_is_liked_by_some_grain():
    assert {g.stance for g in CH.grains} == {"o", "s", "u"}
    assert len({g.id for g in CH.grains}) == len(CH.grains)


def test_good_grains_wear_slowly_and_bad_ones_quickly():
    by_quality = sorted(CH.grains, key=lambda g: g.multiplier)
    assert by_quality[0].wear > 1 > by_quality[-1].wear  # the worst grain wears out fastest, the best slowest
    assert all(a.wear >= b.wear for a, b in zip(by_quality, by_quality[1:], strict=False))  # and it is monotone: better is always slower


def test_the_wrong_style_glances_off_at_a_fraction_and_the_right_one_hits_fully():
    a, b, c = f.Spot(), f.Spot(), f.Spot()
    full = a.swing(100, RULES, NoGood(1), 0.0, right(a))
    glance = b.swing(100, RULES, NoGood(1), 0.0, wrong(b))
    plain = c.swing(100, RULES, NoGood(1))
    assert (full.correct, glance.correct, plain.correct) == (True, False, None)
    assert full.damage == plain.damage == 100 and glance.damage == round(100 * CH.wrong_stance_factor)
    assert glance.effort == pytest.approx(full.effort * CH.wrong_stance_factor)  # xp follows the quality of the chop


def test_chopping_wears_the_spot_and_a_worn_spot_chops_weaker():
    spot = f.Spot()
    first = spot.swing(100, RULES, NoGood(1), 0.0, "s").damage
    assert spot.wear == pytest.approx(CH.wear_per_chop)  # a plain spot (wear 1)
    spot.wear = 0.99
    assert spot.preview(100, RULES) == round(100 * (1 - CH.wear_penalty * 0.99)) < first
    assert f.Spot().preview(100, RULES) == 100


def test_a_spot_wears_at_its_grains_pace_and_a_seasoned_axe_slows_it():
    burl, knotty = f.Spot("Burl", 1.4, "burl"), f.Spot("Knotty", 0.7, "knotty")
    burl.swing(10, RULES, NoGood(1))
    knotty.swing(10, RULES, NoGood(1))
    assert burl.wear < CH.wear_per_chop < knotty.wear
    slowed = f.Spot()
    slowed.swing(10, RULES, NoGood(1), 0.0, None, wear_slow=0.45)
    assert slowed.wear == pytest.approx(CH.wear_per_chop * 0.55)
    capped = f.Spot()
    capped.swing(10, RULES, NoGood(1), 0.0, None, wear_slow=5.0)
    assert capped.wear == pytest.approx(CH.wear_per_chop * f.MIN_WEAR_FACTOR)  # even a silly amount cannot stop wear altogether


def test_a_fully_worn_spot_is_replaced_by_a_new_unworn_one():
    spot = f.Spot()
    spot.wear = 1 - CH.wear_per_chop / 2
    swing = spot.swing(10, RULES, NoGood(1), 0.0, None)
    assert swing.ended and spot.wear == 0 and spot.grain != "plain"
    assert not f.Spot().swing(10, RULES, NoGood(1), 0.0, None).ended


def test_a_wedge_leans_toward_good_grains_by_its_bias():
    def share_good(bias):
        picks = [f.Spot.pick(RULES, Random(i), bias, exclude="plain") for i in range(3000)]
        return sum(p.quality > 1 for p in picks) / len(picks)

    assert share_good(0) < share_good(4) < share_good(12)
    assert all(f.Spot.pick(RULES, Random(i), 0, exclude="burl").grain != "burl" for i in range(200))  # you never land where you were


async def test_a_wedge_is_spent_to_move_off_the_spot_and_you_need_one(db):
    user = await player(1)
    spot = f.Spot()
    spot.wear = 0.5
    with pytest.raises(f.ForagingError, match="no Rotation Wedge"):
        await f.spend_wedge(user, spot, "rotation_wedge", Random(1))
    with pytest.raises(f.ForagingError, match="not a rotation wedge"):
        await f.spend_wedge(user, spot, "apple", Random(1))
    await user.add_item("rotation_wedge", 2)
    await f.spend_wedge(user, spot, "rotation_wedge", Random(1))
    assert spot.wear == 0 and spot.grain != "plain" and await user.item_quantity("rotation_wedge") == 1
    assert [(w.item, q) for w, q in await f.wedges(user)] == [("rotation_wedge", 1)]


async def test_a_better_wedge_really_lands_you_on_better_grains(db):
    user = await player(1)
    await user.add_item("rotation_wedge", 150)
    await user.add_item("gilded_wedge", 150)
    share = {}
    for item in ("rotation_wedge", "gilded_wedge"):
        good = 0
        for i in range(150):
            spot = f.Spot("Plain", 1.0, "plain")
            await f.spend_wedge(user, spot, item, Random(i))
            good += spot.quality > 1
        share[item] = good / 150
    assert share["gilded_wedge"] > share["rotation_wedge"] + 0.3


# ---- special spots ---------------------------------------------------------------------------------------------------------------
def special(kind, **kw):
    sp = CH.special(kind)
    return f.Spot("Plain", 1.0, "plain", special=kind, **kw), sp


def test_a_heartwood_spot_hits_far_harder_but_only_in_the_right_style():
    spot, sp = special("heartwood")
    hit = spot.swing(100, RULES, NoGood(1), 0.0, right(spot))
    assert hit.damage == round(100 * sp.amount) and hit.special == "damage"
    spot, _ = special("heartwood")
    miss = spot.swing(100, RULES, NoGood(1), 0.0, wrong(spot))
    assert miss.damage == round(100 * CH.wrong_stance_factor) and miss.special == ""  # just a glancing blow
    assert special("heartwood")[0].preview(100, RULES) == round(100 * sp.amount)


def test_a_golden_knot_pays_more_xp_without_hitting_harder():
    spot, sp = special("golden_knot")
    hit = spot.swing(100, RULES, NoGood(1), 0.0, right(spot))
    assert hit.damage == 100 and hit.effort == pytest.approx(sp.amount) and hit.special == "xp"
    spot, _ = special("golden_knot")
    assert spot.swing(100, RULES, NoGood(1), 0.0, wrong(spot)).effort == pytest.approx(CH.wrong_stance_factor)


def test_a_rich_seam_marks_a_private_tree_only_and_a_wrong_chop_marks_nothing():
    spot, sp = special("rich_seam")
    assert spot.swing(100, RULES, NoGood(1), 0.0, right(spot)).mark == sp.amount
    spot, _ = special("rich_seam")
    assert spot.swing(100, RULES, NoGood(1), 0.0, wrong(spot)).mark == 0
    shared, _ = special("rich_seam", )
    shared.private = False
    assert shared.swing(100, RULES, NoGood(1), 0.0, right(shared)).mark == 0
    assert all(f.Spot.pick(RULES, Random(i), special_mult=50, private=False).special != "rich_seam" for i in range(400))


def test_special_spots_are_rare_short_lived_and_a_wedge_makes_them_likelier():
    share = lambda mult: sum(bool(f.Spot.pick(RULES, Random(i), special_mult=mult).special) for i in range(6000)) / 6000  # noqa: E731
    assert share(1) == pytest.approx(CH.special_chance, abs=0.02) and share(4) > 2.5 * share(1)
    spot, _ = special("heartwood")
    assert sum(1 for _ in iter(lambda: spot.swing(10, RULES, NoGood(1), 0.0, None).ended, True)) < 8  # a few chops, not twenty-five
    assert CH.special("heartwood").wear > 3  # (a big wear number: it is gone quickly)


async def test_felling_a_marked_tree_pays_the_bonus_on_bits(db):
    user = await player(1)
    base, marked = f.Tree(1, 1000, 0), f.Tree(1, 1000, 0, bonus=0.5)
    a = await f.fell_private(user, base, Random(1))
    b = await f.fell_private(user, marked, Random(1))
    assert b.bits == round(a.bits * 1.5)


def test_double_chop_hits_twice_but_pays_the_xp_of_one_swing():
    never = f.Spot().swing(100, RULES, NoGood(1), 0.0, None, 0.0, 0.0)
    assert never.damage == 100 and not never.doubled
    sure = f.Spot().swing(100, RULES, Random(1), 0.0, None, 0.0, 1.0)
    assert sure.doubled and sure.damage in (200, 300) and sure.effort in (1.0, 1 + CH.good_chop_bonus)  # (300: a good chop too)
    hits = sum(f.Spot().swing(10, RULES, Random(i), 0.0, None, 0.0, 0.3).doubled for i in range(4000)) / 4000
    assert hits == pytest.approx(0.3, abs=0.03)


async def test_the_double_strike_enchant_gives_the_chance(db):
    user = await player(1)
    inst = await user.give_instance("starter_axe")
    await add_enchant(user, inst.id, "double_strike")
    await add_enchant(user, inst.id, "double_strike")
    assert effective_stats(await user.instance(inst.id), REG).stats["double_chop"] == pytest.approx(0.16)


def test_wedges_can_be_found_chopping_and_the_better_ones_are_rarer():
    pool = {i.id: i for i in f.drop_pool(REG)}
    rates = [pool[w.item].drop.rate for w in RULES.rotate.wedges]
    assert rates == sorted(rates) and len(set(rates)) == 3
    assert [w.special_mult for w in RULES.rotate.wedges] == sorted(w.special_mult for w in RULES.rotate.wedges)
    assert REG.item("gilded_wedge").price <= 100_000  # (a wedge only moves you to a new spot: it should not cost a fortune)


def test_the_wedges_get_better_and_cost_more():
    wedges = RULES.rotate.wedges
    assert [w.bias for w in wedges] == sorted(w.bias for w in wedges) and wedges[0].bias == 0
    prices = [REG.item(w.item).price for w in wedges]
    assert prices == sorted(prices) and prices[0] > 0


async def test_the_seasoned_enchant_slows_wear_on_the_axe(db):
    user = await player(1)
    inst = await user.give_instance("starter_axe")
    await equip(user, "foraging", inst.id)
    await add_enchant(user, inst.id, "seasoned")
    stats = effective_stats(await user.instance(inst.id), REG)
    assert stats.stats["wear_slow"] == pytest.approx(0.15)


# ---- the notes -------------------------------------------------------------------------------------------------------------------------
async def test_a_right_style_is_remembered_and_a_wrong_one_is_crossed_off(db):
    user = await player(1)
    assert await f.note_style(user, "plain", "u", False) is True  # a wrong guess is news
    assert await f.note_style(user, "plain", "u", False) is False  # ...but only once
    assert await f.note_style(user, "plain", "o", False) is True
    plain = next(n for n in await f.grain_notes(user) if n.grain.id == "plain")
    assert plain.known is None and sorted(plain.ruled_out) == ["o", "u"]  # two ruled out: the third is easy to work out
    assert await f.note_style(user, "plain", "s", True) is True
    plain = next(n for n in await f.grain_notes(user) if n.grain.id == "plain")
    assert plain.known == "s" and plain.ruled_out == ""  # knowing it replaces the crossed-off guesses
    assert await f.note_style(user, "plain", "s", True) is False
    assert await f.note_style(user, "plain", "o", False) is False  # a known grain can't be un-known
    burl = next(n for n in await f.grain_notes(user) if n.grain.id == "burl")
    assert burl.known is None and burl.ruled_out == ""  # each grain has its own notes


def test_you_can_always_work_a_grain_out_in_at_most_two_wrong_guesses():
    for grain in CH.grains:
        tried = []
        for letter in "osu":
            if letter == grain.stance:
                break
            tried.append(letter)
        assert len(tried) <= 2


# ---- on the screens -----------------------------------------------------------------------------------------------------------------
async def test_the_panel_shows_the_spot_and_its_wear_but_never_the_style(db, monkeypatch):
    from tests.test_hub import chop, click, freeze_time, hub, with_axe

    freeze_time(monkeypatch)
    user = await with_axe()
    nav, inter = await hub("tree", tree=f.Tree(1, 10_000, 10_000))
    text_now = lambda: " ".join(c.content for c in nav.walk_children() if hasattr(c, "content"))  # noqa: E731
    page = text_now()
    assert "Plain" in page and "100%" in page and "a chop" in page
    assert "likes" not in page and not any(name in page for name, _ in f.STANCES.values())  # the style is only in your notes
    wrong_label = f.STANCES[wrong(nav.screen.spot)][0]
    await click(nav, inter, wrong_label)
    assert "glanced off" in text_now() and "crossed off" in text_now()
    await chop(nav, inter)
    assert "Learned" in text_now()
    plain = next(n for n in await f.grain_notes(user) if n.grain.id == "plain")
    assert plain.known == right(nav.screen.spot)  # the right style was written down


async def test_the_grain_notes_page_lists_every_grain_what_you_know_and_what_you_crossed_off(db, monkeypatch):
    from tests.test_hub import click, freeze_time, hub, with_axe

    freeze_time(monkeypatch)
    user = await with_axe()
    await f.note_style(user, "plain", "s", True)
    await f.note_style(user, "knotty", "o", False)
    nav, inter = await hub("tree", tree=f.Tree(1, 5_000, 4_000))
    tree = nav.screen.tree
    await click(nav, inter, "Grain notes")
    assert nav.screen.id == "result"
    page = " ".join(c.content for c in nav.walk_children() if hasattr(c, "content"))
    for grain in CH.grains:
        assert grain.name in page
    assert f"{f.STANCES['s'][1]} {f.STANCES['s'][0]}" in page and f"✖️{f.STANCES['o'][1]}" in page
    await click(nav, inter, "Back to chopping")
    assert nav.screen.id == "tree" and nav.screen.tree is tree  # the very same tree: nothing was lost
    forage, forage_inter = await hub("forage")
    await click(forage, forage_inter, "Grain notes")
    assert forage.screen.id == "result"


async def test_a_wedge_button_appears_with_a_wedge_and_moves_you_to_a_new_spot(db, monkeypatch):
    from tests.test_hub import buttons, click, freeze_time, hub, with_axe

    freeze_time(monkeypatch)
    user = await with_axe()
    nav, inter = await hub("tree", tree=f.Tree(1, 10_000, 10_000))
    assert not [b for b in buttons(nav) if "Wedge" in (b.label or "")]  # none held: no button
    await user.add_item("iron_wedge", 2)
    nav, inter = await hub("tree", tree=f.Tree(1, 10_000, 10_000))
    nav.screen.spot.wear = 0.5
    assert [b.label for b in buttons(nav) if "Wedge" in (b.label or "")] == ["Iron Wedge ×2"]
    await click(nav, inter, "Iron Wedge ×2")
    assert nav.screen.spot.wear == 0 and await user.item_quantity("iron_wedge") == 1


async def test_a_heartwood_spot_on_screen_shows_itself_and_hits_the_tree_hard_and_a_rich_seam_marks_it(db, monkeypatch):
    from tests.test_hub import chop, freeze_time, hub, with_axe

    freeze_time(monkeypatch)
    await with_axe()
    power = REG.item("starter_axe").tool.power
    nav, inter = await hub("tree", tree=f.Tree(1, 100_000, 100_000))
    nav.screen.spot = f.Spot("Plain", 1.0, "plain", special="heartwood")
    await nav._render()
    text_now = lambda: " ".join(c.content for c in nav.walk_children() if hasattr(c, "content"))  # noqa: E731
    assert "Heartwood" in text_now() and f"**{round(power * CH.special('heartwood').amount)}** a chop" in text_now()
    await chop(nav, inter)
    assert nav.screen.tree.hp == 100_000 - round(power * CH.special("heartwood").amount) and "Heartwood: a huge hit" in text_now()
    nav.screen.spot = f.Spot("Plain", 1.0, "plain", special="rich_seam")
    await chop(nav, inter)
    assert nav.screen.tree.bonus == pytest.approx(CH.special("rich_seam").amount) and "Marked" in text_now()
    for _ in range(6):
        nav.screen.spot = f.Spot("Plain", 1.0, "plain", special="rich_seam")
        await chop(nav, inter)
    assert nav.screen.tree.bonus == CH.mark_cap  # (marks stop adding at the cap)


def test_a_shared_tree_spot_never_becomes_a_rich_seam_when_it_rotates():
    spot = f.Spot(private=False)
    for i in range(400):
        spot.rotate(RULES, Random(i), special_mult=50)
        assert spot.special != "rich_seam"
    mine = f.Spot()
    assert any((mine.rotate(RULES, Random(i), special_mult=50), mine.special)[1] == "rich_seam" for i in range(400))


async def test_a_marked_tree_makes_more_drop_rolls(db):
    user = await player(1)
    plain = await f.fell_private(user, f.Tree(1, 50_000, 0), Random(1))
    marked = await f.fell_private(user, f.Tree(1, 50_000, 0, bonus=0.5), Random(1))
    assert sum(marked.drops.values()) > 1.3 * sum(plain.drops.values())


async def test_the_better_wedges_really_find_special_spots_more_often(db):
    user = await player(1)
    await user.add_item("rotation_wedge", 400)
    await user.add_item("gilded_wedge", 400)
    found = {}
    for item in ("rotation_wedge", "gilded_wedge"):
        found[item] = 0
        for i in range(400):
            spot = f.Spot()
            await f.spend_wedge(user, spot, item, Random(i))
            found[item] += bool(spot.special)
    assert found["gilded_wedge"] > 3 * found["rotation_wedge"]
