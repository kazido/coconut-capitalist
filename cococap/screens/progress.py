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
                 f"\n-# {p.points:,} of {p.max_points:,} points. Every point is a milestone you reach once, so there is no grinding it."),
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
    """Every enemy: unknown until you slay one, then its stats, and its skills once you know it well. Milestones pay Coconut Level."""

    id = "bestiary"
    label = "Bestiary"
    emoji = "📖"
    description = "Every monster you have met, and how many you have slain"
    links = ()

    async def build(self) -> Page:
        reg = get_registry()
        rules = reg.progress.bestiary
        kills = (await self.user.skill("combat")).kills
        blocks = [*self.note_block()]
        known = 0
        for enemy in reg.enemies.values():
            count = kills.get(enemy.id, 0)
            if count == 0:
                blocks.append(text("### ❓ Unknown\n-# Slay one to learn about it."))
                continue
            known += 1
            steps, each = (rules.boss_steps, rules.boss_points) if enemy.boss else (rules.steps, rules.points)
            upcoming = next((s for s in steps if count < s), None)
            lines = [f"### {enemy.emoji} {enemy.name}" + ("  ·  👑 boss" if enemy.boss else ""),
                     f"❤️ {enemy.hp}  ⚔️ {enemy.attack}  🛡️ {enemy.defense}  ⚡ {enemy.speed}" + (f"  🔰 {enemy.shield}" if enemy.shield else ""),
                     f"Slain **{count:,}**" + (f"  ·  next milestone {upcoming:,} (+{each} points)" if upcoming else "  ·  every milestone reached ✅")]
            if count >= rules.steps[min(1, len(rules.steps) - 1)] or enemy.boss:
                skill_names = ", ".join(reg.combat.skills[s].name for s in enemy.skills)
                lines.append(f"Moves: {skill_names}")
            blocks.append(text("\n".join(lines)))
        blocks.append(sep())
        blocks.append(text(f"-# {known} of {len(reg.enemies)} found"))
        return Page("Bestiary", blocks, accent=0x8E44AD)
