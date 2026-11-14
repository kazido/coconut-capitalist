import discord

from cococap.registry import get_registry
from cococap.services import upgrades
from cococap.services.equipment import effective_stats
from cococap.services.inventory import instance_label
from cococap.ui import Page, Screen
from cococap.ui.components import bits, button, row, section, sep, text

MAX_SHOWN = 6


class UpgradeScreen(Screen):
    id = "upgrade"
    label = "Upgrade Tools"
    emoji = "🔨"
    description = "Turn a tool into the next one up"
    links = ("inventory",)

    async def build(self) -> Page:
        reg = get_registry()
        offers = await upgrades.offers(self.user)
        body = [*self.note_block()]
        if not offers:
            body.append(text("Nothing to upgrade. Buy a starter tool in the shop first; "
                             "tools that are already the best of their kind don't show up here."))
        owned = await self.user.items()
        for offer in offers[:MAX_SHOWN]:
            cost = offer.cost
            needs = [f"**{bits(cost.bits)}** bits"] if cost.bits else []
            needs += [f"{owned.get(i, 0):,}/{q:,} {reg.item(i).name}" for i, q in cost.items.items()]
            now = effective_stats(offer.instance).power
            after = offer.target.tool.power
            lines = (f"### {offer.current.emoji or '🔨'} {instance_label(offer.instance)}  →  {offer.target.name}\n"
                     f"Power **{now}** → **{after}**  ·  needs " + ", ".join(needs))
            if offer.level_needed:
                lines += f"\n-# {offer.target.name} needs level {offer.level_needed} in its skill."
            body.append(section(lines, accessory=button(
                "Upgrade", style=discord.ButtonStyle.success, disabled=not offer.affordable,
                on_click=self._upgrade(offer.instance.id))))
        if len(offers) > MAX_SHOWN:
            body.append(text(f"-# …and {len(offers) - MAX_SHOWN} more tools."))
        body += [sep(), row(button("Back to inventory", emoji="🎒", on_click=self._back))]
        return Page("Upgrade Tools", body, accent=0xB8860B)

    def _upgrade(self, instance_id: int):
        async def go(interaction: discord.Interaction) -> None:
            done = await upgrades.upgrade(self.user, instance_id)
            await self.refresh(interaction, f"🔨 Your {done.current.name} became a **{done.target.name}**!")

        return go

    async def _back(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "inventory")
