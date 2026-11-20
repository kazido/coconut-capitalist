"""Accessories pane: the Accessories tab of the Tools page. Pick a skill, see its 2 slots, equip or unequip.

A tab of the Tools page (screens/tools.py), not a registered screen. Rules live in services/accessories.py.
"""

import discord

from cococap import emojis
from cococap.registry import get_registry
from cococap.registry.models import ACCESSORY_SKILLS
from cococap.services import accessories
from cococap.ui import Page, Screen
from cococap.ui.components import button, row, select, sep, text


def _describe(inst, rules) -> str:
    """"Work Gloves (Vein Sense) · ore yield +0.02": the name, its traits and its stat bonuses."""
    template = rules.template(inst.template_id)
    traits = ", ".join(rules.trait(t).name for t in inst.traits)
    stats = ", ".join(f"{stat.replace('_', ' ')} +{amount:g}" for stat, amount in accessories.stats_of(inst).items())
    return f"**{template.name}**" + (f" ({traits})" if traits else "") + (f" · {stats}" if stats else "")


class AccessoriesPane(Screen):
    """Your accessories for one skill: its slots, and the spares to put in them."""

    label = "Accessories"
    emoji = emojis.Lazy("ui_bag", "💍")

    def __init__(self, nav):
        super().__init__(nav)
        self.skill = "mining"
        self.picked: int | None = None  # the spare accessory chosen in the dropdown

    async def build(self) -> Page:
        reg = get_registry()
        rules = reg.accessories
        worn = await accessories.equipped(self.user, self.skill, reg)
        worn_ids = {i.id for i in worn if i is not None}
        body = [*self.note_block(), row(select("Pick a skill...", [
            discord.SelectOption(label=skill.title(), value=skill, default=skill == self.skill) for skill in ACCESSORY_SKILLS
        ], self._pick_skill))]
        body.append(text("\n".join(
            f"**Slot {n}:** " + (_describe(inst, rules) if inst is not None else "empty")
            for n, inst in enumerate(worn, 1)
        )))
        template_ids = {t.id for t in rules.templates if t.skill == self.skill}
        owned = [i for i in await self.user.instances() if i.template_id in template_ids]
        body.append(sep())
        if not owned:
            body.append(text(f"-# No {self.skill} accessories. Buy a basic one in the Shop or wait for a drop."))
            return Page("Accessories", body, accent=0x8E44AD)
        if self.picked not in {i.id for i in owned}:
            self.picked = None
        body.append(row(select("Pick an accessory...", [
            discord.SelectOption(label=(rules.template(i.template_id).name + (" (worn)" if i.id in worn_ids else ""))[:100],
                                 value=str(i.id), default=i.id == self.picked)
            for i in owned
        ], self._pick_spare)))
        # One toggle: takes off a worn accessory, or wears a spare in the first empty slot.
        wearing = self.picked in worn_ids
        full = None not in worn
        body.append(row(button("Unequip" if wearing else "Equip",
                               style=discord.ButtonStyle.secondary if wearing else discord.ButtonStyle.primary,
                               on_click=self._toggle, disabled=self.picked is None or (full and not wearing))))
        if full and self.picked is not None and not wearing:
            body.append(text("-# Both slots are full. Unequip one first."))
        return Page("Accessories", body, accent=0x8E44AD)

    async def _pick_skill(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.skill = values[0]
        self.picked = None
        await self.refresh(interaction)

    async def _pick_spare(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.picked = int(values[0])
        await self.refresh(interaction)

    async def _toggle(self, interaction: discord.Interaction) -> None:
        if self.picked is None:
            return await self.refresh(interaction, "Pick an accessory first.")
        reg = get_registry()
        worn = await accessories.equipped(self.user, self.skill, reg)
        worn_ids = [i.id if i is not None else None for i in worn]
        if self.picked in worn_ids:
            await accessories.unequip(self.user, self.skill, worn_ids.index(self.picked))
            return await self.refresh(interaction, "Took it off.")
        if None not in worn_ids:
            return await self.refresh(interaction, "Both slots are full. Unequip one first.")
        instance = await accessories.equip(self.user, self.skill, self.picked, worn_ids.index(None))
        await self.refresh(interaction, f"Wearing **{reg.accessories.template(instance.template_id).name}**.")
