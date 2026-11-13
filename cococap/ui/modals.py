"""Modals: a pop-up form. The hub uses them for "how many?" and "how much do you bet?"."""

from typing import Awaitable, Callable

import discord
from discord import ui

from .nav import report_error


class PromptModal(ui.Modal):
    """A one-field form. ``on_submit(interaction, text)`` runs with what the player typed."""

    def __init__(
        self,
        title: str,
        label: str,
        on_submit: Callable[[discord.Interaction, str], Awaitable[None]],
        *,
        default: str = "",
        placeholder: str = "",
        description: str | None = None,
        max_length: int = 20,
    ):
        super().__init__(title=title)
        self.field = ui.TextInput(default=default, placeholder=placeholder, max_length=max_length)
        self.add_item(ui.Label(text=label, component=self.field, description=description))
        self._handler = on_submit

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self._handler(interaction, self.field.value.strip())

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await report_error(interaction, error, "modal")
