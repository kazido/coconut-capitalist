import discord

from cococap.services.inventory import inventory_lines
from cococap.ui import Page, Screen
from cococap.ui.components import button, row, sep, text

PER_PAGE = 12


class InventoryScreen(Screen):
    id = "inventory"
    label = "Inventory"
    emoji = "🎒"
    description = "Your items"
    links = ("tools", "shop", "trade")

    def __init__(self, nav):
        super().__init__(nav)
        self.page = 0

    async def build(self) -> Page:
        lines = inventory_lines(await self.user.items())  # (tools live on the Tools page)
        body = [*self.note_block()]
        pages = max(1, -(-len(lines) // PER_PAGE))
        self.page = min(self.page, pages - 1)
        body.append(text("\n".join(lines[self.page * PER_PAGE : (self.page + 1) * PER_PAGE]) if lines else "You don't have any items yet. Get to it!"))
        if pages > 1:
            body.append(
                row(
                    button(emoji="◀️", on_click=self._turn(-1), disabled=self.page == 0),
                    button(f"{self.page + 1}/{pages}", disabled=True),
                    button(emoji="▶️", on_click=self._turn(1), disabled=self.page >= pages - 1),
                )
            )
        body += [sep(), row(button("Sell", emoji="💰", style=discord.ButtonStyle.success, disabled=not lines, on_click=self._sell),
                            button("Tools", emoji="🧰", on_click=self._tools),
                            button("Trade", emoji="🎁", on_click=self._trade))]
        return Page("Inventory", body, accent=0x99B0A2)

    def _turn(self, step: int):
        async def turn(interaction: discord.Interaction) -> None:
            self.page += step
            await self.refresh(interaction)

        return turn

    async def _sell(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "shop", mode="sell")

    async def _tools(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "tools")

    async def _trade(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "trade")
