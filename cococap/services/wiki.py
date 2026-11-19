"""The in-game wiki. Every page is written from the game's own data (the registry), so it can never go out of date: change a
price, a pet's bonus or a water's fish in ``configs/`` and the wiki changes with it. No Discord here: a page is a list of
text blocks."""

from cococap import emojis
from cococap.constants import Rarities
from cococap.registry import Item, Registry, get_registry
from cococap.services import fishing

TOPICS: list[tuple[str, str, str]] = [  # (id, title, emoji)
    ("start", "Getting started", "🥥"),
    ("mining", "Mining", "⛏️"),
    ("farming", "Farming", "🌽"),
    ("foraging", "Foraging", "🌳"),
    ("fishing", "Fishing", "🎣"),
    ("fish", "Fish", "🐟"),
    ("waters", "Waters", "🌊"),
    ("pots", "Crab pots and bait", "🦀"),
    ("crafting", "Crafting: the Workbench", "🛠️"),
    ("tools", "Tools and upgrades", "🔨"),
    ("enchants", "Enchants and scrolls", "📜"),
    ("stars", "Starred materials", "⭐"),
    ("pets", "Pets", "🐾"),
    ("party", "Parties", "👥"),
    ("items", "Item lookup", "🎒"),
]


def _n(value: int) -> str:
    return f"{value:,}"


def _materials(items: dict[str, int], reg: Registry) -> str:
    return ", ".join(f"{q:,} {reg.item(i).name}" for i, q in items.items())


# A topic shown as several pages (the wiki screen pages through them with arrows). Each part is a `_PAGES` id.
GROUPS: dict[str, list[str]] = {"fish": ["fish", "fish2"], "waters": ["waters", "waters2"], "tools": ["tools", "tools2", "tools3"]}


def parts(topic: str) -> list[str]:
    """The `_PAGES` ids that make up a topic, in reading order."""
    return GROUPS.get(topic, [topic])


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
        "**Where to start.** Check in (Work, Daily, Weekly) for bits, use **/play**: you start with a free starter tool for every skill (a Rookie Pickaxe, Starter Axe, Starter Rod and Tin Watering "
        "Can, equipped for you; the Tools page hands out any you are missing) and pick a skill. You own **one tool of each kind**; make it better "
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
        f"(you start with {m.descent.braces_base}), Scarab Bombs blow {m.descent.bomb_layers} rows, and the vault at the bottom pays big.",
        f"**Ores** (copper, iron, gold) sell or feed the **magnet** (level {m.magnet.level}): its meter holds {_n(m.magnet.capacity)} points (an ore is worth "
        f"{', '.join(f'{v} for a {reg.item(k).name}' for k, v in m.magnet.values.items())}) and every row you dig with it on marks the richest column and burns {m.magnet.drain_per_row:g}. "
        "What is left stays for the next mine, and you can only feed it outside a mine. **Gems** are rare; with mining level {m.reactor.gem_slot_level} you can set them in the **reactor**, which also "
        "mines lodes for you while you are away.",
        "**Kinds of mine.** Every mine you enter is rolled: most are **Standard**, but now and then you get one with a twist, shown at the top of the mine before you dig. "
        + "; ".join(f"{t.emoji} **{t.name}** ({t.description.rstrip('.').lower()})" for t in m.mine_types[1:]) + ".",
        f"**Wyrmholes.** Now and then a lode in the shaft is replaced by a **wyrmhole** (you see them {m.descent.lookahead} rows ahead, only in row {m.wyrmhole.min_depth + 1} and down{'' if m.wyrmhole.max_depth is None else f' to row {m.wyrmhole.max_depth + 1}'}). "
        "Dig it and the mine ends (what you carry is banked) and you drop in. Most are **small**: "
        f"{m.mini_wyrmhole.columns} nodes wide and {len(m.mini_wyrmhole.rows)} rows deep, pick **one** node on each row, deeper rows pay better ore. About 1 in {round(1 / m.wyrmhole.big_chance)} is **big**, "
        "and its LAST row hides a gem: the implosion gem, or a reactor core gem you do not own yet. No hazards and no empty nodes in either, and you earn mining xp for every row.",
    ]


def _farming(reg: Registry) -> list[str]:
    f = reg.farming
    crops = sorted((i for i in reg.items.values() if i.crop), key=lambda i: i.sell_price)
    lines = [f"{c.display}: sells {_n(c.sell_price)}, {reg.item(c.crop.seed).seed.cycles} rains to grow, feeds a pet {_n(c.crop.pet_xp)}" for c in crops]
    return [
        f"**Farming** needs seeds and a **watering can**. You start with {f.free_plots} plot; up to 9 with **land deeds**. Each hour it **rains** and every "
        f"growing plot has a {f.grow_chance:.0%} chance to grow a step (even while you are away). When it is ripe, harvest it.",
        "**Watering.** Once an hour you can water your plots: each one you water always grows a step. Your can only reaches so many plots an "
        "hour (the Tin Watering Can: 3), so a bigger farm needs a better can (see Tools: the can goes up to the whole farm, and the better ones also "
        "give bigger harvests and more drops). A harvest also drops **materials** (Rich Compost, Morning Dewdrop, Beeswax, Living Vine, Golden Pollen, Plant Fiber): "
        "longer crops roll more often, and you spend them upgrading cans and a little in every other tool.",
        f"**Extras.** A rain in which something grew may bring a rain god's blessing. A harvest has a 1 in {f.anomaly_odds} chance of an "
        f"anomaly that refreshes your Work and Daily. The **Farmer's Market** (farming level {f.market.min_level}, open {f.market.open_hours}h at a time, daily from {', '.join(f'{h}:00' for h in sorted(f.market.opens))} UTC) pays "
        f"+{f.market.price_bonus:.0%} for crops.",
        "**Crops**\n" + "\n".join(lines),
    ]


def _species_text(reg: Registry) -> str:
    f = reg.foraging
    """The tree species, by forest band, with their signature drops (empty when the rules have none)."""
    if not any(sp.drops for sp in f.species):
        return ""
    return ("**Tree species.** A tree's species is set by its forest, and each species drops its own signature items (on top of the usual drops, and more often; odds are per drop roll): " + "; ".join(
        f"{sp.emoji} **{sp.name}** (forests {sp.zone_min}-{sp.zone_max}) " + " and ".join(f"{reg.item(d.item).name} 1 in {round(1 / d.rate)}" for d in sp.drops) for sp in f.species) + ".")


def _foraging(reg: Registry) -> list[str]:
    f = reg.foraging
    c = f.community
    return [
        f"**Foraging** needs an axe. Chop a tree down for drops (sell them for bits) and xp. There are **{f.zones} forests**: forest 2 needs level {reg.areas.location_levels[1]}, forest 10 level {reg.areas.location_levels[9]} and forest {f.zones} level {reg.areas.location_levels[f.zones - 1]}, and each opens at a higher level than the last (and needs you to have travelled to its area); "
        f"from forest {f.heavy_zone} alone, trees are heavy and you swing at half power unless your axe has **Soloist**.",
        "**Learn the grain.** Every spot has a grain (Plain, Knotty, Clean, Twisted, Split or Burl), and every grain likes **one chop style** "
        f"({emojis.icon('up', '⬆️')} Overhead, {emojis.icon('again', '↔️')} Sidecut or {emojis.icon('down', '⬇️')} Undercut). Chop in that style for full strength; any other glances off at half. "
        "Your **Grain notes** (a button on the foraging pages) remember the style you have found and cross off the ones that failed, so you learn each grain once. "
        "The spot never tells you its style, so you have to remember it.",
        "**Spots wear out.** Every chop wears the spot, and a worn spot chops weaker. Good grains (Clean, Burl) wear slowly and bad ones (Knotty, Twisted) "
        "go quickly; when a spot is gone you move to a new random grain by yourself. An axe with **Seasoned** makes spots last longer. "
        "Stuck on a bad grain? Use a **rotation wedge** (find it chopping or buy it in the shop) to move off at once: the Iron and Gilded wedges, made at the Workbench, lean toward the good grains. A good chop hits extra hard.",
        f"**Special spots** are rare and wear out fast, but chopped in the right style they pay off: {emojis.icon('gem', '💎')} **Heartwood** hits the tree several times harder, {emojis.icon('sparkle', '✨')} **Golden Knot** pays double xp, "
        f"and {emojis.icon('page', '🏷️')} **Rich Seam** marks a tree of your own for more drops when it falls. Better wedges make them likelier. An axe with **Double Strike** sometimes chops twice.",
        f"**Releaf Foundation** (level {f.releaf.min_level}, a button on the foraging page): the whole server gives foraging drops of any rarity (the item is gone for good) "
        f"to one shared meter, worth {', '.join(f'{p} for rarity {r}' for r, p in sorted(f.releaf.points.items()))}. When the meter is full (the goal is **{f.releaf.share_points}** points per active forager) a **Bloom** starts for {f.releaf.bloom_hours:g} hours: "
        f"**+{f.releaf.bloom_xp:.0%}** foraging xp and **+{f.releaf.bloom_drops:.0%}** drop chances for EVERYONE, whether they gave or not. Giving is closed during a Bloom, "
        f"and one person can give at most {f.releaf.share_cap:g} shares ({int(f.releaf.share_points * f.releaf.share_cap)} points) per round. There is no personal reward, only the thank-you list.",
        *([_species_text(reg)] if _species_text(reg) else []),
        f"**The community tree.** One grows every hour and stands for {c.open_minutes} minutes. Everyone's chops add up; "
        f"chop at least {c.min_share:.0%} of it to be paid, and a bigger crowd earns a bonus. Rewards arrive in your own panel, even if you were offline.",
    ]


def _fishing(reg: Registry) -> list[str]:
    r = reg.fishing
    return [
        "**Fishing** needs a rod. **Cast** and wait for a bite, then you have a few seconds to **pull up the line** (a little forgiveness is built in). "
        "Then you **reel**: press the arrows shown, in order. A few steps turn into **Reel** as you reach them, and the toughest fish hide arrows "
        f"behind a **{emojis.icon('unknown', '❓')}** that follows that fish's own secret pattern: your **field notes** (Records page) record what each {emojis.icon('unknown', '❓')} turned out to be.",
        f"**Quests** (level {r.quests.min_level}): daily and weekly catches of specific fish. **Collection books** (level {r.book.min_level}): turn fish in "
        "for rewards and level the book up. The **community book** and **monthly goals** are shared by the whole server.",
        f"**Extras.** About 1 in {r.treasure.hallucination_odds} catches brings a **hallucination**: remember the four numbers, because a **treasure chest** "
        f"may turn up next. About 1 cast in {r.boss.odds} is a **boss** with its own twist and a pile of loot. Every catch has a size, with personal and server records.",
        f"**Double Hook.** A rod with the **Double Hook** enchant (or the Angler's Double Hook Mastery node) sometimes has a second line already biting after you land a fish: "
        f"a **Quick cast** you can take for {r.double_hook.window_seconds:g} seconds from the result page. It is free, in the same water, and pays like any catch; ignoring it costs nothing "
        "(your Hot Streak is safe). Never after a boss or chest, and a Quick cast never offers another.",
    ]


def _one_in(chance: float) -> str:
    return "every cast" if chance >= 0.995 else f"1 in {round(1 / chance):,} casts"


def where_to_catch_text(fish: Item, reg: Registry) -> str:
    """Where to catch a fish: the best water first, with the real chance of it on a cast there."""
    places = fishing.where_to_catch(fish.id, reg)
    if not places:
        return "not found in any water yet"
    best, chance = places[0]
    text = f"Max odds in {best.emoji} {best.name} ({_one_in(chance)})"
    others = ", ".join(f"{w.name} ({_one_in(c)})" for w, c in places[1:3])  # (the best two others; a fish in many waters says "and N more")
    more = f" and {len(places) - 3} more" if len(places) > 3 else ""
    return text + (f"; also {others}{more}" if others else "") + f". Needs fishing level {min(fishing.water_level(reg, w.id) for w, _ in places)}."


def _fish(reg: Registry, top: int = 7, bottom: int = 1) -> list[str]:
    out = []  # two pages (rarest first) so each fits one Discord message
    for rarity in range(top, bottom - 1, -1):
        fish = [i for i in reg.items.values() if i.category == "fish" and i.rarity == rarity]
        if not fish:
            continue
        lines = [f"{i.display}: {_n(i.sell_price)} bits, {i.size.min:g}-{i.size.max:g} cm\n-# {where_to_catch_text(i, reg)}" for i in sorted(fish, key=lambda x: -x.sell_price)]
        out.append(f"**{Rarities.from_value(rarity).rarity_name}**\n" + "\n".join(lines))
    return out


def _waters(reg: Registry, start: int = 0, stop: int | None = None) -> list[str]:
    out = []
    for w in reg.fishing.waters[start:stop]:  # split over two pages, so each fits one Discord message
        odds = ", ".join(f"{reg.item(i).name} {_one_in(c).replace(' casts', '')}" for i, c in sorted(fishing.water_chances(w).items(), key=lambda kv: kv[1]))
        out.append(f"**{w.emoji} {w.name}** (level {fishing.water_level(reg, w.id)}, waits ×{w.wait_multiplier:g})\n{w.description}\n-# {odds}")
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


def _tools(reg: Registry, only: tuple[str, ...] = ("axe", "can"), intro: bool = True) -> list[str]:
    out = ["**One tool of each kind.** The shop sells no tools: you start with a free starter tool of each kind. Everything better comes from "
           f"**Inventory {emojis.icon('next', '→')} Tools {emojis.icon('next', '→')} Upgrade**: your tool keeps its enchants and becomes the next one up for bits and materials. The first steps "
           "use only the tool's own skill; later ones add a little from others. Each level earns clearly more than the last: about x1.5 at "
           "level 2, x2.6 at level 3, x4 at level 4 and x18 at level 8, and a better rod also brings rarer fish and more of them."] if intro else []
    kinds: dict[str, list[Item]] = {}
    for item in reg.items.values():
        if item.tool and item.tool.kind in only:
            kinds.setdefault(item.tool.kind, []).append(item)
    for kind, tools in sorted(kinds.items()):
        targets = {r.to for o in tools for r in (o.tool.upgrade, o.tool.fork) if r}
        current = next(t for t in tools if t.id not in targets)
        lines = []

        def walk(tool: Item, lines: list[str]) -> None:
            """List every step up from `tool`. At a fork both roads are listed, each tagged with its path's name."""
            while tool.tool.upgrade:
                forked = tool.tool.fork is not None
                for road in (tool.tool.upgrade, tool.tool.fork):
                    if road is not None:
                        nxt = reg.item(road.to)
                        tag = f" [{nxt.tool.path} path]" if forked and nxt.tool.path else ""
                        lines.append(f"{tool.name} {emojis.icon('next', '→')} **{nxt.name}** (power {nxt.tool.power}){tag}: {_n(road.bits)} bits, {_materials(road.items, reg)}")
                if forked:
                    walk(reg.item(tool.tool.fork.to), lines)
                tool = reg.item(tool.tool.upgrade.to)

        walk(current, lines)
        out.append(f"**{kind.title()}s**\n" + "\n".join(lines))
    return out


def _enchants(reg: Registry) -> list[str]:
    lines = []
    for e in reg.enchants.values():
        scroll = next((i for i in reg.items.values() if i.scroll and i.scroll.enchant == e.id), None)
        lines.append(f"{e.emoji} **{e.name}** (max {e.max_level}, {'/'.join(e.applies_to)}): {e.description}"
                     + (f"  ·  {scroll.display}" if scroll else ""))
    return [f"**Enchants** are put on a tool with a one-use **scroll** (Inventory {emojis.icon('next', '→')} Enchant). Scrolls turn up in play: chopping, deep mining, "
            "treasure chests and boss loot.", "\n".join(lines)]


def _pets(reg: Registry) -> list[str]:
    rules = reg.economy.pets
    from cococap.services import pets as pet_service

    odds = pet_service.orb_odds(reg)
    kinds = pet_service.orb_ids(reg)
    orb_lines = []
    for orb_id in kinds:
        orb = reg.item(orb_id)
        chances = pet_service.orb_odds(reg, orb=orb_id)
        by_rarity = {r: sum(c for pid, c in chances.items() if reg.pets[pid].rarity == r) for r in sorted(rules.xp_scale)}
        orb_lines.append(f"{orb.emoji} **{orb.name}** ({orb.price:,} bits): " + ", ".join(
            f"{Rarities.from_value(r).rarity_name} {c:.0%}" for r, c in by_rarity.items() if c > 0))
    lines = []
    for pet in sorted(reg.pets.values(), key=lambda p: (p.rarity, p.name)):
        bonus = ", ".join(b.text.format(v=b.value) for b in pet.bonuses)
        lines.append(f"{pet.emoji} **{pet.name}** {pet_service.skill_emoji(pet)} ({Rarities.from_value(pet.rarity).rarity_name}, {odds[pet.id]:.1%} per orb): {bonus}")
    return [
        f"**Pets** hatch from **Familiar Orbs** (shop, treasure chests, boss loot). Your active pet's bonuses work everywhere. A duplicate adds a star "
        f"(up to {rules.max_stars}, +{rules.star_bonus:.0%} each), your active pet also levels as you play (it gains {rules.play_xp_share:.0%} of the xp you earn in its own skill; a global pet {rules.play_xp_global:.0%} of any), food and crops level it faster (to {rules.max_level}), and a Spirit adds skill xp. **Hunt** a pet in the "
        f"Familiar Orbs page and orbs favour it (×{rules.target_boost:g}, more with each miss).",
        f"**Feeding.** Pets level up on **food**: crops (farming's food) and what each skill drops in three tiers (worth {', '.join(f'{x:,}' for x in rules.food_xp)} pet xp): "
        "foraging drops **Acorn Mix, Honeycomb and Golden Sap**, mining **Stone Biscuit, Crystal Chew and Geode Feast**, fishing **Fish Flakes, Dried Squid and Sea Feast**. "
        f"Every pet has **one skill**, shown as an emoji after its name: {emojis.icon('rod', '🎣')} fishing, {emojis.icon('pickaxe', '⛏️')} mining, {emojis.icon('tree', '🌳')} foraging, {emojis.icon('can', '🌽')} farming, {emojis.icon('sword', '⚔️')} combat, or {emojis.icon('world', '🌐')} **global** "
        f"for pets whose bonus works everywhere ({', '.join(p.name for p in sorted(reg.pets.values(), key=lambda p: (p.rarity, p.name)) if p.skill == 'global')}). "
        f"Food of **a pet's own skill is worth x{rules.matched_food_multiplier:g}** to it, a {emojis.icon('world', '🌐')} global pet gets **x{rules.global_food_multiplier:g}** from any food, "
        "and food of another skill is worth the plain amount. "
        "A pet's numbers are shown at its current level (a fresh pet gives a tenth) with the max level in brackets.",
        "**Orbs** come in three kinds, bought on the Familiar Orbs page. A cheaper orb mostly gives common pets, a pricier one mostly rare ones "
        "(chance of each rarity; the percentages beside each pet below are for the standard orb):\n" + "\n".join(orb_lines),
        "**Levels.** Common pets level up quickest and rare pets slowest: a level costs xp of "
        + ", ".join(f"{Rarities.from_value(r).rarity_name} x{s / rules.xp_scale[3]:.2g}" for r, s in sorted(rules.xp_scale.items())) + " (relative to a rarity-3 pet).",
        "**All pets** (bonuses at max level, one star)\n" + "\n".join(lines),
    ]


def _stars(reg: Registry) -> list[str]:
    from cococap import emojis
    from cococap.services import stars

    r = reg.economy.stars
    rows = []
    for label, at in (("first area", 0.0), ("a quarter down", 0.25), ("halfway", 0.5), ("three quarters down", 0.75), ("the deepest area", 1.0)):
        w = stars.weights(at, reg)
        rows.append(f"{label}: " + ", ".join(f"{emojis.stars(n) if n else 'plain'} {p:.0%}" for n, p in enumerate(w) if p >= 0.005))
    mult = ", ".join(f"{emojis.stars(n) if n else 'plain'} x{m:g}" for n, m in enumerate(r.sell_multipliers))
    names = ", ".join(reg.item(i).name for i in r.starrable)
    return [
        "**Starred materials** are special, higher quality versions of some materials. A normal drop has **no star**; stars (1 to 3) are the lucky ones. "
        f"A starred material works exactly like the plain one but is its own stack and sells for more ({mult} the plain price). Stars only drop: they cannot be crafted up.",
        f"**Which materials.** {names}.",
        "**Where they drop.** Mining, foraging, farming and fishing all roll a star for each material stack you get. The deeper the area you work in "
        "(the further down the list of mines, forests, waters and fields), the better the stars. Chances by depth:\n" + "\n".join(rows),
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


def _crafting(reg: Registry) -> list[str]:
    lines = []
    for r in reg.recipes.values():
        cost = _materials(r.inputs, reg) + (f" and {_n(r.bits)} bits" if r.bits else "")
        lines.append(f"{r.emoji or ''} **{r.name}**: {cost}" + (f" ({r.skill} level {r.min_level})" if r.min_level else ""))
    return [
        "**The Workbench** (Inventory, then Workbench) makes things from materials you gathered, instead of buying them. Pick a recipe, see what you have against "
        "what it needs, and craft one, ten or as many as you can. Everything is used up and the result given together: if anything is short, nothing is taken.",
        "**Recipes.**\n" + "\n".join(lines),
        "**Selling** is one item at a time: open the Shop, switch to Sell, pick an item, then sell 1x, 10x or a custom amount.",
    ]


_PAGES = {"start": _start, "mining": _mining, "farming": _farming, "foraging": _foraging, "fishing": _fishing, "fish": lambda reg: _fish(reg, 7, 4), "fish2": lambda reg: _fish(reg, 3, 1),
          "waters": lambda reg: _waters(reg, 0, 7), "waters2": lambda reg: _waters(reg, 7), "pots": _pots, "crafting": _crafting, "tools": _tools, "tools2": lambda reg: _tools(reg, ("rod",), intro=False), "tools3": lambda reg: _tools(reg, ("pickaxe", "sword"), intro=False), "enchants": _enchants, "pets": _pets, "stars": _stars, "party": _party, "items": _items}

SKILL_FILTERS = ["mining", "farming", "foraging", "fishing", "combat", "general"]


def items_for(skill: str, registry: Registry | None = None) -> list[Item]:
    """Every item of a skill ("general" = not tied to a skill), by rarity then name. Star variants are left out: they sit under their base item."""
    reg = registry or get_registry()
    pool = [i for i in reg.items.values() if (i.skill or "general") == skill and not i.star_of]
    return sorted(pool, key=lambda i: (i.rarity, i.name))
