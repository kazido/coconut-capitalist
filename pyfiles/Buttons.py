from discord import Interaction, ButtonStyle, PartialEmoji
from discord.ui import Button, View


class SwitchButton(Button):
    def __init__(self, parent_interaction: Interaction, view_to_switch_to: View, button_label: str, emoji=None, row=1):
        self.parent_interaction = parent_interaction
        self.view_to_switch_to = view_to_switch_to
        super().__init__(label=button_label, style=ButtonStyle.blurple, emoji=emoji, row=row)

    async def callback(self, switch_interaction: Interaction):
        if switch_interaction.user != self.parent_interaction.user:
            return
        self.view.stop()
        new_view = self.view_to_switch_to
        await switch_interaction.response.edit_message(embed=new_view.view_embed, view=new_view)
        
# Button that sends page to next page
class Paginator_Forward_Button(Button):
    def __init__(self, parent_interaction, view_categories: dict):
        self.parent_interaction = parent_interaction
        self.view_categories = view_categories
        super().__init__(label='\u200b', emoji='▶️', style=ButtonStyle.blurple, row=1)
    
    async def callback(self, next_page_interaction: Interaction):
        if self.parent_interaction.user != next_page_interaction.user:
            return
        if self.view.current_page+1 == len(self.view_categories):
            self.view.current_page = 0
        else:
            self.view.current_page += 1
        self.view.view_embed = list(self.view_categories)[self.view.current_page]['view_embed']
        self.view.update_buttons(tools_dict=list(self.view_categories)[self.view.current_page])
        await next_page_interaction.response.edit_message(embed=self.view.view_embed, view=self.view)
            
            
# Button that sends page to next page
class Paginator_Backward_Button(Button):
    def __init__(self, parent_interaction, view_categories: dict):
        self.parent_interaction = parent_interaction
        self.view_categories = view_categories
        super().__init__(label='\u200b', emoji='◀️', style=ButtonStyle.blurple, row=1)
    
    async def callback(self, back_page_interaction: Interaction):
        if self.parent_interaction.user != back_page_interaction.user:
            return
        if self.view.current_page == 0:
            self.view.current_page = len(self.view_categories)-1
        else:
            self.view.current_page -= 1
        self.view.view_embed = list(self.view_categories)[self.view.current_page]['view_embed']
        self.view.update_buttons(tools_dict=list(self.view_categories)[self.view.current_page])
        await back_page_interaction.response.edit_message(embed=self.view.view_embed, view=self.view)
        

# Button that sends paginator back one page
class PreviousPageButton(Button):
    def __init__(self, parent_interaction, row=None):  # Initialize with a back arrow, grey color and a row, if given.
        self.parent_interaction = parent_interaction
        super().__init__(emoji=PartialEmoji.from_str("<:backarrow:1050563563917418586>"), style=ButtonStyle.grey, custom_id="back", row=row)

    async def callback(self, previous_page_interaction: Interaction):
        assert self.view is not None
        view = self.view
        if self.parent_interaction.user != previous_page_interaction.user:
            return  # Return if user isn't the same as the one using the command
        if view.current_page == 0:  # If we are on the first page, don't continue
            view.current_page = len(view.pages)-1
        else:
            view.current_page -= 1
        self.view.view_embed = list(self.view_categories)[self.view.current_page]['view_embed']
        update_purchase_button_values(view, view.pages[view.page_number - 1], view.user)
        await previous_page_interaction.response.edit_message(embed=view.pages[view.page_number - 1].embed, view=view)