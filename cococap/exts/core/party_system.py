import discord as d
import random
import asyncio

from discord.ext import commands
from discord import app_commands as ac
from cococap.utils.messages import Cembed
from cococap.user import User
from cococap.models import PartyDocument
from logging import getLogger


log = getLogger(__name__)
log.setLevel(10)

NEW_PARTY_FOOTER = "Invite members to your party using /party invite"


class PartySystemCog(commands.Cog, name="PartySystem"):
    # Party up with other players.

    def __init__(self, bot):
        self.bot = bot

        # These are context menu commands which can be used when right clicking a user in discord
        self.invite_command = ac.ContextMenu(name="invite to party", callback=self.invite)
        self.kick_command = ac.ContextMenu(name="kick from party", callback=self.kick)
        self.promote_command = ac.ContextMenu(name="promote to leader", callback=self.promote)

    async def cog_load(self) -> None:
        self.bot.tree.add_command(self.invite_command)
        self.bot.tree.add_command(self.kick_command)
        self.bot.tree.add_command(self.promote_command)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.invite_command)
        self.bot.tree.remove_command(self.kick_command)
        self.bot.tree.remove_command(self.promote_command)

    # Party command group
    party = ac.Group(name="party", description="Party up with other players.")

    # Lists the members of a player's party
    @party.command(name="list")
    async def list(self, interaction: d.Interaction):
        """See who is in your party."""
        # Load the user
        user = User(interaction.user.id)
        await user.load()

        party_id = user.get_field("party_id")

        if not party_id:
            embed = Cembed(desc="You are not currently in a party.", color=d.Color.red())
            embed.set_author(name="Cannot list party")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        party: PartyDocument = await PartyDocument.find_one(PartyDocument.party_id == party_id)
        party_member_ids = party.party_members

        embed = d.Embed(
            title=":busts_in_silhouette: Party Members",
            description="**Members**",
            color=d.Color.from_rgb(84, 178, 209),
        )
        embed.set_footer(text="Your very own party!")

        for member_id in party_member_ids:
            discord_member = d.utils.get(interaction.guild.members, id=member_id)
            if party.party_owner == discord_member.id:
                embed.description += f"\n:trident: • {discord_member.mention}"
            else:
                embed.description += f"\n:bust_in_silhouette: • {discord_member.mention}"
        await interaction.response.send_message(embed=embed)

    # Creates a unique party ID and adds user
    @party.command(name="create")
    async def create(self, interaction: d.Interaction):
        """Creates a private party, complete with a private party channel."""
        # Load the user
        user = User(interaction.user.id)
        await user.load()

        party_id = user.get_field("party_id")

        if party_id:
            embed = d.Embed(description="You are already in a party!", color=d.Color.red())
            embed.set_author(name="Cannot create a party")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Generate a random 4 digit ID
        async def generate_party_id():
            party_id = random.randint(1000, 9999)
            if await PartyDocument.find_one(PartyDocument.party_id == party_id) is None:
                # Successfully rolled a unique party ID
                return party_id
            # Reroll if the party ID already exists
            await generate_party_id()

        party_id = await generate_party_id()

        # Create the party and insert it
        party = PartyDocument(party_id=party_id, party_owner=user.uid)
        party.party_members.append(user.uid)
        await party.insert()

        # Update the user's party id
        user.document.party_id = party_id
        await user.save()

        embed = d.Embed(
            description=f"Your party has been created!",
            color=d.Color.green(),
        )
        embed.set_author(name="Party created")
        embed.set_footer(text=NEW_PARTY_FOOTER)
        await interaction.response.send_message(embed=embed)
        return

    # Removes user and everyone else from party and deletes party ID.
    @party.command(name="disband", description="Disbands your current party.")
    async def disband(self, interaction: d.Interaction):
        # Load the user
        user = User(interaction.user.id)
        await user.load()
        party_id = user.get_field("party_id")

        error_embed = d.Embed(color=d.Color.red())
        error_embed.set_author(name="Cannot disband party")

        # Query to find all users with the same party ID
        party: PartyDocument = await PartyDocument.find_one(PartyDocument.party_id == party_id)
        party_members_ids = party.party_members

        if not party_id:
            error_embed.description = "You are not in a party."
            await interaction.response.send_message(embed=error_embed)
            return

        elif party.party_owner != interaction.user.id:
            error_embed.description = "You are not the leader of your party!"
            await interaction.response.send_message(embed=error_embed)
            return

        # Go through every user in the party and clear their party data
        for member_id in party_members_ids:
            # Clear the party data in the database
            member = User(member_id)
            await member.load()

            member.document.party_id = None
            await member.save()

        # Delete party role and channel from discord guild
        await party.delete()

        success_embed = d.Embed(color=d.Color.green())
        success_embed.set_author(name="Party successfully disbanded")
        await interaction.response.send_message(embed=success_embed)
        return

    # Leaves party if user isn't the leader.
    @party.command(name="leave", description="Leave your current party.")
    async def leave(self, interaction: d.Interaction):
        # Load the user
        user = User(interaction.user.id)
        await user.load()
        party_id = user.get_field("party_id")
        party: PartyDocument = await PartyDocument.find_one(PartyDocument.party_id == party_id)
        party_member_ids = party.party_members

        if party.party_owner == interaction.user.id and len(party_member_ids) > 1:
            embed = d.Embed(
                description="You are the leader of the party. \
                \nPromote someone else to party leader or disband the party.",
                color=d.Color.red(),
            )
            embed.set_author(name="You cannot leave the party")
            await interaction.response.send_message(embed=embed)
            log.debug(f"{party_id} - Leader cannot leave party with more than 1 member.")
            return

        elif party.party_owner == interaction.user.id and len(party_member_ids) == 1:
            # Remove and delete appropriate roles
            await interaction.response.send_message("*You left the party.*", ephemeral=True)
            await party.delete()
            log.debug(f"{party_id} - Solo leader left.")
        else:
            party.party_members.remove(user.uid)
            await party.save()
            left_party_embed = d.Embed(
                title="Party member left.",
                description=f"{interaction.user.mention} has left the party.",
                color=d.Color.light_gray(),
            )
            await interaction.response.send_message(embed=left_party_embed)
            log.debug(f"{party_id} - {interaction.user.name} left party.")

        # Clear the user's party data in the database
        user.document.party_id = None
        await user.save()
        return

    # Invites specified user to a party, doesn't need to be registered.
    async def invite(self, interaction: d.Interaction, member: d.Member):
        # Load the user
        user = User(interaction.user.id)
        await user.load()
        party_id = user.get_field("party_id")

        error_embed = d.Embed(color=d.Color.red())
        error_embed.set_author(name=f"Cannot invite user to party")

        party: PartyDocument = await PartyDocument.find_one(PartyDocument.party_id == party_id)
        party_members_ids = party.party_members

        if not party_id:
            error_embed.description = "You are not in a party."
            await interaction.response.send_message(embed=error_embed)
            return

        elif party.party_owner != interaction.user.id:
            error_embed.description = "You are not the leader of your party!"
            await interaction.response.send_message(embed=error_embed)
            return

        # If they think they're really smart
        elif interaction.user == member:
            error_embed.description = "You can't invite yourself."
            await interaction.response.send_message(embed=error_embed)
            return

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

        invite_embed = d.Embed(
            title=f"Party invite!",
            description=f"{interaction.user.mention} invited you to join the party!",
            color=d.Color.from_rgb(84, 178, 209),
        )

        class InviteView(d.ui.View):
            def __init__(self, member: d.Member, timeout: float | None = 180):
                super().__init__(timeout=timeout)
                self.member = member

            @d.ui.button(label="Join", style=d.ButtonStyle.green)
            async def join_button(self, join_inter: d.Interaction, button: d.ui.Button):
                if join_inter.user != self.member:
                    return

                party: PartyDocument = await PartyDocument.find_one(
                    PartyDocument.party_id == party_id
                )
                if not party:
                    failed_invite_embed = d.Embed(
                        description=f"The party you were attempting to join has been disbanded.",
                        color=d.Color.red(),
                    )
                    failed_invite_embed.set_author(name="Party invited failed")
                    await invite_message.edit(embed=failed_invite_embed, view=None)
                    return

                # Update invited user's party information in the database
                invited_user.document.party_id = party_id
                await invited_user.save()
                # Add user to list of party members
                party.party_members.append(invited_user.uid)
                await party.save()

                # Embed to inform the party that a new member has joined
                success_embed = d.Embed(
                    title=f"Welcome to the party!",
                    description=f"{member.mention} has joined the party!",
                    color=d.Color.from_rgb(84, 178, 209),
                )
                await interaction.channel.send(embed=success_embed)
                return

            @d.ui.button(label="Decline", style=d.ButtonStyle.red)
            async def decline_button(self, decline_interaction: d.Interaction, button: d.ui.Button):
                if decline_interaction.user != member:
                    return
                return

        await interaction.response.send_message(f"Party invite sent to {member.mention}")
        invite_message = await interaction.channel.send(
            content=f"Hey, {member.mention}!", embed=invite_embed, view=InviteView(member=member)
        )
        await invite_message.delete(60)
        return

    # Removes specified user from the party.
    async def kick(self, interaction: d.Interaction, member_to_kick: d.Member):
        # Load the users
        user = User(interaction.user.id)
        user_to_kick = User(member_to_kick.id)
        await user.load()
        await user_to_kick.load()

        party_id = user.get_field("party_id")

        error_embed = d.Embed(color=d.Color.red())
        error_embed.set_author(name=f"Cannot kick user from the party")

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

        party: PartyDocument = await PartyDocument.find_one(PartyDocument.party_id == party_id)
        party_member_ids = party.party_members
        party_role = d.utils.get(interaction.guild.roles, name=f"{self.role_prefix} {party_id}")

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

        kicked_embed = d.Embed(
            title="User kicked from party.",
            description=f"{member_to_kick.mention} has been kicked from the party.",
            color=d.Color.light_gray(),
        )
        await interaction.response.send_message(embed=kicked_embed)
        return

    # Promotes a user as the party leader. Done exclusively through d roles.
    async def promote(self, interaction: d.Interaction, member: d.Member):
        # Load the user
        user = User(interaction.user.id)
        await user.load()
        party_id = user.get_field("party_id")

        party: PartyDocument = await PartyDocument.find_one(PartyDocument.party_id == party_id)
        party_member_ids = party.party_members

        error_embed = d.Embed(color=d.Color.red())
        error_embed.set_author(name=f"Cannot promote user")

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
        party_channel = d.utils.get(interaction.guild.channels, id=party.channel_id)
        await party_channel.edit(
            name=f"💠︱{member.display_name}'s-party", reason="Party leader changed."
        )

        success_embed = d.Embed(
            description=f"{member.mention} has been promoted to party leader!",
            color=d.Color.green(),
        )
        success_embed.set_author(name="Promotion successful")

        await interaction.response.send_message(embed=success_embed)
        return


async def setup(bot):
    await bot.add_cog(PartySystemCog(bot))
