import discord

from discord import Interaction, ButtonStyle

class Menu(discord.ui.View):
    def __init__(self, embed=None, timeout: float | None = 180):
        super().__init__(timeout=timeout)
        self.embed: discord.Embed = embed

    async def on_timeout(self) -> None:
        await self.clear_items()
        await self.stop()
        
    @discord.ui.button(label="Close", emoji="✖️", style=ButtonStyle.red, row=4)
    async def back(self, interaction: Interaction, button: discord.ui.Button):
        self.embed.color = discord.Color.dark_grey()
        self.embed.set_footer(text=f"Menu has been closed by {interaction.user.name}.")
        await self.clear_items()
        await self.stop()
        await interaction.response.edit_message(embed=self.embed, view=self)
        
class ParentMenu(Menu):
    def __init__(self, embed=None, timeout: float | None = 180):
        self.menus: list[Menu] = []
        self.current: int = 0
        super().__init__(embed, timeout)
        
    async def add_submenu(self, submenu: "SubMenu"):
        self.menus.append(submenu)
        
    async def move_forward(self):
        # Should be called whenever we move forward a menu
        self.current += 1
    
    async def move_backward(self):
        # Should be called whenever we move back a menu
        self.current -= 1
        
class SubMenu(Menu):
    # This is essentially our Node class where we store the embed, and the previous
    def __init__(self, embed=None, timeout: float | None = 180):
        super().__init__(timeout=timeout)
        self.embed: discord.Embed = embed
        
    @discord.ui.button(label="Back", emoji="🔙", style=ButtonStyle.gray, row=3)
    async def back(self, interaction: Interaction, button: discord.ui.Button):
        # Should edit the message and result in the 
        view: ParentMenu = button.view
        view.move_backward()
        prev = view.menus[view.current]
        await interaction.response.edit_message(embed=prev.embed, view=prev)
        


