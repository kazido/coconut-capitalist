import discord

from cococap import emojis
from cococap.registry import get_registry
from cococap.services import areas, crafting
from cococap.ui import Page, Screen
from cococap import map_runtime
from cococap.ui.components import button, gallery, needs_text, row, select, text


class ShipScreen(Screen):
    """The ship: where you are, build/upgrade the ship, sail to an area, and craft the fuel the next new area burns."""

    id = "ship"
    label = "Travel"
    emoji = emojis.icon('ship', '🚢')
    description = "Sail to new areas and upgrade your ship"
    links = ("smithing",)

    async def build(self) -> Page:
        reg = get_registry()
        await self.user.refresh()
        owned = await self.user.items()
        st = await areas.state(self.user, reg)
        all_areas = reg.areas.areas
        here = all_areas[st.current]
        tier = areas.next_tier(st, reg)
        built = reg.areas.ship_tiers[st.tier - 1] if st.tier else None

        lines = [f"### {here.emoji} {here.name}", f"-# {here.description}",
                 f"Ship: {built.emoji + ' ' + built.name if built else 'none yet'}"]
        # The world map: reached areas, the one ahead, and a red X where you are now.
        map_png = map_runtime.render_map(st.current, st.highest)
        body = [*self.note_block(), gallery("attachment://map.png"), text("\n".join(lines))]

        if tier is not None:
            levels = await areas._levels(self.user)
            floor = min(tier.skill_floors.values())
            best = max(levels.values())
            ok = any(levels[s] >= need for s, need in tier.skill_floors.items())
            need = needs_text(tier.bits, self.user.purse, tier.parts, owned, reg)
            body.append(text(f"### {tier.emoji} {'Build' if not st.tier else 'Upgrade to'} the {tier.name}\n{need}\n"
                             f"{emojis.icon('check', '✅') if ok else emojis.icon('cross', '❌')} Level **{floor}** in any one skill (your best is {best})"))
            body.append(row(button("Build" if not st.tier else "Upgrade", emoji=emojis.icon('craft', '🔨'), style=discord.ButtonStyle.success,
                                   on_click=self._upgrade)))

        # Sailing: any area you have reached is free; the next new one burns fuel and needs the matching ship tier.
        options = []
        for i, area in enumerate(all_areas[: min(st.highest + 2, len(all_areas))]):
            if i == st.current:
                continue
            if i <= st.highest:
                note = "free"
            else:
                note = "burns fuel" if st.tier >= i else f"needs ship tier {i}"
            options.append(discord.SelectOption(label=area.name, value=area.id, emoji=area.emoji, description=note))
        if options:
            body.append(row(select("Sail to...", options, self._sail)))

        # Fuel for the next unreached area, with a button to craft it when the Workbench can.
        if st.highest + 1 < len(all_areas):
            nxt = all_areas[st.highest + 1]
            recipe = next((r for r in crafting.recipes(reg) if r.output in nxt.fuel), None)
            fuel = needs_text(0, 0, nxt.fuel, owned, reg)
            body.append(text(f"### {emojis.icon('flame', '⛽')} Fuel for {nxt.name}\n{fuel}"))
            if recipe is not None:
                can = await crafting.craftable_count(self.user, recipe)
                body.append(row(button("Craft fuel", emoji=emojis.icon('flame', '⛽'), disabled=can < 1, on_click=self._fuel(recipe.id))))
        # Overdrive: burn a fuel you hold (area reached) for a timed boost in every skill.
        running = await areas.overdrive_state(self.user, reg)
        od_lines = [f"### {emojis.icon('flame', '⛽')} Overdrive"]
        od_lines.append(f"{running[0].emoji} **{reg.item(next(iter(running[0].fuel))).name}**: +{running[0].overdrive.xp:.0%} skill xp, +{running[0].overdrive.drop_amount:.0%} drops, "
                        f"{running[1] // 60 + 1} min left" if running else "Burn a fuel for a timed boost in every skill.")
        body.append(text("\n".join(od_lines)))
        burn = [discord.SelectOption(label=reg.item(next(iter(a.fuel))).name, value=a.id, emoji=a.emoji,
                                     description=(f"+{a.overdrive.xp:.0%} xp, +{a.overdrive.drop_amount:.0%} drops; you have {owned.get(next(iter(a.fuel)), 0):,}"
                                                  + (" (replaces the current one)" if running and running[0].id != a.id else ""))[:100])
                for a in all_areas[: st.highest + 1] if a.fuel and owned.get(next(iter(a.fuel)), 0) > 0]
        if burn:
            body.append(row(select("Burn a fuel...", burn, self._burn)))
        return Page("Ship", body, accent=0x2E86C1, files=[("map.png", map_png)])

    async def _upgrade(self, interaction: discord.Interaction) -> None:
        tier = await areas.upgrade_ship(self.user)
        await self.refresh(interaction, f"{tier.emoji} You now have the **{tier.name}**.")

    async def _sail(self, interaction: discord.Interaction, values: list[str]) -> None:
        area = await areas.travel(self.user, values[0])
        await self.refresh(interaction, f"{area.emoji} You sail to **{area.name}**.")

    async def _burn(self, interaction: discord.Interaction, values: list[str]) -> None:
        area = await areas.burn_fuel(self.user, values[0])
        await self.refresh(interaction, f"{emojis.icon('flame', '⛽')} Overdrive burning: **{area.name}** fuel.")

    def _fuel(self, recipe_id: str):
        async def go(interaction: discord.Interaction) -> None:
            made = await crafting.craft(self.user, recipe_id, 1)
            await self.refresh(interaction, f"{emojis.icon('flame', '⛽')} Crafted {made.recipe.name}.")

        return go
