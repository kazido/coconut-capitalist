"""Guards against the economy scaling out of hand: what an hour of each skill pays, how top-heavy the drops are, and how Work compares to playing.

These run the same simulations as `python -m scripts.balance`. When one fails, a payout was changed without looking at the others: read DESIGN.md
("Where the bits come from") before loosening a bound."""

from collections import Counter
from random import Random

from cococap.registry import get_registry
from cococap.services import foraging as f
from cococap.services import loot
from cococap.services import mining as m
from scripts import balance

REG = get_registry()
PER_MINUTE = 60 / balance.CLICK_SECONDS


def mining_haul(runs=700):
    tot, clicks = Counter(), 0
    for seed in range(runs):
        run = m.MineRun(REG.mining, REG, Random(seed), cursors=[2], braces=1)
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
        tot.update(run.haul)
    return tot, clicks


def foraging_value_per_roll():
    values = {}
    for item in f.drop_pool(REG):
        rng = Random(1)
        mean = sum(loot.skewed_roll(rng, item.drop.min, item.drop.max) for _ in range(4000)) / 4000
        values[item.id] = item.sell_price * mean / item.drop.rate
    return values


def test_an_hour_of_each_skill_at_starter_gear_pays_about_the_same():
    mining = balance.mining_per_click() * PER_MINUTE
    foraging = balance.foraging_per_click(1) * PER_MINUTE
    worth, seconds = balance.fishing_per_cast()
    fishing = worth * 60 / seconds
    pay = {"mining": mining, "foraging": foraging, "fishing": fishing}
    assert all(6_000 <= v <= 25_000 for v in pay.values()), pay  # bits per active minute (the top was 20,000 until the brace buff lifted mining)
    assert max(pay.values()) / min(pay.values()) < 2.2, pay  # nothing out-earns another by more than about double


def test_no_single_foraging_drop_is_most_of_what_chopping_pays():
    values = foraging_value_per_roll()
    total = sum(values.values())
    assert max(values.values()) / total <= 0.35, {k: round(v / total, 2) for k, v in values.items() if v / total > 0.1}
    common = sum(v for i, v in values.items() if REG.item(i).drop.rate <= 3)  # the things you find all the time
    assert common / total >= 0.15  # ...are a real part of the pay, not pennies (hardwood and feathers)


def test_no_single_ore_or_find_is_most_of_what_mining_pays():
    tot, clicks = mining_haul()
    worth = {i: REG.item(i).sell_price * q for i, q in tot.items()}
    total = sum(worth.values())
    assert max(worth.values()) / total <= 0.55, {i: round(v / total, 2) for i, v in worth.items() if v / total > 0.1}
    assert REG.item("material_copper_ore").sell_price >= 40  # (the commonest ore is not worth pennies)


def test_the_commonest_materials_are_worth_something_next_to_the_rare_ones():
    for common, rare in (("material_hardwood", "material_maple_leaf"), ("material_feather", "material_aged_feather"), ("material_copper_ore", "material_gold_ore")):
        ratio = REG.item(rare).sell_price / REG.item(common).sell_price
        assert ratio <= 3000, (common, rare, ratio)  # a rare drop is a lot, not a million times a common one
    assert REG.item("material_hardwood").sell_price >= 2_000


def test_a_days_work_pays_less_than_an_hour_of_playing_at_the_ranks_new_players_reach():
    hour = balance.mining_per_click() * PER_MINUTE * 60
    for rank in range(8):
        assert REG.rank(rank).wage * 4 <= hour, rank  # (four claims a day)
