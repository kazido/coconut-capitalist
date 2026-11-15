import discord

from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from cococap.registry import get_registry
from cococap.screens import open_screen
from utils.items.items import MAX_CHOICES, construct_embed, item_autocomplete

SKILLS = ["mining", "foraging", "fishing", "farming", "combat"]


class WikiCog(commands.Cog, name="Wiki"):
    """The wiki lives in the /play hub; this just opens it."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="wiki", description="How does everything work? Skills, fish, pets, tools and items.")
    @app_commands.describe(item="look up a specific item", category="or browse the items of a skill")
    @app_commands.choices(category=[Choice(name=s.title(), value=s) for s in SKILLS])
    @app_commands.autocomplete(item=item_autocomplete)
    async def wiki(self, interaction: discord.Interaction, item: str | None = None, category: Choice[str] | None = None):
        reg = get_registry()
        if item:
            found = reg.find_item(item)
            if found is None:
                return await interaction.response.send_message("I don't know that item. Try the autocomplete suggestions.", ephemeral=True)
            return await open_screen(interaction, "wiki", topic="items", skill=found.skill or "general", item=found.id)
        if category:
            return await open_screen(interaction, "wiki", topic="items", skill=category.value)
        await open_screen(interaction, "wiki")


async def setup(bot):
    await bot.add_cog(WikiCog(bot))
