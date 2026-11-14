import random
from collections import Counter
import time

import discord

from cococap.registry import get_registry
from cococap.services import farming
from cococap.ui import Page, Result, Screen
from cococap.ui.components import button, row, sep, select, text, xp_bar
from cococap.user import User

PER_ROW = 3


class FarmScreen(Screen):
    id = "farm"
    label = "Farm"
    emoji = "🌾"
    description = "Plant seeds, wait for the rain, harvest"
    links = ("market",)

    def __init__(self, nav):
        super().__init__(nav)
        self.seed: str | None = None  # the seed an empty plot will be planted with

    # ---- rendering -----------------------------------------------------------------------------
    async def build(self) -> Page:
        reg = get_registry()
        gift = await farming.starter_gift(self.user)
        if gift:
            self.note = "🎁 Welcome, farmer! Here are some seeds to start: " + ", ".join(f"{q} {reg.item(i).display}" for i, q in gift.items())
        skill, rain = await farming.sync(self.user)
        views = farming.plot_views(skill, reg, time.time())
        owned = await self.user.items()
        seeds = {i: q for i, q in owned.items() if (item := reg.find_item(i)) and item.seed}
        if self.seed not in seeds:
            self.seed = next(iter(seeds), None)
        deeds = owned.get(reg.farming.deed_item, 0)
        if rain.matured and not self.note:
            self.note = "🌧️ " + ", ".join(f"Plot {n}" for n in rain.matured) + (" is" if len(rain.matured) == 1 else " are") + " ready to harvest!"

        overflow, needed = User.xp_for_next_level(skill.xp)
        body = [
            *self.note_block(),
            text(f"**Level {farming.level_of(skill)}**  {xp_bar(overflow / needed if needed else 0)}  {overflow:,}/{needed:,} xp\n"
                 f"🌧️ Next rain <t:{farming.next_rain(time.time())}:R>  ·  💧 Blessings: **{skill.rain_god_blessings}**"
                 + (f"  ·  {reg.item(reg.farming.deed_item).display}: **{deeds}**" if deeds else "")),
            sep(),
            text(self._plot_lines(views, reg)),
        ]
        for start in range(0, farming.PLOTS, PER_ROW):
            body.append(row(*(self._plot_button(v, reg, deeds) for v in views[start:start + PER_ROW])))
        if seeds:
            body.append(row(select(
                "Seed to plant",
                [discord.SelectOption(
                    label=reg.item(i).name, value=i, default=i == self.seed, emoji=reg.item(i).emoji or "🌱",
                    description=f"{q:,} owned · {reg.item(i).seed.cycles} cycles",
                ) for i, q in seeds.items()],
                self._pick_seed,
            )))
        empty = sum(1 for v in views if v.empty)
        body.append(row(
            button("Harvest all", emoji="🧺", style=discord.ButtonStyle.success, disabled=not any(v.ready for v in views), on_click=self._harvest_all),
            button("Water", emoji="💧", style=discord.ButtonStyle.primary,
                   disabled=not any(v.growing and not v.watered for v in views), on_click=self._water),
            button("Plant all", emoji="🌱", disabled=not (self.seed and empty), on_click=self._plant_all),
            button("Market", emoji="🛒", on_click=self._market),
        ))
        return Page("Farm", body, accent=0x6AA84F)

    def _plot_lines(self, views, reg) -> str:
        lines = []
        for v in views:
            if v.ready:
                lines.append(f"**{v.number}** · {reg.item(v.crop_id).display} is **ready**")
            elif v.growing:
                lines.append(f"**{v.number}** · {reg.item(v.seed_id).display}  {v.cycle}/{v.needed} cycles" + ("  💧" if v.watered else ""))
        return "\n".join(lines) or "Nothing is growing yet. Pick a seed, then plant it in a plot."

    def _plot_button(self, v: farming.PlotView, reg, deeds: int) -> discord.ui.Button:
        click = self._clicked(v.number)
        if not v.unlocked:
            return button("Buy plot", emoji="🔒", disabled=deeds == 0, on_click=click)
        if v.ready:
            return button(f"{v.number} Harvest", emoji=reg.item(v.crop_id).emoji or "🌾", style=discord.ButtonStyle.success, on_click=click)
        if v.growing:
            return button(f"{v.number} · {v.progress:.0%}", emoji=reg.item(v.seed_id).emoji or "🌱", disabled=True)
        return button(f"{v.number} Plant", emoji="🟫", on_click=click)

    # ---- actions: each calls the service, then redraws -------------------------------------------------
    def _clicked(self, number: int):
        async def clicked(interaction: discord.Interaction) -> None:
            view = farming.plot_views(await self.user.skill("farming"), get_registry())[number - 1]
            if not view.unlocked:
                await farming.buy_plot(self.user, number)
                return await self.refresh(interaction, f"You bought plot {number}.")
            if view.ready:
                return await self._report(interaction, [await farming.harvest(self.user, number, random.Random())])
            if view.empty:
                if self.seed is None:
                    return await self.refresh(interaction, "You have no seeds. Buy some in the shop.")
                await farming.plant(self.user, number, self.seed)
                return await self.refresh(interaction, f"Planted {get_registry().item(self.seed).name} in plot {number}.")
            await self.refresh(interaction)

        return clicked

    async def _report(self, interaction: discord.Interaction, harvests: list[farming.Harvest]) -> None:
        reg = get_registry()
        parts = [f"{h.amount:,} {reg.item(h.crop_id).display}" for h in harvests]
        lines = ["Harvested " + ", ".join(parts) + f"  ·  **+{sum(h.xp for h in harvests)}** xp"]
        extras = sum((h.extras for h in harvests), Counter())
        if extras:
            lines.append("🧵 Also found: " + ", ".join(f"{q:,} {reg.item(i).display}" for i, q in extras.items()))
        if any(h.anomaly for h in harvests):
            lines.append("✨ **An agricultural anomaly!** Marvelous! Your work and daily are ready again.")
        self.result = Result("Harvest!", lines, emoji="🧺", accent=0x2F919E, back_label="Back to the farm")
        await self.refresh(interaction)

    async def _harvest_all(self, interaction: discord.Interaction) -> None:
        harvests = await farming.harvest_all(self.user, random.Random())
        if not harvests:
            return await self.refresh(interaction, "Nothing is ready yet.")
        await self._report(interaction, harvests)

    async def _water(self, interaction: discord.Interaction) -> None:
        report = await farming.water(self.user)
        if not report.watered:
            return await self.refresh(interaction, "💧 Everything growing has been watered this hour. Come back after the next rain!")
        note = f"💧 You watered {report.watered} plot(s): **{report.grew}** grew."
        if report.matured:
            note += " " + ", ".join(f"Plot {n}" for n in report.matured) + (" is" if len(report.matured) == 1 else " are") + " ready!"
        await self.refresh(interaction, note)

    async def _plant_all(self, interaction: discord.Interaction) -> None:
        views = farming.plot_views(await self.user.skill("farming"), get_registry())
        planted = 0
        for v in views:
            if v.empty and await self.user.item_quantity(self.seed) > 0:
                await farming.plant(self.user, v.number, self.seed)
                planted += 1
        await self.refresh(interaction, f"Planted {planted} plot(s) with {get_registry().item(self.seed).name}." if planted else "No seeds or no empty plots.")

    async def _pick_seed(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.seed = values[0]
        await self.refresh(interaction)

    async def _market(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "market")
