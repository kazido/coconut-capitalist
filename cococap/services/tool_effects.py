"""What a tool's power actually DOES, in numbers, for each kind of tool. Pure: used by the upgrade and tools pages so a player can see what
an upgrade gives them ("Ore per lode ×1.5 → ×2.5"). The real mechanics live in mining / foraging / fishing / farming / combat; this only
reads their rules, so it can never disagree with the game."""

from dataclasses import dataclass

from cococap.registry import Registry, get_registry

# one line on what power means for each kind (shown on the upgrade page)
HOW = {
    "pickaxe": "⛏️ Power = more ore from every lode you dig.",
    "axe": "🪓 Power = how much of a tree one chop takes off.",
    "rod": "🎣 Power = faster bites, more forgiven arrows, and rarer and extra fish.",
    "can": "🚿 Power = how many plots you can water an hour.",
    "sword": "⚔️ Power = how hard you hit in a fight.",
}


@dataclass(frozen=True)
class Effect:
    label: str
    value: str


def effects(kind: str, power: int, registry: Registry | None = None) -> list[Effect]:
    """The numbers a tool of this kind and power gives."""
    from cococap.services import fishing

    reg = registry or get_registry()
    if kind == "pickaxe":
        d = reg.mining.descent
        return [Effect("Ore per lode", f"×{1 + d.power_yield_bonus * max(0, power - d.power_base):.2f}")]
    if kind == "axe":
        return [Effect("Hit points per chop", f"{power}")]
    if kind == "can":
        return [Effect("Plots watered an hour", f"{power}")]
    if kind == "sword":
        p = reg.combat.player
        return [Effect("Attack from the sword", f"+{p.attack_per_power * power}")]
    if kind == "rod":
        rules = reg.fishing
        extra = rules.rod.extra_fish_per_power * max(0, power - 3)
        return [Effect("Wait for a bite", f"~{fishing.typical_wait(power, rules):.0f}s"),
                Effect("Forgiven wrong arrows", f"{fishing.slips_allowed(power, rules)}"),
                Effect("Rare fish", f"+{fishing.rod_luck(power, rules):.0%} likelier"),
                Effect("Extra fish per catch", f"+{extra:.1f}")]
    return []


def compare(kind: str, now: int, after: int, registry: Registry | None = None) -> list[str]:
    """"Ore per lode ×1.50 → ×2.50" for each effect (only the ones that change are worth a line, but all are shown so nothing is hidden)."""
    return [f"{a.label}: {a.value} → **{b.value}**" for a, b in zip(effects(kind, now, registry), effects(kind, after, registry), strict=True)]


def summary(kind: str, power: int, registry: Registry | None = None) -> str:
    """One line of a tool's current numbers, for the Tools page."""
    return "  ·  ".join(f"{e.label} {e.value}" for e in effects(kind, power, registry))
