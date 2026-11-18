import random

import discord

from cococap import emojis
from cococap.registry import get_registry
from cococap.services import pets, shop
from cococap.ui import Page, PromptModal, Result, Screen
from cococap.ui.tabs import TabsScreen
from cococap.ui.components import button, row, select, sep, text, xp_bar
from cococap.user import User

def stars_text(n: int) -> str:
    return emojis.stars(n)


def skill_line(pet) -> str:
    """The one skill a pet looks after, as "Global 🌐" or "Mining ⛏️"."""
    return f"{pet.skill.title()} {pets.skill_emoji(pet)}"


class PetScreen(Screen):
    """Looking after your pets: who they are, who is active, feeding and Spirits. Orbs have their own page."""

    label = "Pets"
    emoji = emojis.Lazy("ui_paw", "🐾")
    description = "Your pets: look at them, feed them, pick who helps you"

    def __init__(self, nav):
        super().__init__(nav)
        self.focus: str | None = None  # the pet you are looking at and looking after (the active one until you pick another)

    def focus_id(self, house) -> str | None:
        if self.focus in house.pets:
            return self.focus
        return house.active if house.active in house.pets else next(iter(sorted(house.pets)), None)

    async def build(self) -> Page:
        reg = get_registry()
        rules = reg.economy.pets
        house = self.user.pethouse
        owned_items = await self.user.items()
        body = [*self.note_block()]

        if not house.pets:
            body.append(text("No pets yet. A **Familiar Orb** hatches one (found while fishing, or in the shop; switch to the Familiar Orbs page with the menu above). Every pet gives a bonus."))
            return Page("Pets", body, accent=0x27AE60)

        focus = self.focus_id(house)
        pet = reg.pets[focus]
        mine = house.pets[focus]
        level = pets.pet_level(mine.xp, pet.rarity, reg)
        low, high = pets.level_xp(level, pet.rarity, reg), pets.level_xp(level + 1, pet.rarity, reg)
        bar = xp_bar((mine.xp - low) / (high - low) if level < rules.max_level and high > low else 1.0)
        body.append(text(
            f"### {pet.emoji} {pet.name}  {stars_text(mine.stars)}  ·  Lv {level}" + (f"  ·  {emojis.icon('check', '✅')} active" if focus == house.active else "")
            + f"\n-# {pet.description}"
            + f"\n{bar}  " + (f"{mine.xp - low:,}/{high - low:,} xp" if level < rules.max_level else "max level")
            + "\n" + "\n".join(f"{emojis.icon('next', '▸')} {line}" for line in pets.describe(pet, mine, reg))
            + f"\n{skill_line(pet)}"))
        found = f"-# {len(house.pets)} of {len(reg.pets)} pets found"
        body.append(text(found))
        body.append(row(select("Look at a pet...", [
            discord.SelectOption(label=reg.pets[i].name, value=i, emoji=reg.pets[i].emoji, default=i == focus,
                                 description=f"Lv {pets.pet_level(p.xp, reg.pets[i].rarity, reg)}  ·  {reg.pets[i].skill.title()}" + ("  ·  active" if i == house.active else ""))
            for i, p in sorted(house.pets.items())][:25], self._switch)))
        body.append(sep())
        foods = [(reg.item(i), q) for i, q in owned_items.items() if q > 0 and (it := reg.find_item(i)) and pets.food_xp(it, reg) > 0]
        foods.sort(key=lambda e: (pets.food_skill(e[0]) or "", pets.food_xp(e[0], reg)))
        if foods:
            body.append(row(select(f"Feed {pet.name}...", [
                discord.SelectOption(label=f"{c.name} ×{q:,}", value=c.id, emoji=c.emoji, description=self._food_note(c, pet, reg))
                for c, q in foods][:25], self._feed)))
        else:
            body.append(text(f"-# {emojis.icon('food', '🍽️')} Pets eat crops and the food your skills drop: Acorn Mix from trees, Fish Flakes from fishing, "
                             "Stone Biscuits from the mine. Food of a pet's own skill is worth more."))
        spirits = [(reg.item(i), q) for i, q in owned_items.items() if q > 0 and (it := reg.find_item(i)) and it.category == "pet_item"
                   and it.skill and it.skill not in mine.spirits]
        if spirits:
            body.append(row(select("Give a Spirit to your pet...", [
                discord.SelectOption(label=f"{s.name} ×{q}", value=s.id, emoji=s.emoji,
                                     description=f"+{rules.spirit_bonus:.0%} {s.skill} xp while it is active") for s, q in spirits][:25],
                                   self._spirit)))
        return Page("Pets", body, accent=0x27AE60)

    @staticmethod
    def _food_note(food, pet, reg) -> str:
        """What one of this food is worth to THIS pet: the hint shown while you pick what to feed."""
        base, boost = pets.food_xp(food, reg), pets.food_multiplier(pet, food, reg)
        skill = pets.food_skill(food)  # a dropdown description cannot show custom emoji: plain words only
        return f"{base:,} xp each" + (f" (x{boost:g} {skill})" if boost != 1 and skill else f" (x{boost:g})" if boost != 1 else "")

    async def _switch(self, interaction: discord.Interaction, values: list[str]) -> None:
        """Picking a pet in the menu looks at it AND makes it your active pet."""
        self.focus = values[0]
        house = self.user.pethouse
        if house.active != values[0]:
            pet = await pets.set_active(self.user, values[0])
            await self.refresh(interaction, f"{pet.emoji} **{pet.name}** is your active pet now.")
            return
        await self.refresh(interaction)

    async def _feed(self, interaction: discord.Interaction, values: list[str]) -> None:
        crop_id = values[0]
        reg = get_registry()
        have = await self.user.item_quantity(crop_id)
        pet_id = self.focus_id(self.user.pethouse)

        async def submitted(modal_interaction: discord.Interaction, raw: str) -> None:
            try:
                quantity = have if raw.strip().lower() in ("all", "") else int(raw.replace(",", ""))
            except ValueError:
                raise pets.PetError("Enter a whole number, or 'all'.") from None
            fed = await pets.feed(self.user, crop_id, quantity, pet_id=pet_id)
            note = f"{emojis.icon('apple', '🍎')} {fed.pet.name} ate {fed.quantity:,} {reg.item(crop_id).display}  ·  +{fed.xp:,} pet xp" + (f" (x{fed.multiplier:g})" if fed.multiplier != 1 else "")
            if fed.level_after > fed.level_before:
                note += f"\n{emojis.icon('party', '🎉')} **{fed.pet.name} reached level {fed.level_after}!**"
            await self.refresh(modal_interaction, note)

        await interaction.response.send_modal(PromptModal(
            f"Feed {reg.item(crop_id).name}", f"How many? (you have {have:,})", submitted, default=str(have), max_length=9,
            description=self._food_note(reg.item(crop_id), reg.pets[pet_id], reg)))

    async def _spirit(self, interaction: discord.Interaction, values: list[str]) -> None:
        pet, skill = await pets.give_spirit(self.user, values[0], pet_id=self.focus_id(self.user.pethouse))
        await self.refresh(interaction, f"{emojis.icon('sparkle', '✨')} {pet.name} now carries the {skill} Spirit.")


def orb_items(reg=None):
    """Every orb the shop sells (an item whose id ends in `_orb`, with a price), cheapest first. Add an orb in items.toml (and its odds in economy.toml) and it shows up here."""
    reg = reg or get_registry()
    return sorted((i for i in reg.shop_items() if i.id.startswith("key_orb_")), key=lambda i: (i.price, i.name))


class OrbScreen(Screen):
    """Familiar Orbs: open them and aim them at the pet you are hunting."""

    label = "Familiar Orbs"
    emoji = emojis.Lazy("ui_orb", "🔮")
    description = "Open orbs to hatch pets, and hunt a pet you want"

    async def build(self) -> Page:
        reg = get_registry()
        rules = reg.economy.pets
        house = self.user.pethouse
        owned = await self.user.items()
        kinds = pets.orb_ids(reg)
        have = "  ·  ".join(f"{reg.item(i).emoji} {reg.item(i).name} **{owned.get(i, 0):,}**" for i in kinds)
        body = [*self.note_block(),
                text(f"### {emojis.icon('orb', '🔮')} Familiar Orbs\n{have}\nAn orb hatches a random pet (a pet you own gains a star). The Lesser orb is cheap and mostly "
                     "gives common pets, the Greater one mostly rare ones. Find orbs fishing, or buy them here.")]
        if house.target in reg.pets:
            target = reg.pets[house.target]
            chance = pets.orb_odds(reg, house.target, house.misses)[house.target]
            body.append(text(f"{emojis.icon('target', '🎯')} **Hunting {target.emoji} {target.name}**  ·  **{chance:.1%}** per orb (×{pets.target_boost(house.misses, reg):g})"
                             + (f"  ·  {house.misses} misses so far make it likelier" if house.misses else "")))
        hunt = [discord.SelectOption(label="No target", value="none", emoji=emojis.icon("cross", "🚫"), default=house.target is None)]
        for pet in sorted(reg.pets.values(), key=lambda p: (p.rarity, p.name)):
            mine = house.pets.get(pet.id)
            if mine is not None and mine.stars >= rules.max_stars:
                continue  # nothing left to hunt
            chance = pets.orb_odds(reg, pet.id, 0)[pet.id]
            hunt.append(discord.SelectOption(label=pet.name + (f" ({mine.stars}/{rules.max_stars})" if mine else ""), value=pet.id, emoji=pet.emoji,
                                             description=f"rarity {pet.rarity}  ·  {chance:.1%} per orb when hunted", default=pet.id == house.target))
        body.append(row(select("Hunt a pet (orbs favour it)...", hunt[:25], self._hunt)))
        for orb_id in kinds:  # one button per orb: Open it if you own some, otherwise Buy it (asks how many)
            orb = reg.item(orb_id)
            count = owned.get(orb_id, 0)
            if count > 0:
                body.append(row(button(f"Open {orb.name} ({count:,})", emoji=orb.emoji, style=discord.ButtonStyle.primary, on_click=self._open_orb(orb_id))))
            else:
                body.append(row(button(f"Buy {orb.name} ({orb.price:,} bits)", emoji=orb.emoji, style=discord.ButtonStyle.success,
                                       disabled=not orb.buyable or self.user.purse < orb.price, on_click=self._buy(orb_id))))
        return Page("Familiar Orbs", body, accent=0x27AE60)

    def _buy(self, item_id: str):
        """Asks how many in a popup (like the shop's). Pricing and the purchase itself are the shop's (services/shop.buy)."""
        async def go(interaction: discord.Interaction) -> None:
            async def submitted(modal_interaction: discord.Interaction, raw: str) -> None:
                from cococap.screens.shop import parse_quantity

                await self._purchase(modal_interaction, item_id, parse_quantity(raw))

            await interaction.response.send_modal(PromptModal(f"Buy {get_registry().item(item_id).name}", "How many?", submitted, default="1", max_length=4))

        return go

    async def _purchase(self, interaction: discord.Interaction, item_id: str, quantity: int) -> None:
        purchase = await shop.buy(self.user, item_id, quantity)
        await self.refresh(interaction, f"Bought {purchase.quantity:,} × {get_registry().item(item_id).name} for {emojis.bits(purchase.total)}.")

    async def _hunt(self, interaction: discord.Interaction, values: list[str]) -> None:
        pet = await pets.set_target(self.user, None if values[0] == "none" else values[0])
        await self.refresh(interaction, f"{emojis.icon('target', '🎯')} Orbs now favour {pet.emoji} **{pet.name}**." if pet else f"{emojis.icon('target', '🎯')} You are not hunting anything now.")

    def _open_orb(self, orb_id: str):
        async def go(interaction: discord.Interaction) -> None:
            await self._hatch(interaction, orb_id)

        return go

    async def _hatch(self, interaction: discord.Interaction, orb_id: str) -> None:
        got = await pets.open_orb(self.user, random.Random(), orb=orb_id)
        reg = get_registry()
        orb = reg.item(orb_id)
        pet = got.pet
        mine = self.user.pethouse.pets[pet.id]  # (open_orb has refreshed the player)
        lines = [f"### {pet.emoji} {pet.name}  {stars_text(got.stars)}" + (f"  {emojis.icon('target', '🎯')} **Target hit!**" if got.target_hit else ""),
                 f"-# {pet.description}",
                 "**A new friend!**" if got.is_new else (f"Another {pet.name}! It now has **{got.stars}** stars." if not got.maxed
                                                        else f"You already have a five-star {pet.name}: it gains {reg.economy.pets.maxed_xp:,} xp instead."),
                 "\n".join(f"{emojis.icon('next', '▸')} {line}" for line in pets.describe(pet, mine, reg)), skill_line(pet)]
        self.result = Result("The orb hatches!", lines, emoji=orb.emoji, accent=0x27AE60, again=self._open_orb(orb_id), again_label="Another orb",
                             back_label="Back to the orbs")
        await self.refresh(interaction)


class PetsScreen(TabsScreen):
    """Pets: looking after them, and the Familiar Orbs that hatch new ones, as tabs of one page."""

    id = "pets"
    label = "Pets"
    emoji = emojis.Lazy("ui_paw", "🐾")
    description = "Your pets: look at them, feed them, pick who helps you"
    panes = {"pets": PetScreen, "orbs": OrbScreen}
