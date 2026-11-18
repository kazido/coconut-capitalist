"""What a tool's power DOES, in numbers, for each kind of tool: one main effect, and several smaller ones that come with it, so every upgrade
changes a few things at once (like the rod always did). `power_stats` is the single source: the game reads the same numbers the upgrade
page shows, so the page can never disagree with what really happens. Pure; the rules are in `configs/tools.toml` and the main effect of each
kind is in that skill's own rules."""

from dataclasses import dataclass

from cococap import emojis
from cococap.registry import Registry, get_registry

BASE_POWER = 3  # every tool starts here; the extras count only the points above it

# one line on what power means for each kind (shown on the upgrade page)
HOW = {
    "pickaxe": f"{emojis.icon('pickaxe', '⛏️')} Power = more ore per lode, slower pressure, more rich lodes and a spare brace now and then.",
    "axe": f"{emojis.icon('axe', '🪓')} Power = a bigger bite out of a tree, more good chops, and spots that last longer.",
    "rod": f"{emojis.icon('rod', '🎣')} Power = faster bites, more forgiven arrows, and rarer and extra fish.",
    "can": f"{emojis.icon('can', '🚿')} Power = more plots watered an hour, bigger harvests, more drops, and seeds that come back.",
    "sword": f"{emojis.icon('sword', '⚔️')} Power = a harder hit, and a tougher you: more hp and defense in a fight.",
}


@dataclass(frozen=True)
class Effect:
    label: str
    value: str


def power_stats(kind: str, power: int, registry: Registry | None = None, path: str | None = None) -> dict[str, float]:
    """The extra stats a tool of this kind and power carries (merged into its stats, so Mastery, enchants and the games see them as usual).
    A forked tool's `path` leans them (the pickaxe's Warden keeps the safety, the Prospector the rich lodes)."""
    reg = registry or get_registry()
    above = max(0, power - BASE_POWER)
    r = reg.tools
    if kind == "pickaxe":
        w = r.pickaxe.paths.get(path or "")
        wd, wr, wb = (w.danger_reduction, w.rich_chance, w.braces) if w else (1.0, 1.0, 1.0)
        return {"danger_reduction": r.pickaxe.danger_reduction * above * wd, "rich_chance": r.pickaxe.rich_chance * above * wr,
                "braces": float(int(above * wb) // r.pickaxe.braces_every)}
    if kind == "axe":
        w = r.axe.paths.get(path or "", {})
        return {"good_chop": r.axe.good_chop * above * w.get("good_chop", 1.0), "wear_slow": r.axe.wear_slow * above * w.get("wear_slow", 1.0)}
    if kind == "can":
        w = r.can.paths.get(path or "", {})
        return {"crop_yield": r.can.crop_yield * above * w.get("crop_yield", 1.0), "drop_luck": r.can.drop_luck * above * w.get("drop_luck", 1.0),
                "seed_back": min(1.0, r.can.seed_back * above * w.get("seed_back", 1.0))}
    return {}


def sword_stats(power: int, registry: Registry | None = None) -> tuple[int, float]:
    """(extra max hp, extra defense) a sword of this power gives in a fight."""
    reg = registry or get_registry()
    above = max(0, power - BASE_POWER)
    return round(reg.tools.sword.hp * above), reg.tools.sword.defense * above


def effects(kind: str, power: int, registry: Registry | None = None, path: str | None = None, stats: dict[str, float] | None = None) -> list[Effect]:
    """The numbers a tool of this kind and power gives (on `path`, if it has forked; `stats` are the tool's own, like a road's extra ore)."""
    from cococap.services import fishing

    reg = registry or get_registry()
    extra = power_stats(kind, power, reg, path)
    if kind == "pickaxe":
        d = reg.mining.descent
        ore = (1 + d.power_yield_bonus * max(0, power - d.power_base)) * (1 + (stats or {}).get("ore_yield", 0.0))
        return [Effect("Ore per lode", f"×{ore:.2f}"),
                Effect("Pressure builds", f"{extra['danger_reduction']:.0%} slower"),
                Effect("Rich lode chance", f"+{extra['rich_chance']:.1%}"),
                Effect("Extra braces", f"+{int(extra['braces'])}")]
    if kind == "axe":
        return [Effect("Hit points per chop", f"{power}"),
                Effect("Good chop chance", f"+{extra['good_chop']:.1%}"),
                Effect("Spot wear", f"{extra['wear_slow']:.0%} slower")]
    if kind == "can":
        return [Effect("Plots watered an hour", f"{power}"),
                Effect("Bigger harvests", f"+{extra['crop_yield']:.0%}"),
                Effect("More drops", f"+{extra['drop_luck']:.0%}"),
                Effect("Seed comes back", f"{extra['seed_back']:.0%}")]
    if kind == "sword":
        hp, defense = sword_stats(power, reg)
        return [Effect("Attack from the sword", f"+{reg.combat.player.attack_per_power * power}"),
                Effect("Extra max hp", f"+{hp}"),
                Effect("Extra defense", f"+{defense:.1f}")]
    if kind == "rod":
        rules = reg.fishing
        more = rules.rod.extra_fish_per_power * max(0, power - 3)
        return [Effect("Wait for a bite", f"~{fishing.typical_wait(power, rules):.0f}s"),
                Effect("Forgiven wrong arrows", f"{fishing.slips_allowed(power, rules)}"),
                Effect("Rare fish", f"+{fishing.rod_luck(power, rules):.0%} likelier"),
                Effect("Extra fish per catch", f"+{more:.1f}")]
    return []


def compare(kind: str, now: int, after: int, registry: Registry | None = None, now_path: str | None = None, after_path: str | None = None,
            now_stats: dict[str, float] | None = None, after_stats: dict[str, float] | None = None) -> list[str]:
    """"Ore per lode: ×1.50 → **×2.50**" for each effect (all of them are shown, so nothing is hidden). A road can change the extras."""
    return [f"{a.label}: {a.value} → **{b.value}**"
            for a, b in zip(effects(kind, now, registry, now_path, now_stats), effects(kind, after, registry, after_path, after_stats), strict=True)]


def summary(kind: str, power: int, registry: Registry | None = None, path: str | None = None, stats: dict[str, float] | None = None) -> str:
    """One line of a tool's current numbers, for the Tools page."""
    return "  ·  ".join(f"{e.label} {e.value}" for e in effects(kind, power, registry, path, stats))
