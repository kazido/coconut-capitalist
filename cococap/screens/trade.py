import math

import discord

from cococap.errors import CustomError
from cococap import emojis
from cococap.registry import get_registry
from cococap.services import trade
from cococap.ui import Page, PromptModal, Screen
from cococap.ui.components import bits, button, row, section, select, sep, text, user_select

SHOWN_ITEMS = 25  # (a dropdown holds 25: your most valuable stacks come first)


def describe(items: dict[str, int], bit_amount: int) -> str:
    reg = get_registry()
    parts = [f"{reg.item(i).display} ×{q:,}" for i, q in items.items()]
    if bit_amount:
        parts.append(f"**{emojis.bits(bit_amount)}**")
    return "\n".join(parts) if parts else "*nothing yet*"


def parse_number(raw: str) -> int:
    try:
        return int(raw.replace(",", ""))
    except ValueError:
        raise CustomError("Enter a whole number, like 5.") from None


class TradeScreen(Screen):
    """Trade with another player: ask them, then both of you fill your side of one shared window and both press Accept."""

    id = "trade"
    label = "Trade"
    emoji = emojis.Lazy("ui_trade", "🤝")
    description = "Swap items and bits with another player"
    links = ()

    @property
    def refresh_every(self) -> float:  # type: ignore[override]
        """Redraw every 3 s so the other player's changes (and a request sent to you) show up on their own; every second during the countdown."""
        window = trade.window_of(self.user.id)
        return 1 if window is not None and trade.countdown_left(window) is not None else 3

    async def build(self) -> Page:
        body = [*self.note_block()]
        await trade.settle(self.user.id)  # (the countdown may have just run out: whoever looks first makes the trade happen)
        if receipt := trade.receipt_of(self.user.id):
            return Page("Trade", [*body, *await self._receipt(receipt)], accent=0xE67E73)
        if finished := trade.pop_result(self.user.id):
            body.append(text(f"### {finished}"))
        if (window := trade.window_of(self.user.id)) and not window.closed:
            return Page("Trade", [*body, *await self._window(window)], accent=0xE67E73)
        if invite := trade.invite_for(self.user.id):
            who = await self.nav.name_of(invite.sender_id)
            body += [text(f"### {emojis.icon('trade', '🤝')} {who} wants to trade\n-# Expires <t:{int(invite.expires_at)}:R>."),
                     row(button("Accept", emoji=emojis.icon('check', '✅'), style=discord.ButtonStyle.success, on_click=self._accept_invite),
                         button("Decline", on_click=self._decline))]
        if waiting := trade.invite_from(self.user.id):
            who = await self.nav.name_of(waiting.recipient_id)
            body.append(section(f"### {emojis.icon('timer', '⏳')} Waiting for {who}\n-# Expires <t:{int(waiting.expires_at)}:R>.", accessory=button("Cancel", on_click=self._withdraw)))
        body += [sep(), text("### Start a trade\nPick a player. When they accept, you both get a window to add items and bits, and a trade happens when you both press Accept. "
                             "One of you adding nothing makes it a gift."),
                 row(user_select("Trade with...", self._ask))]
        return Page("Trade", body, accent=0xE67E73)

    # --- the receipt ------------------------------------------------------------------------------------------------------------------
    async def _receipt(self, receipt: trade.Receipt) -> list:
        name = await self.nav.name_of(receipt.partner_id)
        return [text(f"### {emojis.icon('trade', '🤝')} Trade complete!\n**You gave**\n{describe(receipt.gave_items, receipt.gave_bits)}\n\n"
                     f"**You got from {name}**\n{describe(receipt.got_items, receipt.got_bits)}"),
                row(button("Continue", style=discord.ButtonStyle.success, on_click=self._continue))]

    async def _continue(self, interaction: discord.Interaction) -> None:
        trade.dismiss_receipt(self.user.id)
        await self.refresh(interaction)

    # --- the shared window ------------------------------------------------------------------------------------------------------------
    async def _window(self, window: trade.Window) -> list:
        me, them = self.user.id, window.other(self.user.id)
        name = await self.nav.name_of(them)
        mine, theirs = window.offer(me), window.offer(them)
        left = trade.countdown_left(window)
        countdown = f"\n\n### {emojis.icon('timer', '⏳')} Trading in {max(1, math.ceil(left))}... (change anything or undo to stop)" if left is not None else ""
        tick = lambda uid: f" {emojis.icon('check', '✅')} accepted" if uid in window.accepted else ""  # noqa: E731
        body = [text(f"### {emojis.icon('trade', '🤝')} Trading with {name}\n"
                     f"**You**{tick(me)}\n{describe(*mine)}\n\n**{name}**{tick(them)}\n{describe(*theirs)}{countdown}"
                     f"\n-# Any change takes both Accepts back. Tools and gear can't be traded. Closes <t:{int(window.expires_at)}:R> if nothing changes.")]
        stacks = sorted((await trade.tradable(self.user)).items(), key=lambda kv: -get_registry().item(kv[0]).sell_price * kv[1])[:SHOWN_ITEMS]
        if stacks:
            body.append(row(select("Add an item...", [
                discord.SelectOption(label=get_registry().item(i).name[:90], description=f"you have {q:,}", value=i, emoji=get_registry().item(i).emoji or None) for i, q in stacks], self._add_item)))
        accepted = me in window.accepted
        body.append(row(button("Find item", emoji=emojis.icon('search', '🔎'), on_click=self._find_item),
                        button("Add bits", emoji=emojis.currency("bits"), on_click=self._add_bits),
                        button("Empty my side", disabled=not (mine[0] or mine[1]), on_click=self._empty),
                        button("Accepted: undo" if accepted else "Accept", emoji=emojis.icon('check', '✅'), style=discord.ButtonStyle.secondary if accepted else discord.ButtonStyle.success,
                               disabled=not (mine[0] or mine[1] or theirs[0] or theirs[1]) and not accepted, on_click=self._unaccept if accepted else self._accept(window.version)),
                        button("Cancel trade", emoji=emojis.icon('cross', '✖️'), style=discord.ButtonStyle.danger, on_click=self._cancel)))
        return body

    async def _add_item(self, interaction: discord.Interaction, values: list[str]) -> None:
        item_id = values[0]
        have = (await self.user.items()).get(item_id, 0)
        name = get_registry().item(item_id).name

        async def submitted(modal_interaction: discord.Interaction, raw: str) -> None:
            try:
                await trade.put_items(self.user, item_id, min(parse_number(raw), have))
            except trade.TradeError as error:
                return await self.refresh(modal_interaction, str(error))
            await self.refresh(modal_interaction, f"Offering {name}." if parse_number(raw) else f"Took {name} back out.")

        await interaction.response.send_modal(PromptModal(f"Offer {name}", f"How many? (you have {have:,}; 0 to take it out)", submitted, default=str(have), max_length=9))

    async def _find_item(self, interaction: discord.Interaction) -> None:
        """The dropdown only holds 25 stacks: this finds ANY tradable item by (part of) its name, with an optional amount ("iron ore 20")."""
        async def submitted(modal_interaction: discord.Interaction, raw: str) -> None:
            words = raw.strip().split()
            amount = None
            if len(words) > 1 and words[-1].replace(",", "").isdigit():
                amount = int(words.pop().replace(",", ""))
            query = " ".join(words).lower()
            reg = get_registry()
            stacks = await trade.tradable(self.user)
            exact = [i for i in stacks if reg.item(i).name.lower() == query]
            matches = exact or [i for i in stacks if query and query in reg.item(i).name.lower()]
            if not matches:
                return await self.refresh(modal_interaction, f"You have no tradable item called \"{' '.join(words)}\".")
            if len(matches) > 1:
                names = ", ".join(reg.item(i).name for i in matches[:6])
                return await self.refresh(modal_interaction, f"Which one? {names}" + ("..." if len(matches) > 6 else ""))
            item_id = matches[0]
            have = stacks[item_id]
            count = have if amount is None else min(amount, have)
            try:
                await trade.put_items(self.user, item_id, count)
            except trade.TradeError as error:
                return await self.refresh(modal_interaction, str(error))
            await self.refresh(modal_interaction, f"Offering {count:,} {reg.item(item_id).name}." if count else f"Took {reg.item(item_id).name} back out.")

        await interaction.response.send_modal(PromptModal("Find an item", "Item name, then an amount (default: all)", submitted, placeholder="iron ore 20", max_length=60))

    async def _add_bits(self, interaction: discord.Interaction) -> None:
        async def submitted(modal_interaction: discord.Interaction, raw: str) -> None:
            try:
                await trade.put_bits(self.user, parse_number(raw))
            except trade.TradeError as error:
                return await self.refresh(modal_interaction, str(error))
            await self.refresh(modal_interaction)

        await interaction.response.send_modal(PromptModal("Offer bits", "How many bits? (0 for none)", submitted, max_length=12))

    async def _empty(self, interaction: discord.Interaction) -> None:
        await self._run(interaction, lambda: trade.empty_mine(self.user.id))

    def _accept(self, version: int):
        async def go(interaction: discord.Interaction) -> None:
            await self._run(interaction, lambda: trade.accept(self.user, version))

        return go

    async def _unaccept(self, interaction: discord.Interaction) -> None:
        await self._run(interaction, lambda: trade.unaccept(self.user.id))

    async def _cancel(self, interaction: discord.Interaction) -> None:
        trade.cancel(self.user.id)
        await self.refresh(interaction)

    async def _run(self, interaction: discord.Interaction, action) -> None:
        try:
            result = action()
            if hasattr(result, "__await__"):
                await result
        except trade.TradeError as error:
            return await self.refresh(interaction, str(error))
        await self.refresh(interaction)

    # --- asking -------------------------------------------------------------------------------------------------------------------------
    async def _ask(self, interaction: discord.Interaction, member: discord.abc.User) -> None:
        try:
            trade.ask(self.user.id, member.id, is_bot=member.bot)
        except trade.TradeError as error:
            return await self.refresh(interaction, str(error))
        await self.refresh(interaction, f"{emojis.icon('page', '📨')} Asked **{await self.nav.name_of(member.id)}**. It shows on their Trade page for a minute.")

    async def _withdraw(self, interaction: discord.Interaction) -> None:
        trade.withdraw_ask(self.user.id)
        await self.refresh(interaction)

    async def _decline(self, interaction: discord.Interaction) -> None:
        trade.decline(self.user.id)
        await self.refresh(interaction, "Declined.")

    async def _accept_invite(self, interaction: discord.Interaction) -> None:
        try:
            trade.accept_invite(self.user.id)
        except trade.TradeError as error:
            return await self.refresh(interaction, str(error))
        await self.refresh(interaction)
