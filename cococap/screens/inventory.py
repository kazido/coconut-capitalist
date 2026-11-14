import discord

from cococap.services.equipment import TOOL_FOR_SKILL
from cococap.services.inventory import instance_lines, inventory_lines
from cococap.ui import Page, Screen
from cococap.ui.components import button, row, sep, text
from cococap.user import User

PER_PAGE = 12


class InventoryScreen(Screen):
    id = "inventory"
    label = "Inventory"
    emoji = "🎒"
    description = "Your items and tools"
    links = ("tools", "enchant")

    def __init__(self, nav):
        super().__init__(nav)
        self.page = 0

    async def _equipped_ids(self) -> set[int]:
        ids = set()
        for skill in TOOL_FOR_SKILL:  # (every skill with a tool: pickaxe, axe, sword, rod and watering can)
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
        body += [sep(), row(button("Tools", emoji="🧰", style=discord.ButtonStyle.primary if instances else discord.ButtonStyle.secondary,
                                   on_click=self._tools),
                            button("Enchant", emoji="📜", on_click=self._enchant))]
        return Page("Inventory", body, accent=0x99B0A2)

    def _turn(self, step: int):
        async def turn(interaction: discord.Interaction) -> None:
            self.page += step
            await self.refresh(interaction)

        return turn

    async def _enchant(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "enchant")

    async def _tools(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "tools")
