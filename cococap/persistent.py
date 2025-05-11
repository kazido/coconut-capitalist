import discord
import asyncio


class PersistentView(discord.ui.View):
    def __init__(self, *, timeout=180):
        super().__init__(timeout=None)

    @discord.ui.button(label="Click me", custom_id="verify_button")
    async def verify(self, interaction: discord.Interaction):
        await interaction.response.send_message("Clicked!", ephemeral=True)
        await asyncio.sleep(1)
        await interaction.delete_original_response()
