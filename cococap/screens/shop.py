import discord

from cococap.errors import CustomError
from cococap.registry import get_registry
from cococap.services import shop
from cococap.ui import Page, Screen, PromptModal
from cococap.ui.components import bits, button, row, section, sep, text

PER_PAGE = 4


def parse_quantity(raw: str) -> int:
    try:
        return int(raw.replace(",", ""))
    except ValueError:
        raise CustomError("Enter a whole number, like 5.") from None


class ShopScreen(Screen):
    id = "shop"
    label = "Shop"
    emoji = "🛒"
    description = "Buy seeds and supplies, sell what you've gathered"

    def __init__(self, nav):
        super().__init__(nav)
        self.page = 0
        self.mode = "buy"
        self.category: str | None = None  # None = everything; otherwise a skill name or "general"

    async def _entries(self):
        reg = get_registry()
        if self.mode == "buy":
            items = sorted(reg.shop_items(), key=lambda i: (i.skill or "", i.price, i.name))
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
            text(f"💸 You have **{bits(self.user.purse)}** bits"),
            row(
                button("Buy", emoji="🛒", style=discord.ButtonStyle.primary if self.mode == "buy" else discord.ButtonStyle.secondary, on_click=self._set_mode("buy")),
                button("Sell", emoji="💰", style=discord.ButtonStyle.primary if self.mode == "sell" else discord.ButtonStyle.secondary, on_click=self._set_mode("sell")),
            ),
            *self._category_rows(categories),
            sep(),
        ]
        if not entries:
            body.append(text("Nothing here yet." if self.mode == "buy" else "You have nothing to sell."))
        for item, owned in entries[self.page * PER_PAGE : (self.page + 1) * PER_PAGE]:
            if self.mode == "buy":
                blurb = f"**{bits(item.price)}** bits  ·  {item.description}"[:300]
                accessory = button("Buy", style=discord.ButtonStyle.success, disabled=self.user.purse < item.price, on_click=self._ask_quantity(item.id, "buy", 1))
            else:
                blurb = f"×{owned:,}  ·  {bits(item.sell_price)} each  ·  **{bits(item.sell_price * owned)}** for all"  # (the count is plain text, not in the bold heading)
                accessory = button("Sell", style=discord.ButtonStyle.success, on_click=self._ask_quantity(item.id, "sell", owned))
            body.append(section(f"### {item.display}\n{blurb}", accessory=accessory))
        if pages > 1:
            body.append(
                row(
                    button(emoji="◀️", on_click=self._turn(-1), disabled=self.page == 0),
                    button(f"{self.page + 1}/{pages}", disabled=True),
                    button(emoji="▶️", on_click=self._turn(1), disabled=self.page >= pages - 1),
                )
            )
        return Page("Shop", body, accent=discord.Colour.gold().value)

    CATEGORY_EMOJI = {"mining": "⛏️", "farming": "🌽", "foraging": "🌳", "fishing": "🐟", "combat": "⚔️", "general": "📦"}

    def _category_rows(self, categories: list[str]) -> list:
        """Buttons to filter the list: All, then one per skill that has something to show."""
        if len(categories) < 2:
            return []
        buttons = [button("All", style=discord.ButtonStyle.primary if self.category is None else discord.ButtonStyle.secondary, on_click=self._set_category(None))]
        for c in categories:
            buttons.append(
                button(
                    c.title() if self.category == c else None,
                    emoji=self.CATEGORY_EMOJI.get(c, "📦"),
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

    def _ask_quantity(self, item_id: str, action: str, default: int):
        async def ask(interaction: discord.Interaction) -> None:
            name = get_registry().item(item_id).name

            async def submitted(modal_interaction: discord.Interaction, raw: str) -> None:
                quantity = parse_quantity(raw)
                if action == "buy":
                    purchase = await shop.buy(self.user, item_id, quantity)
                    note = f"Bought {purchase.quantity:,} × {name} for {bits(purchase.total)} bits."
                else:
                    earned = await shop.sell(self.user, item_id, quantity)
                    note = f"Sold {quantity:,} × {name} for {bits(earned)} bits."
                await self.refresh(modal_interaction, note)

            await interaction.response.send_modal(
                PromptModal(f"{action.title()} {name}", "How many?", submitted, default=str(default), max_length=9)
            )

        return ask
