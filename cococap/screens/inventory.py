import discord

from cococap.errors import CustomError
from cococap.registry import get_registry
from cococap.services.equipment import equip, skill_for_tool
from cococap.services.inventory import instance_label, instance_lines, inventory_lines
from cococap.ui import Page, Screen
from cococap.ui.components import button, row, select, sep, text
from cococap.user import User

PER_PAGE = 12
TOOL_SKILLS = ("mining", "foraging", "combat", "fishing")


class InventoryScreen(Screen):
    id = "inventory"
    label = "Inventory"
    emoji = "🎒"
    description = "Your items and tools; equip a tool here"
    links = ("upgrade",)

    def __init__(self, nav):
        super().__init__(nav)
        self.page = 0

    async def _equipped_ids(self) -> set[int]:
        ids = set()
        for skill in TOOL_SKILLS:
            equipped = (await self.user.skill(skill)).equipped_instance_id
            if equipped is not None:
                ids.add(equipped)
        return ids

    async def build(self) -> Page:
        items = await self.user.items()
        instances = await self.user.instances()
        equipped = await self._equipped_ids()
        lines = instance_lines(instances, equipped) + inventory_lines(items)
        body = [*self.note_block()]
        if not lines:
            body.append(text("You don't have any items yet. Get to it!"))
            return Page("Inventory", body, accent=0x99B0A2)

        pages = max(1, -(-len(lines) // PER_PAGE))
        self.page = min(self.page, pages - 1)
        body.append(text("\n".join(lines[self.page * PER_PAGE : (self.page + 1) * PER_PAGE])))
        if pages > 1:
            body.append(
                row(
                    button(emoji="◀️", on_click=self._turn(-1), disabled=self.page == 0),
                    button(f"{self.page + 1}/{pages}", disabled=True),
                    button(emoji="▶️", on_click=self._turn(1), disabled=self.page >= pages - 1),
                )
            )
        if instances:
            reg = get_registry()
            # A menu allows one default and 25 options, and you have a tool equipped per skill: so no defaults
            # (equipped tools say so in their description), and the equipped ones come first if there are many.
            shown = sorted(instances, key=lambda i: i.id not in equipped)[:25]
            options = [
                discord.SelectOption(
                    label=instance_label(i)[:100],
                    value=str(i.id),
                    emoji=reg.item(i.template_id).emoji or None,
                    description="Equipped" if i.id in equipped else None,
                )
                for i in shown
            ]
            body += [sep(), row(select("Equip a tool...", options, self._equip)),
                     row(button("Upgrade tools", emoji="🔨", on_click=self._upgrades))]
        return Page("Inventory", body, accent=0x99B0A2)

    def _turn(self, step: int):
        async def turn(interaction: discord.Interaction) -> None:
            self.page += step
            await self.refresh(interaction)

        return turn

    async def _upgrades(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "upgrade")

    async def _equip(self, interaction: discord.Interaction, values: list[str]) -> None:
        instance = await self.user.instance(int(values[0]))
        if instance is None:
            raise CustomError("You don't own that tool.")
        kind = get_registry().item(instance.template_id).tool.kind
        skill = skill_for_tool(kind)
        await equip(self.user, skill, instance.id)
        await self.refresh(interaction, f"Equipped **{instance_label(instance)}** for {skill}.")
