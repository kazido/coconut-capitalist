import discord
import time

from discord import utils
from typing import Literal

from cococap import instance
from cococap.item_models import DataRanks
from cococap.constants import DiscordGuilds
from cococap.models import UserCollection

from logging import getLogger

log = getLogger(__name__)
log.setLevel(20)


class User:
    def __init__(self, uid: int) -> None:
        log.info("Initializing user object with user id: " + str(uid))
        self.uid = uid
        self.discord_info = self.get_discord_info()
        self.document: UserCollection

    async def load(self):
        """Loads the object with information from MongoDB"""
        self.document = await UserCollection.find_one(
            UserCollection.discord_id == self.uid
        )
        if self.document is None:
            new_user = UserCollection(name=self.discord_info.name, discord_id=self.uid)
            await new_user.insert()

    def get_discord_info(self) -> discord.Member:
        """Gets a user's discord info"""
        # If I ever expand the bot to other guilds, this needs to chance
        guild: discord.Guild = instance.get_guild(DiscordGuilds.PRIMARY_GUILD.value)
        discord_user: discord.Member = guild.get_member(self.uid)
        if discord_user is None:
            raise Exception(f"No discord member with ID {self.uid}.")
        return discord_user

    # NEEDS UPDATING!!!
    def get_user_rank(self) -> DataRanks:
        """Retrieve the corresponding rank of a user based on their roles in a Discord guild."""
        guild = instance.get_guild(DiscordGuilds.PRIMARY_GUILD.value)

        for rank in DataRanks.select():
            discord_role = utils.get(guild.roles, id=rank.rank_id)

            # Check to see if the user has any matching role in discord
            if discord_role in self.discord_user.roles:
                return rank
        return None

    def __str__(self) -> str:
        return self.discord_info.name

    # --- UPDATE METHODS ---
    async def update_purse(self, amount: int):
        self.document.purse += amount
        await self.document.save()

    async def update_bank(self, amount: int):
        self.document.bank += amount
        await self.document.save()

    async def update_tokens(self, *, tokens: int):
        self.document.tokens += tokens
        await self.document.save()

    async def update_game(self, *, in_game: bool):
        self.document.in_game = in_game
        await self.document.save()

    async def update_xp(self, *, skill: str, xp: int):
        if not hasattr(self.document, skill):
            return "Object does not have skill {skill}."
        getattr(self.document, skill)["xp"] += xp
        await self.document.save()

    # --- GET METHODS ---
    def get_field(self, field: str):
        if not hasattr(self.document, field):
            return "Object does not have field {field}."
        return getattr(self.document, field)

    def get_tool(self, *, skill: str):
        if not hasattr(self.document, skill):
            return "Object does not have skill {skill}."
        return getattr(self.document, skill)["equipped_tool"]

    # --- COOLDOWN METHODS ---
    COMMAND_TYPES = Literal["daily", "work", "weekly"]
    
    async def set_cooldown(self, command_type: COMMAND_TYPES):
        now = time.time()
        self.document.cooldowns[command_type] = now
        await self.document.save()

    def check_cooldown(self, command_type: COMMAND_TYPES):
        """Checks to see if a command is currently on cooldown. Returns boolean result and cooldown, if any"""
        last_used = self.document.cooldowns[command_type]
        cooldown_hours = {"work": 6, "daily": 21, "weekly": 167}

        now = time.time()
        seconds_since_last_used = now - last_used
        hours_since_last_used = seconds_since_last_used / 3600

        if hours_since_last_used < cooldown_hours:
            # Cooldown has not yet finished
            off_cooldown = last_used + float(cooldown_hours * 3600)
            seconds_remaining = off_cooldown - now

            def format_time(time):
                if time == 0:
                    time = "00"
                return time

            # Calculate and format the remaining cooldown
            days = int(seconds_remaining // 86400)
            hours = format_time(int((seconds_remaining % 86400) // 3600))
            minutes = format_time(int((seconds_remaining % 3600) // 60))
            seconds = format_time(int(seconds_remaining % 60))

            cooldown = f"{days} days {hours}:{minutes}:{seconds} remaining"
            return False, cooldown  # The check has been failed
        else:
            return True, None  # The check has been passed
