import discord

from cococap.registry import get_registry
from cococap.services import crafting
from cococap.ui import Page, Screen
from cococap.ui.components import bits, button, needs_text, row, select, text
from cococap.ui.rewards import rewards_result


class CraftScreen(Screen):
    """The Workbench: pick a recipe, see what it needs against what you have, craft one, ten or as many as you can."""

    id = "craft"
    label = "Workbench"
    emoji = "🛠️"
    description = "Make things from materials"
    links = ()

    def __init__(self, nav):
        super().__init__(nav)
        self.recipe_id: str | None = None
        self.last = 1  # how many the last craft made (for "Craft again")

    async def build(self) -> Page:
        reg = get_registry()
        owned = await self.user.items()
        await self.user.refresh()
        listed = crafting.recipes(reg)
        recipe = reg.recipes.get(self.recipe_id) or listed[0]
        self.recipe_id = recipe.id
        count = await crafting.craftable_count(self.user, recipe)
        level = await crafting.skill_level(self.user, recipe)
        locked = level < recipe.min_level

        options = []
        for r in listed:
            can = await crafting.craftable_count(self.user, r)
            options.append(discord.SelectOption(label=r.name, value=r.id, emoji=r.emoji or None, default=r.id == recipe.id,
                                                description=(f"you can make {can:,}" if can else "missing something")[:100]))
        output = reg.item(recipe.output)
        made = f"**{recipe.quantity:,}** {output.display}" if recipe.quantity > 1 else output.display
        lines = [f"### 🛠️ {recipe.emoji or ''} {recipe.name}", f"Makes {made}", f"-# {output.description}" if output.description else "",
                 "", needs_text(recipe.bits, self.user.purse, recipe.inputs, owned, reg)]
        if recipe.min_level:
            lines.append(f"{'✅' if not locked else '❌'} {recipe.skill.title()} level **{recipe.min_level}** (you are level {level})")
        lines.append(f"-# You can make **{count:,}** right now. Sell All keeps what recipes use while \"Keep upgrade materials\" is on.")
        body = [*self.note_block(), text("\n".join(lines)), row(select("Pick a recipe...", options, self._pick)),
                row(button("Craft 1", emoji="🛠️", style=discord.ButtonStyle.success, disabled=count < 1, on_click=self._craft(1)),
                    button("Craft 10", disabled=count < 10, on_click=self._craft(10)),
                    button(f"Craft max ({count:,})" if count else "Craft max", disabled=count < 1, on_click=self._craft(None)))]
        return Page("Workbench", body, accent=0xB8860B)

    async def _pick(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.recipe_id = values[0]
        await self.refresh(interaction)

    def _craft(self, times: int | None):
        async def go(interaction: discord.Interaction) -> None:
            reg = get_registry()
            recipe = crafting.find(self.recipe_id, reg)
            n = times if times is not None else await crafting.craftable_count(self.user, recipe)
            made = await crafting.craft(self.user, recipe.id, max(n, 1), reg)
            self.last = made.times
            fee = f"  (for {bits(made.bits)} bits)" if made.bits else ""
            self.result = rewards_result("Crafted!", items=made.items, headline=[f"🛠️ You made **{made.times:,}** × {recipe.name}{fee}."],
                                         emoji="🛠️", accent=0xB8860B, again=self._again, again_label="Craft again", back_label="Back to the Workbench")
            await self.refresh(interaction)

        return go

    async def _again(self, interaction: discord.Interaction) -> None:
        await self._craft(self.last)(interaction)
