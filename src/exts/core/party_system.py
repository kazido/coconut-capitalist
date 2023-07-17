import discord
import random
import peewee

from discord.ext import commands
from discord import app_commands
from src import models as m
from src import instance
from src.constants import PartyRoles, DiscordGuilds
from src.utils.user_manager import UserManager


class PartySystemCog(commands.Cog, name='PartySystem'):
    """Party up with other players."""

    def __init__(self, bot):
        self.bot = bot
        self.guild = instance.get_guild(DiscordGuilds.PRIMARY_GUILD.value)
        self.leader_role = discord.utils.get(
            self.guild.roles, 
            id=PartyRoles.PARTY_LEADER.value
            )

    # Party command group
    party = app_commands.Group(
        name="party", description="Party up with other players.")

    @party.command(name="list", description="See who is in your party.")
    async def list(self, interaction: discord.Interaction):
        """Lists the members of a player's party"""
        user = UserManager(interaction.user.id, interaction=interaction)

        error_embed = discord.Embed(title="Cannot list party.",
                                    description="",
                                    color=discord.Color.red())
        
        user_party_id = user.get_data("party_id")

        if not user_party_id:
            error_embed.description += "You are not in a party."
            await interaction.response.send_message(embed=error_embed)
            return

        # Query to find all users with the same party ID
        query = ((m.Users.party_id == user_party_id))
        query_executions = m.Users.select().where(query)

        embed = discord.Embed(title=":busts_in_silhouette: Party Members",
                              description="Your very own party! (Insert private channel mention here)",
                              color=discord.Color.from_rgb(84, 178, 209))

        party_members = [member for member in query_executions]
        for member in party_members:
            embed.description += f"\n:bust_in_silhouette: {getattr(member, 'name')}"
        await interaction.response.send_message(embed=embed)

    @party.command(name="create", description="Creates a private party, complete with a private party channel.")
    async def create(self, interaction: discord.Interaction):
        """Creates a unique party ID and adds user. Also creates a private party channel."""
        # Party leadership should be done through discord roles only.
        user = m.Users.initialize(interaction=interaction)

        if user.party_id:
            embed = discord.Embed(
                title="Cannot create party.",
                description="You are already in a party!",
                color=discord.Color.red())
            await interaction.response.send_message(embed=embed)
            return

        # Generate a random 4 digit ID
        def generate_party_id():
            party_id = random.randint(1000, 9999)
            try:
                # Reroll if the party ID already exists
                m.Users.select().where(m.Users.party_id == party_id).get()
                generate_party_id()
            except peewee.DoesNotExist:
                # Successfully rolled a unique party ID
                return party_id

        user.party_id = generate_party_id()
        user.save()

        # add the party leader role to the user
        await interaction.user.add_roles(self.leader_role)

        embed = discord.Embed(
            title="Party created!",
            description="Your party has been created! (Insert channel mention here)",
            color=discord.Color.green())
        await interaction.response.send_message(embed=embed)
        return

    @party.command(name="disband", description="Disbands your current party.")
    async def disband(self, interaction: discord.Interaction):
        """Removes user and everyone else from party and deletes party ID."""
        user = m.Users.initialize(interaction=interaction)

        error_embed = discord.Embed(
            title="Cannot disband party.",
            description="",
            color=discord.Color.red()
        )

        if not user.party_id:
            error_embed.description += "You are not in a party."
            await interaction.response.send_message(embed=error_embed)
            return

        elif not PartySystemCog.leader_role in interaction.user.roles:
            error_embed.description += "You are not the leader of your party!"
            await interaction.response.send_message(embed=error_embed)
            return

        # Query to find all users with the same party ID
        query = ((m.Users.party_id == user.party_id))
        query_executions = m.Users.select().where(query)
        party_members = [member for member in query_executions]

        # Go through every user in the party and set their party ID to null
        for member in party_members:
            member.party_id = None
            member.save()

        # Remove party leader role from user who used command
        await interaction.user.remove_roles(PartySystemCog.leader_role)

        success_embed = discord.Embed(
            title="Party successfully disbanded.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=success_embed)
        return

    @party.command(name="invite", description="Invite another user to your party.")
    async def invite(self, interaction: discord.Interaction, user: discord.User):
        """Invites specified user to a party, doesn't need to be registered."""
        user = m.Users.initialize(interaction=interaction)

        error_embed = discord.Embed(
            title=f"Cannot invite {user.display_name} to party.",
            description="",
            color=discord.Color.red()
        )

        if not user.party_id:
            error_embed.description += "You are not in a party."
            await interaction.response.send_message(embed=error_embed)
            return

        elif not PartySystemCog.leader_role in interaction.user.roles:
            error_embed.description += "You are not the leader of your party!"
            await interaction.response.send_message(embed=error_embed)
            return

        query = ((m.Users.party_id == user.party_id))
        query_execution = m.Users.select().where(query)
        party_members = [member for member in query_execution]
        
        
        
        success_embed = discord.Embed(
            title=f"{user.display_name} has joined the party!",
            description=f"Party size: {len(party_members)}",
            color=discord.Color.green()
        )

    @party.command(name="kick", description="Remove a pesky user from your party.")
    async def kick(self, interaction: discord.Interaction, user: discord.User):
        """Removes specified user from the party."""
        pass

    @party.command(name="promote", description="Promote a user in your party to leader.")
    async def promote(self, interaction: discord.Interaction):
        """Promotes a user as the party leader. Done exclusively through discord roles."""
        pass

    @party.command(name="leave", description="Leave your current party.")
    async def leave(self, interaction: discord.Interaction):
        """Leaves party if user isn't the leader."""
        pass


async def setup(bot):
    await bot.add_cog(PartySystemCog(bot))
