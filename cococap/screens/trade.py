import discord

from cococap.errors import CustomError
from cococap.registry import get_registry
from cococap.services import trade
from cococap.ui import Page, PromptModal, Screen
from cococap.ui.components import bits, button, row, section, select, sep, text, user_select

SHOWN_ITEMS = 25  # (a dropdown holds 25: your most valuable stacks come first)


def describe(items: dict[str, int], bit_amount: int) -> str:
    reg = get_registry()
    parts = [f"{reg.item(i).display} ×{q:,}" for i, q in items.items()]
    if bit_amount:
        parts.append(f"💸 **{bits(bit_amount)}** bits")
    return "\n".join(parts) if parts else "*nothing yet*"


def parse_number(raw: str) -> int:
    try:
        return int(raw.replace(",", ""))
    except ValueError:
        raise CustomError("Enter a whole number, like 5.") from None


class TradeScreen(Screen):
    """Send a gift of items and bits to another player. They accept or decline; nothing is asked back."""

    id = "trade"
    label = "Trade"
    emoji = "🎁"
    description = "Send items and bits to another player"
    links = ()
    refresh_every = 5  # so a gift sent while the page is open shows up (and one that expires goes away)

    def __init__(self, nav):
        super().__init__(nav)
        self.to: int | None = None  # who the gift is for
        self.items: dict[str, int] = {}
        self.bits = 0

    async def build(self) -> Page:
        body = [*self.note_block()]
        if incoming := trade.pending_for(self.user.id):
            who = await self.nav.name_of(incoming.sender_id)
            body += [text(f"### 🎁 A gift from {who}\n{describe(incoming.items, incoming.bits)}\n-# Expires <t:{int(incoming.expires_at)}:R>. Nothing is asked back."),
                     row(button("Accept", emoji="✅", style=discord.ButtonStyle.success, on_click=self._accept),
                         button("Decline", on_click=self._decline)), sep()]
        if waiting := trade.sent_by(self.user.id):
            who = await self.nav.name_of(waiting.recipient_id)
            body += [section(f"### ⏳ Waiting for {who}\n{describe(waiting.items, waiting.bits)}", accessory=button("Take back", on_click=self._withdraw)), sep()]
        body.append(text("### 📤 Send a gift\n" + (f"To **{await self.nav.name_of(self.to)}**" if self.to else "Pick a player first.")
                         + "\n" + describe(self.items, self.bits)))
        body.append(row(user_select("Send to...", self._pick_player)))
        stacks = sorted((await trade.tradable(self.user)).items(), key=lambda kv: -get_registry().item(kv[0]).sell_price * kv[1])[:SHOWN_ITEMS]
        if stacks:
            body.append(row(select("Add an item...", [
                discord.SelectOption(label=get_registry().item(i).name[:90], description=f"you have {q:,}", value=i) for i, q in stacks], self._add_item)))
        body.append(row(button("Add bits", emoji="💸", on_click=self._add_bits),
                        button("Clear", disabled=not (self.items or self.bits), on_click=self._clear),
                        button("Send", emoji="📨", style=discord.ButtonStyle.success, disabled=not (self.to and (self.items or self.bits)), on_click=self._send)))
        body.append(text(f"-# Tools and gear can't be sent. Gifts of bits are at least {trade.MIN_BITS}. They have {trade.OFFER_SECONDS // 60} minutes to accept."))
        return Page("Trade", body, accent=0xE67E73)

    # --- building the gift -----------------------------------------------------------------------------------------------------
    async def _pick_player(self, interaction: discord.Interaction, member: discord.abc.User) -> None:
        if member.bot or member.id == self.user.id:
            return await self.refresh(interaction, "Pick another (human) player.")
        self.to = member.id
        await self.refresh(interaction)

    async def _add_item(self, interaction: discord.Interaction, values: list[str]) -> None:
        item_id = values[0]
        have = (await self.user.items()).get(item_id, 0)
        name = get_registry().item(item_id).name

        async def submitted(modal_interaction: discord.Interaction, raw: str) -> None:
            quantity = min(parse_number(raw), have)
            if quantity <= 0:
                return await self.refresh(modal_interaction, "Enter a number above zero.")
            self.items[item_id] = quantity
            await self.refresh(modal_interaction, f"Added {quantity:,} {name}.")

        await interaction.response.send_modal(PromptModal(f"Send {name}", f"How many? (you have {have:,})", submitted, default=str(have), max_length=9))

    async def _add_bits(self, interaction: discord.Interaction) -> None:
        async def submitted(modal_interaction: discord.Interaction, raw: str) -> None:
            self.bits = max(0, parse_number(raw))
            await self.refresh(modal_interaction, f"The gift includes {bits(self.bits)} bits." if self.bits else "Removed the bits.")

        await interaction.response.send_modal(PromptModal("Send bits", "How many bits?", submitted, default=str(self.bits or ""), max_length=12))

    async def _clear(self, interaction: discord.Interaction) -> None:
        self.items, self.bits = {}, 0
        await self.refresh(interaction)

    # --- sending and answering ---------------------------------------------------------------------------------------------------
    async def _send(self, interaction: discord.Interaction) -> None:
        try:
            await trade.offer(self.user, self.to, self.items, self.bits)
        except trade.TradeError as error:
            return await self.refresh(interaction, str(error))
        self.items, self.bits = {}, 0
        await self.refresh(interaction, f"📨 Sent! **{await self.nav.name_of(self.to)}** can accept it from their Trade page.")

    async def _withdraw(self, interaction: discord.Interaction) -> None:
        trade.withdraw(self.user.id)
        await self.refresh(interaction, "You took the gift back.")

    async def _decline(self, interaction: discord.Interaction) -> None:
        trade.decline(self.user.id)
        await self.refresh(interaction, "Gift declined.")

    async def _accept(self, interaction: discord.Interaction) -> None:
        try:
            got = await trade.accept(self.user)
        except trade.TradeError as error:
            return await self.refresh(interaction, str(error))
        await self.refresh(interaction, f"🎁 You received a gift from **{await self.nav.name_of(got.sender_id)}**!")
