"""The Join/Decline invite message sent to a player invited to a party."""

import discord
from discord import Interaction

from cococap.errors import CustomError
from cococap.services.party import Party


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


async def send_invite(interaction: Interaction, party: Party, member: discord.Member) -> None:
    """Invite `member` (after the rules in ``Party.check_invite`` passed) with a Join/Decline message."""
    embed = discord.Embed(
        title="Party invite!",
        description=f"{interaction.user.mention} invited you to join the party!",
        color=discord.Color.from_rgb(84, 178, 209),
    )
    view = PartyInviteView(party=party, invited=member, inviter=interaction.user)
    await interaction.response.send_message(content=f"Hey, {member.mention}!", embed=embed, view=view)
    view.message = await interaction.original_response()
