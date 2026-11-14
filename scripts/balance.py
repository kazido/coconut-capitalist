"""Balance report: what each skill pays for the same amount of play, at starter gear.

    .venv/bin/python -m scripts.balance

Everything is simulated with fixed seeds, so the numbers are repeatable. "Active minute" assumes a click every
CLICK_SECONDS seconds. Farming is mostly waiting, so it is reported per plot per hour (and per active minute, counting
only the clicks it needs). This is a guide for tuning `configs/*.toml`, not a test.
"""

from random import Random

from cococap.registry import get_registry
from cococap.services import foraging as f
from cococap.services import fishing as fi
from cococap.services import loot
from cococap.services import mining as m

REG = get_registry()
CLICK_SECONDS = 5.0
price = lambda item_id: REG.item(item_id).sell_price


def mining_per_click() -> float:
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

    runs = [mine(s) for s in range(800)]
    return sum(v for v, _ in runs) / sum(c for _, c in runs)


def foraging_per_click(zone: int = 1, axe: str = "starter_axe") -> float:
    rules = REG.foraging
    rng = Random(1)
    mean_q = {i.id: sum(loot.skewed_roll(rng, i.drop.min, i.drop.max) for _ in range(5000)) / 5000 for i in f.drop_pool(REG)}
    per_roll = sum(price(i.id) * mean_q[i.id] / i.drop.rate for i in f.drop_pool(REG))
    power = REG.item(axe).tool.power
    rng, dealt, clicks = Random(2), 0, 4000
    spot = f.Spot.pick(rules, rng)
    cycle = f.cycle_length(zone, rules)
    for _ in range(clicks):
        dealt += spot.swing(power, rules, rng, 0.0, spot.expected(rules, cycle), cycle).damage
    pay_per_hp = rules.bits_per_hp * f.zone_reward_factor(zone, rules) + per_roll * f.expected_rolls(1, rules, zone)
    return pay_per_hp * dealt / clicks


def fishing_per_cast() -> tuple[float, float]:
    rng = Random(2)
    n = 20000
    worth = sum(fi.roll_fish(rng, REG).sell_price for _ in range(n)) / n
    rules = REG.fishing
    power = REG.item("starter_rod").tool.power
    seconds = sum(fi.wait_seconds(power, rules, rng) for _ in range(2000)) / 2000 + 1.5 * (rules.reel.base_length + 2)
    return worth, seconds


def farming_table() -> list[tuple[str, int, float, float, float]]:
    rules = REG.farming
    per_cycle = 1 - (1 - rules.grow_chance) * (1 - rules.water_chance)  # rain + one watering an hour
    rows = []
    for item in REG.items.values():
        if not item.seed:
            continue
        crop = REG.item(item.seed.grows_into)
        harvest = (crop.crop.min_harvest + crop.crop.max_harvest) / 2
        value = harvest * crop.sell_price
        hours_watered = item.seed.cycles / per_cycle
        hours_rain = item.seed.cycles / rules.grow_chance
        rows.append((item.id, item.seed.cycles, value, value / hours_watered, value / hours_rain))
    return sorted(rows, key=lambda r: r[1])


def pet_xp_per_hour() -> dict[str, float]:
    """Base pet xp (before the x3 / x2) an hour of each skill's food drops, at starter gear and the clicks per minute above."""
    from cococap.registry.models import Item

    xp = lambda item: REG.economy.pets.food_xp[item.pet_food.tier - 1]
    foods = lambda skill: [i for i in REG.items.values() if isinstance(i, Item) and i.category == "pet_food" and i.skill == skill]
    per_roll = lambda skill: sum(xp(i) / i.drop.rate for i in foods(skill))
    clicks_hour = 3600 / CLICK_SECONDS
    # rolls per hour: foraging = hp chopped / hp_per_roll (zone 1); mining = lodes (about 8 per 40 clicks... one lode per click, roughly); fishing = catches
    forage_rolls = clicks_hour * foraging_dmg_per_click() / REG.foraging.hp_per_roll
    _, seconds = fishing_per_cast()
    return {"foraging": per_roll("foraging") * forage_rolls, "mining": per_roll("mining") * clicks_hour * 0.9,
            "fishing": per_roll("fishing") * 3600 / seconds}


def foraging_dmg_per_click(zone: int = 1) -> float:
    rules = REG.foraging
    rng, dealt, clicks = Random(2), 0, 4000
    spot = f.Spot.pick(rules, rng)
    cycle = f.cycle_length(zone, rules)
    power = REG.item("starter_axe").tool.power
    for _ in range(clicks):
        dealt += spot.swing(power, rules, rng, 0.0, spot.expected(rules, cycle), cycle).damage
    return dealt / clicks


def main() -> None:
    mine = mining_per_click()
    print(f"Click every {CLICK_SECONDS:.0f}s -> {60 / CLICK_SECONDS:.0f} clicks per active minute\n")
    print(f"{'mining':10} {mine:>10,.0f} bits/click   {mine * 60 / CLICK_SECONDS:>12,.0f} bits/active minute")
    for zone in (1, 4, 7, 10):
        per = foraging_per_click(zone)
        print(f"{'foraging z' + str(zone):10} {per:>10,.0f} bits/click   {per * 60 / CLICK_SECONDS:>12,.0f} bits/active minute")
    worth, seconds = fishing_per_cast()
    print(f"{'fishing':10} {worth:>10,.0f} bits/catch   {worth * 60 / seconds:>12,.0f} bits/active minute ({seconds:.0f}s a catch)")
    print("\nPet food (base pet xp an hour of play; x3 for a pet of that skill):")
    for skill, value in pet_xp_per_hour().items():
        print(f"  {skill:10} {value:>8,.0f} xp/hour")
    print("\nFarming (per plot, watered once an hour / rain only):")
    for seed, cycles, value, watered, rain in farming_table():
        print(f"  {seed:22} {cycles:>4} cycles  {value:>14,.0f} bits a harvest  {watered:>12,.0f}/h watered  {rain:>12,.0f}/h rain")


if __name__ == "__main__":
    main()
