import asyncio
from discord.ext import commands
from ClassLibrary import *
import json
from Cogs.ErrorHandler import registered


def get_role_color(ctx):
    roles = ["Peasant", "Farmer", "Citizen", "Educated", "Cultured", "Weathered", "Wise", "Expert"]
    for role in roles:
        retrieve_role = discord.utils.get(ctx.guild.roles, name=role)
        if retrieve_role in ctx.author.roles:
            return retrieve_role.color
        else:
            pass


async def price_check(ctx, rank):
    user = User(ctx)
    if await user.check_balance('tokens') < rank.price:
        return False
    else:
        return True


class Ranks(commands.Cog):
    """Rank up for a higher wage!"""
    def __init__(self, bot):
        self.bot = bot

    @registered()
    @commands.command(name="Rank", description="Check your current rank and it's perks.")
    async def rank(self, ctx):
        ranks = [peasant, farmer, citizen, educated, cultured, weathered, wise, expert]
        user_role = get_role(ctx)
        embed = discord.Embed(
            title=f"Current Rank: *{user_role.name}* {user_role.emoji}",
            color=get_role_color(ctx)
        )
        if user_role.perms[0] is not None:
            perms = ', '.join(user_role.perms)
        else:
            perms = "This rank has no special perks."
        embed.add_field(name="Perks", value=perms)
        embed.add_field(name="Wage", value=f"{'{:,}'.format(user_role.wage)} bits")
        rank = 0
        for index, x in enumerate(ranks):
            if x.name.capitalize() == user_role.name:
                rank = index
        embed.add_field(name="Next Rank", value=f"{ranks[rank + 1].name} {ranks[rank + 1].emoji}"
                                                f" | Cost: **{ranks[rank + 1].price}** tokens",
                        inline=False)
        embed.set_footer(text=f"User: {ctx.author.name}")
        embed.set_thumbnail(url=ctx.author.display_avatar)
        await ctx.send(embed=embed)

    @registered()
    @commands.command(name="Rankup", description="Spend tokens to move on to the next rank!", brief="-rankup")
    async def rankup(self, ctx):
        user = User(ctx)
        # Checking to see what the highest role they have is
        classes = [peasant, farmer, citizen, educated, cultured, weathered, wise, expert]
        next_role = None
        for index, role in enumerate(classes):
            retrieve_role = discord.utils.get(ctx.guild.roles, name=role.name.capitalize())
            if retrieve_role in ctx.author.roles:
                if index == len(classes) - 1:
                    embed = discord.Embed(
                        title="Max rank!",
                        description="You are already at the max rank, "
                                    "so you can't rank up any further!",
                        color=discord.Color.red()
                    )
                    await ctx.send(embed=embed)
                    return
                next_role = classes[index+1]
                role_to_remove = retrieve_role
                role_to_add = discord.utils.get(ctx.guild.roles, name=str(next_role.name).capitalize())
                break
            else:
                pass

        if await price_check(ctx, next_role):
            class RolePurchaseButtons(discord.ui.View):
                def __init__(self, *, timeout=180):
                    super().__init__(timeout=timeout)

                @discord.ui.button(label=f"{'{:,}'.format(next_role.price)} tokens", style=discord.ButtonStyle.green)
                async def green_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user != ctx.author:
                        return
                    else:
                        await ctx.author.add_roles(role_to_add)
                        await ctx.author.remove_roles(role_to_remove)
                        await user.update_tokens(-next_role.price)
                        purchased_embed = discord.Embed(
                            title="Purchased!",
                            description=f"You are now rank: **{next_role.name}** {next_role.emoji}!",
                            color=discord.Color.green()
                        )
                        purchased_embed.set_footer(text=f"User: {ctx.author.name}")
                        await interaction.response.edit_message(embed=purchased_embed, view=None)

                @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
                async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    for child in self.children:
                        child.label = ":("
                        child.disabled = True
                    if interaction.user != ctx.author:
                        return
                    cancel_embed = discord.Embed(
                        title=f"Cancelled rankup to {next_role.name} {next_role.emoji}",
                        description="Unfortunate. Maybe you'll rank up later?",
                        color=discord.Color.red()
                    )
                    cancel_embed.add_field(name="Hypothetical Wage", value=f"{'{:,}'.format(next_role.wage)} bits")
                    cancel_embed.set_footer(text="You WOULD have received a new name color.")
                    await interaction.response.edit_message(embed=cancel_embed, view=self)
                    await asyncio.sleep(2)
                    await message.delete()
        else:
            class RolePurchaseButtons(discord.ui.View):
                def __init__(self, *, timeout=180):
                    super().__init__(timeout=timeout)

                @discord.ui.button(label=f"{'{:,}'.format(next_role.price)} tokens",
                                   style=discord.ButtonStyle.red, disabled=True)
                async def red_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    pass

        embed = discord.Embed(
            title=f"{next_role.name} {next_role.emoji}",
            description=next_role.description,
            color=role_to_add.color
        )
        embed.add_field(name="Wage", value=f"{'{:,}'.format(next_role.wage)} bits")
        embed.set_footer(text="You will also receive a new name color.")
        message = await ctx.send(embed=embed, view=RolePurchaseButtons())


async def setup(bot):
    await bot.add_cog(Ranks(bot))
