import discord

from discord import Interaction, ButtonStyle
from logging import getLogger

from cococap.utils.messages import button_check

log = getLogger(__name__)
log.setLevel(10)


class MenuHandler:
    def __init__(self, interaction: Interaction) -> None:
        self.interaction: Interaction = interaction
        self.menus: list[Menu] = []  # Our list of menus we can view
        self.current: int = 0  # The index of our currently selected menu

    def add_menu(self, menu: "Menu"):
        # Adds a menu to the handler for navigation
        self.menus.append(menu)

    def move_forward(self) -> "Menu":
        # Should be called whenever we move forward a menu
        log.debug("Menu handler moved forward.")
        self.current += 1
        if self.current > len(self.menus) - 1:
            self.current = 0
        return self._get_current()

    def move_backward(self) -> "Menu":
        # Should be called whenever we move back a menu
        log.debug("Menu handler moved backward.")
        self.current -= 1
        if self.current < 0:
            self.current = len(self.menus) - 1
        return self._get_current()

    def move_to(self, menu_id: str) -> "Menu":
        # Can be called when you want to move to a menu with an ID
        # Useful if the menus are not in order
        log.debug(f"Menu handler moved to menu with id: {menu_id}")
        for i, menu in enumerate(self.menus):
            if menu.id == menu_id:
                self.current = i
        return self._get_current()

    def move_home(self) -> "Menu":
        # Can be called to take the menu to the original menu (main menu)
        log.debug("Menu handler moved home.")
        self.current = 0
        return self._get_current()

    def _get_current(self) -> "Menu":
        # Retrieves an updated menu
        return self.menus[self.current]


class Menu(discord.ui.View):
    """
    A Menu is a discord View that stores an embed.
    Multiple menus can be stored and navigated through using a MenuHandler.
    A Menu can have an id for precise navigation. 
    If no id is given the menu can only be accessed by linearly moving
    through the list of menus.
    """
    def __init__(self, handler: MenuHandler, id: str = None, embed: discord.Embed = None):
        super().__init__()
        self.id: str = id
        self.embed: discord.Embed = embed
        self.handler: MenuHandler = handler
        self.handler.add_menu(self)

    async def on_timeout(self) -> None:
        self.clear_items()
        self.stop()

    @discord.ui.button(label="Back", emoji="🔙", style=discord.ButtonStyle.gray, row=4)
    async def back(self, interaction: Interaction, button: discord.ui.Button):
        if not await button_check(interaction, [self.handler.interaction.user.id]):
            return
        self.handler.move_backward()
        menu = self.handler.get_current()
        await interaction.response.edit_message(embed=menu.embed, view=menu)
        
class PaginationMenu(Menu):
    """
    A PaginationMenu is similar to a menu, except it provides
    buttons to linearly move through the MenuHandler.
    """
    def __init__(self, handler: MenuHandler, embed: discord.Embed = None):
        super().__init__(handler, id, embed)
        # Remove the back button because we just move left and right
        self.remove_item(self.back)
    
    @discord.ui.button(emoji="✖️", style=ButtonStyle.red, row=4)
    async def close(self, interaction: Interaction, button: discord.ui.Button):
        if not await button_check(interaction, [self.handler.interaction.user.id]):
            return
        self.embed.color = discord.Color.dark_grey()
        self.embed.set_footer(text=f"Menu has been closed by {interaction.user.name}.")
        self.clear_items()
        self.stop()
        await interaction.response.edit_message(embed=self.embed, view=self)


class MainMenu(Menu):
    """
    MainMenu is intended to function as a home menu for the menu handler.
    The only difference from a normal Menu is that it has a close button
    which closes the whole menu rather than a back button.
    """

    def __init__(self, handler: MenuHandler, embed: discord.Embed = None):
        super().__init__(handler, "home", embed)
        # Remove the back button because we are the main menu
        self.remove_item(self.back)

    @discord.ui.button(label="Close", emoji="✖️", style=ButtonStyle.red, row=4)
    async def close(self, interaction: Interaction, button: discord.ui.Button):
        if not await button_check(interaction, [self.handler.interaction.user.id]):
            return
        self.embed.color = discord.Color.dark_grey()
        self.embed.set_footer(text=f"Menu has been closed by {interaction.user.name}.")
        self.clear_items()
        self.stop()
        await interaction.response.edit_message(embed=self.embed, view=self)
