import random
from collections import Counter

import discord

from cococap.services import mining
from cococap.ui import Page, Screen
from cococap.ui.components import button, row, sep, text

from cococap.ui.rewards import rewards_result
from .mine import CURSOR, NOTCH, _cell, item_emoji, loot_lines


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
        header = [NOTCH] * len(hole.nodes)
        if not hole.finished:
            header[hole.cursor] = CURSOR
        shaft = "".join(item_emoji(i) if hole.finished else _cell() for i, _ in hole.nodes) if hole.finished else _cell() * len(hole.nodes)
        body = [*self.note_block(), text("You can dig only **one** node. Somewhere in here is an implosion gem..."),
                sep(), text("".join(header) + "\n" + shaft)]
        if not hole.finished:
            body.append(row(
                button(emoji="⬅️", on_click=self._move(-1)),
                button("Dig", emoji="⛏️", style=discord.ButtonStyle.primary, on_click=self._dig),
                button(emoji="➡️", on_click=self._move(1)),
            ))
            return Page("Wyrmhole", body, accent=0x9B59B6)
        item_id, quantity = hole.revealed
        body += [sep(), text("## Your pick\n" + loot_lines(Counter({item_id: quantity}))),
                 row(button("Back to the mines", emoji="⛏️", on_click=self._back))]
        return Page("Wyrmhole", body, accent=0x9B59B6)

    def _move(self, step: int):
        async def move(interaction: discord.Interaction) -> None:
            self.hole.move(step)
            await self.refresh(interaction)

        return move

    async def _dig(self, interaction: discord.Interaction) -> None:
        await mining.finish_wyrmhole(self.user, self.hole)
        item_id, quantity = self.hole.revealed
        self.result = rewards_result("Your pick", items={item_id: quantity}, headline=["🌀 You dug one node of the wyrmhole."], emoji="🌀", accent=0x9B59B6,
                                     back=self._back, back_label="Back to the mines")  # (no loot table to quote odds from: a rare pick shows its rarity)
        await self.refresh(interaction)

    async def _back(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "mining")
