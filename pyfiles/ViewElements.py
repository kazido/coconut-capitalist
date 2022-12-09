from discord import Interaction, ButtonStyle, PartialEmoji, Embed, Color
from discord.ui import Button, View
from classLibrary import RequestUser

# View for the overall shop, with buttons to select subshops
class ShopView(View):
    def __init__(self, subshops: list, command_interaction, *, timeout=20):
        super().__init__(timeout=timeout)
        self.subshops = subshops
        self.command_interaction = command_interaction
        self.embed = self.create_embed()
        for subshop in self.subshops:
            self.add_item(subshop.go_here_button)
        self.add_item(CloseShopButton(command_interaction, row=1))
        
    # Creates an embed with fields for each sub shop
    def create_embed(self):
        embed = Embed(
            title="Shop Select",
            description="Choose which section you would like to shop from!",
            color=Color.teal())
        embed.set_author(name=f"{self.command_interaction.user.name} - Shopping",
                         icon_url=self.command_interaction.user.display_avatar)
        for subshop in self.subshops:
            embed.add_field(name=subshop.subshop_dict['name'], value=subshop.subshop_dict['description'])
        return embed
            
    async def on_timeout(self) -> None:
        shop_closed_embed = Embed(
            title="Shop Closed",
            description=f"Thanks for your business, {self.command_interaction.user.mention}!\nCome again!",
            color=Color.from_str("0x41a651")
        )
        await self.command_interaction.edit_original_response(embed=shop_closed_embed, view=None)
        
# Button to close the shop
class CloseShopButton(Button):
    def __init__(self, parent_interaction, row=None):
        self.parent_interaction = parent_interaction
        super().__init__(emoji=PartialEmoji.from_str("<:exit:1050611309957357588>"), style=ButtonStyle.blurple, custom_id="return", row=row)
        
    async def callback(self, shop_exit_interaction: Interaction):
        if self.parent_interaction.user != shop_exit_interaction.user:
            return  # Return if user isn't the same as the one using the command
        shop_closed_embed = Embed(
                    title="Shop Closed",
                    description=f"Thanks for your business, {self.parent_interaction.user.mention}!\nCome again!",
                    color=Color.from_str("0x41a651")
                )
        await shop_exit_interaction.response.edit_message(embed=shop_closed_embed, view=None)
        
# Sub shop view, with pagination buttons to purchase an item
class SubShopView(View):
    def __init__(self, subshop_dict: dict, parent_view: ShopView, *, timeout=20):
        super().__init__(timeout=timeout)
        self.subshop_dict = subshop_dict
        self.parent_view: ShopView = parent_view
        self.go_here_button = SwitchButton(parent_view.command_interaction, self, subshop_dict['name'], subshop_dict['emoji'])
        self.pages: list = subshop_dict['pages']  # List of pages to paginate through
        self.page_no: int = 0    # Current page is 0, will be changed with buttons
        self.page: SubShopPage = self.pages[self.page_no]  # Pages is indexed using page_no
        self.embed: Embed = self.page.embed
        pagination_buttons = [PaginateBackwardButton(self.parent_view.command_interaction), 
                              PurchaseItemButton(self.parent_view.command_interaction), 
                              PaginateForwardButton(self.parent_view.command_interaction), 
                              PaginateReturnButton(self.parent_view.command_interaction)]
        for button in pagination_buttons:
            self.add_item(button)
        
    def page_forward(self):
        if self.page_no == len(self.pages)-1: # If we are on the last page, page_no is first page of pages
            self.page_no = 0
        else:
            self.page_no += 1  # If we are not on the last page, increase the page_no by 1
        return self.pages[self.page_no] # return the SubShopPage we should be on
        
    
    def page_backward(self):
        if self.page_no == 0:  # if we are on the first page, page_no is last page of pages
            self.page_no = len(self.pages)-1
        else:
            self.page_no -= 1  # if not on the last page, decrease the page_no by 1
        return self.pages[self.page_no]  # return the SubShopPage we should be on
    
    async def on_timeout(self) -> None:
        shop_closed_embed = Embed(
            title="Shop Closed",
            description=f"Thanks for your business, {self.parent_view.command_interaction.user.mention}!\nCome again!",
            color=Color.from_str("0x41a651")
        )
        await self.parent_view.command_interaction.edit_original_response(embed=shop_closed_embed, view=None)
    
# Page for item in list of items
class SubShopPage():
    rarity_colors = {
        "common": "0x99f7a7",
        "uncommon": "0x63efff",
        "rare": "0x0c61cf",
        "super rare": "0x6e3ade",
        "legendary": "0xe3ab3b",
        "premium": "0xe3a019"
        }
    def __init__(self, entity_ref_id: str, entity_info: dict):
        self.entity_ref_id = entity_ref_id
        self.entity_price = entity_info['price']
        self.embed: Embed = self.create_embed(entity_info=entity_info)
        
    def create_embed(self, entity_info):
        page_embed = Embed(
            title=entity_info['name'], # Sets embed title to item name
            description=entity_info['description'] + f"\nCost: **{entity_info['price']:,}** bits", # Sets embed description to item description and price
            color=SubShopPage.rarity_colors[entity_info['rarity']] # Sets embed to be color of item rarity
            )
        for entity_info_field, field_dict in entity_info.items():
            if entity_info_field in ['stats', 'perks']:
                description = ""
                for index, stat in enumerate(field_dict):
                    for stat_name, stat_value in field_dict[stat]['embed_format'].items():
                        description += f"{stat_name}: {stat_value}"
                        if index != len(field_dict):
                            description += "\n"
                self.embed.add_field(name=entity_info_field.capitalize(), value=description)
        return page_embed
    
# Button that sends user to subshop
class SwitchButton(Button):
    def __init__(self, parent_interaction: Interaction, view_to_switch_to: View, button_label: str, emoji=None, row=1):
        self.parent_interaction = parent_interaction
        self.view_to_switch_to = view_to_switch_to
        super().__init__(label=button_label, style=ButtonStyle.blurple, emoji=emoji, row=row)

    async def callback(self, switch_interaction: Interaction):
        if switch_interaction.user != self.parent_interaction.user:
            return
        self.view.stop()
        view = self.view_to_switch_to
        await switch_interaction.response.edit_message(embed=view.embed, view=view)
        
# Button that sends paginator backward one page
class PaginateBackwardButton(Button):
    def __init__(self, parent_interaction, row=None):  # Initialize with a backward arrow, grey color and a row, if given.
        self.parent_interaction = parent_interaction
        super().__init__(emoji=PartialEmoji.from_str("<:backarrow:1050563563917418586>"), style=ButtonStyle.grey, custom_id="back", row=row)

    async def callback(self, paginate_backward_interaction: Interaction):
        assert self.view is not None
        view: SubShopView = self.view
        if self.parent_interaction.user != paginate_backward_interaction.user:
            return  # Return if user isn't the same as the one using the command
        page: SubShopPage = view.page_backward()
        
        await paginate_backward_interaction.response.edit_message(embed=page.embed, view=view)
    
# Button for purchasing the item on the page   
class PurchaseItemButton(Button):
    def __init__(self, parent_interaction: Interaction):
        user = RequestUser(parent_interaction.user.id, interaction=parent_interaction)
        if user.instance.money >= self.view.page.entity_price:
            label = "Purchase!"
            style = ButtonStyle.green
            emoji = '💰'
            disabled = False
        else:
            label = "Can't afford"
            style = ButtonStyle.grey
            emoji = None
            disabled = True
        super().__init__(label=label, style=style, emoji=emoji, disabled=disabled, row=0)
        
    async def callback(self, purchase_interaction: Interaction):
        await purchase_interaction.response.send_message("This isn't ready yet.", ephemeral=True)
        return

# Button that sends paginator forward one page
class PaginateForwardButton(Button):
    def __init__(self, parent_interaction, row=None):  # Initialize with a forward arrow, grey color and a row, if given.
        self.parent_interaction = parent_interaction
        super().__init__(emoji=PartialEmoji.from_str("<:forwardarrow:1050571261971017769>"), style=ButtonStyle.grey, custom_id="forward", row=row)

    async def callback(self, paginate_forward_interaction: Interaction):
        assert self.view is not None
        view: SubShopView = self.view
        if self.parent_interaction.user != paginate_forward_interaction.user:
            return  # Return if user isn't the same as the one using the command
        page: SubShopPage = view.page_forward()
        
        await paginate_forward_interaction.response.edit_message(embed=page.embed, view=view)
   
# Button that returns embed to parent view   
class PaginateReturnButton(Button):
    def __init__(self, parent_interaction, row=None):
        self.parent_interaction = parent_interaction
        super().__init__(emoji=PartialEmoji.from_str("<:return:1050614735864864859>"), style=ButtonStyle.blurple, custom_id="return", row=row)
        
    async def callback(self, paginate_return_interaction: Interaction):
        assert self.view is not None
        view: SubShopView = self.view
        if self.parent_interaction.user != paginate_return_interaction.user:
            return  # Return if user isn't the same as the one using the command
        await paginate_return_interaction.response.edit_message(embed=view.parent_view.embed, view=view.parent_view)