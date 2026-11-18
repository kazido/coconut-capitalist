import discord
import random

from logging import getLogger
from discord.ext import commands
from discord import app_commands, Interaction
from cococap import emojis
from cococap.user import User
from cococap.exts.utils.error import CustomError
from cococap.services.party import (  # noqa: F401  (re-exported: tests and other cogs import these from here)
    AlreadyInParty,
    NotPartyOwner,
    Party,
    PartyNotEmpty,
    PartyNotFound,
    UserNotInParty,
)
from cococap.services import party_invites
from utils.custom_embeds import SuccessEmbed, CustomEmbed


log = getLogger(__name__)


class PartyEmbed(SuccessEmbed):
    def __init__(self, *, desc, interaction):
        super().__init__(desc=desc, interaction=interaction, activity="partying")


async def load_party(interaction: Interaction) -> Party | None:
    """The clicker's party, loaded once per interaction and kept in `interaction.extras`.

    The cog's `interaction_check` only runs for the cog's slash commands, NOT for the right-click (context menu) commands, which are
    registered on the bot's tree. So the checks below load the party themselves instead of trusting that something did it before.
    """
    if "party" not in interaction.extras:
        interaction.extras["party"] = await Party.for_user(interaction.user.id)
    return interaction.extras["party"]


# Custom check to make sure the user is in a party
async def in_party(interaction: Interaction):
    party = await load_party(interaction)
    if not party:
        raise PartyNotFound("You are not currently in a party.")
    return True  # There is a party associated with the interaction


# Custom check to make sure the user is NOT in a party
async def not_in_party(interaction: Interaction):
    party = await load_party(interaction)
    if party:
        raise AlreadyInParty("You are already in a party.")
    return True  # There is a party associated with the interaction


# Custom check to make sure the user owns the party
async def is_owner(interaction: Interaction):
    party = await load_party(interaction)

    if party is None or not party.is_owner(interaction.user.id):
        raise NotPartyOwner("You are not the party owner.")
    return True  # The interaction user owns the associated party


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
        return await discord.utils.maybe_coroutine(super().interaction_check, interaction)  # (the base check is a plain function in this discord.py)

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

        emptied = await party.leave(interaction.user.id)
        if emptied:
            return await interaction.response.send_message("*You left the party.*", ephemeral=True)
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

        party.check_invite(interaction.user.id, member.id, is_bot=member.bot)
        party_invites.offer(party, interaction.user.id, member.id)  # no message in the channel: it shows on their Party page for a minute
        await interaction.response.send_message(f"{emojis.icon('page', '📨')} Invited **{member.display_name}**. It shows on their Party page for a minute.", ephemeral=True)

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
