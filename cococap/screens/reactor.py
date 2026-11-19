import random
from collections import Counter

import discord

from cococap import emojis
from cococap.registry import get_registry
from cococap.services import mining
from cococap.ui import Page, Screen
from cococap.services.equipment import equipped_stats
from cococap.ui.components import bar, button, duration, row, select, sep, text


class ReactorScreen(Screen):
    """The Reactor page: gems, auto-miner, prestige and the magnet."""

    id = "reactor"
    label = "Reactor"
    emoji = emojis.Lazy("ui_reactor", "⚙️")
    description = "Gems, auto-miner, prestige and the magnet"
    links = ("mining",)

    def __init__(self, nav):
        super().__init__(nav)
        self.ore: str | None = None  # the ore picked to feed the magnet

    async def build(self) -> Page:
        reg = get_registry()
        rules, d = reg.mining, reg.mining.descent
        status = await mining.reactor_status(self.user)
        self._owned = await self.user.items()
        skill, level = status["mining"], status["level"]
        reactor = skill.reactor
        cores = (reactor.core_1, reactor.core_2, reactor.core_3, reactor.core_4)

        slots = []
        for number, (core, wanted) in enumerate(zip(cores, rules.reactor.core_gems, strict=True), start=1):
            if core.gem_id:
                slots.append(f"{number}. {reg.item(core.gem_id).display}")
            else:
                slots.append(f"{number}. {emojis.get('cell_empty', '▫️')} *{reg.item(wanted).name}*")
        if not status["gem_slots_open"]:
            slots.append(f"-# Gem slots unlock at mining level {rules.reactor.gem_slot_level}.")

        slowdown = min(d.max_reduction, d.reactor_reduction * (reactor.level - 1))
        braces = d.braces_base + (reactor.level - 1) // d.braces_per_reactor_levels
        odds = mining.wyrmhole_odds(mining.gems_placed(skill), rules)
        columns = status["columns_dug"]
        per = rules.reactor.prestige_per_extra_column
        next_column = f" (next: Lv {((reactor.level - 1) // per + 1) * per + 1})" if columns < rules.columns else ""
        perks = (
            f"{emojis.skill('mining', '⛏️')} **{columns}** column(s){next_column}  ·  **{braces}** brace(s)\n"
            f"**{slowdown:.0%}** slower pressure  ·  {emojis.get('wyrmhole', '🕳️')} wyrmhole **1 in {odds:,}**"
        )

        tool = await equipped_stats(self.user, "mining")
        speed, extra_hours = (tool.stats.get("auto_speed", 0.0), tool.stats.get("auto_hours", 0.0)) if tool else (0.0, 0.0)
        auto = (
            f"{emojis.get('autominer', '⚙️')} **Auto-miner**: **{round(reactor.level * (1 + speed))}** lode(s) / {duration(rules.reactor.automine_seconds)}"
            f"  ·  holds {rules.reactor.automine_cap_hours + extra_hours:g}h\n"
            f"**{status['pending_lodes']:,}** waiting"
        )
        imp = reg.item(rules.wyrmhole.implosion_item).display
        if reactor.level >= rules.reactor.max_prestige:
            prestige = "Max level."
        elif status["prestige_unlocked"]:
            prestige = f"All cores lit: an {imp} raises the reactor a level."
        else:
            prestige = f"Prestige: fill all four cores, then spend an {imp}."

        body = [
            *self.note_block(),
            text(f"### {emojis.icon('reactor', '⚙️')} Reactor Level {reactor.level} / {rules.reactor.max_prestige}\n" + "\n".join(slots) + "\n" + perks),
            sep(),
            text(auto + "\n-# " + prestige),
        ]
        body.append(row(
            button("Claim lodes", emoji=emojis.icon("rock_firm", "🪨"), style=discord.ButtonStyle.success, disabled=status["pending_lodes"] == 0, on_click=self._claim),
            button("Insert gems", emoji=reg.item(rules.reactor.core_gems[0]).emoji or None, on_click=self._insert, disabled=not status["gem_slots_open"]),
            button("Prestige", emoji=reg.item(rules.wyrmhole.implosion_item).emoji or None, on_click=self._prestige, disabled=not status["prestige_unlocked"]),
        ))
        if tool and tool.stats.get("lifeline"):
            wait = skill.lifeline_wait
            body.append(text(f"{emojis.icon('lifeline', '🛟')} **Lifeline**: " + ("ready" if wait <= 0 else f"recharging, **{wait}** more mine(s)")))
        if level >= rules.magnet.level:
            body += [sep(), *self._magnet_parts(reg, skill, tool)]
        return Page("Reactor", body, accent=0x4FC3F7)

    async def _claim(self, interaction: discord.Interaction) -> None:
        fed: Counter[str] = Counter()
        lodes, loot = await mining.claim_lodes(self.user, random.Random(), fed_out=fed)
        reg = get_registry()
        found = ", ".join(f"{q:,} {reg.item(i).name}" for i, q in loot.items()) or "nothing"
        into = f" {sum(mining.magnet_value(i, reg) * q for i, q in fed.items()):,} meter went into the magnet ({', '.join(f'{q:,} {reg.item(i).name}' for i, q in fed.items())})." if fed else ""
        await self.refresh(interaction, f"Claimed {lodes:,} lodes: {found}.{into}")

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

    def _magnet_parts(self, reg, skill, tool) -> list:
        """The magnet: how full it is (in rows it can still mark), what to feed it with and exactly what that does, and its two switches."""
        magnet = reg.mining.magnet
        save = min(0.9, tool.stats.get("magnet_save", 0.0)) if tool else 0.0
        drain = magnet.drain_per_row * (1 - save)
        rows = int(skill.magnet_meter // drain) if drain else 0
        meter = skill.magnet_meter
        parts = [text(f"### Magnet\n{bar(meter / magnet.capacity, 10, 'meter')}  {meter:,}/{magnet.capacity:,}  ·  ~**{rows}** rows\n"
                      f"-# Marks the richest column of each row: **{drain:g}** meter a row. Feed it outside a mine.")]
        owned = self._owned
        # Any mining material you own that has a meter value, most owned first (a select holds 25 at most)
        fuel = sorted(((ore, n) for ore, n in owned.items() if mining.magnet_value(ore, reg) is not None), key=lambda kv: -kv[1])[:25]
        if fuel:
            options = [discord.SelectOption(label=reg.item(ore).name, value=ore, emoji=reg.item(ore).emoji or None, default=ore == self.ore,
                                            description=f"you have {n:,}  ·  +{mining.magnet_value(ore, reg)} meter each")
                       for ore, n in fuel]
            parts.append(row(select("Feed the magnet with...", options, self._pick_ore)))
        else:
            parts.append(text("-# You have no mining materials to feed it."))
        if self.ore and mining.magnet_value(self.ore, reg) is not None:
            value, have = mining.magnet_value(self.ore, reg), owned.get(self.ore, 0)
            room = magnet.capacity - meter
            fits = -(-room // value) if room > 0 else 0  # (ore it takes to fill it, rounded up)
            name = reg.item(self.ore).name

            def feed(count: int):
                async def go(interaction: discord.Interaction) -> None:
                    await self._feed(interaction, count)

                return go

            fill = min(have, fits)
            preview = f"-# **{name}**: have {have:,}, full needs {fits:,}. " if fits else "-# Meter full. "
            if fill:
                after = min(magnet.capacity, meter + value * fill)
                preview += f"Fill uses **{fill:,}** (+{after - meter:,})."
            parts.append(text(preview))
            parts.append(row(*(button(f"Feed {n}", on_click=feed(n), disabled=have < 1 or fits < 1 or n > min(have, fits)) for n in (1, 10, 100)),
                              button(f"Fill ({fill:,})", style=discord.ButtonStyle.success, on_click=feed(fill), disabled=fill < 1)))
        parts.append(row(
            button(f"Magnet {'on' if skill.magnet_on else 'off'}", emoji=emojis.icon("magnet", "✨"), style=discord.ButtonStyle.primary if skill.magnet_on else discord.ButtonStyle.secondary,
                   on_click=self._toggle("magnet_on", skill.magnet_on)),
            button(f"Auto-feed {'on' if skill.magnet_auto_feed else 'off'}", emoji=emojis.get("autominer", "⚙️"),
                   style=discord.ButtonStyle.primary if skill.magnet_auto_feed else discord.ButtonStyle.secondary,
                   on_click=self._toggle("magnet_auto_feed", skill.magnet_auto_feed)),
        ))
        return parts

    async def _pick_ore(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.ore = values[0]
        await self.refresh(interaction)

    async def _feed(self, interaction: discord.Interaction, count: int) -> None:
        reg = get_registry()
        meter, used = await mining.deposit_ore(self.user, self.ore, count)
        value = mining.magnet_value(self.ore, reg)
        await self.refresh(interaction, f"Fed the magnet **{used:,} {reg.item(self.ore).name}** (+{used * value:,} meter, now {meter:,}/{reg.mining.magnet.capacity:,}).")

    def _toggle(self, option: str, current: bool):
        async def go(interaction: discord.Interaction) -> None:
            await mining.set_magnet_option(self.user, option, not current)
            await self.refresh(interaction)

        return go
