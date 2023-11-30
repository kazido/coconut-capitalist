import discord

from cococap.entity_models import Users, UsersChildTables
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
    def __init__(self, user_id: int) -> None:
        # TODO: self.discord_guild currently initializes as the Coconut Farm..
        log.info("Initializing user object with user id: " + str(user_id))
        self.discord_guild: discord.Guild = instance.get_guild(DiscordGuilds.PRIMARY_GUILD.value)
        self.discord_user: discord.Member = self.discord_guild.get_member(user_id)
        
        # Ensure that the user exists in the guild
        if self.discord_user is None:
            raise UserDoesNotExist(f"No discord member with ID {user_id}.")
        user_data, _ = Users.get_or_create(user_id=user_id)
        
        # set self.field for each field in the users table
        for field in user_data.__data__.keys():
            setattr(self, field, getattr(user_data, field))
            
        # set self.table_name.field for each field in all child tables of the users table
        for table in UsersChildTables:
            table_data, _ = table.value.get_or_create(user_id=user_id)
            setattr(self, table.name, table_data)
            
        # update username
        if self.name != self.discord_user.name:
            self.update_field('name', self.discord_user.name)

    def __str__(self) -> str:
        return self.name
    
    def update_field(self, field_name: str, value) -> None:
        if '.' in field_name:
            nested_fields = field_name.split('.')
            current_obj = self
            for nested_field in nested_fields[:-1]:
                current_obj = getattr(current_obj, nested_field)
            setattr(current_obj, nested_fields[-1], value)
        else:
            if not hasattr(self, field_name):
                raise ValueError(f"Field '{field_name}' does not exist in model {Users.__name__}")
            updated_rows = Users.set_by_id(self.user_id, {field_name: value})
            if updated_rows:
                setattr(self, field_name, value)
        
    def start_game(self):
        self.update_field('in_game', True)
        log.info(f"Started game for user with ID {self.user_id}")

    def end_game(self):
        # TODO: give player xp here, maybe rewards?
        self.update_field('in_game', False)
        log.info(f"Ended game for user with ID {self.user_id}")

    def get_user_rank(self) -> DataRanks:
        """Retrieve the corresponding rank of a user based on their roles in a Discord guild."""
        guild = instance.get_guild(DiscordGuilds.PRIMARY_GUILD.value)

        for rank in DataRanks.select():
            discord_role = discord.utils.get(guild.roles, id=rank.rank_id)

            # Check to see if the user has any matching role in discord
            if discord_role in self.discord_user.roles:
                return rank
        return None
