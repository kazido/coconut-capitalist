import discord

from discord.ext import commands
from discord import app_commands
from discord.app_commands import Choice

from cococap.item_models import Master


class WikiCog(commands.Cog, name="Wiki"):
    def __init__(self, bot):
        self.bot = bot
        
        
    @app_commands.command(name="wiki", description="What is this item?")
    @app_commands.guilds(977351545966432306, 856915776345866240)
    @app_commands.describe(category="category of item")
    @app_commands.choices(
        category=[
            Choice(name="General", value=""),
            Choice(name="Mining", value="mining"),
            Choice(name="Foraging", value="foraging"),
        ]
    )
    async def wiki(self, interaction: discord.Interaction, category: Choice[str] | None):
        class WikiView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)
                select_menu = WikiSelect(category=category)

                self.add_item(select_menu)

            async def on_timeout(self):
                self.clear_items()
                self.stop()
                await interaction.edit_original_response(view=self)
                return

        class WikiSelect(discord.ui.Select):
            def __init__(self, category: str | None):
                super().__init__(placeholder="Select an item to view")
                query = Master.select()
                # If a category was specified, only show those results
                if category:
                    query = Master.select().where(Master.skill == category.value)
                for item in query:
                    item: Master
                    if item.emoji:
                        self.add_option(
                            label=item.display_name,
                            description=item.description,
                            emoji=discord.PartialEmoji.from_str(item.emoji),
                            value=item.item_id,
                        )

            async def callback(self, interaction: discord.Interaction):
                embed: discord.Embed = construct_embed(self.values[0], for_shop=False)
                await interaction.response.edit_message(embed=embed)
                return

        await interaction.response.send_message(view=WikiView())