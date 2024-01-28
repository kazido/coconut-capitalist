import discord

from discord import Interaction, ButtonStyle


class Menu(discord.ui.View):
    def __init__(self, embed=None, prev_menu=None, timeout: float | None = 180):
        super().__init__(timeout=timeout)
        self.embed: discord.Embed = embed
        self.prev_menu: Menu = prev_menu
        if self.prev_menu is None:
            self.remove_item(self.back_button)
        
    async def on_timeout(self) -> None:
        await self.stop()
        
    @discord.ui.button(label="Back", emoji="🔙", style=ButtonStyle.gray, row=4)
    async def back_button(self, interaction: Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=self.prev_menu.embed, view=self.prev_menu)