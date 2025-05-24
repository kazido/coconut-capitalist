from typing import Any
import discord

from discord import Interaction, ButtonStyle
from logging import getLogger

log = getLogger(__name__)


class Button(discord.ui.Button):
    def __init__(self, interaction: Interaction, menu: "Menu"):
        self.interaction = interaction
        self.menu = menu
        super().__init__(label=menu.name, emoji=menu.emoji, style=discord.ButtonStyle.blurple)

    async def callback(self, interaction: Interaction) -> Any:
        menu = self.menu.handler.move_to(self.menu.custom_id)
        await interaction.response.edit_message(embed=menu.embed, view=menu)


class CloseButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Close", emoji="✖️", style=ButtonStyle.red)

    async def callback(self, interaction):
        self.view.embed.color = discord.Color.dark_grey()
        self.view.embed.set_footer(text=f"Menu has been closed by {interaction.user.name}.")
        self.view.clear_items()
        self.view.stop()
        await interaction.response.edit_message(embed=self.view.embed, view=self.view)


class MenuHandler:
    def __init__(self, interaction: Interaction) -> None:
        self.interaction: Interaction = interaction
        self.menus: list[Menu] = []  # Our list of menus we can view
        self.current: int = 0  # The index of our currently selected menu

    def add_menu(self, menu: "Menu"):
        # Adds a menu to the handler for navigation
        self.menus.append(menu)
        menu.handler = self

    def _generate_button(self, menu: "Menu"):
        return Button(self.interaction, menu)

    def move_forward(self) -> "Menu":
        # Should be called whenever we move forward a menu
        log.debug("Menu handler moved forward.")
        self.current += 1
        if self.current > len(self.menus) - 1:
            self.current = 0
        return self.get_current()

    def move_backward(self) -> "Menu":
        # Should be called whenever we move back a menu
        log.debug("Menu handler moved backward.")
        self.current -= 1
        if self.current < 0:
            self.current = len(self.menus) - 1
        return self.get_current()

    def move_to(self, menu_id: str) -> "Menu":
        # Can be called when you want to move to a menu with an ID
        # Useful if the menus are not in order
        log.debug(f"Menu handler moved to menu with id: {menu_id}")
        for i, menu in enumerate(self.menus):
            if menu.custom_id == menu_id:
                self.current = i
        return self.get_current()

    def move_home(self) -> "Menu":
        # Can be called to take the menu to the original menu (main menu)
        log.debug("Menu handler moved home.")
        self.current = 0
        return self.get_current()

    def get_current(self) -> "Menu":
        # Retrieves an updated menu
        return self.menus[self.current]


class Menu(discord.ui.View):
    """
    A Menu is a discord View that stores an embed.
    Menus are hierarchical: you can move forward/backward through menus (like a stack or tree).
    At the highest level, you can close the menu.
    """

    def __init__(self, embed: discord.Embed, emoji: discord.PartialEmoji = None):
        super().__init__()
        self.custom_id: str = embed.title.lower()
        self.name: str = embed.title
        self.emoji: discord.PartialEmoji = emoji
        self.embed: discord.Embed = embed
        self.handler: MenuHandler = None
        self.add_item(CloseButton())

    async def on_timeout(self) -> None:
        self.clear_items()
        self.stop()

    async def interaction_check(self, interaction):
        return interaction.user == self.handler.interaction.user


class PaginationMenu(Menu):
    """
    A PaginationMenu is a Menu with left/right navigation for linear paging (carousel style).
    No back/forward hierarchy, just left/right and close.
    """

    def __init__(self, embed: discord.Embed = None):
        super().__init__(embed=embed)

    @discord.ui.button(label="Prev", emoji="⬅️", style=ButtonStyle.blurple)
    async def prev(self, interaction: Interaction, button: discord.ui.Button):
        menu = self.handler.move_backward()
        await interaction.response.edit_message(embed=menu.embed, view=menu)

    @discord.ui.button(label="Next", emoji="➡️", style=ButtonStyle.blurple)
    async def next(self, interaction: Interaction, button: discord.ui.Button):
        menu = self.handler.move_forward()
        await interaction.response.edit_message(embed=menu.embed, view=menu)


class DirectMenu(Menu):
    """
    A DirectMenu allows direct navigation to any menu via buttons or a select menu.
    No forward/backward, just direct access to any menu in the handler.
    """

    def __init__(
        self, embed: discord.Embed, emoji: discord.PartialEmoji = None, use_select: bool = False
    ):
        super().__init__(embed=embed, emoji=emoji)
        self.use_select = use_select

    def update_buttons(self):
        # Call this after handler is set and menus are added
        if self.use_select:
            self.add_item(MenuSelect(self))
        else:
            for menu in self.handler.menus:
                if menu is not self:
                    self.add_item(DirectNavButton(self, menu))


class DirectNavButton(discord.ui.Button):
    def __init__(self, parent: DirectMenu, target_menu: Menu):
        super().__init__(
            label=target_menu.name, emoji=target_menu.emoji, style=discord.ButtonStyle.blurple
        )
        self.parent = parent
        self.target_menu = target_menu

    async def callback(self, interaction: Interaction):
        menu = self.parent.handler.move_to(self.target_menu.custom_id)
        await interaction.response.edit_message(embed=menu.embed, view=menu)


class MenuSelect(discord.ui.Select):
    def __init__(self, parent: DirectMenu):
        options = [
            discord.SelectOption(label=menu.name, value=menu.custom_id)
            for menu in parent.handler.menus
            if menu is not parent
        ]
        super().__init__(placeholder="Select a menu...", options=options, row=0)
        self.parent = parent

    async def callback(self, interaction: Interaction):
        menu = self.parent.handler.move_to(self.values[0])
        await interaction.response.edit_message(embed=menu.embed, view=menu)
