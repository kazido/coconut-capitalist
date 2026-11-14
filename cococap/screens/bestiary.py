import discord

from cococap.registry import get_registry
from cococap.services import bestiary
from cococap.ui import Page, Screen
from cococap.ui.components import row, select, sep, text


class BestiaryScreen(Screen):
    """Every creature: unknown until you meet one, then how many, and the next goal. The counts never stop climbing."""

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
        every = bestiary.creatures(await bestiary.load(self.user), reg)
        mine = [c for c in every if c.group == self.group]
        blocks = [*self.note_block()]
        if self.group == "combat":
            for c in mine:
                blocks.append(text(self._combat_entry(c, reg) if c.count else "### ❓ Unknown\n-# Slay one to learn about it."))
        else:
            blocks.append(text("### 🐟 Fish\n" + "\n".join(self._line(c) for c in mine if not c.boss)))
            blocks.append(text("### 👑 Sea bosses\n" + "\n".join(self._line(c) for c in mine if c.boss)))
        blocks.append(sep())
        blocks.append(text(f"-# {sum(1 for c in every if c.count)} of {len(every)} creatures found"))
        blocks.append(row(select("Show...", [
            discord.SelectOption(label=name, value=key, emoji=emoji, default=key == self.group) for key, (emoji, name) in bestiary.GROUPS.items()
        ], self._pick)))
        return Page("Bestiary", blocks, accent=0x8E44AD)

    @staticmethod
    def _goal(c: bestiary.Creature) -> str:
        return f"next goal {c.next_goal:,}" if c.next_goal else "every goal reached ✅"

    def _line(self, c: bestiary.Creature) -> str:
        if not c.count:
            return "❓ Unknown"
        return f"{c.emoji} **{c.name}**  ·  {c.count:,} {c.verb}  ·  {self._goal(c)}" + (f"  ·  {c.detail}" if c.detail else "")

    def _combat_entry(self, c: bestiary.Creature, reg) -> str:
        enemy = reg.enemies[c.id]
        lines = [f"### {enemy.emoji} {enemy.name}" + ("  ·  👑 boss" if enemy.boss else ""),
                 f"❤️ {enemy.hp}  ⚔️ {enemy.attack}  🛡️ {enemy.defense}  ⚡ {enemy.speed}" + (f"  🔰 {enemy.shield}" if enemy.shield else ""),
                 f"Slain **{c.count:,}**  ·  {self._goal(c)}"]
        if c.count >= reg.bestiary.steps[min(1, len(reg.bestiary.steps) - 1)] or enemy.boss:  # you know a monster's moves once you have fought a few
            lines.append("Moves: " + ", ".join(reg.combat.skills[s].name for s in enemy.skills))
        return "\n".join(lines)

    async def _pick(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.group = values[0]
        await self.refresh(interaction)
