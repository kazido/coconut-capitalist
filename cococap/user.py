import discord
import time

from enum import Enum

from cococap.models import UserDocument
from utils.utils import timestamp_to_digital

from logging import getLogger

log = getLogger(__name__)


class Cooldowns(Enum):
    WORK = 6
    DAILY = 21
    WEEKLY = 167


class User:
    def __init__(self, uid: int):
        log.info(f"Initializing user with uid: {str(uid)}")
        self.uid = uid
        self._document: UserDocument

    async def load(self):
        """Method to load a user object with information from MongoDB, taking in a discord uid"""
        self._document = await UserDocument.find_one(UserDocument.discord_id == self.uid)
        if not self._document:
            # TODO: Handle tutorial here I think, probably needs to be moved out of this though
            self._document = UserDocument(name="unnamed user", discord_id=self.uid)
            await self._document.insert()
        return self

    def __str__(self):
        return self._document.name

    async def save(self):
        """Save the user document after any changes"""
        await self._document.save()

    # UPDATE METHODS ------------------------------------
    async def inc_purse(self, amount: int):
        self._document.purse += amount
        await self.save()

    async def inc_bank(self, amount: int):
        self._document.bank += amount
        await self.save()

    async def inc_tokens(self, *, tokens: int):
        self._document.tokens += tokens
        await self.save()

    async def inc_luckbucks(self, *, amount: int):
        self._document.luckbucks += amount
        await self.save()

    async def inc_xp(self, *, skill: str, xp: int, interaction: discord.Interaction):
        # TODO: Needs an overhaul to work with Tiers and Areas and Pets
        # ALSO MAYBE WE SHOULD MAKE THIS SIMPLER AND MOVE THE COMPLEX LOGIC ELSEWHERE
        current_xp = getattr(self._document, skill)["xp"]
        current_level = self.xp_to_level(current_xp)
        pet, pet_data = self.get_active_pet()
        rewarded_xp = xp
        # if skill in pet_data.skill:
        #     rewarded_xp = xp + ((pet_data.max_level / 10) * pet["level"])
        level_to_be = self.xp_to_level(current_xp + rewarded_xp)
        if level_to_be > current_level:
            # If the user will level up, give them rewards
            bit_reward = level_to_be * 10000
            await self.inc_purse(amount=bit_reward)
            await self.inc_tokens(tokens=1)

            # Send an embed congratulating them
            embed = discord.Embed(
                title=f"{skill.capitalize()} level up! {current_level} -> {level_to_be}",
                description=f"Congratulations {interaction.user.mention}!",
                color=discord.Color.gold(),
            )
            embed.add_field(
                name="Rewards",
                value=f":money_with_wings: +**{level_to_be*10000:,}** bits\n:coin: +**1** token",
            )
            embed.set_thumbnail(url=interaction.user.avatar.url)
            await interaction.channel.send(embed=embed)

        getattr(self._document, skill)["xp"] += rewarded_xp
        await self.save()
        return pet_data

    async def in_game(self, in_game: bool):
        self._document.in_game = in_game
        await self.save()

    # ITEM METHODS -----------------------------------
    async def create_item(self, item_id: str, quantity: int = 1):
        """Inserts an item into the database with specified owner and quantity"""

        inventory: dict = self.get_field("items")

        # Ensure that the item is an actual item first
        if not Master.get_or_none(item_id=item_id):
            message = f"'{item_id}' is not a valid item id."
            log.warning(message)
            return False, message
        if quantity < 1:
            message = f"Tried to create {quantity} {item_id}. Less than 1."
            log.warning(message)
            return False, message
        # Retrieve or create the item in the database
        if item_id not in inventory.keys():
            inventory[item_id] = {"quantity": quantity}
            message = f"{quantity} new {item_id} created with owner: {self}."
            log.info(message)
            await self.save()
            return True, message
        else:
            # If an item was found, add to it's quantity
            inventory[item_id]["quantity"] += quantity
            message = f"Added {quantity} {item_id} to: {self}"
            log.info(message)
            await self.save()
            return True, message

    async def delete_item(self, item_id: str, quantity: int = None):
        inventory: dict = self.get_field("items")
        # Ensure that the item is an actual item first
        if not Master.get_or_none(item_id=item_id):
            message = f"Tried to delete: {item_id}. Error: not a valid item id."
            log.warning(message)
            return False, message
        if (quantity != None) and (quantity < 1):
            message = f"Tried to delete: {quantity} {item_id}. Error: less than 1."
            log.warning(message)
            return False, message
        if item_id in inventory.keys():
            # Try to decrement quantity of existing item
            if quantity and (inventory[item_id]["quantity"] - quantity > 0):
                inventory[item_id]["quantity"] -= quantity
                message = f"Deleted {quantity} {item_id} from {self}."
                log.info(message)
                await self.save()
                return True, message
            else:
                inventory.pop(item_id)
                message = f"Deleted all {item_id} from {self}."
                log.info(message)
                await self.save()
                return True, message
        else:
            # If item doesn't exist, do nothing
            message = f"Tried to delete {quantity} {item_id} from {self}. Does not exist."
            log.warning(message)
            return False, message

    async def trade_item(self, new_owner: int, item_id: str, quantity: int = None):
        user_2 = User(uid=new_owner)
        await user_2.load()

        inventory: dict = self.get_field("items")

        # Ensure that the item is an actual item first
        if not Master.get_or_none(item_id=item_id):
            message = f"Tried to trade: {item_id}. Error: not a valid item id."
            log.warning(message)
            return False, message
        if item_id in inventory.keys():
            # Transfer the ownership of the item if it exists
            item = inventory[item_id]
            if quantity:
                if quantity > item["quantity"]:
                    message = f"Tried to trade {quantity} {item_id}. Error: more than owned."
                    log.warning(message)
                    return False, message
                # Inserts same item into tradee's inventory
                await user_2.create_item(item_id, quantity)
                # Removes items from trader's inventory
                await self.delete_item(item_id, quantity)
                message = f"Traded {quantity} {item_id} from {self} to {user_2}."
                log.info(message)
                return True, message
            else:
                # Inserts same item into tradee's inventory
                await user_2.create_item(item_id, inventory[item_id]["quantity"])
                # Removes items from trader's inventory
                await self.delete_item(item_id)
                message = f"Traded all {item_id} from {self} to {user_2}."
                log.info(message)
                return True, message
        # If item doesn't exist, do nothing
        message = f"Tried to trade {item_id} from {self} to {user_2}. Item does not exist."
        log.warning(message)
        return False, message

    # GET METHODS ------------------------------------
    def get_field(self, field: str):
        if not hasattr(self._document, field):
            raise AttributeError(f"{self._document} does not have field '{field}'.")
        return getattr(self._document, field)

    def update_field(self, field: str, value, save: bool = False):
        """Update a (possibly nested) field in the user document."""
        parts = field.split(".")
        obj = self._document
        for part in parts[:-1]:
            if isinstance(obj, dict):
                if part not in obj:
                    raise AttributeError(f"{obj} does not have key '{part}'.")
                obj = obj[part]
            else:
                if not hasattr(obj, part):
                    raise AttributeError(f"{obj} does not have attribute '{part}'.")
                obj = getattr(obj, part)
        last_part = parts[-1]
        if isinstance(obj, dict):
            obj[last_part] = value
        else:
            setattr(obj, last_part, value)
        if save:
            return self.save()

    # XP METHODS ------------------------------------
    @staticmethod
    def level_to_xp(level):
        xp = ((level - 1) / 0.07) ** 2
        return int(xp)

    @staticmethod
    def xp_to_level(xp):
        level = 0.07 * (xp ** (1 / 2))
        return int(level + 1)

    @staticmethod
    def xp_for_next_level(xp):
        # Get current level and xp needed for current level
        level = User.xp_to_level(xp)
        level_xp = User.level_to_xp(level)
        # Get the next level and xp needed for next level
        next_level = level + 1
        next_level_xp = User.level_to_xp(next_level)
        # Get the overflow of xp above current level
        overflow_xp_at_level = xp - level_xp
        xp_between_levels = next_level_xp - level_xp
        return int(overflow_xp_at_level), int(xp_between_levels)

    @staticmethod
    def create_xp_bar(xp) -> str:
        overflow_xp, xp_needed = User.xp_for_next_level(xp)
        ratio = overflow_xp / xp_needed
        xp_bar = "<:xp_bar_left:1203894026265428021>"
        xp_bar_size = 10
        for _ in range(int(ratio * xp_bar_size)):
            xp_bar += "<:xp_bar_big:1203894024243777546>"
        for _ in range(xp_bar_size - int(ratio * xp_bar_size)):
            xp_bar += "<:xp_bar_small:1203894025137037443>"
        xp_bar += f"<:xp_bar_right:1203894027418599505>"
        return xp_bar

    # COOLDOWN METHODS ------------------------------------
    async def set_cooldown(self, command: Cooldowns):
        now = time.time()
        self._document.cooldowns[command.name.lower()] = now
        await self.save()

    def get_cooldown(self, cooldown: Cooldowns):
        return self._document.cooldowns.get(cooldown.name.lower())
