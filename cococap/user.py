import discord

from discord import utils
from discord.ext import commands
from cococap.entity_models import *

from cococap.item_models import DataRanks
from cococap.constants import DiscordGuilds

from logging import getLogger

from cococap import instance


log = getLogger(__name__)
log.setLevel(20)


class UserDoesNotExist(Exception):
    pass


class RowDoesNotExist(Exception):
    pass

class User:
    def __init__(self, uid: int) -> None:
        log.info("Initializing user object with user id: " + str(uid))
        self.uid = uid
        
        # set self.field for each field in the users table
        data, _ = Users.get_or_create(user_id=uid)
        for field in data.__data__.keys():
            setattr(self, field, getattr(data, field))
            
        # set self.table_name.field for each field in all child tables of the users table
        for table in UsersChildTables:
            table_data, _ = table.value.get_or_create(user_id=uid)
            setattr(self, table.name, table_data)
            
        self.update_name()
            
    def get_discord_info(self):
        guild: discord.Guild = instance.get_guild(DiscordGuilds.PRIMARY_GUILD.value)
        self.discord_user: discord.Member = guild.get_member(self.uid)
        if self.discord_user is None:
            raise UserDoesNotExist(f"No discord member with ID {self.uid}.")
        return self.discord_user
        
    def update_name(self):
        user = self.get_discord_info()
        if self.name != user.name:
            self.name = user.name

    def __str__(self) -> str:
        return self.name
        
    def start_game(self):
        self.in_game = True
        log.info(f"Started game for user with ID {self.user_id}")

    def end_game(self):
        # TODO: give player xp here, maybe rewards?
        self.in_game = False
        log.info(f"Ended game for user with ID {self.user_id}")

    def get_user_rank(self) -> DataRanks:
        """Retrieve the corresponding rank of a user based on their roles in a Discord guild."""
        guild = instance.get_guild(DiscordGuilds.PRIMARY_GUILD.value)

        for rank in DataRanks.select():
            discord_role = utils.get(guild.roles, id=rank.rank_id)

            # Check to see if the user has any matching role in discord
            if discord_role in self.discord_user.roles:
                return rank
        return None