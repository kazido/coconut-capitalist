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
        spares = [i for i in await self.user.instances() if i.template_id in template_ids and i.id not in worn_ids]
        body.append(sep())
        if not spares:
            body.append(text(f"-# No spare {self.skill} accessories. Buy a basic one in the Shop or wait for a drop."))
        else:
            if self.picked not in {i.id for i in spares}:
                self.picked = None
            body.append(row(select("Pick a spare accessory...", [
                discord.SelectOption(label=rules.template(i.template_id).name[:100], value=str(i.id), default=i.id == self.picked)
                for i in spares
            ], self._pick_spare)))
        body.append(row(
            button("Equip in slot 1", style=discord.ButtonStyle.primary, on_click=self._equip(0)),
            button("Equip in slot 2", style=discord.ButtonStyle.primary, on_click=self._equip(1)),
        ))
        body.append(row(
            button("Unequip 1", style=discord.ButtonStyle.secondary, on_click=self._unequip(0)),
            button("Unequip 2", style=discord.ButtonStyle.secondary, on_click=self._unequip(1)),
        ))
        return Page("Accessories", body, accent=0x8E44AD)

    async def _pick_skill(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.skill = values[0]
        self.picked = None
        await self.refresh(interaction)

    async def _pick_spare(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.picked = int(values[0])
        await self.refresh(interaction)

    def _equip(self, slot: int):
        async def go(interaction: discord.Interaction) -> None:
            if self.picked is None:
                await self.refresh(interaction, "Pick a spare accessory first.")
                return
            instance = await accessories.equip(self.user, self.skill, self.picked, slot)
            self.picked = None
            name = get_registry().accessories.template(instance.template_id).name
            await self.refresh(interaction, f"Wearing **{name}** in slot {slot + 1}.")

        return go

    def _unequip(self, slot: int):
        async def go(interaction: discord.Interaction) -> None:
            await accessories.unequip(self.user, self.skill, slot)
            await self.refresh(interaction, f"Took off the accessory in slot {slot + 1}.")

        return go
