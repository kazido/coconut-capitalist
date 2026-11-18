import random
from collections import Counter

import discord

from cococap.registry import get_registry
from cococap.services import mining, odds
from cococap.ui import Page, Screen
from cococap.ui.components import button, row, sep, text

from cococap.ui.rewards import rewards_result
from cococap import emojis
from .mine import NOTCH, _cell, _cursor, item_emoji, loot_lines


class WyrmholeScreen(Screen):
    id = "wyrmhole"
    label = "Wyrmhole"
    emoji = "🌀"
    description = "One node. Make it count."
    links = ("mining", "mine")

    def __init__(self, nav):
        super().__init__(nav)
        self.hole: mining.WyrmholeSession | None = None

    @property
    def locked(self) -> bool:
        return self.hole is not None and not self.hole.finished

    async def on_abandon(self) -> None:
        if self.locked:
            await mining.finish_wyrmhole(self.user, self.hole)  # walking away still takes your pick

    async def build(self) -> Page:
        hole = self.hole
        if hole is None:
            return Page("Wyrmhole", [text("There's no wyrmhole here.")])
        if hole.small:
            return self._small_page(hole)
        header = [NOTCH] * len(hole.nodes)
        if not hole.finished:
            header[hole.cursor] = _cursor()
        shaft = "".join(item_emoji(i) if hole.finished else _cell() for i, _ in hole.nodes) if hole.finished else _cell() * len(hole.nodes)
        body = [*self.note_block(), text("You can dig only **one** node. Somewhere in here is an implosion gem..."),
                sep(), text("".join(header) + "\n" + shaft)]
        if not hole.finished:
            body.append(self._controls())
            return Page("Wyrmhole", body, accent=0x9B59B6)
        item_id, quantity = hole.revealed
        body += [sep(), text("## Your pick\n" + loot_lines(Counter({item_id: quantity}))),
                 row(button("Back to the mines", emoji=emojis.icon("pickaxe", "⛏️"), on_click=self._back))]
        return Page("Wyrmhole", body, accent=0x9B59B6)

    def _small_page(self, hole: mining.WyrmholeSession) -> Page:
        """A small wyrmhole: the rows you dug show your pick, the row you are on shows the cursor, the rest are still rock."""
        lines = []
        for r, nodes in enumerate(hole.rows):
            if r < len(hole.picks):
                lines.append("".join(item_emoji(item) if c == hole.columns_picked[r] else _cell() for c, (item, _) in enumerate(nodes)) + f"  ✅ {hole.picks[r][1]:,} {get_registry().item(hole.picks[r][0]).name}")
            else:
                lines.append(_cell() * len(nodes))
        header = [NOTCH] * hole.width
        header[hole.cursor] = _cursor()
        shaft = "\n".join(lines[:hole.row]) + ("\n" if hole.row else "") + "".join(header) + "\n" + "\n".join(lines[hole.row:])
        body = [*self.note_block(),
                text(f"## {emojis.icon('small_wyrmhole', '🕳️')} A small wyrmhole\nDig **one** node on each of the **{len(hole.rows)}** rows. Row **{hole.row + 1}** of {len(hole.rows)}: the deeper, the better the loot. Whatever you pick is yours."),
                sep(), text(shaft), self._controls()]
        return Page("Wyrmhole", body, accent=0x9B59B6)

    def _controls(self):
        return row(
            button(emoji="⬅️", on_click=self._move(-1)),
            button("Dig", emoji=emojis.icon("pickaxe", "⛏️"), style=discord.ButtonStyle.primary, on_click=self._dig),
            button(emoji="➡️", on_click=self._move(1)),
        )

    def _move(self, step: int):
        async def move(interaction: discord.Interaction) -> None:
            self.hole.move(step)
            await self.refresh(interaction)

        return move

    async def _dig(self, interaction: discord.Interaction) -> None:
        if self.hole.finished:  # a second click that was already on its way
            return await self.refresh(interaction)
        self.hole.dig()
        if not self.hole.finished:  # a small wyrmhole: on to the next row
            return await self.refresh(interaction)
        await mining.finish_wyrmhole(self.user, self.hole)
        loot = self.hole.loot()
        headline = [f"{emojis.icon('small_wyrmhole', '🕳️')} You dug the whole small wyrmhole."] if self.hole.small else [f"{emojis.icon('wyrmhole', '🌀')} You dug one node of the wyrmhole."]
        lookup = odds.mini_wyrmhole() if self.hole.small else None  # (the big wyrmhole has no loot table to quote odds from: a rare pick shows its rarity)
        self.result = rewards_result("Your picks" if self.hole.small else "Your pick", items=loot, headline=headline, emoji=emojis.icon("wyrmhole", "🌀"), accent=0x9B59B6,
                                     back=self._back, back_label="Back to the mines", odds=lookup)
        await self.refresh(interaction)

    async def _back(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "mining")
