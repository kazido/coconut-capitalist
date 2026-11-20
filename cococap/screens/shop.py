import discord

from cococap import emojis
from cococap.errors import CustomError
from cococap.registry import get_registry
from cococap.services import farming, market, shop, smithing
from cococap.ui import Page, Screen, PromptModal
from cococap.ui.components import bits, button, row, section_art, select, sep, text
from cococap.ui.tabs import TabsScreen

PER_PAGE = 10
QUICK_AMOUNT = 10  # the "10x" buttons


def parse_quantity(raw: str) -> int:
    try:
        return int(raw.replace(",", ""))
    except ValueError:
        raise CustomError("Enter a whole number, like 5.") from None


def clamp_quantity(raw: str, maximum: int) -> int:
    """What a custom amount means: a whole number from 1 up to `maximum`. Asking for more than you can is clamped to the max, not an error,
    so the modal's prefilled max always works. Anything that is not a whole number, or is below 1, gets a friendly message."""
    try:
        quantity = int(raw.replace(",", ""))
    except ValueError:
        quantity = 0
    if quantity < 1:
        raise CustomError(f"Enter a whole number from 1 to {maximum:,}.")
    return min(quantity, maximum)


class ShopPane(Screen):
    """Buy seeds and supplies, or sell what you've gathered one item at a time. The Shop page (ShopScreen)."""

    label = "Shop"
    emoji = emojis.Lazy("ui_shop", "🛒")
    description = "Buy seeds and supplies, or sell what you've gathered"

    def __init__(self, nav):
        super().__init__(nav)
        self.page = 0
        self.mode = "buy"
        self.selected: str | None = None
        self.category: str | None = None  # None = everything; otherwise a skill name or "general"

    async def _entries(self):
        reg = get_registry()
        if self.mode == "buy":
            locked = await farming.locked_seeds(self.user, reg)
            items = sorted((i for i in reg.shop_items() if i.id not in locked), key=lambda i: (i.skill or "", i.price, i.name))
            return [(i, None) for i in items]
        owned = await self.user.items()
        sellable = [(reg.find_item(k), q) for k, q in owned.items()]
        return sorted(((i, q) for i, q in sellable if i and i.sellable), key=lambda e: e[0].name)

    @staticmethod
    def _category_of(item) -> str:
        return item.skill or "general"

    async def build(self) -> Page:
        all_entries = await self._entries()
        categories = sorted({self._category_of(i) for i, _ in all_entries}, key=lambda c: (c == "general", c))
        if self.category not in categories:
            self.category = None
        entries = [(i, q) for i, q in all_entries if self.category in (None, self._category_of(i))]
        pages = max(1, -(-len(entries) // PER_PAGE))
        self.page = min(self.page, pages - 1)
        body = [
            *self.note_block(),
            text(f"You have **{emojis.bits(self.user.purse)}**"),
            row(
                button("Buy", emoji=emojis.icon('sell', '🛒'), style=discord.ButtonStyle.primary if self.mode == "buy" else discord.ButtonStyle.secondary, on_click=self._set_mode("buy")),
                button("Sell", emoji=emojis.icon('sell', '💰'), style=discord.ButtonStyle.primary if self.mode == "sell" else discord.ButtonStyle.secondary, on_click=self._set_mode("sell")),
            ),
            *self._category_rows(categories),
            sep(),
        ]
        if not entries:
            body.append(text("Nothing here yet." if self.mode == "buy" else "You have nothing to sell."))
        shown = entries[self.page * PER_PAGE : (self.page + 1) * PER_PAGE]
        if shown:
            if self.selected not in {i.id for i, _ in shown}:
                self.selected = shown[0][0].id
            body += await self._listing(shown)
        if pages > 1:
            body.append(
                row(
                    button(emoji=emojis.icon('prev', '◀️'), on_click=self._turn(-1), disabled=self.page == 0),
                    button(f"{self.page + 1}/{pages}", disabled=True),
                    button(emoji=emojis.icon('next', '▶️'), on_click=self._turn(1), disabled=self.page >= pages - 1),
                )
            )
        return Page("Shop", body, accent=discord.Colour.gold().value)

    def _line(self, item, owned) -> str:
        if self.mode == "buy":
            return f"{item.display}  ·  **{emojis.bits(item.price)}**"
        return f"{item.display}  ·  ×{owned:,}  ·  {emojis.bits(item.sell_price * owned)}"

    async def _listing(self, shown) -> list:
        """A markdown list of this page, one dropdown to pick from it, the picked item's details, and its amount buttons (1x, 10x, custom)."""
        buy = self.mode == "buy"
        picked, owned = next((i, q) for i, q in shown if i.id == self.selected)
        lines = [(f"{emojis.icon('next', '▶')} **" if i.id == self.selected else "") + self._line(i, q).replace("**", "") + ("**" if i.id == self.selected else "") for i, q in shown]
        options = [
            discord.SelectOption(
                label=i.name, value=i.id, emoji=i.emoji or None, default=i.id == self.selected,
                description=(f"{bits(i.price)} bits" if buy else f"×{q:,}  ·  {bits(i.sell_price)} each")[:100],
            )
            for i, q in shown
        ]
        if buy:
            # What you can afford AND may own: a tool is one per kind, so it is 0 or 1 here.
            limit = await shop.max_affordable(self.user, picked.id)
            detail = f"### {picked.display}\n**{emojis.bits(picked.price)}**  ·  {picked.description}"[:600]
        else:
            limit = owned
            detail = f"### {picked.display}\n×{owned:,}  ·  {bits(picked.sell_price)} each  ·  **{bits(picked.sell_price * owned)}** for all"
        verb = self.mode.title()
        style = discord.ButtonStyle.success
        actions = row(
            button(f"{verb} 1x", style=style, disabled=limit < 1, on_click=self._trade(picked.id, 1)),
            button(f"{verb} {QUICK_AMOUNT}x", style=style, disabled=limit < QUICK_AMOUNT, on_click=self._trade(picked.id, QUICK_AMOUNT)),
            # Custom is never disabled: when you can't afford any, the modal still opens and buying then gives the friendly error.
            button(f"{verb} custom", style=discord.ButtonStyle.primary, on_click=self._ask_custom(picked.id, limit)),
        )
        art = emojis.image_url("item", picked.id)
        # Discord gives a dropdown a whole row, so the buttons sit straight under it: list, details (+picture), dropdown, buttons.
        return [text("\n".join(lines)), section_art(detail, art), row(select("Pick an item...", options, self._pick)), actions]

    async def _pick(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.selected = values[0]
        await self.refresh(interaction)

    def _category_rows(self, categories: list[str]) -> list:
        """Buttons to filter the list: All, then one per skill that has something to show."""
        if len(categories) < 2:
            return []
        buttons = [button("All", style=discord.ButtonStyle.primary if self.category is None else discord.ButtonStyle.secondary, on_click=self._set_category(None))]
        for c in categories:
            buttons.append(
                button(
                    c.title() if self.category == c else None,
                    emoji=emojis.skill(c, emojis.icon('crate', '📦')),
                    style=discord.ButtonStyle.primary if self.category == c else discord.ButtonStyle.secondary,
                    on_click=self._set_category(c),
                )
            )
        return [row(*buttons[i : i + 5]) for i in range(0, len(buttons), 5)]

    def _set_category(self, category: str | None):
        async def pick(interaction: discord.Interaction) -> None:
            self.category, self.page = category, 0
            await self.refresh(interaction)

        return pick

    def _set_mode(self, mode: str):
        async def switch(interaction: discord.Interaction) -> None:
            self.mode, self.page = mode, 0
            await self.refresh(interaction)

        return switch

    def _turn(self, step: int):
        async def turn(interaction: discord.Interaction) -> None:
            self.page += step
            await self.refresh(interaction)

        return turn

    async def _perform(self, interaction: discord.Interaction, item_id: str, quantity: int) -> None:
        """Buy or sell (whichever mode the page is in) and redraw with what happened. The services raise the friendly errors."""
        name = get_registry().item(item_id).name
        if self.mode == "buy":
            purchase = await shop.buy(self.user, item_id, quantity)
            note = f"Bought {purchase.quantity:,} × {name} for {emojis.bits(purchase.total)}."
        else:
            earned = await shop.sell(self.user, item_id, quantity)
            note = f"Sold {quantity:,} × {name} for {emojis.bits(earned)}."
        await self.refresh(interaction, note)

    def _trade(self, item_id: str, quantity: int):
        async def trade(interaction: discord.Interaction) -> None:
            await self._perform(interaction, item_id, quantity)

        return trade

    def _ask_custom(self, item_id: str, limit: int):
        async def ask(interaction: discord.Interaction) -> None:
            name = get_registry().item(item_id).name
            action = self.mode

            async def submitted(modal_interaction: discord.Interaction, raw: str) -> None:
                # With nothing affordable the max is 0: clamp to 1 so buying gives its own "you need N bits" error.
                await self._perform(modal_interaction, item_id, clamp_quantity(raw, max(limit, 1)))

            await interaction.response.send_modal(
                PromptModal(
                    f"{action.title()} {name}",
                    f"How many? (max {limit:,})",
                    submitted,
                    default=str(max(limit, 1)),
                    max_length=9,
                )
            )

        return ask


def _restock_text(seconds: int) -> str:
    hours, minutes = divmod(-(-max(seconds, 0) // 60), 60)  # rounds up to whole minutes
    return f"{hours}h {minutes}m" if hours else f"{minutes}m"


class MarketPane(Screen):
    """A smithing-part shop: a few parts for bits, restocked on a timer, one of each per player (services/market.py)."""

    shop = ""  # "merchant" or "black_market" (configs/market.toml)

    def __init__(self, nav):
        super().__init__(nav)
        self.picked: int | None = None  # the slot picked in the dropdown

    async def build(self) -> Page:
        reg = get_registry()
        body = [*self.note_block(), text(f"You have **{emojis.bits(self.user.purse)}**")]
        if not await market.unlocked(self.user, self.shop, reg):
            body.append(text(market.unlock_text(self.shop, reg)))
            return Page(self.label, body, accent=discord.Colour.gold().value)
        offers = await market.stock(self.user, self.shop, registry=reg)
        body.append(text(f"Restocks in {_restock_text(market.seconds_until_restock(self.shop, registry=reg))}"))
        rules = smithing._rules(reg)
        lines = []
        for o in offers:
            names = smithing.trait_icons(o.traits, rules)
            status = " · **sold**" if o.bought else ""
            lines.append(f"**{o.slot + 1}.** {smithing.part_label(o.part_type, o.tier)} part · {names} · {emojis.bits(o.price)}{status}")
        body.append(text("\n".join(lines)))
        open_offers = [o for o in offers if not o.bought]
        if not open_offers:
            body.append(text("Sold out until the next restock."))
            return Page(self.label, body, accent=discord.Colour.gold().value)
        if self.picked not in {o.slot for o in open_offers}:
            self.picked = open_offers[0].slot
        options = [
            discord.SelectOption(
                label=f"Slot {o.slot + 1}: T{o.tier} Tool {o.part_type.title()} {smithing.trait_icons(o.traits, rules, plain=True)}", value=str(o.slot),
                description=f"{bits(o.price)} bits", default=o.slot == self.picked,
            )
            for o in open_offers
        ]
        body.append(row(select("Pick a part...", options, self._pick)))
        body.append(row(button("Buy", emoji=emojis.icon('sell', '💰'), style=discord.ButtonStyle.success, on_click=self._buy)))
        return Page(self.label, body, accent=discord.Colour.gold().value)

    async def _pick(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.picked = int(values[0])
        await self.refresh(interaction)

    async def _buy(self, interaction: discord.Interaction) -> None:
        if self.picked is None:
            await self.refresh(interaction, "Pick a part first.")
            return
        offer = await market.buy(self.user, self.shop, self.picked)
        self.picked = None
        await self.refresh(interaction, f"Bought a {smithing.part_label(offer.part_type, offer.tier)} part for {emojis.bits(offer.price)}.")


class MerchantPane(MarketPane):
    shop = "merchant"
    label = "Merchant"
    emoji = emojis.Lazy("ui_merchant", "🧳")
    description = "A travelling merchant with cheap parts, restocked every hour"


class BlackMarketPane(MarketPane):
    shop = "black_market"
    label = "Black Market"
    emoji = emojis.Lazy("ui_black_market", "🕶️")
    description = "Rich parts at steep prices, restocked every day"


class ShopScreen(TabsScreen):
    """The Shop page: buy seeds and supplies, and sell what you have one item at a time (ShopPane)."""

    id = "shop"
    label = "Shop"
    emoji = emojis.Lazy("ui_shop", "🛒")
    description = "Buy seeds and supplies, or sell what you've gathered one item at a time"
    panes = {"buy": ShopPane, "merchant": MerchantPane, "black_market": BlackMarketPane}
