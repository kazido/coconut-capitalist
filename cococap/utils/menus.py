import discord

from discord import Interaction, ButtonStyle
from logging import getLogger
from cococap.utils.messages import Cembed, button_check

log = getLogger(__name__)
log.setLevel(10)


class MenuHandler:
    def __init__(self, interaction: Interaction) -> None:
        self.interaction: Interaction = interaction
        self.menus: list[Menu] = []
        self.current: int = 0
        
    def add_menu(self, menu: "Menu"):
        self.menus.append(menu)
        menu.index = len(self.menus) - 1
        
    def move_forward(self):
        # Should be called whenever we move forward a menu
        log.debug("Menu handler moved forward.")
        self.current += 1
    
    def move_backward(self):
        # Should be called whenever we move back a menu
        log.debug("Menu handler moved backward.")
        self.current -= 1
        
    def get_current(self):
        return self.menus[self.current]
        
class Menu(discord.ui.View):
    def __init__(self,  handler: MenuHandler, embed=None):
        super().__init__()
        self.embed: discord.Embed = embed
        self.button = self.close
        self.index: int
        self.handler: MenuHandler = handler
        self.handler.add_menu(self)
        
    @property
    def index(self):
        """I am the 'index' property."""
        return self.__index
    
    @index.setter
    def index(self, index: int):
        self.__index = index
        if index != 0:
            self.remove_item(self.close)
        else:
            self.remove_item(self.back)

    async def on_timeout(self) -> None:
        self.clear_items()
        self.stop()
        
    @discord.ui.button(label="Close", emoji="✖️", style=ButtonStyle.red, row=4)
    async def close(self, interaction: Interaction, button: discord.ui.Button):
        if not await button_check(interaction, [self.handler.interaction.user.id]):
            return
        self.embed.color = discord.Color.dark_grey()
        self.embed.set_footer(text=f"Menu has been closed by {interaction.user.name}.")
        self.clear_items()
        self.stop()
        await interaction.response.edit_message(embed=self.embed, view=self)
        
    @discord.ui.button(label = "Back", emoji = "🔙", style = discord.ButtonStyle.gray, row=4)
    async def back(self, interaction: Interaction, button: discord.ui.Button):
        if not await button_check(interaction, [self.handler.interaction.user.id]):
            return
        self.handler.move_backward()
        menu = self.handler.get_current()
        await interaction.response.edit_message(embed=menu.embed, view=menu)
        


