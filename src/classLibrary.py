import random
import datetime
import math
import discord
import randfacts

from src import models as m
from src.models import db as database

class RequestUser:
    pass

class UserManager:
    def __init__(self, user_id, interaction) -> None:
        self._user = m.User.get_or_create(id=user_id)
        self.cooldowns = m.Usercooldowns.get_or_create(id=user_id)
        self.farm = m.Farms.get_or_create(id=user_id)
        self.items = m.Items.select().where(m.Items.owner_id == user_id).objects()
        self._user.name = discord.utils.get(interaction.guild.members, id=user_id).display_name
        self._user.save()
        # try:
        #     active_pet = mm.Pets.select().where((mm.Pets.owner_id == user_id) & mm.Pets.active).get()
        #     self.active_pet = Pet(active_pet.id)
        # except mm.DoesNotExist:
        #     self.active_pet = None
        # for rank in ranks:
        #     role_in_discord = discord.utils.get(interaction.guild.roles, name=rank.capitalize())
        #     if role_in_discord in interaction.user.roles:
        #         self.rank = rank
        #         break

    async def check_ins(self, interaction, check_in_type):
        TWENTY_ONE_HOURS_IN_SECONDS = 75600  # Used for checking seconds between DAILY cooldown
        SIX_HOURS_IN_SECONDS = 21600  # Used for checking seconds between WORK cooldown
        now = datetime.datetime.now().timestamp()  # Current time, used to compare with last used time
        work_off_cooldown = float(self.cooldowns.worked_last) + float(SIX_HOURS_IN_SECONDS)
        daily_off_cooldown = float(self.cooldowns.daily_used_last) + float(TWENTY_ONE_HOURS_IN_SECONDS)
        description = title = None

        off_cooldown = work_off_cooldown if check_in_type == 'work' else daily_off_cooldown

        if float(now) <= float(off_cooldown):  # If it has NOT been enough time since they last used the command
            on_cooldown_embed = discord.Embed(color=discord.Colour.red())
            cd_left_in_seconds = int(off_cooldown - float(now))
            day = cd_left_in_seconds // 86400
            hours = (cd_left_in_seconds - (day * 86400)) // 3600
            minutes = (cd_left_in_seconds - ((day * 86400) + (hours * 3600))) // 60
            seconds = cd_left_in_seconds - ((day * 86400) + (hours * 3600) + (minutes * 60))
            cool_down_left_formatted = datetime.time(hours, minutes, seconds)
            on_cooldown_embed.add_field(name=f"You already collected your {check_in_type}!",
                                        value=f"Next in: **{cool_down_left_formatted}**")
            on_cooldown_embed.set_footer(text=f"User: {interaction.user.name}")
            await interaction.response.send_message(embed=on_cooldown_embed)
            return
        match check_in_type:  # Match statement to check which type of cooldown we need to test
            case 'work':  # If the checkin type is work, set title and description
                wage = ranks[self.rank]['wage']
                title = random.choice(ranks[self.rank]['responses'])
                description = f" :money_with_wings:" \
                              f" **+{wage:,} bits** ({self.rank.capitalize()} wage)"
                if self.active_pet:
                    work_multiplier = pets[self.active_pet.instance.rarity]['bonuses']['work']
                    description += f"\n:money_with_wings: " \
                                   f"**+{int(wage * work_multiplier):,} bits** (pet bonus)"
                    self.update_balance(wage + wage * work_multiplier)
                else:
                    self.update_balance(wage)
                self.cooldowns.worked_last = now
            case 'daily':
                wage = areas[str(self._user.area)]['tokens']
                title = f"Daily Tokens"
                description = f"**:coin:" \
                              f" +{wage} tokens** ({areas[str(self._user.area)]['name'].capitalize()} standard)"
                if self.active_pet:
                    pet_bonus = pets[self.active_pet.instance.rarity]['bonuses']['daily']
                    description += f"\n:coin:" \
                                   f" **+{int(pet_bonus)} tokens** (pet bonus)"
                    self.update_tokens(wage + pet_bonus)
                else:
                    self.update_tokens(wage)
                self.cooldowns.daily_used_last = now
        check_in_embed = discord.Embed(title=title, description=description, color=discord.Color.blue())
        check_in_embed.set_author(name=f"{interaction.user.name} - "
                                       f"{check_in_type}", icon_url=interaction.user.display_avatar)
        if check_in_type == 'daily':
            bank_interest_rate = 0.003+0.027*(math.e**(-(self._user.bank/20_000_000)))
            check_in_embed.add_field(name="Your Tokens",
                                     value=f"You have **{self._user.tokens:,}** tokens")
            check_in_embed.add_field(name="Bank Interest",
                                     value=f"You recieved **{int(self._user.bank * bank_interest_rate):,}** bits in *interest*")
            self.update_balance(amount=self._user.bank * bank_interest_rate, bank=True)
            check_in_embed.add_field(name=f"Random Fact", value=f'{randfacts.get_fact()}', inline=False)
        elif check_in_type == 'work':
            check_in_embed.add_field(name="Your Bits",
                                     value=f"You have **{int(self._user.money):,}** bits in your purse")
        check_in_embed.set_footer(text="Increase your profits by unlocking better pets and ranking up.")
        await interaction.response.send_message(embed=check_in_embed)
        self.cooldowns.save()

    def __del__(self):  # On cleanup of the object, close the connection to the database
        database.close()


# class Pet:
#     def __init__(self, pet_id) -> None:
#         self.instance = mm.Pets.get(id=pet_id)
#         self.pet_embed = discord.Embed(title=f"Pet: {self.instance.name}",
#                                        color=discord.Color.from_str(pets[self.instance.rarity]['color']))
#         self.pet_embed.add_field(name="Rarity", value=f"{self.instance.rarity.replace('_', ' ')}")
#         self.pet_embed.add_field(name="Species",
#                                  value=f"{pets[self.instance.rarity]['animals'][self.instance.species]['emoji']}")
#         self.pet_embed.add_field(name="Health",
#                                  value=f"**{self.instance.health}/{pets[self.instance.rarity]['health']}**",
#                                  inline=False)
#         self.pet_embed.add_field(name="Level", value=f"{self.instance.level}")

#     def feed(self, crop):
#         pass

#     def switch_active_pet(self, pet_id):
#         for pet in mm.Pets.select().objects():
#             if pet.pet_id == pet_id:  # Set current active pet to inactive
#                 self.instance.active = False
#                 self.instance.save()
#                 pet.active = True  # Update matching pet to be active and to be objects active pet
#                 pet.save()

#     def rename(self, new_name):
#         self.instance.name = new_name
#         self.instance.save()
#         return new_name
    


# class Tree:
#     rare_drops = [item for item in materials if item.startswith("MATERIAL_TREE")]
#     tree_heights = [randint(20, 40), randint(40, 50), randint(50, 60), randint(90, 100)]

#     def __init__(self, user1):
#         self.height = numpy.random.choice(Tree.tree_heights, p=[0.499, 0.300, 0.200, 0.001])
#         self.hitpoints = round(self.height / 2)
#         self.rare_drops = Tree.rare_drops
#         self.embed = None
#         self.user1, self.user2 = user1, None
#         self.user1_axe = self.user1.instance.axe
#         self.user2_axe = None

#     @property
#     def hitpoints(self):
#         return self._hitpoints

#     @hitpoints.setter
#     def hitpoints(self, new_hitpoints):
#         if new_hitpoints <= 0:
#             self._hitpoints = 0
#             self.embed = self.on_chopped_down()
#         else:
#             self._hitpoints = new_hitpoints

#     def on_chopped_down(self):
#         chopped_embed = discord.Embed(
#             title="Tree chopped! :evergreen_tree:",
#             description=f"{self.user1.instance.name} and {self.user2.instance.name} "
#                         f"successfully chopped down a **{self.height}ft** tree!",
#             color=0x573a26
#         )
#         return chopped_embed
