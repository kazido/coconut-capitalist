from discord import Interaction, ButtonStyle, PartialEmoji, Embed, Color
from discord.ui import Button, View
from classLibrary import RequestUser
from myModels import ROOT_DIRECTORY
import json

with open(f'{ROOT_DIRECTORY}\projfiles\game_entities\\consumables.json', 'r') as consumables_file:
    consumables = json.load(consumables_file)

# View for the overall shop, with buttons to select subshops
class ShopView(View):
    def __init__(self, command_interaction, *, timeout=60):
        super().__init__(timeout=timeout)
        self.subshops = []
        self.command_interaction = command_interaction
        self.embed = self.create_embed()
        self.add_item(CloseShopButton(command_interaction, row=2))
        
    # Creates an embed with fields for each sub shop
    def create_embed(self):
        embed = Embed(
            title="Shop Select",
            description="Choose which section you would like to shop from!",
            color=Color.teal())
        embed.set_author(name=f"{self.command_interaction.user.name} - Shopping",
                         icon_url=self.command_interaction.user.display_avatar)
        return embed
        
    # Adds a subshop button when one is added
    def add_subshop(self, subshop):
        self.add_item(subshop.go_here_button)
        self.embed.add_field(name=subshop.subshop_dict['name'], value=subshop.subshop_dict['description'])
        self.subshops.append(subshop)
    
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
        super().__init__(label="Exit", emoji=PartialEmoji.from_str("<:close:1050634248983412746>"), style=ButtonStyle.red, custom_id="return", row=row)
        
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
    def __init__(self, subshop_dict: dict, parent_view: ShopView, *, timeout=60):
        super().__init__(timeout=timeout)
        self.subshop_dict = subshop_dict
        self.parent_view: ShopView = parent_view
        self.go_here_button = SwitchButton(parent_view.command_interaction, self, subshop_dict['name'], subshop_dict['emoji'])
        self.pages: list = subshop_dict['pages']  # List of pages to paginate through
        self.page_no: int = 0    # Current page is 0, will be changed with buttons
        self.page: SubShopPage = self.pages[self.page_no]  # Pages is indexed using page_no
        self.embed: Embed = self.page.embed
        self.parent_view.add_subshop(self)
        pagination_buttons = [PaginateBackwardButton(self.parent_view.command_interaction), 
                              PurchaseItemButton(self.parent_view.command_interaction, self), 
                              PaginateForwardButton(self.parent_view.command_interaction), 
                              PaginateReturnButton(self.parent_view.command_interaction, row=1)]
        for button in pagination_buttons:
            self.add_item(button)
        
    def page_forward(self):
        if self.page_no == len(self.pages)-1: # If we are on the last page, page_no is first page of pages
            self.page_no = 0
        else:
            self.page_no += 1  # If we are not on the last page, increase the page_no by 1
        for child in self.children:
            if child.custom_id == 'purchase':
                child: PurchaseItemButton
                child.refresh(self.pages[self.page_no])
        return self.pages[self.page_no] # return the SubShopPage we should be on
        

    def page_backward(self):
        if self.page_no == 0:  # if we are on the first page, page_no is last page of pages
            self.page_no = len(self.pages)-1
        else:
            self.page_no -= 1  # if not on the last page, decrease the page_no by 1
        for child in self.children:
            if child.custom_id == 'purchase':
                child: PurchaseItemButton
                child.refresh(self.pages[self.page_no])
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
    def __init__(self, entity_ref_id: str, entity_info: dict, command_interaction: Interaction):
        self.entity_ref_id = entity_ref_id
        self.entity_price = entity_info['price']
        self.command_interaction = command_interaction
        self.embed: Embed = self.create_embed(entity_info=entity_info)
        
    def create_embed(self, entity_info):
        page_embed = Embed(
            title=entity_info['name'], # Sets embed title to item name
            description=entity_info['description'] + f"\nCost: **{self.entity_price:,}** bits", # Sets embed description to item description and price
            color=Color.from_str(SubShopPage.rarity_colors[entity_info['rarity']]) # Sets embed to be color of item rarity
            )
        page_embed.set_author(name=f"{self.command_interaction.user.name} - Shopping",
                         icon_url=self.command_interaction.user.display_avatar)
        fields = self.get_attributes(entity_info=entity_info, entity_ref_id=self.entity_ref_id)
        for field_name, field_value in fields.items():
            page_embed.add_field(name=field_name, value=field_value)
        return page_embed
    
    def get_attributes(self, entity_info, entity_ref_id):
        fields = {}
        if entity_ref_id.startswith('SEED'):
            seed_info = ""
            seed_grows_into = consumables['CROPS'][entity_info['grows_into']]
            average_profit = seed_grows_into['sell_price'] * ((seed_grows_into['STAT_harvest_low'] + seed_grows_into['STAT_harvest_high'])/2) - entity_info['price']
            average_grow_time = 100 / entity_info['STAT_growth_odds']
            seed_info += f"Average Profit: **{int(average_profit):,}** bits\n"
            seed_info += f"Average Time to Grow: **{int(average_grow_time):,}** hours\n"
            seed_info += f"Pet XP: **{seed_grows_into['pet_xp']:,}** xp"
            fields['Info'] = seed_info
        elif entity_ref_id.startswith('TOOL'):
            tool_info = ""
            for entity_info_field, field_value in entity_info.items():
                if entity_info_field.startswith('STAT_'):
                    stat_name_formatted = entity_info_field.strip('STAT_').replace('_', ' ').title()
                    tool_info += f"{stat_name_formatted}: **{field_value}**\n"
            fields['Stats'] = tool_info
        elif entity_ref_id.startwith('PET'):
            pet_info = perk_info = ""
            pet_info += f"Max Level: **{entity_info['STAT_max_level']}\n"
            pet_info += f"Health: **{entity_info['STAT_health']:,}**\n"
            perk_info += f"Work: **+{entity_info['PERK_work']*100:,}%** bits\n"
            perk_info += f"Daiy: **+{entity_info['PERK_daily']:,}** tokens"
            fields['Stats'] = pet_info
            fields['Perks'] = perk_info
        return fields
        
# Button that sends user to subshop
class SwitchButton(Button):
    def __init__(self, parent_interaction: Interaction, view_to_switch_to: View, button_label: str, emoji=None, row=0):
        self.parent_interaction = parent_interaction
        self.view_to_switch_to = view_to_switch_to
        super().__init__(label=button_label, style=ButtonStyle.blurple, emoji=emoji, row=row)

    async def callback(self, switch_interaction: Interaction):
        if switch_interaction.user != self.parent_interaction.user:
            return
        self.view.stop()
        view = self.view_to_switch_to
        view.page_no = 0
        for child in view.children:
            if child.custom_id == 'purchase':
                child: PurchaseItemButton
                child.refresh(view.pages[view.page_no])
        await switch_interaction.response.edit_message(embed=view.embed, view=view)
        
# Button that sends paginator backward one page
class PaginateBackwardButton(Button):
    def __init__(self, parent_interaction, row=None):  # Initialize with a backward arrow, grey color and a row, if given.
        self.parent_interaction = parent_interaction
        super().__init__(emoji=PartialEmoji.from_str("<:left_arrow:1050633298667389008>"), style=ButtonStyle.grey, custom_id="back", row=row)

    async def callback(self, paginate_backward_interaction: Interaction):
        assert self.view is not None
        view: SubShopView = self.view
        if self.parent_interaction.user != paginate_backward_interaction.user:
            return  # Return if user isn't the same as the one using the command
        page: SubShopPage = view.page_backward()
        
        await paginate_backward_interaction.response.edit_message(embed=page.embed, view=view)
    
# Button for purchasing the item on the page   
class PurchaseItemButton(Button):
    def __init__(self, parent_interaction: Interaction, parent_view: SubShopView):
        self.parent_interaction = parent_interaction
        self.parent_view = parent_view
        self.refresh(self.parent_view.page)
        
    async def callback(self, purchase_interaction: Interaction):
        await purchase_interaction.response.send_message("This isn't ready yet.", ephemeral=True)
        return

    def refresh(self, page):
        user = RequestUser(self.parent_interaction.user.id, interaction=self.parent_interaction)
        if user.instance.money >= page.entity_price:
            label = "Purchase!"
            style = ButtonStyle.green
            emoji = '💰'
            disabled = False
        else:
            label = "Can't afford"
            style = ButtonStyle.grey
            emoji = None
            disabled = True
        super().__init__(label=label, style=style, emoji=emoji, disabled=disabled, row=0, custom_id='purchase')

# Button that sends paginator forward one page
class PaginateForwardButton(Button):
    def __init__(self, parent_interaction, row=None):  # Initialize with a forward arrow, grey color and a row, if given.
        self.parent_interaction = parent_interaction
        super().__init__(emoji=PartialEmoji.from_str("<:right_arrow:1050633322813993000>"), style=ButtonStyle.grey, custom_id="forward", row=row)

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
        super().__init__(label="Go back", emoji=PartialEmoji.from_str("<:return:1050633534836064286>"), style=ButtonStyle.blurple, custom_id="return", row=row)
        
    async def callback(self, paginate_return_interaction: Interaction):
        assert self.view is not None
        view: SubShopView = self.view
        if self.parent_interaction.user != paginate_return_interaction.user:
            return  # Return if user isn't the same as the one using the command
        new_parent_view = ShopView(self.parent_interaction)
        for subshop in view.parent_view.subshops:
            new_parent_view.add_subshop(subshop=subshop)
        await paginate_return_interaction.response.edit_message(embed=view.parent_view.embed, view=new_parent_view)