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
    assert f.zone_level(1, RULES) == 1 and f.zone_level(7, RULES) == 1 + 6 * RULES.levels_per_zone
    assert f.unlocked_zones(1, RULES) == [1]
    assert f.unlocked_zones(f.zone_level(7, RULES), RULES) == list(range(1, 8))
    assert f.unlocked_zones(999, RULES) == list(range(1, RULES.zones + 1))


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


# ---- private trees ------------------------------------------------------------------------------------------------
async def test_felling_a_private_tree_pays_once(db):
    user = await player(1)
    tree = f.Tree(2, 100, 100)
    tree.chop(100)
    reward = await f.fell_private(user, tree, Random(1))
    assert reward.bits == round(100 * RULES.bits_per_hp * f.zone_reward_factor(2, RULES)) and reward.xp == round(100 * RULES.xp_per_hp)
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
    assert zones <= set(range(C.min_zone, C.max_zone + 1)) and len(zones) > 2
    zone, hp = f.community_spec(WINDOW, RULES)
    typical = f.average_hp(zone, RULES) * C.hp_multiplier
    assert 0.8 * typical <= hp <= 1.2 * typical


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
def shares(felled, chops, max_hp=1000, seed=1):
    return f.community_shares(max_hp, felled, chops, RULES, Random(seed), REG)


def test_below_the_minimum_share_you_get_xp_but_no_drops_or_bits():
    result = shares(True, {1: 940, 2: 40, 3: 20})  # player 3 chopped 2%: under the 5% minimum
    assert result[3].drops == {} and result[3].bits == 0 and result[3].xp == round(20 * RULES.xp_per_hp)
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
    assert unfinished[1].xp == round(300 * RULES.xp_per_hp)  # but your work still counts for xp


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
    assert reward.xp == round(tree.max_hp * RULES.xp_per_hp * (1 + REG.economy.party_xp_bonus_by_size[0]))


# ---- chopping: the spot, rotating and good chops -----------------------------------------------------------------------
CH = RULES.chopping


def test_spots_differ_and_rotating_picks_a_random_new_one():
    kinds = {f.Spot.pick(RULES, Random(i)).name for i in range(200)}
    assert kinds == {k.name for k in CH.spots}
    spot = f.Spot("Knotty", 0.7, wear=4)
    spot.rotate(RULES, Random(3))
    assert spot.wear == 0 and spot.name in kinds
    assert f.average_spot_multiplier(RULES) == pytest.approx(1.0, abs=0.05)  # on average a new spot is neither a gift nor a curse


def test_a_spot_only_wears_down_now_and_then_not_on_every_chop():
    rng, spot, worn_after = Random(9), f.Spot(), []
    for _ in range(2000):
        before = spot.wear
        spot.swing(10, RULES, rng)
        worn_after.append(spot.wear - before)
    assert set(worn_after) == {0, 1}
    assert sum(worn_after) / 2000 == pytest.approx(CH.wear_chance, abs=0.03)
    assert worn_after[:3] != [1, 1, 1]


def test_wear_makes_chops_weaker_down_to_a_floor():
    spot = f.Spot(wear=0)
    assert spot.multiplier(RULES) == 1.0 and spot.condition(RULES) == "fresh"
    spot.wear = 2
    assert spot.multiplier(RULES) == pytest.approx(1 - 2 * CH.wear_step) and spot.condition(RULES) == "worn"
    spot.wear = 100
    assert spot.multiplier(RULES) == CH.spot_floor and spot.condition(RULES) == "dull"
    assert spot.preview(100, RULES) == round(100 * CH.spot_floor)


def test_the_kind_of_spot_changes_the_damage_you_deal():
    rng = Random(1)
    damage = {k.name: f.Spot(k.name, k.multiplier).preview(100, RULES) for k in CH.spots}
    assert damage["Knotty"] < damage["Plain"] == 100 < damage["Clean grain"]
    swing = f.Spot("Clean grain", 1.3).swing(100, RULES, rng)
    assert swing.damage == (round(100 * 1.3 * (1 + CH.good_chop_bonus)) if swing.good else 130)


def test_rotating_a_good_spot_is_a_mistake_and_staying_on_a_ruined_one_is_too():
    def per_click(threshold, power=20, clicks=60_000):
        rng, spot, dealt = Random(7), f.Spot.pick(RULES, Random(7)), 0
        for _ in range(clicks):
            if threshold is not None and spot.multiplier(RULES) < threshold:
                spot.rotate(RULES, rng)  # a click that does no damage
            else:
                dealt += spot.swing(power, RULES, rng).damage
        return dealt / clicks

    never, sensible = per_click(None), per_click(0.8)
    assert sensible > never * 2  # leaving a worn spot is clearly right
    assert sensible > per_click(1.3)  # but rotating away from decent spots wastes clicks
    assert sensible > per_click(0.4)  # ...and so does staying on a poor one


def test_a_swing_always_does_at_least_one_damage():
    spot = f.Spot("Knotty", 0.7, wear=30)
    assert spot.swing(1, RULES, Random(1)).damage >= 1 and spot.preview(1, RULES) == 1


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
    while not tree.felled:
        if spot.multiplier(RULES) < 0.8:
            spot.rotate(RULES, rng)
        else:
            tree.chop(spot.swing(power, RULES, rng).damage)
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
    for _ in range(clicks):  # a sensible chopper: moves on once the spot is clearly worse than an average new one
        if spot.multiplier(RULES) < 0.8:
            spot.rotate(RULES, rng)
        else:
            dealt += spot.swing(power, RULES, rng).damage
    pay_per_hp = RULES.bits_per_hp * f.zone_reward_factor(zone, RULES) + per_roll * f.expected_rolls(1, RULES, zone)
    foraging_per_click = pay_per_hp * dealt / clicks
    assert hp > 0 and foraging_per_click < mining_per_click, (foraging_per_click, mining_per_click)
    assert foraging_per_click > 0.4 * mining_per_click  # ...but it is still worth doing


# ---- chop styles: heavy swings and careful cuts ---------------------------------------------------------------------------------
H, CAREFUL = CH.heavy, CH.careful


def test_a_heavy_swing_hits_harder_and_sometimes_misses_and_wears_the_spot_faster():
    results = [f.Spot().swing(100, RULES, Random(i), style="heavy") for i in range(2000)]
    missed = [r for r in results if r.missed]
    assert 0.18 < len(missed) / 2000 < 0.32 and all(r.damage == 0 and not r.good for r in missed)
    landed = [r.damage for r in results if not r.missed and not r.good]
    assert set(landed) == {round(100 * H.damage)}  # a plain, unworn spot: exactly the heavy multiple


def test_a_careful_cut_is_gentler_and_never_wears_the_spot_but_lands_good_chops_more():
    spot = f.Spot()
    rng = Random(4)
    swings = [spot.swing(100, RULES, rng, style="careful") for _ in range(600)]
    assert spot.wear == 0  # never any wear, however long you do it
    assert {s.damage for s in swings if not s.good} == {round(100 * CAREFUL.damage)}
    plain_good = sum(f.Spot().swing(100, RULES, Random(i)).good for i in range(3000))
    careful_good = sum(f.Spot().swing(100, RULES, Random(i), style="careful").good for i in range(3000))
    assert careful_good > plain_good * 1.4


def test_heavy_swings_wear_a_spot_out_faster_than_ordinary_chops():
    def wear_after(style, swings=300):
        spot, rng = f.Spot(), Random(9)
        for _ in range(swings):
            spot.swing(50, RULES, rng, style=style)
        return spot.wear

    assert wear_after("heavy") > 2 * wear_after("normal") > 0
    assert wear_after("careful") == 0


def test_the_preview_shows_what_each_style_would_do():
    spot = f.Spot()
    assert spot.preview(100, RULES) == 100
    assert spot.preview(100, RULES, "heavy") == round(100 * H.damage) and spot.preview(100, RULES, "careful") == round(100 * CAREFUL.damage)
    assert f.Spot("Knotty", 0.7).preview(100, RULES, "heavy") < spot.preview(100, RULES, "heavy")


def test_no_chop_style_is_a_free_lunch_or_a_dead_end():
    """Each is worth using but none beats the others by much: a mix of habits, not a single right answer."""
    def damage_per_click(style, rotate_below=0.7, clicks=40_000, power=20):
        rng = Random(5)
        spot, dealt = f.Spot.pick(RULES, rng), 0
        for _ in range(clicks):
            if spot.multiplier(RULES) < rotate_below:
                spot.rotate(RULES, rng)
            else:
                dealt += spot.swing(power, RULES, rng, style=style).damage
        return dealt / clicks

    rates = {s: max(damage_per_click(s, t) for t in (0.5, 0.7, 0.9)) for s in ("normal", "heavy", "careful")}
    assert max(rates.values()) < 1.25 * rates["normal"], rates
    assert min(rates.values()) > 0.75 * rates["normal"], rates


async def test_the_tree_screens_offer_all_three_swings_and_a_miss_is_just_a_note(db, monkeypatch):
    from tests.test_hub import find_button as button_named

    monkeypatch.setattr("cococap.screens.forage.new_rng", lambda: Random(1))
    user = await User.get(1)
    inst = await user.give_instance("starter_axe")
    await equip(user, "foraging", inst.id)
    from tests.test_hub import click, hub

    nav, inter = await hub("tree", tree=f.Tree(1, 10_000, 10_000))
    for label in ("Chop", "Heavy", "Careful", "Rotate", "Leave"):
        assert button_named(nav, label)
    text = " ".join(c.content for c in nav.walk_children() if hasattr(c, "content"))
    assert "heavy" in text and "careful" in text and "to miss" in text
    nav.screen.rng = type("Miss", (Random,), {"random": lambda self: 0.0})(1)  # every roll is "below the chance": a miss
    hp = nav.screen.tree.hp
    await click(nav, inter, "Heavy")
    assert nav.screen.tree.hp == hp and "swing wide" in " ".join(c.content for c in nav.walk_children() if hasattr(c, "content"))
    await click(nav, inter, "Careful")
    assert nav.screen.tree.hp < hp  # a careful cut never misses
    await click(nav, inter, "Chop")
