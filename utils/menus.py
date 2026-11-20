import discord

from discord import Interaction, ButtonStyle
from logging import getLogger

log = getLogger(__name__)


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

