from pathlib import Path
from datetime import datetime
from random import randint

from discord.ui import Button, View
from discord import Interaction, ButtonStyle


def get_project_root() -> Path:
    return Path(__file__).parent.parent


def seconds_until_tasks():  # Delay drops until half hour
    minutes = randint(20, 40)
    current_time = datetime.now()
    time_until = minutes - current_time.minute
    if time_until == 0:
        return 0
    elif time_until < 0:
        minutes = current_time.minute + randint(5, 20)
        time_until = minutes - current_time.minute
    return (time_until * 60) - current_time.second


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