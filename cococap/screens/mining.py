import random
from collections import Counter

from cococap import emojis
import discord

from cococap.registry import get_registry
from cococap.services import mining
from cococap.services.equipment import equipped_stats
from cococap.ui import Page, Screen
from cococap.ui.components import bar, bits, button, row, sep, text, xp_bar
from cococap.user import User


class MiningScreen(Screen):
    id = "mining"
    label = "Mining"
    emoji = "⛏️"
    description = "Dig for ores and gems"
    links = ("mine", "reactor")

    async def build(self) -> Page:
        reg = get_registry()
        status = await mining.reactor_status(self.user)
        skill, level, rules = status["mining"], status["level"], reg.mining
        overflow, needed = User.xp_for_next_level(skill.xp)
        reactor = skill.reactor

        ores = [f"{reg.item(i).emoji or ''} {q:,}" for i, q in (await self.user.items()).items() if i in rules.magnet.values]
        cores = " ".join(
            (reg.item(c.gem_id).emoji or "💎") if c.gem_id else emojis.get("cell", "⬛")
            for c in (reactor.core_1, reactor.core_2, reactor.core_3, reactor.core_4)
        )
        lines = [f"{emojis.get('autominer', '⚙️')} **Reactor Lv {reactor.level}**  ·  cores {cores}  ·  **{status['pending_lodes']:,}** lodes waiting"]
        if level < rules.reactor.gem_slot_level:
            lines.append(f"-# Gem slots unlock at mining level {rules.reactor.gem_slot_level}.")
        tool = await equipped_stats(self.user, "mining")
        body = [
            *self.note_block(),
            text(f"**Level {level}**  {xp_bar(overflow / needed if needed else 0)}  {overflow:,}/{needed:,} xp"),
            text("Ores: " + ("  ".join(ores) if ores else "none yet") + f"\nLodes mined: **{skill.stats.lodes_mined:,}**"),
            text(f"⛏️ Pickaxe power **{tool.power}**" if tool else
                 "⛏️ You need a pickaxe. Buy a **Rookie Pickaxe** in the shop and it equips itself."),
            sep(),
            text("\n".join(lines)),
            row(
                button("Enter the mines", emoji="⛏️", style=discord.ButtonStyle.primary, disabled=tool is None,
                       on_click=self._enter),
                button("Reactor", emoji=emojis.get("autominer", "⚙️"), on_click=self._reactor),
            ),
        ]
        return Page("Mining", body, accent=0x9E492F)

    async def _enter(self, interaction: discord.Interaction) -> None:
        run = await mining.start_run(self.user, random.Random())
        await self.go(interaction, "mine", run=run)

    async def _reactor(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "reactor")
