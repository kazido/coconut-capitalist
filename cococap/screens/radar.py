import discord

from cococap.registry import get_registry
from cococap.services import fishing
from cococap.services.fishing import FishingError
from cococap.ui import Page, Screen
from cococap.ui.components import bits, button, needs_text, row, select, sep, text
from cococap.user import User


class RadarScreen(Screen):
    """The fishing radar: pick the fish you chase, switch it on, and upgrade it. Every cast with it on (and a chase fish in the water) uses a battery."""

    id = "radar"
    label = "Radar"
    emoji = "📡"
    description = "Make the fish you chase likelier"
    links = ("fish",)

    async def build(self) -> Page:
        reg = get_registry()
        rules = reg.fishing.radar
        view = await fishing.radar(self.user, reg)
        level = User.xp_to_level((await self.user.skill("fishing")).xp)
        body = [*self.note_block()]
        if not view.unlocked:
            body.append(text(f"### 📡 Radar\n🔒 The radar opens at **fishing level {rules.unlock_level}** (you are level {level})."))
            return Page("Radar", body, accent=0x3A7CA5)
        if not view.level:
            body.append(text("### 📡 Radar\nYou have not built one yet. A radar makes the fish you pick **several times likelier**, for a battery a cast. "
                             "It needs batteries from the shop (Fishing section)."))
        else:
            body.append(text(f"### 📡 Radar  ·  level {view.level}/{len(rules.levels)}\n"
                             f"Chased fish are **{view.multiplier:g}x** likelier  ·  **{view.slots}** target slot(s)  ·  🔋 **{view.batteries:,}** batteries\n"
                             + ("🟢 **On**" if view.on else "⚪ **Off**") + (" (it uses one battery a cast, when a target lives in the water)" if view.on else "")))
            fish = sorted({f for w in fishing.unlocked_waters(level, reg.fishing) for f in w.fish}, key=lambda f: (-reg.item(f).rarity, reg.item(f).name))[:25]
            body.append(row(select(f"Chase up to {view.slots}...", [
                discord.SelectOption(label=reg.item(f).name, value=f, emoji=reg.item(f).emoji or None, default=f in view.targets,
                                     description=f"worth {bits(reg.item(f).sell_price)}") for f in fish],
                self._targets)))
            lines = []
            for water in fishing.unlocked_waters(level, reg.fishing):
                for fish_id, chance in fishing.radar_chances(water, view.targets, view.multiplier, reg).items():
                    base = fishing.water_chances(water)[fish_id]
                    lines.append(f"{water.emoji} {water.name}: {reg.item(fish_id).display}  1 in **{round(1 / chance):,}** (was 1 in {round(1 / base):,})")
            body.append(text("**Your chances**\n" + "\n".join(lines) if lines else "-# Pick fish above to see your odds."))
            body.append(row(button("Turn off" if view.on else "Turn on", emoji="⚡", style=discord.ButtonStyle.secondary if view.on else discord.ButtonStyle.success,
                                   disabled=not view.targets and not view.on, on_click=self._toggle(not view.on))))
        if view.next_cost is not None:
            cost = view.next_cost
            owned = await self.user.items()
            body += [sep(), text(f"### ⬆️ {'Build the radar' if not view.level else f'Upgrade to level {view.level + 1}'}  ·  {cost.multiplier:g}x, {cost.slots} slot(s)\n"
                                 + needs_text(cost.bits, self.user.purse, cost.items, owned, reg)),
                     row(button("Build" if not view.level else "Upgrade", emoji="🔨", style=discord.ButtonStyle.success,
                                disabled=self.user.purse < cost.bits or any(owned.get(i, 0) < q for i, q in cost.items.items()), on_click=self._upgrade))]
        body.append(row(button("Back to fishing", emoji="🎣", on_click=self._back)))
        return Page("Radar", body, accent=0x3A7CA5)

    async def _targets(self, interaction: discord.Interaction, values: list[str]) -> None:
        try:
            await fishing.set_radar(self.user, targets=values)
        except FishingError as error:
            return await self.refresh(interaction, str(error))
        await self.refresh(interaction)

    def _toggle(self, on: bool):
        async def go(interaction: discord.Interaction) -> None:
            try:
                await fishing.set_radar(self.user, on=on)
            except FishingError as error:
                return await self.refresh(interaction, str(error))
            await self.refresh(interaction, "📡 Radar on." if on else "📡 Radar off.")

        return go

    async def _upgrade(self, interaction: discord.Interaction) -> None:
        try:
            level = await fishing.upgrade_radar(self.user)
        except FishingError as error:
            return await self.refresh(interaction, str(error))
        await self.user.refresh()
        await self.refresh(interaction, f"📡 Your radar is level **{level}**!")

    async def _back(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "fish")
