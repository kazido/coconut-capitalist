import discord

from cococap.registry import get_registry
from cococap.services import progress
from cococap.ui import Page, Screen
from cococap.ui.components import bar, button, row, select, sep, text


def level_line(p: progress.Progress) -> str:
    """The one-line summary shown on Home: `🟣 Coconut Level 37  ▰▰▰▱▱▱▱▱  62/100`."""
    return f"{p.tier.badge} **Coconut Level {p.level}**  {bar(p.into / p.needed, 8)}  {p.into}/{p.needed}"


class ProgressScreen(Screen):
    """Coconut Level: where the points come from and what is closest to paying out."""

    id = "progress"
    label = "Progress"
    emoji = "🥥"
    description = "Your Coconut Level and where its points come from"
    links = ("bestiary",)

    def __init__(self, nav):
        super().__init__(nav)
        self.focus: str | None = None  # a category whose lines are open

    async def build(self) -> Page:
        p = await progress.progress_of(self.user)
        body = [
            *self.note_block(),
            text(f"### {p.tier.badge} Coconut Level {p.level}  ·  {p.tier.name}\n{bar(p.into / p.needed, 12)}  **{p.into}/{p.needed}** to level {p.level + 1}"
                 f"\n-# {p.points:,} of {p.max_points:,} points  ·  each one is a one-time milestone"),
        ]
        nearest = p.next_up(3)
        if nearest:
            body.append(text("**Closest to paying out**\n" + "\n".join(f"▸ {label}: {cur:,}/{target:,}  (+{points})" for label, cur, target, points in nearest)))
        body.append(sep())
        focus = next((c for c in p.categories if c.key == self.focus), None)
        if focus is None:
            body.append(text("\n".join(f"{c.emoji} **{c.name}**  {c.points:,}/{c.max_points:,}" for c in p.categories)))
        else:
            body.append(text(f"### {focus.emoji} {focus.name}  {focus.points:,}/{focus.max_points:,}\n"
                             + "\n".join(f"▸ **{e.label}** {e.points}/{e.max_points}" + (f"  ·  {e.detail}" if e.detail else "") for e in focus.entries)))
        body.append(row(select("Look closer at...", [
            discord.SelectOption(label="Overview", value="all", emoji="🥥", default=focus is None),
            *(discord.SelectOption(label=c.name, value=c.key, emoji=c.emoji, default=c.key == self.focus,
                                   description=f"{c.points:,}/{c.max_points:,} points") for c in p.categories),
        ], self._look)))  # (a select menu always has a row to itself)
        body.append(row(button("Bestiary", emoji="📖", on_click=self._to_bestiary)))
        return Page("Progress", body, accent=int(p.tier.color, 16))

    async def _look(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.focus = None if values[0] == "all" else values[0]
        await self.refresh(interaction)

    async def _to_bestiary(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "bestiary")


class BestiaryScreen(Screen):
    """Every creature: unknown until you meet one, then how many, and the next milestone. Milestones pay Coconut Level; the counts never stop."""

    id = "bestiary"
    label = "Bestiary"
    emoji = "📖"
    description = "Every creature you have met, and how many you have slain, caught or beaten"
    links = ()

    def __init__(self, nav):
        super().__init__(nav)
        self.group = "combat"

    async def build(self) -> Page:
        reg = get_registry()
        snap = await progress.snapshot(self.user)
        every = progress.creatures(snap, reg)
        mine = [c for c in every if c.group == self.group]
        blocks = [*self.note_block()]
        if self.group == "combat":
            for c in mine:
                blocks.append(text(self._combat_entry(c, reg) if c.count else "### ❓ Unknown\n-# Slay one to learn about it."))
        else:
            fish = [c for c in mine if not c.boss]
            bosses = [c for c in mine if c.boss]
            blocks.append(text("### 🐟 Fish\n" + "\n".join(self._line(c) for c in fish)))
            blocks.append(text("### 👑 Sea bosses\n" + "\n".join(self._line(c) for c in bosses)))
        blocks.append(sep())
        found = sum(1 for c in every if c.count)
        blocks.append(text(f"-# {found} of {len(every)} creatures found"))
        blocks.append(row(select("Show...", [
            discord.SelectOption(label=name, value=key, emoji=emoji, default=key == self.group) for key, (emoji, name) in progress.GROUPS.items()
        ], self._pick)))
        return Page("Bestiary", blocks, accent=0x8E44AD)

    @staticmethod
    def _next(c: progress.Creature) -> str:
        upcoming = next((n for n in c.steps if c.count < n), None)
        return f"next {upcoming:,} (+{c.points})" if upcoming else "all milestones ✅"

    def _line(self, c: progress.Creature) -> str:
        if not c.count:
            return "❓ Unknown"
        return f"{c.emoji} **{c.name}**  ·  {c.count:,} {c.verb}  ·  {self._next(c)}" + (f"  ·  {c.detail}" if c.detail else "")

    def _combat_entry(self, c: progress.Creature, reg) -> str:
        enemy = reg.enemies[c.id]
        rules = reg.progress.bestiary
        upcoming = next((n for n in c.steps if c.count < n), None)
        lines = [f"### {enemy.emoji} {enemy.name}" + ("  ·  👑 boss" if enemy.boss else ""),
                 f"❤️ {enemy.hp}  ⚔️ {enemy.attack}  🛡️ {enemy.defense}  ⚡ {enemy.speed}" + (f"  🔰 {enemy.shield}" if enemy.shield else ""),
                 f"Slain **{c.count:,}**" + (f"  ·  next milestone {upcoming:,} (+{c.points} points)" if upcoming else "  ·  every milestone reached ✅")]
        if c.count >= rules.steps[min(1, len(rules.steps) - 1)] or enemy.boss:
            lines.append("Moves: " + ", ".join(reg.combat.skills[s].name for s in enemy.skills))
        return "\n".join(lines)

    async def _pick(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.group = values[0]
        await self.refresh(interaction)
