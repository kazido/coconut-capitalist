from typing import Any
import discord

from src.entity_models import Users, UsersChildTables
from src.item_models import DataRanks
from src.utils.items import Entity
from src.constants import DiscordGuilds

from logging import getLogger
from playhouse.shortcuts import model_to_dict

from src import instance


log = getLogger(__name__)
log.setLevel(20)


class UserDoesNotExist(Exception):
    pass

class RowDoesNotExist(Exception):
    pass


class User:
    def __init__(self, user_id: int) -> None:
        self.discord_user = instance.get_user(user_id)
        if self.discord_user is None:
            raise UserDoesNotExist(f"No discord user with ID {user_id}.")
        user_data = Users.get_or_create(user_id=user_id)
        # set self.field for each field in the users table
        for field in user_data.__data__.keys():
            setattr(self, field, getattr(user_data, field))
        # set self.table_name.field for each field in all child tables of the users table
        for table in UsersChildTables:
            table_data = table.value.get_or_create(user_id=user_id)
            for field in table_data.__data__.keys():
                attr_name = f"{table.name}.{field}"
                setattr(self, attr_name, getattr(table_data, field))
        # update username
        self.name = self.discord_user.name if self.name != self.discord_user.name else self.name
                
    def __setattr__(self, __name: str, __value: Any) -> None:
        if not hasattr(Users, __name):
            raise ValueError(f"Field '{__name}' does not exist in model {Users.__name__}")
        updated_rows = Users.set_by_id(self.user_id, {__name: __value})
        if updated_rows:
            return updated_rows
        raise UserDoesNotExist(f"No {Users.__name__} found with ID {self.user_id}")
    
    def __getattr__(self, __name: str):
        if not hasattr(self, __name):
            raise ValueError(f"Field '{__name}' does not exist for the user.")
        return self.__getattr__(__name)
    
    def __str__(self) -> str:
        return self.display_name

    def get_user_tool(self, skill: str):
        """Retrieve information about the tool that a user has equipped for specified skill."""
        # TODO: ensure that this works
        user_skill = self.__getattr__(skill)
        user_tool_id = skill.tool_id
        user_tool = Entity(self.user_id, user_tool_id)
        return user_tool
    
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
            discord_role = discord.utils.get(guild.roles, id=rank.rank_id)

            # Check to see if the user has any matching role in discord
            if discord_role in self.discord_user.roles:
                rank_data = model_to_dict(rank)
                return rank_data
