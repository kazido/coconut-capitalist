"""The Bestiary: every creature you can slay, catch or beat, and how many of each you have. The counts never stop climbing; the
`steps` in `configs/bestiary.toml` are just the goals the page shows next. Each skill adds its own creatures in `creatures`."""

from dataclasses import dataclass

from cococap import emojis
from cococap.registry import Registry, get_registry
from cococap.user import User

SKILLS = ("combat", "fishing")  # the skills that have creatures (mining, farming and foraging may add some later)
GROUPS = {"combat": "Monsters", "fishing": "Fish and sea bosses"}  # skill -> page label (icon: emojis.skill)


@dataclass(frozen=True)
class Creature:
    """One line of the Bestiary."""

    group: str  # "combat", "fishing"
    id: str
    name: str
    emoji: str
    boss: bool
    count: int
    verb: str  # "slain", "caught", "beaten"
    steps: list[int]  # the goals, climbing
    detail: str = ""  # shown once you know it (a size record...)

    @property
    def next_goal(self) -> int | None:
        return next((n for n in self.steps if self.count < n), None)


async def load(user: User) -> dict:
    return {name: await user.skill(name) for name in SKILLS}


def creatures(skills: dict, registry: Registry | None = None) -> list[Creature]:
    """Everything the Bestiary tracks, from your skills' counters."""
    reg = registry or get_registry()
    rules = reg.bestiary
    found: list[Creature] = []
    kills = skills["combat"].kills
    for e in reg.enemies.values():
        found.append(Creature("combat", e.id, e.name, e.emoji or emojis.icon("skull", "👹"), e.boss, kills.get(e.id, 0), "slain", rules.boss_steps if e.boss else rules.steps))
    fishing = skills["fishing"]
    fish = sorted((i for i in reg.items.values() if i.skill == "fishing" and i.category == "fish" and i.drop), key=lambda i: (i.rarity, i.name))
    for item in fish:
        count = max(fishing.stats.caught.get(item.id, 0), 1 if item.id in fishing.records else 0)  # a personal best proves you landed one
        best = fishing.records.get(item.id)
        found.append(Creature("fishing", item.id, item.name, item.emoji or emojis.icon("fish", "🐟"), False, count, "caught", rules.fish_steps, f"best {best:g} cm" if best else ""))
    for boss in reg.fishing.boss.bosses:
        found.append(Creature("fishing", f"boss:{boss.name}", boss.name, emojis.icon("crown", "👑"), True, fishing.stats.bosses.get(boss.name, 0), "beaten", rules.boss_steps))
    return found
