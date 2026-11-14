import discord

from cococap.constants import Rarities
from cococap.registry import get_registry
from cococap.services import wiki
from cococap.ui import Page, Screen
from cococap.ui.components import button, row, select, sep, text
from utils.items.items import item_attributes

PER_PAGE = 25


class WikiScreen(Screen):
    """Everything in the game, written from the game's own data so it is never out of date."""

    id = "wiki"
    label = "Wiki"
    emoji = "📖"
    description = "How everything works: skills, fish, pets, tools, items"
    links = ()

    def __init__(self, nav):
        super().__init__(nav)
        self.topic = "start"
        self.skill = "fishing"
        self.item: str | None = None
        self.page = 0

    async def build(self) -> Page:
        reg = get_registry()
        titles = {t: (name, emoji) for t, name, emoji in wiki.TOPICS}
        name, emoji = titles[self.topic]
        body = [*self.note_block()]
        body.append(row(select("Pick a topic...", [
            discord.SelectOption(label=title, value=topic, emoji=icon, default=topic == self.topic) for topic, title, icon in wiki.TOPICS],
            self._pick_topic)))
        body.append(sep())
        if self.topic == "items":
            body += self._item_lookup(reg)
        else:
            body += [text(block) for block in wiki.page(self.topic, reg)]
        return Page(f"Wiki: {name}", body, accent=0x3498DB)

    def _item_lookup(self, reg) -> list:
        parts = [row(select("Pick a skill...", [
            discord.SelectOption(label=s.title(), value=s, default=s == self.skill) for s in wiki.SKILL_FILTERS], self._pick_skill))]
        items = wiki.items_for(self.skill, reg)
        pages = max(1, -(-len(items) // PER_PAGE))
        self.page = min(self.page, pages - 1)
        shown = items[self.page * PER_PAGE:(self.page + 1) * PER_PAGE]
        if shown:
            parts.append(row(select(f"Pick an item ({self.page + 1}/{pages})...", [
                discord.SelectOption(label=i.name, value=i.id, emoji=i.emoji or None, default=i.id == self.item,
                                     description=Rarities.from_value(i.rarity).rarity_name) for i in shown], self._pick_item)))
        if pages > 1:
            parts.append(row(button(emoji="◀️", disabled=self.page == 0, on_click=self._turn(-1)),
                             button(f"{self.page + 1}/{pages}", disabled=True),
                             button(emoji="▶️", disabled=self.page >= pages - 1, on_click=self._turn(1))))
        item = reg.find_item(self.item) if self.item else None
        parts.append(text(f"### {item.display}\n" + item_attributes(item) if item else "Pick an item to read about it."))
        return parts

    async def _pick_topic(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.topic = values[0]
        await self.refresh(interaction)

    async def _pick_skill(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.skill, self.item, self.page = values[0], None, 0
        await self.refresh(interaction)

    async def _pick_item(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.item = values[0]
        await self.refresh(interaction)

    def _turn(self, step: int):
        async def turn(interaction: discord.Interaction) -> None:
            self.page += step
            await self.refresh(interaction)

        return turn
