import random
import time

import discord

from cococap import emojis
from cococap.constants import Rarities
from cococap.registry import get_registry
from cococap.services import pet_score, pets, shop
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
    emoji = emojis.Lazy("ui_pets", "🐾")
    description = "Your pets: look at them, feed them, pick who helps you"

    def __init__(self, nav):
        super().__init__(nav)
        self.details = False  # the per-skill score breakdown is showing
        self.focus: str | None = None  # the pet you are looking at and looking after (the active one until you pick another)

    def focus_id(self, house) -> str | None:
        if self.focus in house.pets:
            return self.focus
        return house.active if house.active in house.pets else next(iter(sorted(house.pets)), None)

    @staticmethod
    def _option_text(pet, owned, active: bool, reg) -> str:
        """A dropdown line: level, skill and what the pet does (plain words only: dropdown text cannot show custom emoji; Discord caps it at 100 characters)."""
        abilities = " · ".join(line.split(" (max level")[0] for line in pets.describe(pet, owned, reg))
        line = ("active · " if active else "") + f"Lv {pets.pet_level(owned.xp, pet.rarity, reg)} · {pet.skill.title()} · {abilities}"
        return line if len(line) <= 100 else line[:99] + "…"

    async def build(self) -> Page:
        reg = get_registry()
        rules = reg.economy.pets
        house = self.user.pethouse
        owned_items = await self.user.items()
        if house.pets and (banked := await pets.bank_idle_haul(self.user)):  # the idle haul banks itself when the page opens
            self.note = f"{emojis.icon('sparkle', '✨')} {banked}" + (f"\n{self.note}" if self.note else "")
            house = self.user.pethouse
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
            + f"\n-# {pets.max_buffs(pet)} (max level)"
            + f"\n{bar}  " + (f"{mine.xp - low:,}/{high - low:,} xp" if level < rules.max_level else "max level")
            + "\n" + "\n".join(f"{emojis.icon('next', '▸')} {line}" for line in pets.describe(pet, mine, reg))
            + f"\n{skill_line(pet)}"))
        found = f"-# {len(house.pets)} of {len(reg.pets)} pets found"
        body.append(text(found))
        body.append(row(select("Look at a pet...", [
            discord.SelectOption(label=f"{reg.pets[i].name} {'⭐' * p.stars}", value=i, emoji=reg.pets[i].emoji, default=i == focus,  # (unicode stars: custom emoji do not render in dropdown text)
                                 description=self._option_text(reg.pets[i], p, i == house.active, reg))
            for i, p in sorted(house.pets.items())][:25], self._switch)))
        if focus == house.active:
            await self._sidekick_block(body, pet, mine, house, owned_items, reg)
        body.append(sep())
        foods = [(reg.item(i), q) for i, q in owned_items.items() if q > 0 and (it := reg.find_item(i)) and pets.food_xp(it, reg) > 0]
        foods.sort(key=lambda e: (pets.food_skill(e[0]) or "", pets.food_xp(e[0], reg)))
        if foods:
            body.append(row(select(f"Feed {pet.name}...", [
                discord.SelectOption(label=f"{c.name} ×{q:,}", value=c.id, emoji=c.emoji, description=self._food_note(c, pet, reg))
                for c, q in foods][:25], self._feed)))
        else:
            body.append(text(f"-# {emojis.icon('food', '🍽️')} Pets level on the food your skills drop (Acorn Mix from trees, Fish Flakes from fishing, "
                             "Stone Biscuits from the mine, Harvest Mash from harvests) or Pet Biscuits from the shop. Food of a pet's own skill is worth more. Crops fuel its idle work."))
        spirits = [(reg.item(i), q) for i, q in owned_items.items() if q > 0 and (it := reg.find_item(i)) and it.category == "pet_item"
                   and it.skill and it.skill not in mine.spirits]
        if spirits:
            body.append(row(select("Give a Spirit to your pet...", [
                discord.SelectOption(label=f"{s.name} ×{q}", value=s.id, emoji=s.emoji,
                                     description=f"+{rules.spirit_bonus:.0%} {s.skill} xp while it is active") for s, q in spirits][:25],
                                   self._spirit)))
        return Page("Pets", body, accent=0x27AE60)

    async def _sidekick_block(self, body: list, pet, mine, house, owned_items: dict, reg) -> None:
        """The active pet's mini-you: score, sidekick bonus from the pets resting, the fuel tank, and Details / Fuel."""
        rules = reg.pet_score
        others = [(reg.pets[k], o) for k, o in house.pets.items() if k != house.active]
        side = pet_score.sidekick_bonus(others, reg)
        score = pet_score.score(pet, mine, registry=reg)
        cap = pets.tank_cap_seconds(reg)
        now = time.time()
        fuel = house.fuel_seconds
        working = max(0.0, min(fuel, now - house.last_collect)) if house.last_collect else 0.0  # idle time waiting to be collected
        hourly = pet_score.haul_xp_per_hour(score, side, registry=reg)
        breakdown = pet_score.total(pet, reg)
        nxt = emojis.icon("next", "▸")
        lines = [
            "**Sidekick work** (idle while you are away)",
            f"{nxt} Score **{breakdown.total}/1000**  ·  skills {breakdown.skills_total}, mastery {breakdown.mastery}, gear {breakdown.gear}, ability {breakdown.ability}",
            f"{nxt} Sidekicks: **+{side:.0%}** from your resting pets (max +{rules.sidekick_cap:.0%})",
            f"{nxt} Tank {xp_bar(fuel / cap if cap else 0)} {fuel / 3600:.1f}/{cap / 3600:.0f} h  ·  hauls about {hourly:,.0f} xp/h",
            f"-# {working / 3600:.1f} h of work is banked when you next open this page" if working > 0 else "-# Fill the tank with crops: it only works while it has fuel.",
        ]
        body.append(text("\n".join(lines)))
        crops = [(reg.item(i), q) for i, q in owned_items.items() if q > 0 and (it := reg.find_item(i)) and it.crop is not None and it.sell_price > 0]
        crops.sort(key=lambda e: e[0].sell_price)
        body.append(row(button("Hide details" if self.details else "Details", on_click=self._toggle_details)))
        if self.details:
            body.append(text("\n".join(f"{name.title()} {xp_bar(pts / pet_score.MAX_SKILL)} {pts}/{pet_score.MAX_SKILL}" for name, pts in breakdown.skills.items())))
        if crops:
            body.append(row(select("Fuel the tank with crops...", [
                discord.SelectOption(label=f"{c.name} ×{q:,}", value=c.id, emoji=c.emoji, description=f"{c.sell_price * rules.fuel_minutes_per_value:.1f} min of fuel each")
                for c, q in crops][:25], self._fuel)))

    async def _toggle_details(self, interaction: discord.Interaction) -> None:
        self.details = not self.details
        await self.refresh(interaction)

    def _drop_lines(self, drops: dict[str, int]) -> str:
        """What the haul found, each marked with the active pet's emoji (like its xp bonus on result screens)."""
        reg = get_registry()
        pet = reg.pets[self.user.pethouse.active]
        return "  ".join(f"{reg.item(i).emoji} {q:,} × {reg.item(i).name} ({pet.emoji})" for i, q in drops.items())

    async def _fuel(self, interaction: discord.Interaction, values: list[str]) -> None:
        crop_id = values[0]
        reg = get_registry()
        have = await self.user.item_quantity(crop_id)

        async def submitted(modal_interaction: discord.Interaction, raw: str) -> None:
            try:
                quantity = have if raw.strip().lower() in ("all", "") else int(raw.replace(",", ""))
            except ValueError:
                raise pets.PetError("Enter a whole number, or 'all'.") from None
            added = await pets.fuel(self.user, crop_id, quantity)
            await self.refresh(modal_interaction, f"{reg.item(crop_id).emoji} Fuel added: **{added / 3600:.1f} h** of work.")

        await interaction.response.send_modal(PromptModal(f"Fuel with {reg.item(crop_id).name}", f"How many? (you have {have:,})", submitted, default=str(have), max_length=9))

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
            if reg.item(crop_id).pet_food is not None:
                note += f"\n+{reg.pet_score.food_buff_bonus:.0%} pet xp for {reg.pet_score.food_buff_minutes:g} min"
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
            target = reg.pets[house.target]  # (no odds here: they differ per orb kind, see the wiki)
            body.append(text(f"{emojis.icon('target', '🎯')} **Hunting {target.emoji} {target.name}**  ·  ×{pets.target_boost(house.misses, reg):g} boost"
                             + (f"  ·  {house.misses} misses so far make it likelier" if house.misses else "")))
        hunt = [discord.SelectOption(label="No target", value="none", emoji=emojis.icon("cross", "🚫"), default=house.target is None)]
        for pet in sorted(reg.pets.values(), key=lambda p: (p.rarity, p.name)):
            mine = house.pets.get(pet.id)
            if mine is not None and mine.stars >= rules.max_stars:
                continue  # nothing left to hunt
            hunt.append(discord.SelectOption(label=pet.name + (f" ({mine.stars}/{rules.max_stars})" if mine else ""), value=pet.id, emoji=pet.emoji,
                                             description=Rarities.from_value(pet.rarity).rarity_name, default=pet.id == house.target))
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
        await self.refresh(interaction, f"{emojis.icon('target', '🎯')} Orbs now favour {pet.emoji} **{pet.name}**.\n-# {pets.max_buffs(pet)} (max level)" if pet else f"{emojis.icon('target', '🎯')} You are not hunting anything now.")

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
                 f"-# {pets.max_buffs(pet)} (max level)",
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
    emoji = emojis.Lazy("ui_pets", "🐾")
    description = "Your pets: look at them, feed them, pick who helps you"
    panes = {"pets": PetScreen, "orbs": OrbScreen}
