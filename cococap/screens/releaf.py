import discord

from cococap.registry import get_registry
from cococap.services import releaf
from cococap.ui import Page, Screen
from cococap.ui.components import bar, button, row, select, sep, text
from cococap import emojis

GREEN = 0x2E7D32


class ReleafScreen(Screen):
    id = "releaf"
    label = "Releaf Foundation"
    emoji = emojis.Lazy("ui_sprout", "🌱")
    description = "Give rare drops together to start a server-wide Bloom"
    links = ("forage",)
    refresh_every = 20.0  # other players give too: keep the meter and the Bloom timer live

    def __init__(self, nav):
        super().__init__(nav)
        self.item: str | None = None  # the item picked to give

    async def build(self) -> Page:
        reg = get_registry()
        rules = reg.foraging.releaf
        s = await releaf.status(self.user)
        found = s.foundation
        body = [*self.note_block()]
        if not s.unlocked:
            body.append(text(f"The Foundation opens at foraging level **{rules.min_level}**."))
            return Page("Releaf Foundation", body, accent=GREEN)

        head = (f"The whole server fills one meter with **rare** foraging drops. When it is full, a **Bloom** starts for everyone: "
                f"**+{rules.bloom_xp:.0%}** foraging xp and **+{rules.bloom_drops:.0%}** drop chances on every tree, for **{rules.bloom_hours:g}** hours.\n"
                f"-# Giving takes the item for good and brings you nothing personal; the Bloom is for everybody, whether they gave or not.")
        body.append(text(head))
        status_line = f"{emojis.icon('sprout', '🌱')}  {bar(found.meter / found.goal, 12, 'meter')}  **{found.meter}/{found.goal}**"
        if found.bloom_active:
            status_line += f"\n{emojis.icon('flower', '🌸')} **Bloom is up!** Ends <t:{int(found.bloom_until)}:R>. Giving reopens after it."
        elif found.full:
            status_line += "\nThe Bloom has just ended: giving reopens in a moment."
        else:
            status_line += f"\nGiving is open. {found.givers} giving this round."
        body += [sep(), text(status_line)]
        if found.top:
            body.append(text("**Thank you!**  " + "  ·  ".join(f"{d.name} **{d.points}**" for d in found.top)))
        body.append(text(f"-# You gave **{s.yours}/{s.cap}** this round (the most one person can give) and **{s.lifetime}** in all."))
        body.append(sep())

        owned = await releaf.donatable(self.user)
        if self.item not in owned:
            self.item = None
        if not owned:
            body.append(text(f"You have nothing the Foundation takes. It accepts foraging items of rarity **{rules.min_rarity}** or more."))
            return Page("Releaf Foundation", body, accent=GREEN)
        ranked = sorted(owned, key=lambda i: (-reg.item(i).rarity, reg.item(i).name))
        options = [discord.SelectOption(label=reg.item(i).name, value=i, emoji=reg.item(i).emoji or None, default=i == self.item,
                                        description=f"you have {owned[i]:,}  ·  +{releaf.points_of(i, reg)} each  ·  sells for {reg.item(i).sell_price:,}")
                   for i in ranked]
        body.append(row(select("Give...", options, self._pick)))
        if self.item:
            body.append(text(self._preview(reg, rules, s, owned)))
            have, fits = owned[self.item], releaf.max_items(releaf.points_of(self.item, reg), found.meter, s.yours, rules) if found.open else 0
            allowed = min(have, fits)

            def give(count: int):
                async def go(interaction: discord.Interaction) -> None:
                    await self._give(interaction, count)

                return go

            body.append(row(*(button(f"Give {n}", on_click=give(n), disabled=allowed < n) for n in (1, 10)),
                            button(f"Give all ({allowed:,})", style=discord.ButtonStyle.success, on_click=give(allowed), disabled=allowed < 1)))
        return Page("Releaf Foundation", body, accent=GREEN)

    def _preview(self, reg, rules, s, owned) -> str:
        item, found = reg.item(self.item), s.foundation
        points = releaf.points_of(self.item, reg)
        have = owned[self.item]
        if not found.open:
            return "-# The Foundation is closed until the Bloom ends."
        fits = releaf.max_items(points, found.meter, s.yours, rules)
        if fits < 1:
            return "-# You have given all you can this round."
        n = min(have, fits)
        return (f"-# **{item.name}**: +{points} each, you have {have:,}. Giving all {n:,} adds **{min(points * n, found.goal - found.meter)}** and loses **{item.sell_price * n:,} bits** "
                f"of sell value for good.")

    async def _pick(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.item = values[0]
        await self.refresh(interaction)

    async def _give(self, interaction: discord.Interaction, count: int) -> None:
        reg = get_registry()
        done = await releaf.donate(self.user, self.item, count)
        note = f"{emojis.icon('sprout', '🌱')} You gave **{done.given:,} {reg.item(self.item).name}** (+{done.points}). The meter is at {done.meter}/{done.goal}."
        if done.returned:
            note += f" {done.returned:,} did not fit and came back."
        if done.bloom_started:
            note += f"\n{emojis.icon('flower', '🌸')} **The Bloom begins!** Everyone's foraging is boosted."
        await self.refresh(interaction, note)
