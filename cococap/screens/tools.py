import discord

from cococap.errors import CustomError
from cococap.registry import get_registry
from cococap.services.equipment import TOOL_FOR_SKILL, effective_stats, equip, skill_for_tool
from cococap.services import tool_effects
from cococap.services.inventory import instance_label
from cococap.ui import Page, Screen
from cococap.ui.components import button, row, section, sep, text
from cococap.screens.upgrade import describe_stats

MAX_SHOWN = 8  # a tool each of five kinds is all the game hands out; imported accounts can own more, and a page has room for only so many
KIND_LABEL = {"pickaxe": "Mining", "axe": "Foraging", "sword": "Combat", "rod": "Fishing", "can": "Farming"}


class ToolsScreen(Screen):
    """Every tool you own: which one is equipped for each skill, with a way to equip it and to upgrade or enchant."""

    id = "tools"
    label = "Tools"
    emoji = "🧰"
    description = "Your tools: equip, upgrade and enchant them"
    links = ("inventory", "upgrade", "enchant")

    async def _equipped_ids(self) -> set[int]:
        ids = set()
        for skill in TOOL_FOR_SKILL:
            equipped = (await self.user.skill(skill)).equipped_instance_id
            if equipped is not None:
                ids.add(equipped)
        return ids

    async def build(self) -> Page:
        reg = get_registry()
        instances = [i for i in await self.user.instances() if reg.item(i.template_id).tool]
        equipped = await self._equipped_ids()
        body = [*self.note_block()]
        if not instances:
            body.append(text("You have no tools yet. The shop sells a starter tool for each skill."))
        order = list(KIND_LABEL)
        shown = sorted(instances, key=lambda i: (i.id not in equipped, order.index(reg.item(i.template_id).tool.kind)))
        for inst in sorted(shown[:MAX_SHOWN], key=lambda i: order.index(reg.item(i.template_id).tool.kind)):
            item = reg.item(inst.template_id)
            tool = item.tool
            stats = effective_stats(inst, reg)
            extra = [describe_stats(tool.stats)] if tool.stats else []
            if tool.path:
                extra.insert(0, f"{tool.path} path")
            line = (f"### {item.emoji or '🔨'} {instance_label(inst)}" + ("  ✅" if inst.id in equipped else "") + "\n"
                    f"{KIND_LABEL[tool.kind]}  ·  power **{stats.power}**" + "".join(f"  ·  {e}" for e in extra)
                    + f"\n-# {tool_effects.summary(tool.kind, stats.power, reg, tool.path, tool.stats)}"
                    + (f"  ·  ✨ {tool.ability_name}" if tool.ability_name else ""))
            if inst.id in equipped:
                accessory = button("Equipped", disabled=True)
            else:
                accessory = button("Equip", style=discord.ButtonStyle.primary, on_click=self._equip(inst.id))
            body.append(section(line, accessory=accessory))
        if len(instances) > MAX_SHOWN:
            body.append(text(f"-# …and {len(instances) - MAX_SHOWN} more tools (the equipped ones are shown first)."))
        body += [sep(), row(button("Upgrade", emoji="🔨", style=discord.ButtonStyle.primary, on_click=self._upgrades),
                            button("Enchant", emoji="📜", on_click=self._enchant),
                            button("Inventory", emoji="🎒", on_click=self._inventory))]
        return Page("Tools", body, accent=0xB8860B)

    def _equip(self, instance_id: int):
        async def go(interaction: discord.Interaction) -> None:
            instance = await self.user.instance(instance_id)
            if instance is None:
                raise CustomError("You don't own that tool.")
            skill = skill_for_tool(get_registry().item(instance.template_id).tool.kind)
            await equip(self.user, skill, instance.id)
            await self.refresh(interaction, f"Equipped **{instance_label(instance)}** for {skill}.")

        return go

    async def _upgrades(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "upgrade")

    async def _enchant(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "enchant")

    async def _inventory(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "inventory")
