import random

import discord

from cococap.registry import get_registry
from cococap.services import pets, shop
from cococap.ui import Page, PromptModal, Result, Screen
from cococap.ui.components import button, row, select, sep, text, xp_bar
from cococap.user import User

STARS = "⭐"


def stars_text(n: int) -> str:
    return STARS * n


def skill_line(pet) -> str:
    """The one skill a pet looks after, as "Global 🌐" or "Mining ⛏️"."""
    return f"{pet.skill.title()} {pets.skill_emoji(pet)}"


class PetScreen(Screen):
    """Looking after your pets: who they are, who is active, feeding and Spirits. Orbs have their own page."""

    id = "pets"
    label = "Pets"
    emoji = "🐾"
    description = "Your pets: look at them, feed them, pick who helps you"
    links = ("orbs",)

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
        orbs_button = button("Familiar Orbs", emoji="🔮", style=discord.ButtonStyle.primary, on_click=self._to_orbs)

        if not house.pets:
            body.append(text("No pets yet. A **Familiar Orb** hatches one (found while fishing, or in the shop). Every pet gives a bonus."))
            body.append(row(orbs_button))
            return Page("Pets", body, accent=0x27AE60)

        focus = self.focus_id(house)
        pet = reg.pets[focus]
        mine = house.pets[focus]
        level = pets.pet_level(mine.xp, reg)
        low, high = pets.level_xp(level, reg), pets.level_xp(level + 1, reg)
        bar = xp_bar((mine.xp - low) / (high - low) if level < rules.max_level and high > low else 1.0)
        body.append(text(
            f"### {pet.emoji} {pet.name}  {stars_text(mine.stars)}  ·  Lv {level}" + ("  ·  ✅ active" if focus == house.active else "")
            + f"\n-# {pet.description}"
            + f"\n{bar}  " + (f"{mine.xp - low:,}/{high - low:,} xp" if level < rules.max_level else "max level")
            + "\n" + "\n".join(f"▸ {line}" for line in pets.describe(pet, mine, reg))
            + f"\n{skill_line(pet)}"))
        found = f"-# {len(house.pets)} of {len(reg.pets)} pets found"
        body.append(text(found))
        body.append(row(select("Look at a pet...", [
            discord.SelectOption(label=reg.pets[i].name, value=i, emoji=reg.pets[i].emoji, default=i == focus,
                                 description=f"Lv {pets.pet_level(p.xp, reg)}  ·  {skill_line(reg.pets[i])}" + ("  ·  active" if i == house.active else ""))
            for i, p in sorted(house.pets.items())][:25], self._switch)))
        body.append(row(button("Make active", emoji="✅", disabled=focus == house.active, on_click=self._make_active), orbs_button))

        body.append(sep())
        foods = [(reg.item(i), q) for i, q in owned_items.items() if q > 0 and (it := reg.find_item(i)) and pets.food_xp(it, reg) > 0]
        foods.sort(key=lambda e: (pets.food_skill(e[0]) or "", pets.food_xp(e[0], reg)))
        if foods:
            body.append(row(select(f"Feed {pet.name}...", [
                discord.SelectOption(label=f"{c.name} ×{q:,}", value=c.id, emoji=c.emoji, description=self._food_note(c, pet, reg))
                for c, q in foods][:25], self._feed)))
        else:
            body.append(text("-# 🍽️ Pets eat crops and the food your skills drop: Acorn Mix from trees, Fish Flakes from fishing, "
                             "Stone Biscuits from the mine. Food of a pet's own skill is worth more."))
        spirits = [(reg.item(i), q) for i, q in owned_items.items() if q > 0 and (it := reg.find_item(i)) and it.category == "pet_item"
                   and it.skill and it.skill not in mine.spirits]
        if spirits:
            body.append(row(select("Give a Spirit to your pet...", [
                discord.SelectOption(label=f"{s.name} ×{q}", value=s.id, emoji=s.emoji,
                                     description=f"+{rules.spirit_bonus:.0%} {s.skill} xp while it is active") for s, q in spirits][:25],
                                   self._spirit)))
        return Page("Pets", body, accent=0x27AE60)

    async def _to_orbs(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "orbs")

    @staticmethod
    def _food_note(food, pet, reg) -> str:
        """What one of this food is worth to THIS pet: the hint shown while you pick what to feed."""
        base, boost = pets.food_xp(food, reg), pets.food_multiplier(pet, food, reg)
        return (f"{base:,} xp each" + (f" → {round(base * boost):,} for {pet.name} (x{boost:g})" if boost != 1 else f" for {pet.name}"))[:100]

    async def _make_active(self, interaction: discord.Interaction) -> None:
        pet = await pets.set_active(self.user, self.focus_id(self.user.pethouse))
        await self.refresh(interaction, f"{pet.emoji} **{pet.name}** is your active pet now.")

    async def _switch(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.focus = values[0]
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
            note = f"🍎 {fed.pet.name} ate {fed.quantity:,} {reg.item(crop_id).display}  ·  +{fed.xp:,} pet xp" + (f" (x{fed.multiplier:g})" if fed.multiplier != 1 else "")
            if fed.level_after > fed.level_before:
                note += f"\n🎉 **{fed.pet.name} reached level {fed.level_after}!**"
            await self.refresh(modal_interaction, note)

        await interaction.response.send_modal(PromptModal(
            f"Feed {reg.item(crop_id).name}", f"How many? (you have {have:,})", submitted, default=str(have), max_length=9,
            description=self._food_note(reg.item(crop_id), reg.pets[pet_id], reg)))

    async def _spirit(self, interaction: discord.Interaction, values: list[str]) -> None:
        pet, skill = await pets.give_spirit(self.user, values[0], pet_id=self.focus_id(self.user.pethouse))
        await self.refresh(interaction, f"✨ {pet.name} now carries the {skill} Spirit.")


def orb_items(reg=None):
    """Every orb the shop sells (an item whose id is `familiar_orb` or ends in `_orb`, with a price), cheapest first. Add an orb tier in items.toml and it shows up here."""
    reg = reg or get_registry()
    return sorted((i for i in reg.shop_items() if i.id == pets.ORB or i.id.endswith("_orb")), key=lambda i: (i.price, i.name))


class OrbScreen(Screen):
    """Familiar Orbs: open them and aim them at the pet you are hunting."""

    id = "orbs"
    label = "Familiar Orbs"
    emoji = "🔮"
    description = "Open orbs to hatch pets, and hunt a pet you want"
    links = ("pets",)

    async def build(self) -> Page:
        reg = get_registry()
        rules = reg.economy.pets
        house = self.user.pethouse
        orbs = (await self.user.items()).get(pets.ORB, 0)
        body = [*self.note_block(),
                text(f"### 🔮 Familiar Orbs  ·  you have **{orbs:,}**\nAn orb hatches a random pet (a pet you own gains a star). "
                     "Find them fishing, or buy them here.")]
        if house.target in reg.pets:
            target = reg.pets[house.target]
            chance = pets.orb_odds(reg, house.target, house.misses)[house.target]
            body.append(text(f"🎯 **Hunting {target.emoji} {target.name}**  ·  **{chance:.1%}** per orb (×{pets.target_boost(house.misses, reg):g})"
                             + (f"  ·  {house.misses} misses so far make it likelier" if house.misses else "")))
        hunt = [discord.SelectOption(label="No target", value="none", emoji="🚫", default=house.target is None)]
        for pet in sorted(reg.pets.values(), key=lambda p: (p.rarity, p.name)):
            mine = house.pets.get(pet.id)
            if mine is not None and mine.stars >= rules.max_stars:
                continue  # nothing left to hunt
            chance = pets.orb_odds(reg, pet.id, 0)[pet.id]
            hunt.append(discord.SelectOption(label=pet.name + (f" ({mine.stars}/{rules.max_stars})" if mine else ""), value=pet.id, emoji=pet.emoji,
                                             description=f"rarity {pet.rarity}  ·  {chance:.1%} per orb when hunted", default=pet.id == house.target))
        body.append(row(select("Hunt a pet (orbs favour it)...", hunt[:25], self._hunt)))
        for orb in orb_items(reg):
            body.append(row(
                button(f"Buy a {orb.name} ({orb.price:,} bits)", emoji=orb.emoji, style=discord.ButtonStyle.success, disabled=self.user.purse < orb.price, on_click=self._buy(orb.id, 1)),
                button("Buy several", emoji="🛒", on_click=self._buy(orb.id, None))))
        body.append(row(
            button(f"Open a Familiar Orb ({orbs})", emoji="🔮", style=discord.ButtonStyle.primary, disabled=orbs < 1, on_click=self._open_orb),
            button("Your pets", emoji="🐾", on_click=self._to_pets)))
        return Page("Familiar Orbs", body, accent=0x27AE60)

    def _buy(self, item_id: str, quantity: int | None):
        """One click buys one; `None` asks how many first. Pricing and the purchase itself are the shop's (services/shop.buy)."""
        async def go(interaction: discord.Interaction) -> None:
            if quantity is not None:
                await self._purchase(interaction, item_id, quantity)
                return

            async def submitted(modal_interaction: discord.Interaction, raw: str) -> None:
                from cococap.screens.shop import parse_quantity

                await self._purchase(modal_interaction, item_id, parse_quantity(raw))

            await interaction.response.send_modal(PromptModal(f"Buy {get_registry().item(item_id).name}", "How many?", submitted, default="5", max_length=4))

        return go

    async def _purchase(self, interaction: discord.Interaction, item_id: str, quantity: int) -> None:
        purchase = await shop.buy(self.user, item_id, quantity)
        await self.refresh(interaction, f"Bought {purchase.quantity:,} × {get_registry().item(item_id).name} for {purchase.total:,} bits.")

    async def _to_pets(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "pets")

    async def _hunt(self, interaction: discord.Interaction, values: list[str]) -> None:
        pet = await pets.set_target(self.user, None if values[0] == "none" else values[0])
        await self.refresh(interaction, f"🎯 Orbs now favour {pet.emoji} **{pet.name}**." if pet else "🎯 You are not hunting anything now.")

    async def _open_orb(self, interaction: discord.Interaction) -> None:
        got = await pets.open_orb(self.user, random.Random())
        reg = get_registry()
        pet = got.pet
        mine = self.user.pethouse.pets[pet.id]  # (open_orb has refreshed the player)
        lines = [f"### {pet.emoji} {pet.name}  {stars_text(got.stars)}" + ("  🎯 **Target hit!**" if got.target_hit else ""),
                 f"-# {pet.description}",
                 "**A new friend!**" if got.is_new else (f"Another {pet.name}! It now has **{got.stars}** stars." if not got.maxed
                                                        else f"You already have a five-star {pet.name}: it gains {reg.economy.pets.maxed_xp:,} xp instead."),
                 "\n".join(f"▸ {line}" for line in pets.describe(pet, mine, reg)), skill_line(pet)]
        self.result = Result("The orb hatches!", lines, emoji="🔮", accent=0x27AE60, again=self._open_orb, again_label="Another orb",
                             back_label="Back to the orbs")
        await self.refresh(interaction)
