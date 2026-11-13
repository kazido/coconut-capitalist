import discord

from cococap.services.party import Party
from cococap.ui import Page, Screen
from cococap.ui.components import button, row, sep, text, user_select
from cococap.ui.party_invite import send_invite


class PartyScreen(Screen):
    id = "party"
    label = "Party"
    emoji = "👥"
    description = "Team up with other players"

    async def build(self) -> Page:
        party = await Party.for_user(self.user.id)
        if party is None:
            return Page("Party", [
                *self.note_block(),
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
            text(f"**Party #{party.party_id}**  ·  {party.member_count()} member(s)\n" + "\n".join(lines)),
        ]
        if party.is_owner(self.user.id):
            body += [sep(), row(user_select("Invite a player...", self._invite)),
                     row(button("Disband party", emoji="💥", style=discord.ButtonStyle.danger, on_click=self._disband))]
        else:
            body += [sep(), row(button("Leave party", emoji="🚪", on_click=self._leave))]
        body.append(text("-# Leaders can also right-click a member (Apps) to promote or kick them."))
        return Page("Party", body, accent=0x54B2D1)

    async def _create(self, interaction: discord.Interaction) -> None:
        await Party.create(self.user.id)
        await self.refresh(interaction, "Your party has been created!")

    async def _invite(self, interaction: discord.Interaction, member: discord.abc.User) -> None:
        party = await Party.for_user(self.user.id)
        if party is None:
            return await self.refresh(interaction, "You are not in a party any more.")
        party.check_invite(self.user.id, member.id, is_bot=member.bot)
        await send_invite(interaction, party, member)  # a separate message the invited player answers

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
