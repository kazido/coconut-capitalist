"""Small building blocks shared by every cog's views.

Cogs should not re-implement "only the person who ran the command may click", timeouts that clean up
after themselves, or yes/no confirmations.
"""

import discord


class OwnedView(discord.ui.View):
    """A view only `owner` can use. On timeout its buttons are removed from the message.

    Set ``view.message`` after sending (``await view.attach(interaction)`` does it for you) so the
    timeout handler can edit it.
    """

    def __init__(self, owner: discord.abc.User, *, timeout: float | None = 180):
        super().__init__(timeout=timeout)
        self.owner = owner
        self.message: discord.Message | discord.InteractionMessage | None = None

    async def attach(self, interaction: discord.Interaction) -> None:
        """Remember the message the view was sent as (call after the initial response)."""
        self.message = await interaction.original_response()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner.id:
            return True
        await interaction.response.send_message("This isn't your menu.", ephemeral=True)
        return False

    async def on_timeout(self) -> None:
        self.clear_items()
        self.stop()
        if self.message is not None:
            try:
                await self.message.edit(view=None)
            except discord.HTTPException:
                pass  # message deleted or interaction token expired: nothing to clean up


class ConfirmView(OwnedView):
    """Yes/No prompt. ``await ConfirmView.ask(interaction, "Sell 5 apples?")`` -> bool."""

    def __init__(self, owner: discord.abc.User, *, timeout: float = 60):
        super().__init__(owner, timeout=timeout)
        self.value: bool | None = None

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        self.stop()
        await interaction.response.edit_message(view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        self.stop()
        await interaction.response.edit_message(view=None)

    @classmethod
    async def ask(cls, interaction: discord.Interaction, text: str) -> bool:
        """Show the prompt (ephemeral) and wait. A timeout counts as "no"."""
        view = cls(interaction.user)
        await interaction.response.send_message(text, view=view, ephemeral=True)
        await view.wait()
        return bool(view.value)
