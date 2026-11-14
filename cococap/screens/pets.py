import random

import discord

from cococap.registry import get_registry
from cococap.services import pets
from cococap.ui import Page, PromptModal, Result, Screen
from cococap.ui.components import button, row, select, sep, text, xp_bar
from cococap.user import User

STARS = "⭐"


def tag(pet) -> str:
    """The pet's name with the emoji of the one skill it looks after (🌐 = global)."""
    return f"{pet.name} {pets.skill_emoji(pet)}"


def stars_text(n: int) -> str:
    return STARS * n


class PetScreen(Screen):
    id = "pets"
    label = "Pets"
    emoji = "🐾"
    description = "Your pets: open orbs, feed them, pick who helps you"
    links = ()

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
            body.append(text("You have no pets yet. A **Familiar Orb** hatches a random pet: they turn up in treasure chests "
                             "and boss loot while fishing, and the shop sells them. Every pet gives a bonus somewhere in the game."))
        else:
            focus = self.focus_id(house)
            active = reg.pets[focus]
            if active is not None:
                mine = house.pets[active.id]
                level = pets.pet_level(mine.xp, reg)
                looks_after = ("**any skill** (global): any food is worth x%g to it" % rules.global_food_multiplier if active.skill == "global"
                               else f"**{active.skill}** {pets.skill_emoji(active)}: its food is worth x%g to it" % rules.matched_food_multiplier)
                low, high = pets.level_xp(level, reg), pets.level_xp(level + 1, reg)
                bar = xp_bar((mine.xp - low) / (high - low) if level < rules.max_level and high > low else 1.0)
                body.append(text(
                    f"### {active.emoji} {tag(active)}  {stars_text(mine.stars)}  ·  Lv {level}" + ("  ·  ✅ active" if focus == house.active else "")
                    + f"\n{bar}  "
                    + (f"{mine.xp - low:,}/{high - low:,} xp" if level < rules.max_level else "max level")
                    + "\n" + "\n".join(f"▸ {line}" for line in pets.describe(active, mine, reg))
                    + f"\n🍽️ Looks after: {looks_after}\n-# {active.description}"))
            roster = [f"{reg.pets[i].emoji} {tag(reg.pets[i])} {stars_text(p.stars)} Lv {pets.pet_level(p.xp, reg)}"
                      + (" ✅" if i == house.active else "") for i, p in sorted(house.pets.items())]
            missing = len(reg.pets) - len(house.pets)
            body.append(text("**Your pets:** " + "  ·  ".join(roster) + (f"  ·  ▫️ {missing} more to find" if missing else "")))
            body.append(row(select("Look at a pet...", [
                discord.SelectOption(label=f"{tag(reg.pets[i])} {stars_text(p.stars)}", value=i, emoji=reg.pets[i].emoji,
                                     default=i == focus, description=(("Active · " if i == house.active else "") + pets.describe(reg.pets[i], p, reg)[0])[:100])
                for i, p in sorted(house.pets.items())][:25], self._switch)))
            body.append(row(button("Make active", emoji="✅", disabled=focus == house.active, on_click=self._make_active)))

        orbs = owned_items.get(pets.ORB, 0)
        body.append(sep())
        if house.target in reg.pets:
            chance = pets.orb_odds(reg, house.target, house.misses)[house.target]
            body.append(text(f"🎯 **Hunting {reg.pets[house.target].emoji} {reg.pets[house.target].name}**  ·  "
                             f"**{chance:.1%}** per orb (×{pets.target_boost(house.misses, reg):g})"
                             + (f"  ·  {house.misses} misses so far make it likelier" if house.misses else "")))
        hunt = [discord.SelectOption(label="No target", value="none", emoji="🚫", default=house.target is None)]
        for pet in sorted(reg.pets.values(), key=lambda p: (p.rarity, p.name)):
            mine = house.pets.get(pet.id)
            if mine is not None and mine.stars >= rules.max_stars:
                continue  # nothing left to hunt
            chance = pets.orb_odds(reg, pet.id, 0)[pet.id]
            hunt.append(discord.SelectOption(label=tag(pet) + (f" ({mine.stars}★)" if mine else ""), value=pet.id, emoji=pet.emoji,
                                             description=f"rarity {pet.rarity}  ·  {chance:.1%} per orb when hunted",
                                             default=pet.id == house.target))
        body.append(row(select("Hunt a pet (orbs favour it)...", hunt[:25], self._hunt)))
        body.append(row(button(f"Open a Familiar Orb ({orbs})", emoji="🔮", style=discord.ButtonStyle.primary, disabled=orbs < 1,
                               on_click=self._open_orb)))
        if house.pets:
            target = house.pets[focus]
            foods = [(reg.item(i), q) for i, q in owned_items.items() if q > 0 and (it := reg.find_item(i)) and pets.food_xp(it, reg) > 0]
            foods.sort(key=lambda e: (pets.food_skill(e[0]) or "", pets.food_xp(e[0], reg)))
            if foods:
                body.append(row(select("Feed your pet...", [
                    discord.SelectOption(label=f"{c.name} ×{q:,}", value=c.id, emoji=c.emoji,
                                         description=self._food_note(c, active, target, reg)) for c, q in foods][:25], self._feed)))
            else:
                body.append(text("-# 🍽️ Pets eat crops and the food your skills drop: Acorn Mix from trees, Fish Flakes from fishing, "
                                 "Stone Biscuits from the mine. Food of a pet's own skill is worth more."))
            spirits = [(reg.item(i), q) for i, q in owned_items.items() if q > 0 and (it := reg.find_item(i)) and it.category == "pet_item"
                       and it.skill and it.skill not in target.spirits]
            if spirits:
                body.append(row(select("Give a Spirit to your pet...", [
                    discord.SelectOption(label=f"{s.name} ×{q}", value=s.id, emoji=s.emoji,
                                         description=f"+{rules.spirit_bonus:.0%} {s.skill} xp while it is active") for s, q in spirits][:25],
                                       self._spirit)))
        return Page("Pets", body, accent=0x27AE60)

    @staticmethod
    def _food_note(food, pet, owned, reg) -> str:
        base, boost = pets.food_xp(food, reg), pets.food_multiplier(pet, food, reg)
        return (f"{base:,} pet xp each" + (f" → {round(base * boost):,} for this pet (x{boost:g})" if boost != 1 else ""))[:100]

    async def _make_active(self, interaction: discord.Interaction) -> None:
        pet = await pets.set_active(self.user, self.focus_id(self.user.pethouse))
        await self.refresh(interaction, f"{pet.emoji} **{pet.name}** is your active pet now.")

    async def _hunt(self, interaction: discord.Interaction, values: list[str]) -> None:
        pet = await pets.set_target(self.user, None if values[0] == "none" else values[0])
        await self.refresh(interaction, f"🎯 Orbs now favour {pet.emoji} **{pet.name}**." if pet else "🎯 You are not hunting anything now.")

    async def _switch(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.focus = values[0]
        await self.refresh(interaction)

    async def _open_orb(self, interaction: discord.Interaction) -> None:
        got = await pets.open_orb(self.user, random.Random())
        reg = get_registry()
        pet = got.pet
        mine = self.user.pethouse.pets[pet.id]  # (open_orb has refreshed the player)
        lines = [f"### {pet.emoji} {pet.name}  {stars_text(got.stars)}" + ("  🎯 **Target hit!**" if got.target_hit else ""),
                 "**A new friend!**" if got.is_new else (f"Another {pet.name}! It now has **{got.stars}** stars." if not got.maxed
                                                        else f"You already have a five-star {pet.name}: it gains {reg.economy.pets.maxed_xp:,} xp instead."),
                 "\n".join(f"▸ {line}" for line in pets.describe(pet, mine, reg)), f"-# {pet.description}"]
        self.result = Result("The orb hatches!", lines, emoji="🔮", accent=0x27AE60, again=self._open_orb_again, again_label="Another orb",
                             back_label="To the Pet House")
        await self.refresh(interaction)

    async def _open_orb_again(self, interaction: discord.Interaction) -> None:
        await self._open_orb(interaction)

    async def _feed(self, interaction: discord.Interaction, values: list[str]) -> None:
        crop_id = values[0]
        reg = get_registry()
        have = await self.user.item_quantity(crop_id)

        async def submitted(modal_interaction: discord.Interaction, raw: str) -> None:
            try:
                quantity = have if raw.strip().lower() in ("all", "") else int(raw.replace(",", ""))
            except ValueError:
                raise pets.PetError("Enter a whole number, or 'all'.") from None
            fed = await pets.feed(self.user, crop_id, quantity, pet_id=self.focus_id(self.user.pethouse))
            note = f"🍎 {fed.pet.name} ate {fed.quantity:,} {reg.item(crop_id).display}  ·  +{fed.xp:,} pet xp" + (f" (x{fed.multiplier:g})" if fed.multiplier != 1 else "")
            if fed.level_after > fed.level_before:
                note += f"\n🎉 **{fed.pet.name} reached level {fed.level_after}!**"
            await self.refresh(modal_interaction, note)

        await interaction.response.send_modal(PromptModal(f"Feed {reg.item(crop_id).name}", f"How many? (you have {have:,})", submitted,
                                                          default=str(have), max_length=9))

    async def _spirit(self, interaction: discord.Interaction, values: list[str]) -> None:
        pet, skill = await pets.give_spirit(self.user, values[0], pet_id=self.focus_id(self.user.pethouse))
        await self.refresh(interaction, f"✨ {pet.name} now carries the {skill} Spirit.")
