import discord

from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from cococap.registry import get_registry
from utils.items.items import MAX_CHOICES, construct_embed, item_autocomplete

SKILLS = ["mining", "foraging", "fishing", "farming", "combat"]


class WikiSelect(discord.ui.Select):
    def __init__(self, items):
        super().__init__(
            placeholder="Select an item to view",
            options=[
                discord.SelectOption(
                    label=item.name,
                    description=item.description[:100] or None,
                    emoji=discord.PartialEmoji.from_str(item.emoji) if item.emoji else None,
                    value=item.id,
                )
                for item in items[:MAX_CHOICES]
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=construct_embed(self.values[0]))


class WikiView(discord.ui.View):
    def __init__(self, items, owner: discord.abc.User):
        super().__init__(timeout=60)
        self.owner = owner
        self.message: discord.Message | None = None
        self.add_item(WikiSelect(items))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.owner.id

    async def on_timeout(self):
        self.clear_items()
        self.stop()
        if self.message:
            try:
                await self.message.edit(view=None)
            except discord.HTTPException:
                pass


class WikiCog(commands.Cog, name="Wiki"):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="wiki", description="What is this item?")
    @app_commands.describe(
        item="look up a specific item", category="or browse the items of a skill"
    )
    @app_commands.choices(category=[Choice(name=s.title(), value=s) for s in SKILLS])
    @app_commands.autocomplete(item=item_autocomplete)
    async def wiki(
        self,
        interaction: discord.Interaction,
        item: str | None = None,
        category: Choice[str] | None = None,
    ):
        reg = get_registry()
        if item:
            if reg.find_item(item) is None:
                return await interaction.response.send_message(
                    "I don't know that item. Try the autocomplete suggestions.", ephemeral=True
                )
            return await interaction.response.send_message(embed=construct_embed(item))

        items = sorted(
            (i for i in reg.items.values() if not category or i.skill == category.value),
            key=lambda i: (i.skill or "", i.rarity, i.name),
        )
        if not items:
            return await interaction.response.send_message("Nothing here yet.", ephemeral=True)
        view = WikiView(items, interaction.user)
        suffix = f" (showing {MAX_CHOICES} of {len(items)}; use `item` to search)" if len(items) > MAX_CHOICES else ""
        await interaction.response.send_message(f"Pick an item{suffix}", view=view)
        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(WikiCog(bot))
