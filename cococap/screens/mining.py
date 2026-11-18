import random
from collections import Counter

from cococap import emojis
import discord

from cococap.registry import get_registry
from cococap.screens.sellall import start_sell_all
from cococap.services import areas, mining
from cococap.services.equipment import equipped_stats
from cococap.ui import Page, Screen
from cococap.ui.components import bar, bits, button, row, select, sep, text, xp_bar
from cococap.user import User


class MiningScreen(Screen):
    id = "mining"
    label = "Mining"
    emoji = emojis.Lazy("tool_pickaxe_rookie", "⛏️")
    description = "Dig for ores and gems"
    links = ("mine", "reactor", "mastery")

    def __init__(self, nav):
        super().__init__(nav)
        self.mine: str | None = None  # the named mine you dig in (None = the newest one you have opened)

    async def build(self) -> Page:
        reg = get_registry()
        status = await mining.reactor_status(self.user)
        skill, level, rules = status["mining"], status["level"], reg.mining
        overflow, needed = User.xp_for_next_level(skill.xp)
        reactor = skill.reactor

        ores = [f"{reg.item(i).emoji or ''} {q:,}" for i, q in (await self.user.items()).items() if i in rules.magnet.values]
        cores = " ".join(
            (reg.item(c.gem_id).emoji or emojis.icon("gem", "💎")) if c.gem_id else emojis.get("cell", "⬛")
            for c in (reactor.core_1, reactor.core_2, reactor.core_3, reactor.core_4)
        )
        lines = [f"{emojis.get('autominer', '⚙️')} **Reactor Lv {reactor.level}**  ·  cores {cores}  ·  **{status['pending_lodes']:,}** lodes waiting"]
        if level < rules.reactor.gem_slot_level:
            lines.append(f"-# Gem slots unlock at mining level {rules.reactor.gem_slot_level}.")
        tool = await equipped_stats(self.user, "mining")
        open_sites = await mining.open_mines(self.user, reg)
        if self.mine not in {s.id for s in open_sites}:
            self.mine = open_sites[-1].id  # a closed or unknown mine falls back to the newest one you can dig
        names = {loc.id: loc for loc in reg.locations["mining"]}
        here = names[self.mine]
        where = [text(f"{here.emoji} **{here.name}**")]
        if len(open_sites) > 1:
            where.append(row(select("Where to dig...", [
                discord.SelectOption(label=names[s.id].name, value=s.id, emoji=names[s.id].emoji, default=s.id == self.mine,
                                     description=f"Ore x{s.yield_mult:g}  ·  rock x{s.hardness_mult:g}") for s in open_sites], self._pick_mine)))
        if (hint := await areas.next_location_hint(self.user, "mining", reg)) is not None:
            where.append(text(f"-# Next mine: {hint}."))
        body = [
            *self.note_block(),
            text(f"**Level {level}**  {xp_bar(overflow / needed if needed else 0)}  {overflow:,}/{needed:,} xp"),
            text("Ores: " + ("  ".join(ores) if ores else "none yet") + f"\nLodes mined: **{skill.stats.lodes_mined:,}**"),
            text(f"{emojis.icon('pickaxe', '⛏️')} Pickaxe power **{tool.power}**" if tool else
                 f"{emojis.icon('pickaxe', '⛏️')} You need a pickaxe. Buy a **Rookie Pickaxe** in the shop and it equips itself."),
            sep(),
            text("\n".join(lines)),
            text("-# Every mine is a different kind: " + ", ".join(f"{t.emoji} {t.name}" for t in rules.mine_types[1:]) + " turn up now and then. The kind shows once you are in."),
            *where,
            row(
                button("Enter the mines", emoji=emojis.icon("pickaxe", "⛏️"), style=discord.ButtonStyle.primary, disabled=tool is None,
                       on_click=self._enter),
                button("Reactor", emoji=emojis.get("autominer", "⚙️"), on_click=self._reactor),
                button("Mastery", emoji=emojis.icon("mastery", "🌟"), on_click=self._mastery),
                button("Sell all", emoji=emojis.icon("sell", "💰"), on_click=self._sell_all),
            ),
        ]
        return Page("Mining", body, accent=0x9E492F)

    async def _enter(self, interaction: discord.Interaction) -> None:
        run = await mining.start_run(self.user, random.Random(), location=self.mine)
        await self.go(interaction, "mine", run=run)

    async def _pick_mine(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.mine = values[0]
        await self.refresh(interaction)

    async def _reactor(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "reactor")

    async def _mastery(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "mastery", skill="mining")

    async def _sell_all(self, interaction: discord.Interaction) -> None:
        await start_sell_all(self, interaction, "mining")
