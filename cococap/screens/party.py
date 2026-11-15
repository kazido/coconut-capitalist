import discord

from cococap.errors import CustomError
from cococap.services import party_invites
from cococap.services.party import Party
from cococap.ui import Page, Screen
from cococap.ui.components import button, row, sep, text, user_select


class PartyScreen(Screen):
    id = "party"
    label = "Party"
    emoji = "👥"
    description = "Team up with other players"
    refresh_every = 5  # so an invite sent while the page is open shows up (and one that expires goes away)

    async def build(self) -> Page:
        party = await Party.for_user(self.user.id)
        invite = await self._invite_section()
        if party is None:
            return Page("Party", [
                *self.note_block(),
                *invite,
                text("You're not in a party.\nCreate one, then invite friends to play together."),
                row(button("Create party", emoji="🎉", style=discord.ButtonStyle.success, on_click=self._create)),
            ], accent=0x54B2D1)

        lines = []
        for member_id in party.members:
            crown = "👑 " if party.is_owner(member_id) else "• "
            you = "  *(you)*" if member_id == self.user.id else ""
            lines.append(f"{crown}**{await self.nav.name_of(member_id)}**{you}")
        body = [
            *self.note_block(),
            *invite,
            text(f"**Party #{party.party_id}**  ·  {party.member_count()} member(s)\n" + "\n".join(lines)),
        ]
        if party.is_owner(self.user.id):
            body += [sep(), row(user_select("Invite a player...", self._invite)),
                     row(button("Disband party", emoji="💥", style=discord.ButtonStyle.danger, on_click=self._disband))]
        else:
            body += [sep(), row(button("Leave party", emoji="🚪", on_click=self._leave))]
        body.append(text("-# Leaders can also right-click a member (Apps) to promote or kick them."))
        return Page("Party", body, accent=0x54B2D1)

    async def _invite_section(self) -> list:
        """The invite waiting for you (there is only ever one, and it lasts a minute), with Join and Decline."""
        invite = party_invites.pending_for(self.user.id)
        if invite is None:
            return []
        who = await self.nav.name_of(invite.inviter_id)
        return [text(f"### 📨 Party invite\n**{who}** invited you to their party. It expires <t:{int(invite.expires_at)}:R>."),
                row(button("Join", emoji="✅", style=discord.ButtonStyle.success, on_click=self._accept),
                    button("Decline", emoji="✖️", on_click=self._decline)),
                sep()]

    async def _accept(self, interaction: discord.Interaction) -> None:
        try:
            await party_invites.accept(self.user.id)
        except CustomError as e:
            return await self.refresh(interaction, str(e))
        await self.refresh(interaction, "You joined the party!")

    async def _decline(self, interaction: discord.Interaction) -> None:
        party_invites.decline(self.user.id)
        await self.refresh(interaction, "Invite declined.")

    async def _create(self, interaction: discord.Interaction) -> None:
        await Party.create(self.user.id)
        await self.refresh(interaction, "Your party has been created!")

    async def _invite(self, interaction: discord.Interaction, member: discord.abc.User) -> None:
        party = await Party.for_user(self.user.id)
        if party is None:
            return await self.refresh(interaction, "You are not in a party any more.")
        party.check_invite(self.user.id, member.id, is_bot=member.bot)
        party_invites.offer(party, self.user.id, member.id)  # nothing is posted in the chat: they see it on their own Party page
        await self.refresh(interaction, f"📨 Invited **{await self.nav.name_of(member.id)}**. It shows on their Party page for a minute.")

    async def _disband(self, interaction: discord.Interaction) -> None:
        party = await Party.for_user(self.user.id)
        if party is not None and party.is_owner(self.user.id):
            await party.delete()
        await self.refresh(interaction, "Party disbanded.")

    async def _leave(self, interaction: discord.Interaction) -> None:
        party = await Party.for_user(self.user.id)
        if party is not None:
            await party.leave(self.user.id)
        await self.refresh(interaction, "You left the party.")
