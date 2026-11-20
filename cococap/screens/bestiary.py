import discord

from cococap import emojis
from cococap.registry import get_registry
from cococap.services import bestiary
from cococap.ui import Page, Screen
from cococap.ui.components import button, row, select, sep, text


class BestiaryScreen(Screen):
    """Every creature: unknown until you meet one, then how many, and the next goal. The counts never stop climbing."""

    id = "bestiary"
    label = "Bestiary"
    emoji = emojis.Lazy("ui_book", "📖")
    description = "Every creature you have met, and how many you have slain, caught or beaten"
    links = ()

    def __init__(self, nav):
        super().__init__(nav)
        self.group = "combat"
        self.page = 0  # combat: which monster's page

    async def build(self) -> Page:
        reg = get_registry()
        every = bestiary.creatures(await bestiary.load(self.user), reg)
        mine = [c for c in every if c.group == self.group]
        blocks = [*self.note_block()]
        pager = None
        if self.group == "combat":
            # One monster per page, in zone order (a page per enemy keeps the message small however many monsters there are).
            order = list(dict.fromkeys(e for ids in self._zone_enemies(reg).values() for e in ids))
            by_id = {c.id: c for c in mine}
            pages = [by_id[e] for e in order if e in by_id]
            self.page = max(0, min(self.page, len(pages) - 1))
            if pages:
                c = pages[self.page]
                blocks.append(text(self._combat_entry(c, reg) if c.count else f"### {emojis.icon('unknown', '❓')} Unknown\n-# Slay one to learn about it."))
                pager = row(button("Prev", emoji=emojis.icon("prev", "◀️"), disabled=self.page == 0, on_click=self._turn(-1)),
                            button(f"{self.page + 1} / {len(pages)}", disabled=True, on_click=self._turn(0)),
                            button("Next", emoji=emojis.icon("next", "▶️"), disabled=self.page >= len(pages) - 1, on_click=self._turn(1)))
        else:
            blocks.append(text(f"### {emojis.icon('fish', '🐟')} Fish\n" + "\n".join(self._line(c) for c in mine if not c.boss)))
            blocks.append(text(f"### {emojis.icon('crown', '👑')} Sea bosses\n" + "\n".join(self._line(c) for c in mine if c.boss)))
        blocks.append(sep())
        blocks.append(text(f"-# {sum(1 for c in every if c.count)} of {len(every)} creatures found"))
        blocks.append(row(select("Show...", [
            discord.SelectOption(label=name, value=key, emoji=emojis.skill(key, "⚔️" if key == "combat" else "🎣"), default=key == self.group) for key, name in bestiary.GROUPS.items()
        ], self._pick)))
        if pager:
            blocks.append(pager)
        return Page("Bestiary", blocks, accent=0x8E44AD)

    @staticmethod
    def _zone_enemies(reg) -> dict[str, list[str]]:
        """Zone id -> its monsters (pool, then its rare mini-boss). Monsters in no zone (key fights) go with the first zone."""
        out = {zid: [*z.enemies, *([z.rare] if z.rare else [])] for zid, z in reg.combat.zones.items()}
        placed = {e for ids in out.values() for e in ids}
        if out:
            out[next(iter(out))] += [e for e in reg.enemies if e not in placed]
        return out

    def _turn(self, step: int):
        async def go(interaction: discord.Interaction) -> None:
            self.page += step
            await self.refresh(interaction)

        return go

    @staticmethod
    def _goal(c: bestiary.Creature) -> str:
        return f"next goal {c.next_goal:,}" if c.next_goal else f"every goal reached {emojis.icon('check', '✅')}"

    def _line(self, c: bestiary.Creature) -> str:
        if not c.count:
            return f"{emojis.icon('unknown', '❓')} Unknown"
        return f"{c.emoji} **{c.name}**  ·  {c.count:,} {c.verb}  ·  {self._goal(c)}" + (f"  ·  {c.detail}" if c.detail else "")

    def _combat_entry(self, c: bestiary.Creature, reg) -> str:
        enemy = reg.enemies[c.id]
        lines = [f"### {enemy.emoji} {enemy.name}" + (f"  ·  {emojis.icon('crown', '👑')} boss" if enemy.boss else ""),
                 f"{emojis.icon('heart', '❤️')} {enemy.hp}  {emojis.icon('sword', '⚔️')} {enemy.attack}  {emojis.icon('shield', '🛡️')} {enemy.defense}  {emojis.icon('bolt', '⚡')} {enemy.speed}" + (f"  {emojis.icon('shield', '🔰')} {enemy.shield}" if enemy.shield else ""),
                 f"Slain **{c.count:,}**  ·  {self._goal(c)}"]
        if c.count >= reg.bestiary.steps[min(1, len(reg.bestiary.steps) - 1)] or enemy.boss:  # you know a monster's moves once you have fought a few
            lines.append("Moves: " + ", ".join(reg.combat.skills[s].name for s in enemy.skills))
        return "\n".join(lines)

    async def _pick(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.group, self.page = values[0], 0
        await self.refresh(interaction)
