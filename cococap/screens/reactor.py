import random

import discord

from cococap import emojis
from cococap.registry import get_registry
from cococap.services import mining
from cococap.ui import Page, Screen
from cococap.ui.components import bar, button, duration, row, sep, text


class ReactorScreen(Screen):
    id = "reactor"
    label = "Reactor"
    emoji = emojis.Lazy("autominer", "⚙️")
    description = "Gems, auto-miner, prestige and the magnet"
    links = ("mining",)

    async def build(self) -> Page:
        reg = get_registry()
        rules, d = reg.mining, reg.mining.descent
        status = await mining.reactor_status(self.user)
        skill, level = status["mining"], status["level"]
        reactor = skill.reactor
        cores = (reactor.core_1, reactor.core_2, reactor.core_3, reactor.core_4)

        slots = []
        for number, (core, wanted) in enumerate(zip(cores, rules.reactor.core_gems, strict=True), start=1):
            if core.gem_id:
                slots.append(f"**{number}.** {reg.item(core.gem_id).display}")
            else:
                slots.append(f"**{number}.** {emojis.get('cell', '⬛')} *empty: {reg.item(wanted).name}*")
        if not status["gem_slots_open"]:
            slots.append(f"-# Gem slots unlock at mining level {rules.reactor.gem_slot_level}.")

        slowdown = min(d.max_reduction, d.reactor_reduction * (reactor.level - 1))
        braces = d.braces_base + (reactor.level - 1) // d.braces_per_reactor_levels
        odds = mining.wyrmhole_odds(mining.gems_placed(skill), rules)
        columns = status["columns_dug"]
        per = rules.reactor.prestige_per_extra_column
        next_column = f"  (next at Lv {((reactor.level - 1) // per + 1) * per + 1})" if columns < rules.columns else ""
        perks = (
            f"Digs **{columns}** column(s){next_column}\n"
            f"Pressure builds **{slowdown:.0%}** slower  ·  **{braces}** brace(s) per run\n"
            f"Wyrmholes: 1 in **{odds:,}** per cell"
        )

        auto = (
            f"{emojis.get('autominer', '⚙️')} **Auto-miner**: {reactor.level} lode(s) every "
            f"{duration(rules.reactor.automine_seconds)}, stored for up to {rules.reactor.automine_cap_hours}h.\n"
            f"**{status['pending_lodes']:,}** lodes waiting to be claimed."
        )
        if reactor.level >= rules.reactor.max_prestige:
            prestige = "Your reactor is at its maximum level."
        elif status["prestige_unlocked"]:
            prestige = f"All four cores are lit. An {reg.item(rules.wyrmhole.implosion_item).display} raises the reactor a level."
        else:
            prestige = f"Fill all four cores, then spend an {reg.item(rules.wyrmhole.implosion_item).display} (found in wyrmholes) to prestige."

        body = [
            *self.note_block(),
            text(f"**Reactor Level {reactor.level}** / {rules.reactor.max_prestige}\n" + "\n".join(slots)),
            text(perks),
            sep(),
            text(auto + "\n" + prestige),
        ]
        if level >= rules.magnet.level:
            body.append(text(f"**Magnet**  {bar(skill.magnet_meter / rules.magnet.capacity)}  {skill.magnet_meter:,}/{rules.magnet.capacity:,}\n"
                             "-# A full magnet marks the richest cell of the next row on your next run."))
        body.append(row(
            button("Claim lodes", style=discord.ButtonStyle.success, disabled=status["pending_lodes"] == 0, on_click=self._claim),
            button("Insert gems", on_click=self._insert, disabled=not status["gem_slots_open"]),
            button("Prestige", on_click=self._prestige, disabled=not status["prestige_unlocked"]),
            button("Feed magnet", on_click=self._feed, disabled=level < rules.magnet.level),
        ))
        return Page("Reactor", body, accent=0x4FC3F7)

    async def _claim(self, interaction: discord.Interaction) -> None:
        lodes, loot = await mining.claim_lodes(self.user, random.Random())
        reg = get_registry()
        found = ", ".join(f"{q:,} {reg.item(i).name}" for i, q in loot.items()) or "nothing"
        await self.refresh(interaction, f"Claimed {lodes:,} lodes: {found}.")

    async def _insert(self, interaction: discord.Interaction) -> None:
        reg, placed, problem = get_registry(), [], None
        owned = await self.user.items()
        for gem in reg.mining.reactor.core_gems:
            if owned.get(gem):
                try:
                    await mining.place_gem(self.user, gem)
                    placed.append(reg.item(gem).name)
                except mining.MiningError as e:
                    problem = str(e)
        await self.refresh(interaction, ("Inserted: " + ", ".join(placed)) if placed else (problem or "You have no reactor gems to insert."))

    async def _prestige(self, interaction: discord.Interaction) -> None:
        level = await mining.prestige(self.user)
        await self.refresh(interaction, f"Your reactor is now level {level}!")

    async def _feed(self, interaction: discord.Interaction) -> None:
        owned, used = await self.user.items(), 0
        for ore in get_registry().mining.magnet.values:
            if owned.get(ore):
                try:
                    _, took = await mining.deposit_ore(self.user, ore, owned[ore])
                    used += took
                except mining.MiningError:
                    if used == 0:
                        raise
                    break
        await self.refresh(interaction, f"Fed the magnet {used:,} ore.")
