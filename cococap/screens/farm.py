import random
from collections import Counter
import time

import discord

from cococap.registry import get_registry
from cococap.services import farming
from cococap.services.equipment import equipped_stats
from cococap.services import odds
from cococap.ui.rewards import rewards_result
from cococap.ui import Page, Result, Screen
from cococap.ui.components import button, row, sep, select, text, xp_bar
from cococap.user import User
from cococap import emojis

PER_ROW = 3


class FarmScreen(Screen):
    id = "farm"
    label = "Farm"
    emoji = emojis.Lazy("ui_wheat", "🌾")
    description = "Plant seeds, wait for the rain, harvest"
    links = ("market", "mastery")

    def __init__(self, nav):
        super().__init__(nav)
        self.seed: str | None = None  # the seed an empty plot will be planted with
        self.page = 0  # which page of plots (nine to a page) is showing

    # ---- rendering -----------------------------------------------------------------------------
    async def build(self) -> Page:
        reg = get_registry()
        gift = await farming.starter_gift(self.user)
        if gift:
            self.note = f"{emojis.icon('gift', '🎁')} Welcome, farmer! Here are some seeds to start: " + ", ".join(f"{q} {reg.item(i).display}" for i, q in gift.items())
        skill, rain = await farming.sync(self.user)
        views = farming.plot_views(skill, reg, time.time())
        owned = await self.user.items()
        seeds = {i: q for i, q in owned.items() if (item := reg.find_item(i)) and item.seed}
        if self.seed not in seeds:
            self.seed = next(iter(seeds), None)
        deeds = owned.get(reg.farming.deed_item, 0)
        if rain.matured and not self.note:
            self.note = f"{emojis.icon('drop', '🌧️')} " + ", ".join(f"Plot {n}" for n in rain.matured) + (" is" if len(rain.matured) == 1 else " are") + " ready to harvest!"

        overflow, needed = User.xp_for_next_level(skill.xp)
        can = await equipped_stats(self.user, "farming")
        can_line = (f"{emojis.icon('can', '🚿')} Can waters **{can.power}** plot(s) an hour" if can
                    else f"{emojis.icon('can', '🚿')} No watering can: buy a **Tin Watering Can** in the shop")
        pages = max(1, -(-farming.PLOTS // farming.PAGE_PLOTS))
        self.page = min(self.page, pages - 1)
        first = self.page * farming.PAGE_PLOTS
        shown = views[first:first + farming.PAGE_PLOTS]
        extras = f"  ·  {reg.item(reg.farming.deed_item).display} **{deeds}**" if deeds else ""
        body = [
            *self.note_block(),
            text(f"**Lv {farming.level_of(skill)}**  {xp_bar(overflow / needed if needed else 0)}  {overflow:,}/{needed:,} xp\n"
                 f"{emojis.icon('drop', '🌧️')} Rain <t:{farming.next_rain(time.time())}:R>  ·  {emojis.icon('drop', '💧')} Blessings **{skill.rain_god_blessings}**{extras}\n{can_line}"),
            sep(),
            text(self._plot_lines(shown, reg, f"Plots {shown[0].number}-{shown[-1].number}" if pages > 1 else None)),
        ]
        for start in range(0, len(shown), PER_ROW):
            body.append(row(*(self._plot_button(v, reg, deeds) for v in shown[start:start + PER_ROW])))
        if seeds:
            body.append(row(select(
                "Seed to plant",
                [discord.SelectOption(
                    label=reg.item(i).name, value=i, default=i == self.seed, emoji=reg.item(i).emoji or emojis.icon('sprout', '🌱'),
                    description=f"{q:,} owned · {reg.item(i).seed.cycles} cycles · {farming.estimate(reg.item(i).seed.cycles, reg.farming).short()}",
                ) for i, q in seeds.items()],
                self._pick_seed,
            )))
        empty = sum(1 for v in shown if v.empty)
        body.append(row(
            button("Harvest all", emoji=emojis.icon('basket', '🧺'), style=discord.ButtonStyle.success, disabled=not any(v.ready for v in views), on_click=self._harvest_all),
            button("Water", emoji=emojis.icon('drop', '💧'), style=discord.ButtonStyle.primary,
                   disabled=can is None or not any(v.growing and not v.watered for v in views), on_click=self._water),
            button("Tend", emoji=emojis.icon('sprout', '🌿'), disabled=not farming.tend_waiting(skill, reg.farming), on_click=self._tend),
            button("Plant page" if pages > 1 else "Plant all", emoji=emojis.icon('sprout', '🌱'), disabled=not (self.seed and empty), on_click=self._plant_all),
            button("Market", emoji=emojis.icon('sell', '🛒'), on_click=self._market),
        ))
        if pages > 1:
            body.append(row(button("Prev", emoji=emojis.icon('prev', '◀️'), disabled=self.page == 0, on_click=self._turn(-1)),
                            button(f"Page {self.page + 1}/{pages}", disabled=True),
                            button("Next", emoji=emojis.icon('next', '▶️'), disabled=self.page >= pages - 1, on_click=self._turn(1))))
        body.append(row(button("Mastery", emoji=emojis.icon('star', '🌟'), on_click=self._mastery)))
        return Page("Farm", body, accent=0x6AA84F)

    def _plot_lines(self, views, reg, heading: str | None = None) -> str:
        """One short line per plot that has something in it: number, crop, progress, watered, time left."""
        lines = [f"**{heading}**"] if heading else []
        for v in views:
            if v.ready:
                lines.append(f"**{v.number}** {reg.item(v.crop_id).display}  {emojis.icon('check', '✅')} **ready**")
            elif v.growing:
                seed = reg.item(v.seed_id)
                lines.append(f"**{v.number}** {seed.emoji or emojis.icon('sprout', '🌱')} {seed.name.removesuffix(' Seed')}  {v.cycle}/{v.needed}" + (f" {emojis.icon('drop', '💧')}" if v.watered else "")
                             + f"  ·  {farming.estimate(v.needed - v.cycle, reg.farming).short()}")
        if len(lines) == (1 if heading else 0):
            lines.append("Nothing is growing here yet. Pick a seed, then plant it.")
        return "\n".join(lines)

    def _plot_button(self, v: farming.PlotView, reg, deeds: int) -> discord.ui.Button:
        click = self._clicked(v.number)
        if not v.unlocked:
            return button("Buy plot", emoji=emojis.icon('lock', '🔒'), disabled=deeds == 0, on_click=click)
        if v.ready:
            return button(f"{v.number} Harvest", emoji=reg.item(v.crop_id).emoji or emojis.icon('wheat', '🌾'), style=discord.ButtonStyle.success, on_click=click)
        if v.growing:
            return button(f"{v.number} · {v.progress:.0%}", emoji=reg.item(v.seed_id).emoji or emojis.icon('sprout', '🌱'), disabled=True)
        return button(f"{v.number} Plant", emoji=emojis.icon('sq_brown', '🟫'), on_click=click)

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
                reg = get_registry()
                when = farming.estimate(reg.item(self.seed).seed.cycles, reg.farming).text()
                return await self.refresh(interaction, f"Planted {reg.item(self.seed).name} in plot {number}: ready in {when}.")
            await self.refresh(interaction)

        return clicked

    async def _report(self, interaction: discord.Interaction, harvests: list[farming.Harvest]) -> None:
        crops = sum((Counter({h.crop_id: h.amount}) for h in harvests), Counter())
        extras = sum((h.extras for h in harvests), Counter())
        notes = []
        if again := [h.plot for h in harvests if h.replanted]:
            notes.append(f"{emojis.icon('tree', '🌲')} **Evergreen!** Plot " + ", ".join(str(n) for n in again) + " replanted itself.")
        if any(h.anomaly for h in harvests):
            notes.append(f"{emojis.icon('sparkle', '✨')} **An agricultural anomaly!** Marvelous! Your work and daily are ready again.")
        self.result = rewards_result("Harvest!", items=crops + extras, xp=sum(h.xp for h in harvests), notes=notes, odds=odds.farming(),
                                     emoji=emojis.icon('basket', '🧺'), accent=0x2F919E, back_label="Back to the farm")
        await self.refresh(interaction)

    async def _harvest_all(self, interaction: discord.Interaction) -> None:
        harvests = await farming.harvest_all(self.user, random.Random())
        if not harvests:
            return await self.refresh(interaction, "Nothing is ready yet.")
        await self._report(interaction, harvests)

    async def _water(self, interaction: discord.Interaction) -> None:
        report = await farming.water(self.user)
        if not report.watered:
            return await self.refresh(interaction, f"{emojis.icon('drop', '💧')} Everything growing has been watered this hour. Come back after the next rain!")
        note = f"{emojis.icon('drop', '💧')} You watered {report.watered} plot(s): **{report.grew}** grew."
        if report.thirsty:
            note += f" {emojis.icon('can', '🚿')} Your can only reaches {report.capacity} plots an hour: **{report.thirsty}** plot(s) stayed dry. A better can waters more."
        if report.matured:
            note += " " + ", ".join(f"Plot {n}" for n in report.matured) + (" is" if len(report.matured) == 1 else " are") + " ready!"
        await self.refresh(interaction, note)

    async def _tend(self, interaction: discord.Interaction) -> None:
        report = await farming.tend(self.user, random.Random())
        got = ", ".join(f"{q:,} × {get_registry().item(i).name}" for i, q in report.found.items()) or "nothing this time"
        await self.refresh(interaction, f"{emojis.icon('sprout', '🌿')} You tended {report.plots} plot(s) ({report.cycles} growth cycle(s)): {got}.")

    def _turn(self, step: int):
        async def go(interaction: discord.Interaction) -> None:
            self.page += step
            await self.refresh(interaction)

        return go

    async def _plant_all(self, interaction: discord.Interaction) -> None:
        views = farming.plot_views(await self.user.skill("farming"), get_registry())
        first = self.page * farming.PAGE_PLOTS
        planted = 0
        for v in views[first:first + farming.PAGE_PLOTS]:  # just this page
            if v.empty and await self.user.item_quantity(self.seed) > 0:
                await farming.plant(self.user, v.number, self.seed)
                planted += 1
        await self.refresh(interaction, f"Planted {planted} plot(s) with {get_registry().item(self.seed).name}." if planted else "No seeds or no empty plots.")

    async def _pick_seed(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.seed = values[0]
        await self.refresh(interaction)

    async def _mastery(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "mastery", skill="farming")

    async def _market(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "market")
