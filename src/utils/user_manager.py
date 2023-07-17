import discord

from discord import utils
from src import models
from src.data.ranks import ranks
from logging import getLogger



log = getLogger(__name__)
log.setLevel(10)


class UserManager:

    def __init__(self, user_id, interaction: discord.Interaction) -> None:

        # Create or retrieve the user instance from the Users table
        log.debug("Request recieved, building user info.")
        self._user, _ = models.Users.get_or_create(user_id=user_id)

        # Setup remaining user data from other sources
        self._user.total_money = self._user.purse + self._user.bank
        self._user.pet = models.Pets.retrieve_pet(user_id=user_id)
        self._user.rank = models.Users.retrieve_rank(user_id=user_id, interaction=interaction)

        # Create or retrieve related instances from other tables
        self._cooldowns, _ = models.UserCooldowns.get_or_create(
            user_id=user_id)
        self._settings, _ = models.Settings.get_or_create(user_id=user_id)
        self._combat, _ = models.Combat.get_or_create(user_id=user_id)
        self._farming, _ = models.Farming.get_or_create(user_id=user_id)
        self._mining, _ = models.Mining.get_or_create(user_id=user_id)
        self._foraging, _ = models.Foraging.get_or_create(user_id=user_id)
        self._fishing, _ = models.Fishing.get_or_create(user_id=user_id)

        # Retrieve all rows where user_id == owner_id for items and pets
        self._items = models.Items.select().where(
            models.Items.owner_id == user_id).objects()
        self._pets = models.Pets.select().where(models.Pets.user == user_id).objects()

        # Update the user's display name if available in the interaction
        user = discord.utils.get(interaction.guild.members, id=user_id)
        if user and (self._user.name != user.display_name):
            log.debug(f"Updating {self._user.name} to {user.display_name}")
            self._user.name = user.display_name
            self._user.save()

    # Method for safely updating user data
    def update_data(self, field_name, value, mode: str = None):
        if hasattr(self._user, field_name):
            if mode == "add":
                old_value = getattr(self._user, field_name)
                new_value = old_value + value
                setattr(self._user, field_name, new_value)
            else:
                setattr(self._user, field_name, value)
            self._user.save()
            return

    # Method for safely retrieving user data
    def get_data(self, field_name):
        if hasattr(self._user, field_name):
            return getattr(self._user, field_name)
    
    # Starts a game for the user, meaning they cannot play other games
    def start_game(self):
        self._user.in_game = True
        log.debug(f"Updating {self._user.name} status to True.")
        self.save()

    # Ends a game for the user, enabling them to play other games
    def end_game(self):
        self._user.in_game = False
        log.debug(f"Updating {self._user.name} status to False.")
        self.save()
        
    # Ensures that the user's bet is valid
    def check_bet(self, bet):
        balance = self.money
        if int(bet) < 0:
            return f"The oldest trick in the book... Nice try.", False
        elif int(bet) > balance:
            return f"No loans. You have {balance} bits.", False
        elif int(bet) == 0:
            return "What did you think this was going to do?", False
        else:
            return "Passed", True
        
    # Retrieves a rank
    def retrieve_rank(user_id, interaction: discord.Interaction):
        guild_roles = interaction.guild.roles
        for rank in ranks.keys():
            log.debug(f"Checking for {rank}...")
            discord_role = utils.get(guild_roles, name=rank.capitalize())
            user = utils.get(interaction.guild.members, id=user_id)
            
            # Check to see if the user has any matching role in discord
            if not discord_role in user.roles:
                return "No rank found"
            log.debug(f"Found {rank} rank.")
            return rank
