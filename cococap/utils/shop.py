from typing import Optional
import discord
import asyncio

from cococap.utils.utils import construct_embed
from cococap import instance as i

from discord import Interaction, ButtonStyle, PartialEmoji, Embed, Color
from discord.interactions import Interaction
from discord.ui import View, Button
from cococap.classLibrary import RequestUser


# View for a shop, will list many items that can be selected and bought
class ShopInterface(View):
    def __init__(self, *, timeout: float | None = 180):
        super().__init__(timeout=timeout)
        self.items = []
        self.embed = self.create_embed()
        self._hovered_item_index = 0
        
    # @Button(emoji=i.get_emoji(1161002648099618869), style=ButtonStyle.blurple, disabled=True)
    async def next_item(self, interaction: discord.Interaction, button: Button):
        self._hovered_item_index += 1
        await interaction.response.edit_message(embed="")
        
    # @Button(emoji=i.get_emoji(1161002666328068126), style=ButtonStyle.blurple, disabled=False)
    async def back_item(self, interaction: discord.Interaction, button: Button):
        self._hovered_item_index -= 1
        
    def create_embed(self):
        embed = Embed(color=discord.Color.green())
        for item in self.items:
            embed.add_field(name="")

# View for the overall shop, with buttons to select subshops
class ItemMenu(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, *, timeout=60):
        super().__init__(timeout=timeout)
        self.pages = []
        self.interaction = interaction
        self.embed = self.create_embed()
        self.add_item(CloseShopButton(interaction, row=2))

    # Creates an embed with fields for each sub shop
    def create_embed(self):
        embed = Embed(
            title="Shop Select",
            description="Choose which section you would like to shop from!",
            color=Color.teal(),
        )
        embed.set_author(
            name=f"{self.interaction.user.name} - Shopping",
            icon_url=self.interaction.user.display_avatar,
        )
        return embed

    async def on_timeout(self) -> None:
        shop_closed_embed = Embed(
            title="Shop Closed",
            description=f"Thanks for your business, {self.interaction.user.mention}!\nCome again!",
            color=Color.from_str("0x41a651"),
        )
        await self.interaction.edit_original_response(
            embed=shop_closed_embed, view=None
        )


class SelectItem(discord.ui.Select):
    """Select menu that displays the possible items a user can view in the shop."""

    def __init__(self):
        super().__init__(placeholder="Select an item", row=0)

    def callback(self, interaction: Interaction):
        if self.view.interaction.user != interaction.user:
            return
        self.view = ItemPage()


class CloseShopButton(discord.ui.Button):
    """A button designed to close the shop module. Will disable any view attached to the message."""

    def __init__(self, row=None):
        # Initialize as a red exit button
        super().__init__(
            label="Exit",
            emoji=PartialEmoji.from_str("<:close:1050634248983412746>"),
            style=ButtonStyle.red,
            custom_id="return",
            row=row,
        )

    async def callback(self, interaction: Interaction):
        # Return if user isn't the same as the one using the command
        if self.view.interaction.user != interaction.user:
            return
        embed = Embed(
            title="SHOP CLOSED",
            description=f"Thanks for your business, {self.view.interaction.user.mention}!\nCome again!",
            color=Color.from_str("0x41a651"),
        )
        await interaction.response.edit_message(embed=embed, view=None)


# Sub shop view, with pagination buttons to purchase an item
class ItemPage(discord.ui.View):
    def __init__(self, item_id, *, timeout=60):
        super().__init__(timeout=timeout)
        self.embed: Embed = construct_embed(item_id, for_shop=True)
            

    def page_forward(self):
        if (
            self.page_no == len(self.pages) - 1
        ):  # If we are on the last page, page_no is first page of pages
            self.page_no = 0
        else:
            self.page_no += (
                1  # If we are not on the last page, increase the page_no by 1
            )
        for child in self.children:
            if child.custom_id == "purchase":
                child: PurchaseItemButton
                child.refresh(self.pages[self.page_no])
        return self.pages[self.page_no]  # return the SubShopPage we should be on

    def page_backward(self):
        if (
            self.page_no == 0
        ):  # if we are on the first page, page_no is last page of pages
            self.page_no = len(self.pages) - 1
        else:
            self.page_no -= 1  # if not on the last page, decrease the page_no by 1
        for child in self.children:
            if child.custom_id == "purchase":
                child: PurchaseItemButton
                child.refresh(self.pages[self.page_no])
        return self.pages[self.page_no]  # return the SubShopPage we should be on

    async def on_timeout(self) -> None:
        await self.parent_view.timeout()


# Page for item in list of items
class SubShopPage:
    def __init__(
        self, entity_ref_id: str, entity_info: dict, command_interaction: Interaction
    ):
        self.entity_ref_id = entity_ref_id
        self.entity_price = entity_info["price"]
        self.command_interaction = command_interaction
        self.embed: Embed = self.create_embed(entity_info=entity_info)

    def create_embed(self, entity_info):
        page_embed = Embed(
            title=entity_info["name"],  # Sets embed title to item name
            description=entity_info["description"]
            + f"\nCost: **{self.entity_price:,}** bits",  # Sets embed description to item description and price
            color=Color.from_str(
                SubShopPage.rarity_colors[entity_info["rarity"]]
            ),  # Sets embed to be color of item rarity
        )
        page_embed.set_author(
            name=f"{self.command_interaction.user.name} - Shopping",
            icon_url=self.command_interaction.user.display_avatar,
        )
        fields = self.get_attributes(
            entity_info=entity_info, entity_ref_id=self.entity_ref_id
        )
        for field_name, field_value in fields.items():
            page_embed.add_field(name=field_name, value=field_value)
        return page_embed

    # def get_attributes(self, entity_info, entity_ref_id):
    #     fields = {}
    #     if entity_ref_id.startswith("SEED"):
    #         seed_info = ""
    #         seed_grows_into = consumables["CROPS"][entity_info["grows_into"]]
    #         average_profit = (
    #             seed_grows_into["sell_price"]
    #             * (
    #                 (
    #                     seed_grows_into["STAT_harvest_low"]
    #                     + seed_grows_into["STAT_harvest_high"]
    #                 )
    #                 / 2
    #             )
    #             - entity_info["price"]
    #         )
    #         average_grow_time = 100 / entity_info["STAT_growth_odds"]
    #         suffix = (
    #             ""
    #             if (
    #                 seed_grows_into["STAT_harvest_low"]
    #                 or seed_grows_into["STAT_harvest_high"]
    #             )
    #             == 1
    #             else "s"
    #         )
    #         seed_info += (
    #             f"Grown Sell Price: **{int(seed_grows_into['sell_price']):,}** bits\n"
    #         )
    #         seed_info += f"Time to Grow: ~**{int(average_grow_time):,}** hours\n"
    #         seed_info += f"Grown Crop Yield: **{seed_grows_into['STAT_harvest_low']}** - **{seed_grows_into['STAT_harvest_high']}** {seed_grows_into['name']}{suffix}\n"
    #         seed_info += f"Pet XP: **{seed_grows_into['pet_xp']:,}** xp per"
    #         fields["Info"] = seed_info
    #     elif entity_ref_id.startswith("TOOL"):
    #         tool_info = ""
    #         for entity_info_field, field_value in entity_info.items():
    #             if entity_info_field.startswith("STAT_"):
    #                 stat_name_formatted = (
    #                     entity_info_field.strip("STAT_").replace("_", " ").title()
    #                 )
    #                 tool_info += f"{stat_name_formatted}: **{field_value}**\n"
    #         fields["Stats"] = tool_info
    #     elif entity_ref_id.startwith("PET"):
    #         pet_info = perk_info = ""
    #         pet_info += f"Max Level: **{entity_info['STAT_max_level']}\n"
    #         pet_info += f"Health: **{entity_info['STAT_health']:,}**\n"
    #         perk_info += f"Work: **+{entity_info['PERK_work']*100:,}%** bits\n"
    #         perk_info += f"Daiy: **+{entity_info['PERK_daily']:,}** tokens"
    #         fields["Stats"] = pet_info
    #         fields["Perks"] = perk_info
    #     return fields


# Button that sends user to subshop
class SwitchButton(discord.ui.Button):
    def __init__(
        self,
        parent_interaction: Interaction,
        view_to_switch_to: discord.ui.View,
        button_label: str,
        emoji=None,
        row=0,
    ):
        self.parent_interaction = parent_interaction
        self.view_to_switch_to = view_to_switch_to
        super().__init__(
            label=button_label, style=ButtonStyle.blurple, emoji=emoji, row=row
        )

    async def callback(self, switch_interaction: Interaction):
        if switch_interaction.user != self.parent_interaction.user:
            return
        self.view.stop()
        view = self.view_to_switch_to
        view.page_no = 0
        for child in view.children:
            if child.custom_id == "purchase":
                child: PurchaseItemButton
                child.refresh(view.pages[view.page_no])
        await switch_interaction.response.edit_message(embed=view.embed, view=view)


class PaginateBackwardButton(discord.ui.Button):
    """Button that sends paginator backward one page"""

    def __init__(self, row=None):
        """Initialize with a backward arrow, grey color and a row, if given."""
        super().__init__(
            emoji=PartialEmoji.from_str("<:left_arrow:1050633298667389008>"),
            style=ButtonStyle.grey,
            custom_id="back",
            row=row,
        )

    async def callback(self, interaction: Interaction):
        view: ItemPage = self.view
        if view.interaction.user != interaction.user:
            return  # Return if user isn't the same as the one using the command
        page: SubShopPage = view.page_backward()

        await interaction.response.edit_message(embed=page.embed, view=view)


# Button for purchasing the item on the page
class PurchaseItemButton(discord.ui.Button):
    def __init__(self, parent_interaction: Interaction, parent_view: ItemPage):
        self.parent_interaction = parent_interaction
        self.parent_view = parent_view
        self.refresh(self.parent_view.page)

    async def callback(self, purchase_interaction: Interaction):
        user = RequestUser(
            self.parent_interaction.user.id, interaction=self.parent_interaction
        )
        # If the user doesn't have enough money to make the purchase
        if user.instance.money < self.parent_view.page.entity_price:
            self.disabled = True
            self.label = "Nope, sorry."
            self.style = ButtonStyle.red
            self.emoji = "☹️"
            for button in self.parent_view.children:
                button.disabled = True
            await purchase_interaction.response.edit_message(view=self.parent_view)
            await asyncio.sleep(1)
            await purchase_interaction.delete_original_response()
            return

        return

    def refresh(self, page):
        user = RequestUser(
            self.parent_interaction.user.id, interaction=self.parent_interaction
        )
        if user.instance.money >= page.entity_price:
            label = "Purchase!"
            style = ButtonStyle.green
            emoji = "💰"
            disabled = False
        else:
            label = "Can't afford"
            style = ButtonStyle.grey
            emoji = None
            disabled = True
        # Reinitializes the button with the proper attributes, based on whether or not the user can purchase
        super().__init__(
            label=label,
            style=style,
            emoji=emoji,
            disabled=disabled,
            row=0,
            custom_id="purchase",
        )


# Button that sends paginator forward one page
class PaginateForwardButton(discord.ui.Button):
    def __init__(
        self, parent_interaction, row=None
    ):  # Initialize with a forward arrow, grey color and a row, if given.
        self.parent_interaction = parent_interaction
        super().__init__(
            emoji=PartialEmoji.from_str("<:right_arrow:1050633322813993000>"),
            style=ButtonStyle.grey,
            custom_id="forward",
            row=row,
        )

    async def callback(self, paginate_forward_interaction: Interaction):
        assert self.view is not None
        view: ItemPage = self.view
        if self.parent_interaction.user != paginate_forward_interaction.user:
            return  # Return if user isn't the same as the one using the command
        page: SubShopPage = view.page_forward()

        await paginate_forward_interaction.response.edit_message(
            embed=page.embed, view=view
        )


# Button that returns embed to parent view
class PaginateReturnButton(discord.ui.Button):
    def __init__(self, row=None):
        super().__init__(
            label="Item menu",
            emoji=PartialEmoji.from_str("<:return:1050633534836064286>"),
            style=ButtonStyle.blurple,
            custom_id="return",
            row=row,
        )

    async def callback(self, interaction: Interaction):
        view: ItemPage = self.view
        if view.interaction.user != interaction.user:
            return

        new_parent_view = ItemMenu(self.parent_interaction)
        for subshop in view.parent_view.pages:
            new_parent_view.add_subshop(subshop=subshop)
        await interaction.response.edit_message(
            embed=view.parent_view.embed, view=new_parent_view
        )
