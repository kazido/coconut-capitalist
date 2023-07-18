from typing import Optional
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
    # Party up with other players.

    def __init__(self, bot):
        self.bot = bot
        self.guild = instance.get_guild(DiscordGuilds.PRIMARY_GUILD.value)
        self.leader_role = discord.utils.get(
            self.guild.roles,
            id=PartyRoles.PARTY_LEADER.value
        )

    # Party command group
    party = app_commands.Group(
        name="party",
        description="Party up with other players.",
        guild_ids=[DiscordGuilds.PRIMARY_GUILD.value]
    )

    # Lists the members of a player's party
    @party.command(name="list", description="See who is in your party.")
    async def list(self, interaction: discord.Interaction):
        user = UserManager(interaction.user.id, interaction=interaction)
        user_party_id = user.get_data("party_id")

        if not user_party_id:
            embed = discord.Embed(
                title="Cannot list party.",
                description="You are not currently in a party.",
                color=discord.Color.red())
            await interaction.response.send_message(embed=embed)
            return

        # Query to find all users with the same party ID
        query = (m.Users.party_id == user_party_id)
        query_executions = m.Users.select().where(query)
        party_members = [member for member in query_executions]

        # Get the party channel
        party_channel = discord.utils.get(
            interaction.guild.channels, id=user.get_data('party_channel_id'))

        embed = discord.Embed(
            title=":busts_in_silhouette: Party Members",
            description=f"Your very own party, complete with a channel! {party_channel.mention}",
            color=discord.Color.from_rgb(84, 178, 209))

        for member in party_members:
            discord_member = discord.utils.get(
                interaction.guild.members, id=member.user_id)
            if self.leader_role in discord_member.roles:
                embed.description += f"\n:trident: {getattr(member, 'name')}"
            else:
                embed.description += f"\n:bust_in_silhouette: {getattr(member, 'name')}"
        await interaction.response.send_message(embed=embed)

    # Creates a unique party ID and adds user. Also creates a private party channel.
    @party.command(name="create", description="Creates a private party, complete with a private party channel.")
    async def create(self, interaction: discord.Interaction):
        # Party leadership should be done through discord roles only.
        user = UserManager(interaction.user.id, interaction=interaction)
        user_party_id = user.get_data("party_id")

        if user_party_id:
            embed = discord.Embed(
                title="Cannot create a party.",
                description="You are already in a party!",
                color=discord.Color.red()
            )
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

        user_party_id = generate_party_id()

        party_role = await interaction.guild.create_role(name=f"Party {user_party_id}", reason="Party created.")
        await interaction.user.add_roles(party_role)

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            party_role: discord.PermissionOverwrite(read_messages=True)
        }

        party_channels_category = discord.utils.get(
            interaction.guild.categories, id=1130405873475387502)
        party_channel = await interaction.guild.create_text_channel(name=f"💠︱{interaction.user.nick}'s-party",
                                                                    overwrites=overwrites,
                                                                    category=party_channels_category)
        party_channel_id = party_channel.id
        user.update_data('party_channel_id', party_channel_id)
        user.update_data("party_id", user_party_id)
        user.save()

        # add the party leader role to the user
        await interaction.user.add_roles(self.leader_role)

        embed = discord.Embed(
            title="Party created!",
            description=f"Your party has been created! {party_channel.mention}",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
        return

    # Removes user and everyone else from party and deletes party ID.
    @party.command(name="disband", description="Disbands your current party.")
    async def disband(self, interaction: discord.Interaction):
        user = UserManager(interaction.user.id, interaction=interaction)
        user_party_id = user.get_data("party_id")

        error_embed = discord.Embed(
            title="Cannot disband party.",
            color=discord.Color.red()
        )

        if not user_party_id:
            error_embed.description = "You are not in a party."
            await interaction.response.send_message(embed=error_embed)
            return

        elif not self.leader_role in interaction.user.roles:
            error_embed.description = "You are not the leader of your party!"
            await interaction.response.send_message(embed=error_embed)
            return

        # Query to find all users with the same party ID
        query = ((m.Users.party_id == user_party_id))
        query_executions = m.Users.select().where(query)
        party_members = [member for member in query_executions]

        party_role = discord.utils.get(
            interaction.guild.roles, name=f"Party {user_party_id}")
        party_channel = discord.utils.get(
            interaction.guild.channels, id=user.get_data('party_channel_id'))

        # Go through every user in the party and clear their party data
        for member in party_members:
            # Remove the party role
            discord_member = discord.utils.get(
                interaction.guild.members, id=member.user_id)
            await discord_member.remove_roles(party_role)
            # Clear the party data in the database
            member.party_id = None
            member.party_channel_id = None
            member.save()

        # Remove party leader role from user who used command
        await interaction.user.remove_roles(self.leader_role)

        # Delete party role and channel from discord guild
        await party_role.delete()
        await party_channel.delete()

        success_embed = discord.Embed(
            title="Party successfully disbanded.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=success_embed)
        return

    # Invites specified user to a party, doesn't need to be registered.
    @party.command(name="invite", description="Invite another user to your party.")
    @app_commands.rename(invited_discord_user='user')
    @app_commands.describe(invited_discord_user='the user to invite to your party')
    async def invite(self, interaction: discord.Interaction, invited_discord_user: discord.User):
        user = UserManager(interaction.user.id, interaction=interaction)
        user_pid = user.get_data("party_id")

        error_embed = discord.Embed(
            title=f"Cannot invite {invited_discord_user.display_name} to party.",
            color=discord.Color.red()
        )

        if not user_pid:
            error_embed.description = "You are not in a party."
            await interaction.response.send_message(embed=error_embed)
            return

        elif not self.leader_role in interaction.user.roles:
            error_embed.description = "You are not the leader of your party!"
            await interaction.response.send_message(embed=error_embed)
            return
        
        # If the person they invited is already in a party
        inv_user = UserManager(invited_discord_user.id, interaction=interaction)
        inv_user_pid = inv_user.get_data('party_id')
        
        embed = discord.Embed(
                title="Cannot invited user to the party.",
                color=discord.Color.red()
            )
        
        # If they think they're really smart
        if interaction.user == invited_discord_user:
            embed.description="You can't invite yourself.",
            await interaction.response.send_message(embed=embed)
            return
        
        elif inv_user_pid:
            if inv_user_pid == user.get_data('party_id'):
                embed.description=f"{invited_discord_user.display_name} is in your party."
            else:
                embed.description=f"{invited_discord_user.display_name} is already in a party.\
                \n Tell them to do /party leave."
            await interaction.response.send_message(embed=embed)
            return

        invite_embed = discord.Embed(
            title=f"Party invite!",
            description=f"{interaction.user.mention} invited you to join the party!",
            color=discord.Color.from_rgb(84, 178, 209)
        )

        party_channel = discord.utils.get(
            interaction.guild.channels, id=user.get_data('party_channel_id'))
        party_role = discord.utils.get(
            interaction.guild.roles, name=f"Party {user.get_data('party_id')}")

        class InviteView(discord.ui.View):
            def __init__(self, *, timeout: float | None = 180):
                super().__init__(timeout=timeout)

            @discord.ui.button(label="Join", style=discord.ButtonStyle.green)
            async def join_button(self, join_interaction: discord.Interaction, button: discord.ui.Button):
                # User has decided to join party, give them proper role and update the database
                member = discord.utils.get(interaction.guild.members, id=join_interaction.user.id)
                await member.add_roles(party_role)
                inv_user.update_data('party_id', user_pid)
                inv_user.update_data('party_channel_id', party_channel.id)
                
                # Tell them they joined and mention the party channel
                party_joined_embed = discord.Embed(
                    title=f"You joined {interaction.user.mention}'s party.",
                    description=f"Join the party channel! {party_channel.mention}.",
                    color=discord.Color.from_rgb(84, 178, 209)
                )
                await join_interaction.response.edit_message(embed=party_joined_embed, view=None)

                # User joined the party, tell party channel
                query = (m.Users.party_id == user_pid)
                query_execution = m.Users.select().where(query)
                party_members = [member for member in query_execution]

                success_embed = discord.Embed(
                    title=f"New party member!",
                    description=f"{invited_discord_user.mention} has joined the party!",
                    color=discord.Color.green()
                    )
                await interaction.followup.send(embed=success_embed)

            @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
            async def decline_button(self, decline_interaction: discord.Interaction, button: discord.ui.Button):
                declined_embed = discord.Embed(
                    title=f"You rejected {interaction.user.mention}'s invite.",
                    description=f"We'll let them know you're not coming...",
                    color=discord.Color.red()
                )
                await decline_interaction.response.edit_message(embed=declined_embed, view=None)
                rejection_embed = discord.Embed(
                    title="Not today...",
                    description=f"Looks like {invited_discord_user.mention} didn't want to join your party.",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=rejection_embed)
                return

        await interaction.response.defer(thinking=True)
        await invited_discord_user.send(embed=invite_embed, view=InviteView())
        

    # Removes specified user from the party.
    @party.command(name="kick", description="Remove a pesky user from your party.")
    @app_commands.rename(user_to_kick='user')
    @app_commands.describe(user_to_kick='the user to kick from your party')
    async def kick(self, interaction: discord.Interaction, user_to_kick: discord.User):
        pass

    # Promotes a user as the party leader. Done exclusively through discord roles.
    @party.command(name="promote", description="Promote a user in your party to leader.")
    @app_commands.rename(user_to_promote='user')
    @app_commands.describe(user_to_promote='the user to give greater privileges to')
    async def promote(self, interaction: discord.Interaction, user_to_promote: discord.User):
        pass

    # Leaves party if user isn't the leader.
    @party.command(name="leave", description="Leave your current party.")
    async def leave(self, interaction: discord.Interaction):
        pass


async def setup(bot):
    await bot.add_cog(PartySystemCog(bot))
