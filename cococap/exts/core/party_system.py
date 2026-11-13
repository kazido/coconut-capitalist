import discord
import random

from logging import getLogger
from discord.ext import commands
from discord import app_commands, Interaction
from cococap.user import User
from sqlalchemy import delete, select, update

from cococap.db import get_database
from cococap.db.tables import PartyMemberRow, PartyRow
from cococap.exts.utils.error import CustomError
from utils.custom_embeds import SuccessEmbed, CustomEmbed


log = getLogger(__name__)


class PartyEmbed(SuccessEmbed):
    def __init__(self, *, desc, interaction):
        super().__init__(desc=desc, interaction=interaction, activity="partying")


# Custom errors
class PartyNotFound(CustomError):
    pass


class AlreadyInParty(CustomError):
    pass


class UserNotInParty(CustomError):
    pass


class NotPartyOwner(CustomError):
    pass


class PartyNotEmpty(CustomError):
    pass


class Party:
    """A party and its members, backed by the parties / party_members tables.

    Instances are snapshots: call ``Party.load`` again to see changes made elsewhere. All changes
    go through single transactions, so two people joining at once cannot corrupt the roster.
    """

    def __init__(self, party_id: int, owner_id: int, members: list[int]):
        self.party_id = party_id
        self._owner_id = owner_id
        self._members = members

    @classmethod
    async def load(cls, party_id: int) -> "Party | None":
        async with get_database().session() as session:
            row = await session.get(PartyRow, party_id)
            if row is None:
                return None
            ids = await session.scalars(
                select(PartyMemberRow.user_id).where(PartyMemberRow.party_id == party_id)
            )
            return cls(party_id, row.owner_id, list(ids))

    @classmethod
    async def for_user(cls, user_id: int) -> "Party | None":
        """The party `user_id` belongs to, if any."""
        async with get_database().session() as session:
            party_id = await session.scalar(
                select(PartyMemberRow.party_id).where(PartyMemberRow.user_id == user_id)
            )
        return await cls.load(party_id) if party_id is not None else None

    @property
    def members(self) -> list[int]:
        return list(self._members)

    @property
    def owner(self) -> int:
        return self._owner_id

    async def add_member(self, user_id: int):
        """Add a member (they must not already be in any party)."""
        if self.is_member(user_id):
            raise AlreadyInParty("The specified user is already in your party.")
        await User.get(user_id)  # make sure the player exists (foreign key)
        async with get_database().session() as session:
            if await session.get(PartyMemberRow, user_id) is not None:
                raise AlreadyInParty(
                    "The specified user is already in a party.",
                    title="Failed to invite the specified user",
                    footer="Tell them to do /party leave.",
                )
            session.add(PartyMemberRow(user_id=user_id, party_id=self.party_id))
        self._members.append(user_id)

    async def remove_member(self, user_id: int):
        """Remove a member from the party."""
        if not self.is_member(user_id):
            raise UserNotInParty("The specified user is not in your party...")
        async with get_database().session() as session:
            await session.execute(delete(PartyMemberRow).where(PartyMemberRow.user_id == user_id))
        self._members.remove(user_id)

    async def change_owner(self, user_id: int):
        async with get_database().session() as session:
            await session.execute(
                update(PartyRow).where(PartyRow.party_id == self.party_id).values(owner_id=user_id)
            )
        self._owner_id = user_id

    async def delete(self):
        """Delete the party; membership rows are removed by the foreign-key cascade."""
        async with get_database().session() as session:
            await session.execute(delete(PartyRow).where(PartyRow.party_id == self.party_id))
        self._members.clear()

    def is_member(self, user_id: int) -> bool:
        return user_id in self._members

    def is_owner(self, user_id: int) -> bool:
        return self._owner_id == user_id

    def member_count(self) -> int:
        return len(self._members)

    @staticmethod
    async def create(owner_id: int) -> "Party":
        await User.get(owner_id)
        async with get_database().session() as session:
            if await session.get(PartyMemberRow, owner_id) is not None:
                raise AlreadyInParty(
                    "You are already in a party.",
                    footer="Use /party leave to leave your current party.",
                )
            for _ in range(50):  # 4-digit ids; retry on the (rare) collision
                party_id = random.randint(1000, 9999)
                if await session.get(PartyRow, party_id) is None:
                    break
            else:
                raise CustomError("Too many parties right now, try again in a bit.")
            session.add(PartyRow(party_id=party_id, owner_id=owner_id))
            await session.flush()  # the member row references the party row
            session.add(PartyMemberRow(user_id=owner_id, party_id=party_id))
        return Party(party_id, owner_id, [owner_id])


# Custom check to make sure the user is in a party
async def in_party(interaction: Interaction):
    party: Party = interaction.extras.get("party")
    if not party:
        raise PartyNotFound("You are not currently in a party.")
    return True  # There is a party associated with the interaction


# Custom check to make sure the user is NOT in a party
async def not_in_party(interaction: Interaction):
    party: Party = interaction.extras.get("party")
    if party:
        raise AlreadyInParty("You are already in a party.")
    return True  # There is a party associated with the interaction


# Custom check to make sure the user owns the party
async def is_owner(interaction: Interaction):
    party: Party = interaction.extras.get("party")

    if party is None or not party.is_owner(interaction.user.id):
        raise NotPartyOwner("You are not the party owner.")
    return True  # The interaction user owns the associated party


class PartyInviteView(discord.ui.View):
    """Join/Decline buttons shown to the invited member."""

    def __init__(self, party: "Party", invited: discord.Member, inviter: discord.abc.User):
        super().__init__(timeout=180)
        self.party = party
        self.invited = invited
        self.inviter = inviter
        self.message: discord.Message | None = None

    async def interaction_check(self, interaction: Interaction) -> bool:
        # Only the invited member may answer.
        return interaction.user.id == self.invited.id

    async def _finish(self, interaction: Interaction, embed: discord.Embed) -> None:
        self.stop()
        await interaction.response.edit_message(content=None, embed=embed, view=None)

    @discord.ui.button(label="Join", style=discord.ButtonStyle.green)
    async def join(self, interaction: Interaction, button: discord.ui.Button):
        # Reload: the party may have been disbanded or changed owner since the invite was sent.
        party = await Party.load(self.party.party_id)
        if party is None:
            return await self._finish(
                interaction,
                discord.Embed(
                    title="Invite failed",
                    description="The party you were invited to has been disbanded.",
                    color=discord.Color.red(),
                ),
            )
        try:
            await party.add_member(interaction.user.id)
        except CustomError as e:
            return await self._finish(
                interaction,
                discord.Embed(title="Invite failed", description=str(e), color=discord.Color.red()),
            )
        await self._finish(
            interaction,
            discord.Embed(
                title="New party member!",
                description=f"{interaction.user.mention} has joined {self.inviter.mention}'s party!",
                color=discord.Color.from_rgb(84, 178, 209),
            ),
        )

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
    async def decline(self, interaction: Interaction, button: discord.ui.Button):
        await self._finish(
            interaction,
            discord.Embed(
                description=f"{interaction.user.mention} declined the invite.",
                color=discord.Color.dark_gray(),
            ),
        )

    async def on_timeout(self) -> None:
        if self.message is not None:
            try:
                await self.message.edit(content=None, view=None)
            except discord.HTTPException:
                pass


class PartySystemCog(commands.GroupCog, name="party"):
    # Party up with other players.

    def __init__(self, bot):
        self.bot = bot

        # These are context menu commands which can be used when right clicking a user in discord
        self.invite_ctx = app_commands.ContextMenu(name="invite to party", callback=self.invite)
        self.kick_ctx = app_commands.ContextMenu(name="kick from party", callback=self.kick)
        self.promote_ctx = app_commands.ContextMenu(name="promote to leader", callback=self.promote)

    async def cog_load(self) -> None:
        self.bot.tree.add_command(self.invite_ctx)
        self.bot.tree.add_command(self.kick_ctx)
        self.bot.tree.add_command(self.promote_ctx)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.invite_ctx)
        self.bot.tree.remove_command(self.kick_ctx)
        self.bot.tree.remove_command(self.promote_ctx)

    async def interaction_check(self, interaction: Interaction):
        user = await User.get(interaction.user.id)
        interaction.extras.update(user=user)
        interaction.extras.update(party=await Party.for_user(user.id))
        return super().interaction_check(interaction)

    # Lists the members of a player's party
    @app_commands.command(name="list", description="See who is in your party")
    @app_commands.check(in_party)
    async def list_members(self, interaction: Interaction):
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
    @app_commands.command(name="create", description="Create a party")
    @app_commands.check(not_in_party)
    async def create(self, interaction: Interaction):
        await Party.create(interaction.user.id)
        embed = PartyEmbed(desc="Your party has been created!", interaction=interaction)
        return await interaction.response.send_message(embed=embed)

    # Removes user and everyone else from party and deletes party ID.
    @app_commands.command(name="disband", description="Disbands your current party")
    @app_commands.check(in_party)
    @app_commands.check(is_owner)
    async def disband(self, interaction: Interaction):
        party: Party = interaction.extras.get("party")

        await party.delete()
        embed = PartyEmbed(desc="Party successfully disbanded.", interaction=interaction)
        return await interaction.response.send_message(embed=embed)

    # Leaves party if user isn't the leader.
    @app_commands.command(name="leave", description="Leave your current party")
    @app_commands.check(in_party)
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
    @app_commands.check(in_party)
    async def invite(self, interaction: Interaction, member: discord.Member):
        party: Party = interaction.extras.get("party")

        if not party.is_owner(interaction.user.id):
            raise NotPartyOwner(
                "Only the party leader can invite members.",
                title="You do not have permission",
                footer="Ask your leader to invite the user to the party.",
            )
        elif interaction.user == member:
            raise AlreadyInParty(
                "You're already here, bro.",
                title="Nice try bucko",
                footer="For real though, good curiosity. Test out all options!",
            )

        if member.bot:
            raise CustomError("Bots can't join parties.")

        embed = discord.Embed(
            title="Party invite!",
            description=f"{interaction.user.mention} invited you to join the party!",
            color=discord.Color.from_rgb(84, 178, 209),
        )
        view = PartyInviteView(party=party, invited=member, inviter=interaction.user)
        await interaction.response.send_message(
            content=f"Hey, {member.mention}!", embed=embed, view=view
        )
        view.message = await interaction.original_response()

    @app_commands.check(in_party)
    async def kick(self, interaction: Interaction, member_to_kick: discord.Member):
        """Remove a specified member from the party."""
        party: Party = interaction.extras.get("party")

        if not party.is_owner(interaction.user.id):
            raise NotPartyOwner(
                "Only the party leader can kick members.",
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

    @app_commands.check(in_party)
    async def promote(self, interaction: Interaction, member: discord.Member):
        """Promotes a user as the party leader."""
        party: Party = interaction.extras.get("party")

        if not party.is_owner(interaction.user.id):
            raise NotPartyOwner("Only the party leader can promote someone.")

        if interaction.user == member:
            raise CustomError("You cannot promote yourself.")

        if not party.is_member(member.id):
            raise UserNotInParty(f"{member.mention} is not in your party.")

        await party.change_owner(member.id)

        # TODO: Party channels do not work at the moment
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
