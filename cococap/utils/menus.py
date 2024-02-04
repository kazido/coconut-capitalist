import discord

from discord import Interaction, ButtonStyle
from logging import getLogger

log = getLogger(__name__)
log.setLevel(10)

class Menu(discord.ui.View):
    def __init__(self, embed=None, timeout: float | None = 180):
        super().__init__(timeout=timeout)
        self.embed: discord.Embed = embed

    async def on_timeout(self) -> None:
        self.clear_items()
        self.stop()
        
    @discord.ui.button(label="Close", emoji="✖️", style=ButtonStyle.red, row=4)
    async def close(self, interaction: Interaction, button: discord.ui.Button):
        self.embed.color = discord.Color.dark_grey()
        self.embed.set_footer(text=f"Menu has been closed by {interaction.user.name}.")
        self.clear_items()
        self.stop()
        await interaction.response.edit_message(embed=self.embed, view=self)
        
class ParentMenu(Menu):
    def __init__(self, embed=None, timeout: float | None = 180):
        self.menus: list[Menu] = []
        self.current: int = 0
        super().__init__(embed, timeout)
        
    def add_submenu(self, submenu: "SubMenu"):
        self.menus.append(submenu)
        
    def move_forward(self):
        # Should be called whenever we move forward a menu
        log.debug("Moved forward.")
        self.current += 1
    
    def move_backward(self):
        # Should be called whenever we move back a menu
        log.debug("Moved backward.")
        self.current -= 1
        
class SubMenu(Menu):
    # This is essentially our Node class where we store the embed, and the previous
    def __init__(self, embed=None, timeout: float | None = 180):
        super().__init__(timeout=timeout)
        self.embed: discord.Embed = embed
        print(self.children)
        
    @discord.ui.button(label="Back", emoji="🔙", style=ButtonStyle.gray, row=3)
    async def back(self, interaction: Interaction, button: discord.ui.Button):
        # Should edit the message and result in the 
        view: ParentMenu = button.view
        view.move_backward()
        prev = view.menus[view.current]
        await interaction.response.edit_message(embed=prev.embed, view=prev)
        


