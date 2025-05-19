import discord
import random

from discord.ext import commands
from discord import app_commands, Interaction
from cococap.user import User
from cococap.models import PartyDocument
from cococap.exts.utils.error import CustomError
from utils.custom_embeds import SuccessEmbed, CustomEmbed
from logging import getLogger


log = getLogger(__name__)


class PartyNotFound(CustomError):
    pass


class AlreadyInParty(CustomError):
    pass


class UserNotInParty(CustomError):
    pass


class NotPartyOwner(CustomError):
    def __init__(self, message="You are not the owner of the party!", title=None, footer=None):
        super().__init__(message, title, footer)


class PartyNotEmpty(CustomError):
    pass


class Party:
    def __init__(self):
        self._id: int
        self._document: PartyDocument
        self._members: list
        self._owner_id: int

    async def load(self, party_id: int):
        party: PartyDocument = await PartyDocument.find_one(PartyDocument.party_id == party_id)
        if not party:
            return None
        self._id = party_id
        self._members = party.party_members
        self._owner_id = party.party_owner
        self._document = party
        return self

    async def save(self):
        await self._document.save()

    @property
    def party_id(self):
        return getattr(self, "_id", None)

    @property
    def members(self):
        return getattr(self, "_members", [])

    @property
    def owner(self):
        return getattr(self, "_owner_id", None)

    async def add_member(self, user_id: int):
        """Add a member to the party and update their document."""
        if self.is_member(user_id):
            raise AlreadyInParty(f"The specified user is in already your party.")
        member: User = await User.get(user_id)
        if member.get_field("party_id"):
            raise AlreadyInParty(
                f"The specified user is already in a party.",
                title=f"Failed to invite the specified user",
                footer="Tell them to do /party leave.",
            )
        self._members.append(user_id)
        await member.set_field("party_id", self.party_id)
        return await self.save()

    async def remove_member(self, user_id: int):
        """Remove a member from the party and update their document."""
        if not self.is_member(user_id):
            raise UserNotInParty("The specified user is not in your party...")
        member: User = await User.get(user_id)
        await member.set_field("party_id", None)
        self._members.remove(user_id)
        return await self.save()

    async def change_owner(self, user_id: int):
        self._owner_id = user_id
        return await self.save()

    async def delete(self):
        """Delete the party and update all affected members."""
        for member in self.members:
            user = await User.get(member)
            await user.set_field("party_id", None)
        await self._document.delete()

    def is_member(self, user_id: int) -> bool:
        return user_id in self._members

    def is_owner(self, user_id: int) -> bool:
        return self._owner_id == user_id

    def member_count(self) -> int:
        return len(self._members)

    @staticmethod
    async def create(owner_id: int):
        party_id = random.randint(1000, 9999)
        party_exists = await PartyDocument.find_one(PartyDocument.party_id == party_id)
        owns_party = await PartyDocument.find_one(PartyDocument.party_owner == owner_id)
        if owns_party:
            raise AlreadyInParty(
                "You are already in a party.",
                footer="Use /party leave to leave your current party.",
            )
        if not party_exists:
            # Create the party
            await PartyDocument(party_id=party_id, party_owner=owner_id).insert()
            party: Party = await Party().load(party_id)
            return await party.add_member(owner_id)

        return await Party.create(owner_id=owner_id)


async def ensure_party(interaction: Interaction):
    party: Party = interaction.extras.get("party")
    if not party:
        raise PartyNotFound(
            "You are not in a party.",
            footer="Create a party with /party create or ask someone to invite you (right click your name -> apps)!",
        )
    return True


class PartySystemCog(commands.GroupCog, name="party"):
    # Party up with other players.

    def __init__(self, bot):
        self.bot = bot

        # These are context menu commands which can be used when right clicking a user in discord
        self.invite_command = app_commands.ContextMenu(name="invite to party", callback=self.invite)
        self.kick_command = app_commands.ContextMenu(name="kick from party", callback=self.kick)
        self.promote_command = app_commands.ContextMenu(
            name="promote to leader", callback=self.promote
        )

    async def cog_load(self) -> None:
        self.bot.tree.add_command(self.invite_command)
        self.bot.tree.add_command(self.kick_command)
        self.bot.tree.add_command(self.promote_command)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.invite_command)
        self.bot.tree.remove_command(self.kick_command)
        self.bot.tree.remove_command(self.promote_command)

    async def interaction_check(self, interaction: Interaction):
        user = await User.get(interaction.user.id)
        interaction.extras.update(user=user)
        party = await Party().load(user.get_field("party_id"))
        interaction.extras.update(party=party)
        return super().interaction_check(interaction)

    # Lists the members of a player's party
    @app_commands.command(name="list")
    @app_commands.check(ensure_party)
    async def list_members(self, interaction: Interaction):
        """See who is in your party."""
        party: Party = interaction.extras.get("party")

        embed = CustomEmbed(
            title=":busts_in_silhouette: Party Members",
            description=f"**Party ID:** {party.party_id}\n**Members ({party.member_count()}):**",
            color=discord.Color.from_rgb(84, 178, 209),
        )

        # Add members to the description
        for member_id in party.members:
            member = discord.utils.get(interaction.guild.members, id=member_id)
            if member:
                emoji = ":crown:" if party.is_owner(member.id) else ":bust_in_silhouette:"
                embed.description += f"\n{emoji} • {member.mention}"

        embed.set_footer(text="Right click a member -> apps to invite them!")
        return await interaction.response.send_message(embed=embed)

    # Creates a unique party ID and adds user
    @app_commands.command(name="create")
    async def create(self, interaction: Interaction):
        """Creates a private party, complete with a private party channel."""
        party: Party = interaction.extras.get("party")

        if party:
            raise AlreadyInParty(
                "You are already in a party!",
                title="Cannot create a party",
                footer="Use /party leave to leave your current party.",
            )

        await Party.create(interaction.user.id)
        embed = SuccessEmbed(
            desc=f"Your party has been created!", interaction=interaction, activity="partying"
        )
        return await interaction.response.send_message(embed=embed)

    # Removes user and everyone else from party and deletes party ID.
    @app_commands.command(name="disband", description="Disbands your current party.")
    @app_commands.check(ensure_party)
    async def disband(self, interaction: Interaction):
        party: Party = interaction.extras.get("party")

        if not party.is_owner(interaction.user.id):
            raise NotPartyOwner(
                title="Failed to disband party",
                footer="You can leave if you'd like...",
            )

        await party.delete()
        success_embed = SuccessEmbed(desc="Party successfully disbanded")
        return await interaction.response.send_message(embed=success_embed)

    # Leaves party if user isn't the leader.
    @app_commands.command(name="leave", description="Leave your current party.")
    @app_commands.check(ensure_party)
    async def leave(self, interaction: Interaction):
        party: Party = interaction.extras.get("party")

        if party.is_owner(interaction.user.id) and party.member_count() > 1:
            raise PartyNotEmpty(
                "You are the leader of the party!",
                title="You cannot leave the party",
                footer="Promote someone else to party leader or disband the party.",
            )

        if party.member_count() == 1:
            await interaction.response.send_message("*You left the party.*", ephemeral=True)
            return await party.delete()

        await party.remove_member(interaction.user.id)
        embed = discord.Embed(
            title="Party member left",
            description=f"*{interaction.user.mention} has left the party.*",
            color=discord.Color.dark_gray(),
        )
        await interaction.response.send_message(embed=embed)

    # Invites specified user to a party, doesn't need to be registered.
    @app_commands.check(ensure_party)
    async def invite(self, interaction: Interaction, member: discord.Member):
        party: Party = interaction.extras.get("party")

        if not party.is_owner(interaction.user.id):
            raise NotPartyOwner(
                title="You do not have permission",
                footer="Ask your leader to invite the user to the party.",
            )
        elif interaction.user == member:
            raise AlreadyInParty(
                "You're already here, bro.",
                title="Nice try bucko",
                footer="For real though, good curiosity. Test out all options!",
            )

        embed = discord.Embed(
            title=f"Party invite!",
            description=f"{interaction.user.mention} invited you to join the party!",
            color=discord.Color.from_rgb(84, 178, 209),
        )

        class InviteView(discord.ui.View):
            def __init__(self, member: discord.Member, timeout: float | None = 180):
                super().__init__(timeout=timeout)
                self.member = member

            async def interaction_check(self, interaction):
                if interaction.user != self.member:
                    return False
                return await super().interaction_check(interaction)

            @discord.ui.button(label="Join", style=discord.ButtonStyle.green)
            async def _join(self, interaction: discord.Interaction, button: discord.ui.Button):
                # Fetch the invited user from the guild
                member = discord.utils.get(guild.members, id=interaction.user.id)

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
                return

            @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
            async def _decline(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.stop()
                return await invite_channel.delete()

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

    @app_commands.check(ensure_party)
    async def kick(self, interaction: Interaction, member_to_kick: discord.Member):
        """Remove a specified member from the party."""
        party: Party = interaction.extras.get("party")

        if party.is_owner(interaction.user.id):
            raise NotPartyOwner(
                title=f"You do not have permission to kick {member_to_kick.display_name}",
                footer="If you really want 'em gone, ask your leader.",
            )

        elif interaction.user == member_to_kick:
            raise CustomError("You cannot kick yourself...")

        await party.remove_member(member_to_kick.id)

        embed = discord.Embed(
            title="User kicked from party.",
            description=f"{member_to_kick.mention} has been kicked from the party.",
            color=discord.Color.dark_gray(),
        )
        return await interaction.response.send_message(embed=embed)

    @app_commands.check(ensure_party)
    async def promote(self, interaction: Interaction, member: discord.Member):
        """Promotes a user as the party leader."""
        party: Party = interaction.extras.get("party")

        if not party.is_owner(interaction.user.id):
            raise NotPartyOwner()

        if interaction.user == member:
            raise CustomError("You cannot promote yourself.")

        if party.is_member(member.id):
            raise UserNotInParty(f"{member.mention} is not in your party.")

        await party.change_owner(member.id)

        # TODO: Party channels do not wort at the moment
        # Change the party channel's name if it exists
        party_channel = discord.utils.get(
            interaction.guild.channels, id=getattr(party, "channel_id", None)
        )
        if party_channel:
            await party_channel.edit(
                name=f"\U0001f536︱{member.display_name}'s-party", reason="Party leader changed."
            )

        success_embed = discord.Embed(
            description=f"{member.mention} has been promoted to party leader!",
            color=discord.Color.green(),
        )
        success_embed.set_author(name="Promotion successful")
        return await interaction.response.send_message(embed=success_embed)


async def setup(bot):
    await bot.add_cog(PartySystemCog(bot))
