import discord
import random
import asyncio

from discord.ext import commands
from discord import app_commands
from cococap.utils.messages import Cembed
from cococap.user import User
from cococap.models import UserCollection, PartyCollection
from cococap import instance
from cococap.constants import PartyRoles, DiscordGuilds
from cococap.constants import GREEN_CHECK_MARK_URL, RED_X_URL
from logging import getLogger


log = getLogger(__name__)
log.setLevel(10)

NEW_PARTY_FOOTER = "Invite members to your party using /party invite"


class PartySystemCog(commands.Cog, name="PartySystem"):
    # Party up with other players.

    def __init__(self, bot):
        self.bot = bot
        self.guild = instance.get_guild(DiscordGuilds.PRIMARY_GUILD.value)
        self.role_prefix = "PRTY"
        self.leader_role = discord.utils.get(self.guild.roles, id=PartyRoles.PARTY_LEADER.value)

        self.invite_command = app_commands.ContextMenu(
            name="invite to party",
            callback=self.invite,
        )
        self.kick_command = app_commands.ContextMenu(name="kick from party", callback=self.kick)
        self.promote_command = app_commands.ContextMenu(
            name="promote to leader", callback=self.promote
        )
        self.bot.tree.add_command(self.invite_command)
        self.bot.tree.add_command(self.kick_command)
        self.bot.tree.add_command(self.promote_command)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.invite_command)
        self.bot.tree.remove_command(self.kick_command)
        self.bot.tree.remove_command(self.promote_command)

    # Party command group
    party = app_commands.Group(
        name="party",
        description="Party up with other players.",
        guild_ids=[DiscordGuilds.PRIMARY_GUILD.value],
    )

    # Lists the members of a player's party
    @party.command(name="list")
    async def list(self, interaction: discord.Interaction):
        """See who is in your party."""
        # Load the user
        user = User(interaction.user.id)
        await user.load()

        party_id = user.get_field("party_id")

        if not party_id:
            embed = Cembed(desc="You are not currently in a party.", color=discord.Color.red())
            embed.set_author(name="Cannot list party", icon_url=RED_X_URL)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        party: PartyCollection = await PartyCollection.find_one(
            PartyCollection.party_id == party_id
        )
        party_member_ids = party.party_members

        # Get the party channel
        party_channel = discord.utils.get(interaction.guild.channels, id=party.channel_id)

        embed = discord.Embed(
            title=":busts_in_silhouette: Party Members",
            description="**Members**",
            color=discord.Color.from_rgb(84, 178, 209),
        )
        embed.add_field(name="Channel", value=party_channel.mention, inline=False)
        embed.set_footer(text="Your very own party, complete with a channel!")

        for member_id in party_member_ids:
            discord_member = discord.utils.get(interaction.guild.members, id=member_id)
            if self.leader_role in discord_member.roles:
                embed.description += f"\n:trident: • {discord_member.mention}"
            else:
                embed.description += f"\n:bust_in_silhouette: • {discord_member.mention}"
        await interaction.response.send_message(embed=embed)

    # Creates a unique party ID and adds user. Also creates a private party channel.
    @party.command(name="create")
    async def create(self, interaction: discord.Interaction):
        """Creates a private party, complete with a private party channel."""
        # Party leadership should be done through discord roles only.
        # Load the user
        user = User(interaction.user.id)
        await user.load()

        party_id = user.get_field("party_id")

        if party_id:
            embed = discord.Embed(
                description="You are already in a party!", color=discord.Color.red()
            )
            embed.set_author(name="Cannot create a party", icon_url=RED_X_URL)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Generate a random 4 digit ID
        async def generate_party_id():
            party_id = random.randint(1000, 9999)
            if await PartyCollection.find_one(PartyCollection.party_id == party_id) is None:
                # Successfully rolled a unique party ID
                return party_id
            # Reroll if the party ID already exists
            await generate_party_id()

        party_id = await generate_party_id()

        party_role = await interaction.guild.create_role(
            name=f"{self.role_prefix} {party_id}", reason="Party created."
        )
        await interaction.user.add_roles(party_role)

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(
                read_messages=False, read_message_history=False
            ),
            party_role: discord.PermissionOverwrite(read_messages=True, read_message_history=False),
        }

        party_channels_category = discord.utils.get(
            interaction.guild.categories, id=1130405873475387502
        )
        party_channel = await interaction.guild.create_text_channel(
            name=f"💠︱{interaction.user.display_name}'s-party",
            overwrites=overwrites,
            category=party_channels_category,
        )

        # Create the party and insert it
        party = PartyCollection(
            party_id=party_id, channel_id=party_channel.id, party_owner=user.uid
        )
        party.party_members.append(user.uid)
        await party.insert()

        # Update the user's party id
        user.document.party_id = party_id
        await user.save()

        # add the party leader role to the user
        await interaction.user.add_roles(self.leader_role)

        embed = discord.Embed(
            description=f"Your party has been created! {party_channel.mention}",
            color=discord.Color.green(),
        )
        embed.set_author(name="Party created!", icon_url=GREEN_CHECK_MARK_URL)
        embed.set_footer(text=NEW_PARTY_FOOTER)
        await interaction.response.send_message(embed=embed)
        return

    # Removes user and everyone else from party and deletes party ID.
    @party.command(name="disband", description="Disbands your current party.")
    async def disband(self, interaction: discord.Interaction):
        # Load the user
        user = User(interaction.user.id)
        await user.load()
        party_id = user.get_field("party_id")

        error_embed = discord.Embed(color=discord.Color.red())
        error_embed.set_author(name="Cannot disband party", icon_url=RED_X_URL)

        if not party_id:
            error_embed.description = "You are not in a party."
            await interaction.response.send_message(embed=error_embed)
            return

        elif not self.leader_role in interaction.user.roles:
            error_embed.description = "You are not the leader of your party!"
            await interaction.response.send_message(embed=error_embed)
            return

        # Query to find all users with the same party ID
        party: PartyCollection = await PartyCollection.find_one(
            PartyCollection.party_id == party_id
        )
        party_members_ids = party.party_members

        party_role = discord.utils.get(
            interaction.guild.roles, name=f"{self.role_prefix} {party_id}"
        )
        party_channel = discord.utils.get(interaction.guild.channels, id=party.channel_id)

        # Go through every user in the party and clear their party data
        for member_id in party_members_ids:
            # Remove the party role
            discord_member = discord.utils.get(interaction.guild.members, id=member_id)
            await discord_member.remove_roles(party_role)

            # Clear the party data in the database
            member = User(member_id)
            await member.load()

            member.document.party_id = None
            await member.save()

        # Remove party leader role from user who used command
        await interaction.user.remove_roles(self.leader_role)

        # Delete party role and channel from discord guild
        await party.delete()
        await party_role.delete()
        await party_channel.delete()

        success_embed = discord.Embed(color=discord.Color.green())
        success_embed.set_author(name="Party successfully disbanded", icon_url=GREEN_CHECK_MARK_URL)
        await interaction.response.send_message(embed=success_embed)
        return

    # Leaves party if user isn't the leader.
    @party.command(name="leave", description="Leave your current party.")
    async def leave(self, interaction: discord.Interaction):
        guild = interaction.guild
        # Load the user
        user = User(interaction.user.id)
        await user.load()
        party_id = user.get_field("party_id")
        party: PartyCollection = await PartyCollection.find_one(
            PartyCollection.party_id == party_id
        )
        party_member_ids = party.party_members

        # Fetch proper role and channel for the party
        party_channel = discord.utils.get(guild.channels, id=party.channel_id)
        party_role = discord.utils.get(guild.roles, name=f"{self.role_prefix} {party_id}")

        if self.leader_role in interaction.user.roles and len(party_member_ids) > 1:
            embed = discord.Embed(
                description="You are the leader of the party. \
                \nPromote someone else to party leader or disband the party.",
                color=discord.Color.red(),
            )
            embed.set_author(name="You cannot leave the party", icon_url=RED_X_URL)
            await interaction.response.send_message(embed=embed)
            log.debug(
                f"{self.role_prefix} {party_id} - Leader cannot leave party with more than 1 member."
            )
            return
        elif self.leader_role in interaction.user.roles and len(party_member_ids) == 1:
            # Remove and delete appropriate roles
            await interaction.user.remove_roles(self.leader_role)
            await party_role.delete()
            await interaction.response.send_message("*You left the party.*", ephemeral=True)
            # Delete the party channel
            await party_channel.delete()
            await party.delete()
            log.debug(f"{self.role_prefix} {party_id} - Solo leader left.")
        else:
            await interaction.user.remove_roles(party_role)
            party.party_members.remove(user.uid)
            await party.save()
            left_party_embed = discord.Embed(
                title="Party member left.",
                description=f"{interaction.user.mention} has left the party.",
                color=discord.Color.light_gray(),
            )
            await party_channel.send(embed=left_party_embed)
            await interaction.response.send_message("*You left the party.*", ephemeral=True)
            log.debug(f"{self.role_prefix} {party_id} - {interaction.user.name} left party.")

        # Clear the user's party data in the database
        user.document.party_id = None
        await user.save()
        return

    # Invites specified user to a party, doesn't need to be registered.
    async def invite(self, interaction: discord.Interaction, member: discord.Member):
        guild = interaction.guild
        # Load the user
        user = User(interaction.user.id)
        await user.load()
        party_id = user.get_field("party_id")

        error_embed = discord.Embed(color=discord.Color.red())
        error_embed.set_author(name=f"Cannot invite user to party", icon_url=RED_X_URL)

        if not party_id:
            error_embed.description = "You are not in a party."
            await interaction.response.send_message(embed=error_embed)
            return

        elif not self.leader_role in interaction.user.roles:
            error_embed.description = "You are not the leader of your party!"
            await interaction.response.send_message(embed=error_embed)
            return

        # If they think they're really smart
        elif interaction.user == member:
            error_embed.description = "You can't invite yourself."
            await interaction.response.send_message(embed=error_embed)
            return

        party: PartyCollection = await PartyCollection.find_one(
            PartyCollection.party_id == party_id
        )
        party_members_ids = party.party_members

        invited_user = User(member.id)
        await invited_user.load()
        invited_user_party_id = invited_user.get_field("party_id")

        # If the person they invited is already in a party
        if invited_user_party_id:
            if invited_user_party_id in party_members_ids:
                error_embed.description = f"{member.display_name} is in your party."
            else:
                error_embed.description = f"{member.display_name} is already in a party.\
                \n Tell them to do /party leave."
            await interaction.response.send_message(embed=error_embed)
            return

        invite_embed = discord.Embed(
            title=f"Party invite!",
            description=f"{interaction.user.mention} invited you to join the party!",
            color=discord.Color.from_rgb(84, 178, 209),
        )

        party_category = discord.utils.get(guild.categories, id=1130405873475387502)

        # Create a temporary role to privately invite the user to the party
        invite_role = await guild.create_role(
            name=f"INVT {party_id}-{member.id}", reason="Party invite."
        )
        await member.add_roles(invite_role)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                read_messages=False, read_message_history=False
            ),
            invite_role: discord.PermissionOverwrite(
                read_messages=True, read_message_history=True, send_messages=False
            ),
        }

        # Create a temporary party channel to
        invite_channel = await guild.create_text_channel(
            name=f"party-invite", overwrites=overwrites, category=party_category
        )

        # Get the channel and the role that the user will recieve upon joining the party
        party_channel = discord.utils.get(guild.channels, id=party.channel_id)
        party_role = discord.utils.get(guild.roles, name=f"{self.role_prefix} {party_id}")

        class InviteView(discord.ui.View):
            def __init__(self, member: discord.Member, timeout: float | None = 180):
                super().__init__(timeout=timeout)
                self.member = member

            @discord.ui.button(label="Join", style=discord.ButtonStyle.green)
            async def join_button(
                self, join_interaction: discord.Interaction, button: discord.ui.Button
            ):
                if join_interaction.user != self.member:
                    return
                # Fetch the invited user from the guild
                member = discord.utils.get(guild.members, id=join_interaction.user.id)

                # Delete the invite role and allow user to see the party channel
                try:
                    await member.add_roles(party_role)
                except discord.errors.NotFound:
                    failed_invite_embed = discord.Embed(
                        description=f"The party you were attempting to join has been disbanded.",
                        color=discord.Color.red(),
                    )
                    failed_invite_embed.set_author(name="Party invited failed", icon_url=RED_X_URL)
                    await invite_message.edit(embed=failed_invite_embed, view=None)
                    return

                # Update invited user's party information in the database
                invited_user.document.party_id = party_id
                await invited_user.save()
                # Add user to list of party members
                party.party_members.append(invited_user.uid)
                await party.save()

                # Embed to inform the party that a new member has joined
                success_embed = discord.Embed(
                    title=f"New party member!",
                    description=f"{member.mention} has joined the party!",
                    color=discord.Color.from_rgb(84, 178, 209),
                )
                await party_channel.send(
                    content=f"Welcome to the party, {member.mention}!",
                    embed=success_embed,
                )
                fulfilled_invite_embed = discord.Embed(
                    title=f"Party joined!",
                    description=f"You joined {interaction.user.mention}'s party! \
                                Join the channel here: {party_channel.mention}",
                    color=discord.Color.from_rgb(84, 178, 209),
                )
                await invite_message.edit(embed=fulfilled_invite_embed, view=None)
                await asyncio.sleep(10)
                await invite_channel.delete()
                await invite_role.delete()
                return

            @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
            async def decline_button(
                self, decline_interaction: discord.Interaction, button: discord.ui.Button
            ):
                if decline_interaction.user != member:
                    return
                # Delete the role
                await invite_channel.delete()
                await invite_role.delete()
                return

        await interaction.response.send_message(f"Party invite sent to {member.mention}")
        invite_message = await invite_channel.send(
            content=f"Hey, {member.mention}!", embed=invite_embed, view=InviteView(member=member)
        )
        await asyncio.sleep(60)
        try:
            await invite_channel.delete()
            await invite_role.delete()
        except discord.errors.NotFound:
            log.debug("Channel already deleted.")
        return

    # Removes specified user from the party.
    async def kick(self, interaction: discord.Interaction, member_to_kick: discord.Member):
        # Load the users
        user = User(interaction.user.id)
        user_to_kick = User(member_to_kick.id)
        await user.load()
        await user_to_kick.load()

        party_id = user.get_field("party_id")

        error_embed = discord.Embed(color=discord.Color.red())
        error_embed.set_author(name=f"Cannot kick user from the party", icon_url=RED_X_URL)

        if not party_id:
            error_embed.description = "You are not in a party."
            await interaction.response.send_message(embed=error_embed)
            return

        elif not self.leader_role in interaction.user.roles:
            error_embed.description = "You are not the leader of your party!"
            await interaction.response.send_message(embed=error_embed)
            return

        elif interaction.user == member_to_kick:
            error_embed.description = "You cannot kick yourself..."
            await interaction.response.send_message(embed=error_embed)
            return

        party: PartyCollection = await PartyCollection.find_one(
            PartyCollection.party_id == party_id
        )
        party_member_ids = party.party_members
        party_role = discord.utils.get(
            interaction.guild.roles, name=f"{self.role_prefix} {party_id}"
        )

        if member_to_kick.id not in party_member_ids:
            error_embed.description = f"{member_to_kick.mention} is not in your party."
            await interaction.response.send_message(embed=error_embed)
            return

        await member_to_kick.remove_roles(party_role)

        # Clear the user's party data in the database
        user_to_kick.document.party_id = None
        await user_to_kick.save()

        party.party_members.remove(user_to_kick.uid)
        await party.save()

        kicked_embed = discord.Embed(
            title="User kicked from party.",
            description=f"{member_to_kick.mention} has been kicked from the party.",
            color=discord.Color.light_gray(),
        )
        await interaction.response.send_message(embed=kicked_embed)
        return

    # Promotes a user as the party leader. Done exclusively through discord roles.
    async def promote(self, interaction: discord.Interaction, member: discord.Member):
        # Load the user
        user = User(interaction.user.id)
        await user.load()
        party_id = user.get_field("party_id")

        party: PartyCollection = await PartyCollection.find_one(
            PartyCollection.party_id == party_id
        )
        party_member_ids = party.party_members

        error_embed = discord.Embed(color=discord.Color.red())
        error_embed.set_author(name=f"Cannot promote user", icon_url=RED_X_URL)

        if not party_id:
            error_embed.description = "You are not in a party."
            await interaction.response.send_message(embed=error_embed)
            return

        elif not self.leader_role in interaction.user.roles:
            error_embed.description = "You are not the leader of your party!"
            await interaction.response.send_message(embed=error_embed)
            return

        elif interaction.user == member:
            error_embed.description = "You cannot promote yourself..."
            await interaction.response.send_message(embed=error_embed)
            return

        elif member.id not in party_member_ids:
            error_embed.description = f"{member.mention} is not in your party."
            await interaction.response.send_message(embed=error_embed)
            return

        # Exchange leader roles
        await member.add_roles(self.leader_role)
        await interaction.user.remove_roles(self.leader_role)

        # Update the party owner
        party.party_owner = member.id
        await party.save()

        # Change the party channel's name
        party_channel = discord.utils.get(interaction.guild.channels, id=party.channel_id)
        await party_channel.edit(
            name=f"💠︱{member.display_name}'s-party", reason="Party leader changed."
        )

        success_embed = discord.Embed(
            description=f"{member.mention} has been promoted to party leader!",
            color=discord.Color.green(),
        )
        success_embed.set_author(name="Promotion successful", icon_url=GREEN_CHECK_MARK_URL)

        await interaction.response.send_message(embed=success_embed)
        return


async def setup(bot):
    await bot.add_cog(PartySystemCog(bot))
