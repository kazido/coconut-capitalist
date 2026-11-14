import random

import discord

from cococap.registry import get_registry
from cococap.services import pets
from cococap.ui import Page, PromptModal, Result, Screen
from cococap.ui.components import button, row, select, sep, text, xp_bar
from cococap.user import User

STARS = "⭐"


def stars_text(n: int) -> str:
    return STARS * n


class PetScreen(Screen):
    id = "pets"
    label = "Pets"
    emoji = "🐾"
    description = "Your pets: open orbs, feed them, pick who helps you"
    links = ()

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
            active = reg.pets[house.active] if house.active in house.pets else None
            if active is not None:
                mine = house.pets[active.id]
                level = pets.pet_level(mine.xp, reg)
                low, high = pets.level_xp(level, reg), pets.level_xp(level + 1, reg)
                bar = xp_bar((mine.xp - low) / (high - low) if level < rules.max_level and high > low else 1.0)
                body.append(text(
                    f"### {active.emoji} {active.name}  {stars_text(mine.stars)}  ·  Lv {level}\n{bar}  "
                    + (f"{mine.xp - low:,}/{high - low:,} xp" if level < rules.max_level else "max level")
                    + "\n" + "\n".join(f"▸ {line}" for line in pets.describe(active, mine, reg))
                    + f"\n-# {active.description}"))
            roster = [f"{reg.pets[i].emoji} {reg.pets[i].name} {stars_text(p.stars)} Lv {pets.pet_level(p.xp, reg)}"
                      + (" ✅" if i == house.active else "") for i, p in sorted(house.pets.items())]
            missing = len(reg.pets) - len(house.pets)
            body.append(text("**Your pets:** " + "  ·  ".join(roster) + (f"  ·  ▫️ {missing} more to find" if missing else "")))
            body.append(row(select("Switch active pet...", [
                discord.SelectOption(label=f"{reg.pets[i].name} {stars_text(p.stars)}", value=i, emoji=reg.pets[i].emoji,
                                     default=i == house.active, description=pets.describe(reg.pets[i], p, reg)[0][:100])
                for i, p in sorted(house.pets.items())][:25], self._switch)))

        orbs = owned_items.get(pets.ORB, 0)
        body.append(sep())
        body.append(row(button(f"Open a Familiar Orb ({orbs})", emoji="🔮", style=discord.ButtonStyle.primary, disabled=orbs < 1,
                               on_click=self._open_orb)))
        if house.active in house.pets:
            crops = [(reg.item(i), q) for i, q in owned_items.items() if q > 0 and (it := reg.find_item(i)) and pets.crop_pet_xp(it) > 0]
            if crops:
                body.append(row(select("Feed your pet a crop...", [
                    discord.SelectOption(label=f"{c.name} ×{q:,}", value=c.id, emoji=c.emoji,
                                         description=f"{pets.crop_pet_xp(c):,} pet xp each") for c, q in crops][:25], self._feed)))
            spirits = [(reg.item(i), q) for i, q in owned_items.items() if q > 0 and (it := reg.find_item(i)) and it.category == "pet_item"
                       and it.skill and it.skill not in house.pets[house.active].spirits]
            if spirits:
                body.append(row(select("Give a Spirit to your pet...", [
                    discord.SelectOption(label=f"{s.name} ×{q}", value=s.id, emoji=s.emoji,
                                         description=f"+{rules.spirit_bonus:.0%} {s.skill} xp while it is active") for s, q in spirits][:25],
                                       self._spirit)))
        return Page("Pets", body, accent=0x27AE60)

    async def _switch(self, interaction: discord.Interaction, values: list[str]) -> None:
        pet = await pets.set_active(self.user, values[0])
        await self.refresh(interaction, f"{pet.emoji} **{pet.name}** is your active pet now.")

    async def _open_orb(self, interaction: discord.Interaction) -> None:
        got = await pets.open_orb(self.user, random.Random())
        reg = get_registry()
        pet = got.pet
        mine = self.user.pethouse.pets[pet.id]  # (open_orb has refreshed the player)
        lines = [f"### {pet.emoji} {pet.name}  {stars_text(got.stars)}",
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
            fed = await pets.feed(self.user, crop_id, quantity)
            note = f"🍎 {fed.pet.name} ate {fed.quantity:,} {reg.item(crop_id).display}  ·  +{fed.xp:,} pet xp"
            if fed.level_after > fed.level_before:
                note += f"\n🎉 **{fed.pet.name} reached level {fed.level_after}!**"
            await self.refresh(modal_interaction, note)

        await interaction.response.send_modal(PromptModal(f"Feed {reg.item(crop_id).name}", f"How many? (you have {have:,})", submitted,
                                                          default=str(have), max_length=9))

    async def _spirit(self, interaction: discord.Interaction, values: list[str]) -> None:
        pet, skill = await pets.give_spirit(self.user, values[0])
        await self.refresh(interaction, f"✨ {pet.name} now carries the {skill} Spirit.")
