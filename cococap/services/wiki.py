"""The in-game wiki. Every page is written from the game's own data (the registry), so it can never go out of date: change a
price, a pet's bonus or a water's fish in ``configs/`` and the wiki changes with it. No Discord here: a page is a list of
text blocks."""

from cococap.constants import Rarities
from cococap.registry import Item, Registry, get_registry

TOPICS: list[tuple[str, str, str]] = [  # (id, title, emoji)
    ("start", "Getting started", "🥥"),
    ("mining", "Mining", "⛏️"),
    ("farming", "Farming", "🌽"),
    ("foraging", "Foraging", "🌳"),
    ("fishing", "Fishing", "🎣"),
    ("fish", "Fish", "🐟"),
    ("waters", "Waters", "🌊"),
    ("pots", "Crab pots and bait", "🦀"),
    ("tools", "Tools and upgrades", "🔨"),
    ("enchants", "Enchants and scrolls", "📜"),
    ("pets", "Pets", "🐾"),
    ("party", "Parties", "👥"),
    ("items", "Item lookup", "🎒"),
]


def _n(value: int) -> str:
    return f"{value:,}"


def _rarity(item: Item) -> str:
    return Rarities.from_value(item.rarity).rarity_name


def _materials(items: dict[str, int], reg: Registry) -> str:
    return ", ".join(f"{q:,} {reg.item(i).name}" for i, q in items.items())


def page(topic: str, registry: Registry | None = None) -> list[str]:
    reg = registry or get_registry()
    builder = _PAGES.get(topic)
    if builder is None:
        raise KeyError(topic)
    return builder(reg)


# ---- the pages -----------------------------------------------------------------------------------------------------------
def _start(reg: Registry) -> list[str]:
    e = reg.economy
    return [
        "**Two currencies.** **Bits** are power: skills, Work, selling and drops pay them, and they buy tools, seeds, land and "
        f"upgrades. **Luckbucks** are for fun: minigames, the weekly bonus and the casino pay them (you start with {e.starting_luckbucks}). "
        f"Bits turn into luckbucks one way at {_n(e.exchange.bits_per_luckbuck)} bits each.",
        "**Where to start.** Check in (Work, Daily, Weekly) for bits, buy a starter tool in the Shop (a Rookie Pickaxe, Starter Axe or "
        "Starter Rod, 2,000 bits: your first tool equips itself) and pick a skill. You own **one tool of each kind**; make it better "
        "with upgrades. Skills level with use, and levels open new things.",
        "**More ways to play.** Join a **party** for bonus xp in every skill, hatch **pets** with Familiar Orbs, and play the minigames "
        "and casino for luckbucks. Use **Home** and **Back** to move around; wins and losses get a page of their own.",
    ]


def _mining(reg: Registry) -> list[str]:
    m = reg.mining
    return [
        f"**Mining** needs a pickaxe. You dig down a **{m.columns}-column mine, {m.descent.floor} rows deep**. Each row you dig makes the mine creak "
        "more (pressure), and the deeper you are the likelier a collapse. A collapse halves what you are carrying, so leave in time.",
        "**Reading the mine.** Signs tell you what lies below: ore, a rich lode, a cooling vent, a cache or a hole. Braces calm the pressure "
        f"(you start with {m.descent.braces_base}), Scarab Bombs blow a whole row, and the vault at the bottom pays big.",
        f"**Ores** (copper, iron, gold) sell or feed the **magnet** (level {m.magnet.level}, {_n(m.magnet.capacity)} to fill: your next mine "
        f"shows the best columns). **Gems** are rare; with mining level {m.reactor.gem_slot_level} you can set them in the **reactor**, which also "
        "mines lodes for you while you are away.",
    ]


def _farming(reg: Registry) -> list[str]:
    f = reg.farming
    crops = sorted((i for i in reg.items.values() if i.crop), key=lambda i: i.sell_price)
    lines = [f"{c.display}: sells {_n(c.sell_price)}, {reg.item(c.crop.seed).seed.cycles} rains to grow, feeds a pet {_n(c.crop.pet_xp)}" for c in crops]
    return [
        f"**Farming** has no tool, only seeds. You start with {f.free_plots} plot; up to 9 with **land deeds**. Each hour it **rains** and every "
        f"growing plot has a {f.grow_chance:.0%} chance to grow a step (even while you are away). When it is ripe, harvest it.",
        f"**Extras.** A rain in which something grew may bring a rain god's blessing. A harvest has a 1 in {f.anomaly_odds} chance of an "
        f"anomaly that refreshes your Work and Daily. The **Farmer's Market** (farming level {f.market.min_level}, Fri and Sat) pays "
        f"+{f.market.price_bonus:.0%} for crops.",
        "**Crops**\n" + "\n".join(lines),
    ]


def _foraging(reg: Registry) -> list[str]:
    f = reg.foraging
    c = f.community
    return [
        f"**Foraging** needs an axe. Chop a tree down for bits, drops and xp. There are **{f.zones} zones** (a new one every {f.levels_per_zone} levels); "
        f"from zone {f.heavy_zone} alone, trees are heavy and you swing at half power unless your axe has **Soloist**.",
        "**Learn the grain.** Every spot has a grain (Plain, Knotty, Clean, Twisted, Split or Burl), and every grain has its own secret **pattern** "
        "of the three stances (⬆️ Overhead, ↔️ Sidecut, ⬇️ Undercut). For each step pick a stance: a wrong one puts an ❌ and you move on to the next. "
        "Your **Grain notes** (a button on the foraging pages) remember the right stances and cross off the wrong ones, so you piece each grain "
        "together. Get every step of a spot right and you earn a little extra xp.",
        "**Remember it.** A new spot shows ❔ for every step again, so you have to remember what you learned. When a spot's pattern is done you "
        "move to a new one by yourself. Deeper trees make you do more steps. A good chop hits extra hard.",
        f"**Re-leaf** (level {f.releaf.min_level}): after felling a tree you can **donate its drops** ({f.releaf.daily_limit} a day). The rarest item "
        f"fills the meter by its rarity x{f.releaf.meter_per_rarity}; at **{f.releaf.meter_goal}** your next tree is a **double tree** with double the hp "
        f"and a jackpot: {f.releaf.double_bits:,} bits, or a 1 in {round(1 / f.releaf.double_spirit_chance)} chance of a Spirit of the Forest.",
        f"**The community tree.** One grows every hour and stands for {c.open_minutes} minutes. Everyone's chops add up; "
        f"chop at least {c.min_share:.0%} of it to be paid, and a bigger crowd earns a bonus. Rewards arrive in your own panel, even if you were offline.",
    ]


def _fishing(reg: Registry) -> list[str]:
    r = reg.fishing
    return [
        "**Fishing** needs a rod. **Cast** and wait for a bite, then you have a few seconds to **pull up the line** (a little forgiveness is built in). "
        "Then you **reel**: press the arrows shown, in order. A few steps turn into **Reel** as you reach them, and the toughest fish hide arrows "
        "behind a **❓** that follows that fish's own secret pattern: your **field notes** (Records page) record what each ❓ turned out to be.",
        f"**Quests** (level {r.quests.min_level}): daily and weekly catches of specific fish. **Collection books** (level {r.book.min_level}): turn fish in "
        "for rewards and level the book up. The **community book** and **monthly goals** are shared by the whole server.",
        f"**Extras.** About 1 in {r.treasure.hallucination_odds} catches brings a **hallucination**: remember the four numbers, because a **treasure chest** "
        f"may turn up next. About 1 cast in {r.boss.odds} is a **boss** with its own twist and a pile of loot. Every catch has a size, with personal and server records.",
    ]


def _fish(reg: Registry) -> list[str]:
    waters = {}
    for w in reg.fishing.waters:
        for fish_id in w.fish:
            waters.setdefault(fish_id, []).append(w.name)
    out = []
    for rarity in range(7, 0, -1):
        fish = [i for i in reg.items.values() if i.category == "fish" and i.rarity == rarity]
        if not fish:
            continue
        lines = [f"{i.display}: {_n(i.sell_price)} bits, {i.size.min:g}-{i.size.max:g} cm, " + ", ".join(waters.get(i.id, ["?"])) for i in sorted(fish, key=lambda x: -x.sell_price)]
        out.append(f"**{Rarities.from_value(rarity).rarity_name}**\n" + "\n".join(lines))
    return out


def _waters(reg: Registry) -> list[str]:
    out = []
    for w in reg.fishing.waters:
        odds = ", ".join(f"{reg.item(i).name} 1/{n:,}" for i, n in sorted(w.fish.items(), key=lambda kv: -kv[1]))
        out.append(f"**{w.emoji} {w.name}** (level {w.min_level}, waits ×{w.wait_multiplier:g})\n{w.description}\n-# {odds}")
    return out


def _pots(reg: Registry) -> list[str]:
    p = reg.fishing.pots
    baits = sorted((i for i in reg.items.values() if i.bait), key=lambda i: (i.price == 0, i.price))
    levels = "\n".join(
        f"Level {n}: a catch every {lv.interval_minutes:g} min, holds {lv.capacity}"
        + (f"  ·  {_n(lv.upgrade_bits)} bits, {_materials(lv.upgrade_items, reg)}" if n > 1 else "")
        for n, lv in enumerate(p.levels, start=1))
    return [
        f"**Crab pots** (fishing level {p.min_level}; you may own one at level {p.slot_levels[0]}, more at {', '.join(map(str, p.slot_levels[1:]))}). "
        f"Craft one for {_n(p.craft_bits)} bits and {_materials(p.craft_items, reg)}, put it in a water, load **bait**, and it catches "
        f"**{Rarities.from_value(p.min_rarity).rarity_name} fish and better** while you are away, using one bait per catch. Collect them later.",
        "**Pot levels**\n" + levels,
        "**Bait**\n" + "\n".join(f"{b.display}: " + (f"{_n(b.price)} bits" if b.price else "found only") + f", {b.bait.luck:g}x rare fish, {b.bait.speed:g}x speed" for b in baits)
        + "\n-# A pot is a side dish: it earns a fraction of fishing yourself. The Python and Crab pets buff it.",
    ]


def _tools(reg: Registry) -> list[str]:
    out = ["**One tool of each kind.** The shop sells only the starter tool, and you can't buy a second. Everything better comes from "
           "**Inventory → Upgrade tools**: your tool keeps its enchants and becomes the next one up for bits and materials. The first steps "
           "use only the tool's own skill; later ones add a little from others."]
    kinds: dict[str, list[Item]] = {}
    for item in reg.items.values():
        if item.tool:
            kinds.setdefault(item.tool.kind, []).append(item)
    for kind, tools in sorted(kinds.items()):
        current = next(t for t in tools if not any(o.tool.upgrade and o.tool.upgrade.to == t.id for o in tools))
        lines = []
        while current.tool.upgrade:
            up = current.tool.upgrade
            nxt = reg.item(up.to)
            lines.append(f"{current.name} → **{nxt.name}** (power {nxt.tool.power}): {_n(up.bits)} bits, {_materials(up.items, reg)}")
            current = nxt
        out.append(f"**{kind.title()}s**\n" + "\n".join(lines))
    return out


def _enchants(reg: Registry) -> list[str]:
    lines = []
    for e in reg.enchants.values():
        scroll = next((i for i in reg.items.values() if i.scroll and i.scroll.enchant == e.id), None)
        lines.append(f"**{e.name}** (max {e.max_level}, {'/'.join(e.applies_to)}): {e.description}"
                     + (f"  ·  {scroll.display}" if scroll else ""))
    return ["**Enchants** are put on a tool with a one-use **scroll** (Inventory → Enchant). Scrolls turn up in play: chopping, deep mining, "
            "treasure chests and boss loot.", "\n".join(lines)]


def _pets(reg: Registry) -> list[str]:
    rules = reg.economy.pets
    from cococap.services import pets as pet_service

    odds = pet_service.orb_odds(reg)
    lines = []
    for pet in sorted(reg.pets.values(), key=lambda p: (p.rarity, p.name)):
        bonus = ", ".join(b.text.format(v=b.value) for b in pet.bonuses)
        lines.append(f"{pet.emoji} **{pet.name}** ({Rarities.from_value(pet.rarity).rarity_name}, {odds[pet.id]:.1%} per orb): {bonus}")
    return [
        f"**Pets** hatch from **Familiar Orbs** (shop, treasure chests, boss loot). Your active pet's bonuses work everywhere. A duplicate adds a star "
        f"(up to {rules.max_stars}, +{rules.star_bonus:.0%} each), crops level them (to {rules.max_level}) and a Spirit adds skill xp. **Hunt** a pet in the "
        f"Pet House and orbs favour it (×{rules.target_boost:g}, more with each miss).",
        "**All pets** (bonuses at max level, one star)\n" + "\n".join(lines),
    ]


def _party(reg: Registry) -> list[str]:
    steps = reg.economy.party_xp_bonus_by_size
    sizes = ", ".join(f"{n} members **+{b:.0%}**" for n, b in enumerate(steps, start=2)) + "+"
    return [
        f"**Parties** are groups that play together. A party's members get bonus xp in every skill, growing with its size: {sizes}. "
        "Start one from the Party page, invite players (or right-click a member), and leave any time.",
        "**Party trees** let a party chop a tree together for a little better rewards than going alone.",
    ]


def _items(reg: Registry) -> list[str]:
    return ["Pick a skill, then an item, to see its details."]


_PAGES = {"start": _start, "mining": _mining, "farming": _farming, "foraging": _foraging, "fishing": _fishing, "fish": _fish,
          "waters": _waters, "pots": _pots, "tools": _tools, "enchants": _enchants, "pets": _pets, "party": _party, "items": _items}

SKILL_FILTERS = ["mining", "farming", "foraging", "fishing", "combat", "general"]


def items_for(skill: str, registry: Registry | None = None) -> list[Item]:
    """Every item of a skill ("general" = not tied to a skill), by rarity then name."""
    reg = registry or get_registry()
    pool = [i for i in reg.items.values() if (i.skill or "general") == skill]
    return sorted(pool, key=lambda i: (i.rarity, i.name))
