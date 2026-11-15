import discord

from cococap.registry import get_registry
from cococap.services import enchanting
from cococap.services.inventory import instance_label
from cococap.ui import Page, Screen
from cococap.ui.components import button, row, select, sep, text


class EnchantScreen(Screen):
    id = "enchant"
    label = "Enchant"
    emoji = "📜"
    description = "Use a scroll to enchant a tool"
    links = ("inventory",)

    def __init__(self, nav):
        super().__init__(nav)
        self.scroll_id: str | None = None

    async def build(self) -> Page:
        reg = get_registry()
        scrolls = await enchanting.owned_scrolls(self.user)
        body = [*self.note_block()]
        if not scrolls:
            body.append(text("You have no scrolls. They turn up in play: deep in the mines, on rare trees, and in "
                             "treasure chests and boss loot while fishing."))
        else:
            if self.scroll_id not in {s.id for s, _ in scrolls}:
                self.scroll_id = None
            body.append(row(select("Pick a scroll...", [
                discord.SelectOption(label=f"{s.name} ×{q}", value=s.id, emoji=s.emoji or None,
                                     description=reg.enchant(s.scroll.enchant).description[:100],
                                     default=s.id == self.scroll_id) for s, q in scrolls], self._pick_scroll)))
            if self.scroll_id:
                scroll = reg.item(self.scroll_id)
                enchant = reg.enchant(scroll.scroll.enchant)
                tools = [i for i in await self.user.instances() if enchanting.problem(scroll, i, reg) is None]
                body.append(text(f"{enchant.emoji} **{enchant.name}**: {enchant.description}"
                                 f" (up to level {enchant.max_level})"))
                if tools:
                    body.append(row(select("Put it on...", [
                        discord.SelectOption(label=instance_label(i)[:100], value=str(i.id),
                                             emoji=reg.item(i.template_id).emoji or None) for i in tools], self._apply)))
                else:
                    body.append(text(f"-# None of your tools can take it right now ({enchant.name} fits a "
                                     f"{' or '.join(enchant.applies_to)})."))
        body += [sep(), row(button("Back to inventory", emoji="🎒", on_click=self._back))]
        return Page("Enchant", body, accent=0x8E44AD)

    async def _pick_scroll(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.scroll_id = values[0]
        await self.refresh(interaction)

    async def _apply(self, interaction: discord.Interaction, values: list[str]) -> None:
        reg = get_registry()
        scroll = reg.item(self.scroll_id)
        done = await enchanting.apply_scroll(self.user, self.scroll_id, int(values[0]))
        await self.refresh(interaction, f"📜 **{reg.enchant(scroll.scroll.enchant).name}** is now on your {instance_label(done)}!")

    async def _back(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "inventory")
