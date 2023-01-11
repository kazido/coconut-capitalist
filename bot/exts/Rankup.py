import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from ClassLibrary import RequestUser, ranks
from cogs.ErrorHandler import registered


class Ranks(commands.Cog):
    """Rank up for a higher wage!"""

    def __init__(self, bot):
        self.bot = bot

    @registered()
    @app_commands.guilds(856915776345866240, 977351545966432306)
    @app_commands.command(name="rank", description="Check your current rank and it's perks.")
    async def rank(self, interaction: discord.Interaction):
        # Grabs the ranks from the class library and determines which discord role the user has
        user = RequestUser(interaction.user.id, interaction=interaction)
        embed = discord.Embed(title=f"Current Rank: *{user.rank.capitalize()}* {ranks[user.rank]['emoji']}",
                              color=discord.Color.from_str("#"+ranks[user.rank]['color']))
        # If the role has permissions, display them
        if ranks[user.rank]['perks']:
            perms = ', '.join(ranks[user.rank]['perks'])
        else:
            perms = "This rank has no special perks."
        embed.add_field(name="Perks", value=perms)
        embed.add_field(name="Wage", value=f"{'{:,}'.format(ranks[user.rank]['wage'])} bits")
        # Finds the next rank in the list and displays the price of the next rank in the embed
        rank = 0
        try:
            for index, rank in enumerate(ranks):
                if rank == user.rank:
                    next_rank_name = list(ranks.keys())[index+1].capitalize()
                    next_rank = ranks[list(ranks.keys())[index+1]]
                    embed.add_field(name="Next Rank",
                                    value=f"{next_rank_name} "
                                          f"{next_rank['emoji']}"
                                          f" | Cost: **{next_rank['price']}** tokens",
                                    inline=False)
        except IndexError:
            embed.add_field(name="Max rank achieved", value="You've reached the max rank! Nice job!", inline=False)
        embed.set_footer(text=f"User: {interaction.user.name}")
        embed.set_thumbnail(url=interaction.user.display_avatar)
        await interaction.response.send_message(embed=embed)

    @registered()
    @app_commands.guilds(856915776345866240, 977351545966432306)
    @app_commands.command(name="rankup", description="Spend tokens to move on to the next rank!")
    async def rankup(self, interaction: discord.Interaction):
        user = RequestUser(interaction.user.id, interaction=interaction)
        rankup_embed = next_rank = None
        for index, rank in enumerate(ranks):  # Loop through ranks to find next rank
            if rank == user.rank:
                next_rank_name = list(ranks.keys())[index + 1].capitalize()
                next_rank = ranks[list(ranks.keys())[index + 1]]
                if index == len(ranks):
                    embed = discord.Embed(
                        title="Max rank!",
                        description="You are already at the max rank, "
                                    "so you can't rank up any further!",
                        color=discord.Color.red())
                    await interaction.response.send_message(embed=embed)
                    return
                else:
                    rankup_embed = discord.Embed(
                        title=f"{next_rank_name} {next_rank['emoji']}",
                        description=next_rank['description'],
                        color=discord.Color.from_str(f"#{next_rank['color']}")
                    )
                    rankup_embed.add_field(name="Wage", value=f"{'{:,}'.format(next_rank['wage'])} bits")
                    rankup_embed.set_footer(text="You will also receive a new name color.")
                role_to_add = discord.utils.get(interaction.guild.roles, name=next_rank_name)
                role_to_remove = discord.utils.get(interaction.guild.roles, name=user.rank.capitalize())
                break

        if user.instance.tokens >= next_rank['price']:
            class RolePurchaseButtons(discord.ui.View):
                def __init__(self, *, timeout=180):
                    super().__init__(timeout=timeout)

                @discord.ui.button(label=f"{'{:,}'.format(next_rank['price'])} tokens",
                                   style=discord.ButtonStyle.green)
                async def green_button(self, green_button_interaction: discord.Interaction, button: discord.ui.Button):
                    if green_button_interaction.user != interaction.user:
                        return
                    else:
                        purchased_embed = discord.Embed(
                            title="Purchased!",
                            description=f"You are now rank: **{next_rank_name}** "
                                        f"{next_rank['emoji']}!",
                            color=discord.Color.green()
                        )
                        purchased_embed.set_footer(text=f"User: {green_button_interaction.user.name}")
                        await interaction.edit_original_response(embed=purchased_embed, view=None)
                        await green_button_interaction.user.add_roles(role_to_add)
                        await green_button_interaction.user.remove_roles(role_to_remove)
                        user.update_tokens(-next_rank['price'])

                @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
                async def cancel_button(self, cancel_interaction: discord.Interaction, button: discord.ui.Button):
                    for child in self.children:
                        child.label = ":("
                        child.disabled = True
                    if cancel_interaction.user != interaction.user:
                        return
                    cancel_embed = discord.Embed(
                        title=f"Cancelled rankup to {next_rank_name} "
                              f"{next_rank['emoji']}",
                        description="Unfortunate. Maybe you'll rank up later?",
                        color=discord.Color.red()
                    )
                    cancel_embed.add_field(name="Hypothetical Wage",
                                           value=f"{'{:,}'.format(next_rank['wage'])} bits")
                    cancel_embed.set_footer(text="You WOULD have received a new name color.")
                    await cancel_interaction.response.edit_message(embed=cancel_embed, view=self)
                    await asyncio.sleep(2)
                    await interaction.delete_original_response()
                    user.__del__()
        else:
            class RolePurchaseButtons(discord.ui.View):
                def __init__(self, *, timeout=180):
                    super().__init__(timeout=timeout)

                @discord.ui.button(label=f"{'{:,}'.format(next_rank['price'])} tokens",
                                   style=discord.ButtonStyle.red, disabled=True)
                async def red_button(self, cant_afford_interaction: discord.Interaction, button: discord.ui.Button):
                    pass
        await interaction.response.send_message(embed=rankup_embed, view=RolePurchaseButtons())


async def setup(bot):
    await bot.add_cog(Ranks(bot))
