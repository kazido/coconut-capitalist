import discord
import time

from discord import utils
from typing import Literal

from cococap import instance
from cococap.item_models import Ranks, Areas
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
            self.document = UserCollection(name=self.discord_info.name, discord_id=self.uid)
            await self.document.insert()

    def get_discord_info(self) -> discord.Member:
        """Gets a user's discord info"""
        # If I ever expand the bot to other guilds, this needs to chance
        guild: discord.Guild = instance.get_guild(DiscordGuilds.PRIMARY_GUILD.value)
        discord_user: discord.Member = guild.get_member(self.uid)
        if discord_user is None:
            raise Exception(f"No discord member with ID {self.uid}.")
        return discord_user

    # NEEDS UPDATING!!!
    def get_user_rank(self) -> Ranks:
        """Retrieve the corresponding rank of a user based on their roles in a Discord guild."""
        guild = instance.get_guild(DiscordGuilds.PRIMARY_GUILD.value)

        for rank in Ranks.select():
            discord_role = utils.get(guild.roles, id=rank.rank_id)

            # Check to see if the user has any matching role in discord
            if discord_role in self.discord_info.roles:
                return rank
        return None

    def __str__(self) -> str:
        return self.discord_info.name
    
    async def save(self):
        await self.document.save()

    # UPDATE METHODS ------------------------------------
    async def inc_purse(self, amount: int):
        self.document.purse += amount
        await self.save()

    async def inc_bank(self, amount: int):
        self.document.bank += amount
        await self.save()

    async def inc_tokens(self, *, tokens: int):
        self.document.tokens += tokens
        await self.save()

    async def inc_xp(self, *, skill: str, xp: int):
        if not hasattr(self.document, skill):
            return "Object does not have skill {skill}."
        getattr(self.document, skill)["xp"] += xp
        await self.save()
        
    async def update_game(self, *, in_game: bool):
        self.document.in_game = in_game
        await self.save()

    # GET METHODS ------------------------------------
    def get_field(self, field: str):
        if not hasattr(self.document, field):
            return "Object does not have field {field}."
        return getattr(self.document, field)

    def get_tool(self, *, skill: str):
        if not hasattr(self.document, skill):
            return "Object does not have skill {skill}."
        return getattr(self.document, skill)["equipped_tool"]
    
    def get_active_pet(self):
        pets = self.document.pets
        if "active" not in pets.keys():
            return None
        return pets["active"]
    
    def get_zone(self):
        return Areas.get_by_id(self.get_field('zone'))
                

    # COOLDOWN METHODS ------------------------------------
    COMMAND_TYPES = Literal["daily", "work", "weekly"]
    
    async def set_cooldown(self, command_type: COMMAND_TYPES):
        now = time.time()
        self.document.cooldowns[command_type] = now
        await self.save()

    def check_cooldown(self, command_type: COMMAND_TYPES):
        """Checks to see if a command is currently on cooldown. Returns boolean result and cooldown, if any"""
        last_used = self.document.cooldowns[command_type]
        cooldowns = {"work": 6, "daily": 21, "weekly": 167}
        cooldown_hours = cooldowns[command_type]

        now = time.time()
        seconds_since_last_used = now - last_used
        hours_since_last_used = seconds_since_last_used / 3600

        if hours_since_last_used < cooldown_hours:
            # Cooldown has not yet finished
            off_cooldown = last_used + float(cooldown_hours * 3600)
            seconds_remaining = off_cooldown - now

            def format_time(time: int):
                if len(str(time)) == 1:
                    time = "0" + str(time)
                return str(time)

            # Calculate and format the remaining cooldown
            days = int(seconds_remaining // 86400)
            hours = format_time(int((seconds_remaining % 86400) // 3600))
            minutes = format_time(int((seconds_remaining % 3600) // 60))
            seconds = format_time(int(seconds_remaining % 60))

            cooldown = f"{days}d" if days != 0 else ""
            cooldown += f"{hours}:{minutes}:{seconds}"
            return False, cooldown  # The check has been failed
        else:
            return True, None  # The check has been passed
    
    # BET CHECKS ------------------------------------
    # Checks to make sure the user isn't betting more than they have or 0
    async def bet_checks(self, bet) -> object:
        user_balance = self.get_field('purse')
        # If they try to bet more than they have in their account.
        if int(bet) > user_balance:
            return f"You don't have enough to place this bet. Balance: {user_balance} bits", False
        # If their bet is <= 0, stop the code.
        elif int(bet) < 0:
            return f"You can't bet a negative amount.", False
        elif bet == 0:
            return "You can't bet 0 bits.", False
        else:
            return "Passed", True
