import discord
import time

from discord import utils
from typing import Literal

from cococap import instance
from cococap.item_models import Ranks, Areas
from cococap.constants import DiscordGuilds, NUMBER_EMOJIS
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
        self.document = await UserCollection.find_one(UserCollection.discord_id == self.uid)
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

    async def get_user_rank(self) -> Ranks:
        """Retrieve the corresponding rank of a user based on their roles in a Discord guild."""
        unranked_id = 959850049188298772
        guild = instance.get_guild(DiscordGuilds.PRIMARY_GUILD.value)

        for rank in Ranks.select():
            discord_role = utils.get(guild.roles, id=rank.rank_id)

            # Check to see if the user has any matching role in discord
            if discord_role in self.discord_info.roles:
                return rank

        # If we don't find any rank, give them unranked
        unranked = guild.get_role(unranked_id)
        await self.discord_info.add_roles(unranked)
        return Ranks.get_by_id(unranked_id)

    def is_busy(self) -> bool:
        in_game = self.get_field("in_game")
        if in_game["in_game"]:
            embed = discord.Embed(
                title="You are busy elsewhere!",
                description=f"You are currently doing something else here: {in_game['channel']}!",
                color=discord.Color.red(),
            )
            return embed
        return False

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

    async def inc_xp(self, *, skill: str, xp: int, interaction: discord.Interaction):
        if not hasattr(self.document, skill):
            return f"Object does not have skill {skill}."
        current_xp = getattr(self.document, skill)["xp"]
        current_level = self.xp_to_level(current_xp)
        level_to_be = self.xp_to_level(current_xp + xp)
        if level_to_be > current_level:
            embed = discord.Embed(
                title=f"{skill.upper()} level up!",
                description=f"Congratulations {interaction.user.mention}, 
                your {skill} level increased from **{current_level}** -> **{level_to_be}**!",
                color=discord.Color.gold()
            )
            embed.set_image(url=interaction.user.avatar.url)
            await interaction.channel.send(embed=embed)
        getattr(self.document, skill)["xp"] += xp
        await self.save()

    async def update_game(self, *, in_game: bool, interaction: discord.Interaction):
        if in_game:
            self.document.in_game["channel"] = interaction.channel.mention
        else:
            self.document.in_game["channel"] = ""
        self.document.in_game["in_game"] = in_game
        await self.save()

    # GET METHODS ------------------------------------
    def get_field(self, field: str):
        if not hasattr(self.document, field):
            return "Object does not have field {field}."
        return getattr(self.document, field)

    def get_active_pet(self):
        pets = self.document.pets
        if "active" not in pets.keys():
            return None
        return pets["active"]

    def get_zone(self):
        return Areas.get_by_id(self.get_field("zone"))

    # XP METHODS ------------------------------------
    def level_to_xp(self, level):
        xp = ((level - 1) / 0.07) ** 2
        return int(xp)

    def xp_to_level(self, xp):
        level = 0.07 * (xp ** (1 / 2))
        return int(level + 1)

    def xp_for_next_level(self, xp):
        # Get current level and xp needed for current level
        level = self.xp_to_level(xp)
        level_xp = self.level_to_xp(level)
        # Get the next level and xp needed for next level
        next_level = level + 1
        next_level_xp = self.level_to_xp(next_level)
        # Get the overflow of xp above current level
        overflow_xp_at_level = xp - level_xp
        xp_between_levels = next_level_xp - level_xp
        return int(overflow_xp_at_level), int(xp_between_levels)

    def create_xp_bar(self, xp) -> str:
        overflow_xp, xp_needed = self.xp_for_next_level(xp)
        ratio = overflow_xp / xp_needed
        xp_bar = "<:xp_bar_left:1203894026265428021>"
        xp_bar_size = 7
        for _ in range(int(ratio * xp_bar_size)):
            xp_bar += "<:xp_bar_big:1203894024243777546>"
        for _ in range(xp_bar_size - int(ratio * xp_bar_size)):
            xp_bar += "<:xp_bar_small:1203894025137037443>"
        xp_bar += f"<:xp_bar_right:1203894027418599505> *({overflow_xp:,}/{xp_needed:,} xp)*"
        return xp_bar

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
