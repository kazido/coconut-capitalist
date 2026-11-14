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


def tool_chain(kind: str) -> list:
    tools = [i for i in REG.items.values() if i.tool and i.tool.kind == kind]
    current = next(t for t in tools if not any(o.tool.upgrade and o.tool.upgrade.to == t.id for o in tools))
    chain = [current]
    while current.tool.upgrade:
        current = REG.item(current.tool.upgrade.to)
        chain.append(current)
    return chain


def rod_per_minute(power: int) -> float:
    """Bits a minute of fishing in the reef at this rod power: bites, rarer fish and extra fish all counted."""
    rules = REG.fishing
    water = next(w for w in rules.waters if w.id == "reef")
    rng, n, worth, seconds = Random(3), 6000, 0.0, 0.0
    for _ in range(n):
        fish = fi.roll_fish(rng, REG, water, fi.rod_luck(power, rules))
        worth += fish.sell_price * (1 + rules.rod.extra_fish_per_power * max(0, power - 3))
        seconds += fi.wait_seconds(power, rules, rng) * water.wait_multiplier + 1.5 * (rules.reel.base_length + 1 + fish.rarity)
    return worth / seconds * 60


def tool_table() -> None:
    """Income of every tool level relative to the starter (target: x1, 1.5, 2.6, 4, 6, 9, 13, 18)."""
    yield_bonus = REG.mining.descent.power_yield_bonus if hasattr(REG.mining.descent, "power_yield_bonus") else 0.25
    rows = {"axe": lambda p: p / REG.item("starter_axe").tool.power,
            "pickaxe": lambda p: (1 + yield_bonus * max(0, p - 1)),
            "rod": lambda p: rod_per_minute(p) / rod_per_minute(REG.item("starter_rod").tool.power)}
    print("\nTool levels (income relative to the starter tool):")
    for kind, gain in rows.items():
        chain = tool_chain(kind)
        print(f"  {kind:8}" + "  ".join(f"L{n}:x{gain(t.tool.power):.1f}" for n, t in enumerate(chain, start=1)))
        print(f"  {'':8}" + "  ".join(f"{(t.tool.upgrade.bits if t.tool.upgrade else 0) / 1e6:>6,.1f}M" for t in chain) + "   (bits to upgrade)")


def level_xp(level: int) -> int:
    """Total xp to reach `level` (the curve in User.level_to_xp)."""
    from cococap.user import User

    return User.level_to_xp(level)


def mining_xp_per_click() -> float:
    runs, lodes, clicks = 400, 0, 0
    for seed in range(runs):
        run = m.MineRun(REG.mining, REG, Random(seed), cursors=[2], braces=1)
        while not run.finished:
            if run.risk >= 0.07:
                run.leave()
                break
            if run.signs(run.depth)[run.cursors[0]] == "hole":
                run.move(1)
            run.dig()
            clicks += 1
        lodes += run.lodes
    return REG.mining.xp_per_column * lodes / clicks


def foraging_xp_per_click(power: int) -> float:
    rules = REG.foraging
    rng, effort, clicks = Random(2), 0.0, 4000
    spot = f.Spot.pick(rules, rng)
    cycle = f.cycle_length(1, rules)
    for _ in range(clicks):
        effort += spot.swing(power, rules, rng, 0.0, spot.expected(rules, cycle), cycle).effort
    return effort / clicks * rules.xp_per_swing


def fishing_xp_per_minute(power: int) -> float:
    """Every fish landed pays its water's xp (never the fish's rarity, never the rod), so only the bites' speed changes it."""
    rules = REG.fishing
    water = next(w for w in rules.waters if w.id == "reef")
    rng, n, seconds = Random(3), 6000, 0.0
    for _ in range(n):
        fish = fi.roll_fish(rng, REG, water, fi.rod_luck(power, rules))
        seconds += fi.wait_seconds(power, rules, rng) * water.wait_multiplier + 1.5 * (rules.reel.base_length + 1 + fish.rarity)
    return water.xp * n / seconds * 60


def combat_xp_per_hour(encounter_id: str, level: int, power: int, kit: str) -> tuple[float, float]:
    """(xp per hour, win rate) farming one encounter with a plain 'best ready skill' player, one click per CLICK_SECONDS."""
    from cococap.services import combat as c

    rules = REG.combat
    p = rules.player
    wins, clicks, xp = 0, 0, 0
    for seed in range(200):
        me = c.Unit(id="p1", name="Hero", side="player", max_hp=p.base_hp + p.hp_per_level * level,
                    attack=p.base_attack + p.attack_per_power * power + p.attack_per_level * level,
                    defense=p.base_defense + p.defense_per_level * level, speed=p.speed, skills=list(rules.kits[kit]))
        b = c.new_battle(me, encounter_id, rng=Random(seed))
        while not b.outcome:
            ready = [x for x in me.skills if me.ready(x) and x != "brace"]
            b.play(ready[-1], min(b.living("enemy"), key=lambda u: u.hp).id)
            clicks += 1
        wins += b.outcome == "win"
        xp += b.xp_earned
    seconds = clicks / 200 * CLICK_SECONDS
    return xp / 200 / seconds * 3600, wins / 200


def xp_report() -> None:
    per_hour = 3600 / CLICK_SECONDS
    print("\nXP an hour of active play (a click every %ds) against the level curve:" % CLICK_SECONDS)
    axe, rod = tool_chain("axe"), tool_chain("rod")
    rows = {
        "mining": mining_xp_per_click() * per_hour,
        "foraging L1 axe": foraging_xp_per_click(axe[0].tool.power) * per_hour,
        "foraging L8 axe": foraging_xp_per_click(axe[-1].tool.power) * per_hour,
        "fishing L1 rod": fishing_xp_per_minute(rod[0].tool.power) * 60,
        "fishing L8 rod": fishing_xp_per_minute(rod[-1].tool.power) * 60,
    }
    for label, enc, lv, pw, kit in (("combat lv1 lone zombie", "graveyard_lone", 1, 1, "largebranch"),
                                    ("combat lv8 horde", "graveyard_horde", 8, 20, "dreamnail")):
        rows[label], win = combat_xp_per_hour(enc, lv, pw, kit)
    print(f"  {'':24}{'xp/hour':>10}  " + "".join(f"{'to L' + str(lv):>9}" for lv in (20, 50, 90)) + "   (hours of play from level 1)")
    for label, xp in rows.items():
        print(f"  {label:24}{xp:>10,.0f}  " + "".join(f"{level_xp(lv) / xp:>8,.0f}h" for lv in (20, 50, 90)))
    print("  level costs: " + ", ".join(f"L{lv} = {level_xp(lv):,} total ({level_xp(lv + 1) - level_xp(lv):,} for the next level)" for lv in (10, 20, 50, 90)))
    per_cycle = 1 - (1 - REG.farming.grow_chance) * (1 - REG.farming.water_chance)
    print(f"  farming: {REG.farming.xp_per_cycle} xp per growth cycle = {REG.farming.xp_per_cycle * per_cycle:,.0f} xp/hour per watered plot, x9 plots = {9 * REG.farming.xp_per_cycle * per_cycle:,.0f}")


def progress_report() -> None:
    """Coconut Level: what finishing everything is worth, per category."""
    from cococap.services import progress as pr

    probe = pr.build(pr.Snapshot(skills={n: __import__("cococap.user", fromlist=["SKILL_MODELS"]).SKILL_MODELS[n]() for n in pr.SKILLS},
                                 rank=0, pethouse=__import__("cococap.models.pethouse", fromlist=["Pethouse"]).Pethouse(), owned_templates=set()), REG)
    per = REG.progress.points_per_level
    print(f"\nCoconut Level ({per} points a level; every source is a one-time milestone):")
    for c in probe.categories:
        print(f"  {c.name:16}{c.max_points:>7,} points  = {c.max_points / per:>5.1f} levels")
    print(f"  {'everything':16}{probe.max_points:>7,} points  = level {probe.max_points // per}")


def main() -> None:
    mine = mining_per_click()
    print(f"Click every {CLICK_SECONDS:.0f}s -> {60 / CLICK_SECONDS:.0f} clicks per active minute\n")
    print(f"{'mining':10} {mine:>10,.0f} bits/click   {mine * 60 / CLICK_SECONDS:>12,.0f} bits/active minute")
    for zone in (1, 4, 7, 10):
        per = foraging_per_click(zone)
        print(f"{'foraging z' + str(zone):10} {per:>10,.0f} bits/click   {per * 60 / CLICK_SECONDS:>12,.0f} bits/active minute")
    worth, seconds = fishing_per_cast()
    print(f"{'fishing':10} {worth:>10,.0f} bits/catch   {worth * 60 / seconds:>12,.0f} bits/active minute ({seconds:.0f}s a catch)")
    tool_table()
    xp_report()
    progress_report()
    print("\nPet food (base pet xp an hour of play; x3 for a pet of that skill):")
    for skill, value in pet_xp_per_hour().items():
        print(f"  {skill:10} {value:>8,.0f} xp/hour")
    print("\nFarming (per plot, watered once an hour / rain only):")
    for seed, cycles, value, watered, rain in farming_table():
        print(f"  {seed:22} {cycles:>4} cycles  {value:>14,.0f} bits a harvest  {watered:>12,.0f}/h watered  {rain:>12,.0f}/h rain")


if __name__ == "__main__":
    main()
