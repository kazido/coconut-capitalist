import discord

from cococap import emojis
from cococap.constants import STARTER_TOOLS
from cococap.registry import get_registry
from cococap.services.equipment import TOOL_FOR_SKILL, effective_stats
from cococap.services import shop
from cococap.services.inventory import instance_label
from cococap.ui import Page, Screen
from cococap.ui.components import button, row, sep, text
from cococap.screens.enchant import EnchantPane
from cococap.screens.upgrade import UpgradePane, describe_stats
from cococap.ui.tabs import TabsScreen

KIND_LABEL = {"pickaxe": "Mining", "axe": "Foraging", "sword": "Combat", "rod": "Fishing", "can": "Farming"}


class ToolsPane(Screen):
    """Your tool for each skill, as a compact list. Upgrade and Enchant are the other tabs of the Tools page."""

    label = "Tools"
    emoji = emojis.Lazy("ui_anvil", "🧰")

    async def _equipped_ids(self) -> set[int]:
        ids = set()
        for skill in TOOL_FOR_SKILL:
            equipped = (await self.user.skill(skill)).equipped_instance_id
            if equipped is not None:
                ids.add(equipped)
        return ids

    async def build(self) -> Page:
        reg = get_registry()
        instances = [i for i in await self.user.instances() if reg.item(i.template_id).tool]
        equipped = await self._equipped_ids()
        body = [*self.note_block()]
        if not instances:
            body.append(text("You have no tools yet. Claim your free starter tools below."))
        # one compact line per skill: the equipped tool (you hold one tool per skill, so there is nothing to pick between)
        lines = []
        for kind in KIND_LABEL:
            mine = [i for i in instances if reg.item(i.template_id).tool.kind == kind]
            if not mine:
                continue
            inst = next((i for i in mine if i.id in equipped), mine[0])
            item = reg.item(inst.template_id)
            tool = item.tool
            extra = ([f"{tool.path} path"] if tool.path else []) + ([describe_stats(tool.stats)] if tool.stats else [])
            lines.append(f"{item.emoji or emojis.icon('craft', '🔨')} **{instance_label(inst)}**  ·  {KIND_LABEL[kind]}  ·  power **{effective_stats(inst, reg).power}**"
                         + "".join(f"  ·  {e}" for e in extra) + (f"  ·  {emojis.icon('sparkle', '✨')} {tool.ability_name}" if tool.ability_name else ""))
        if lines:
            body.append(text("\n".join(lines)))
        if await self._unclaimed():
            body += [sep(), row(button("Claim free starter tools", emoji=emojis.icon("gift", "🎁"), style=discord.ButtonStyle.success, on_click=self._claim))]
        body += [sep(), row(button("Inventory", emoji=emojis.icon("bag", "🎒"), on_click=self._inventory))]
        return Page("Tools", body, accent=0xB8860B)

    async def _unclaimed(self) -> bool:
        reg = get_registry()
        have = {t.tool.kind for i in await self.user.instances() if (t := reg.find_item(i.template_id)) and t.tool}
        for item_id in STARTER_TOOLS:
            if reg.item(item_id).tool.kind not in have and not await self.user.get_stat(f"starter_claimed_{item_id}"):
                return True
        return False

    async def _claim(self, interaction: discord.Interaction) -> None:
        got = await shop.claim_starter_tools(self.user)
        names = ", ".join(get_registry().item(i).name for i in got)
        await self.refresh(interaction, f"{emojis.icon('gift', '🎁')} You got: {names}." if got else "You have no starter tools to claim.")

    async def _inventory(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "inventory")


class ToolsScreen(TabsScreen):
    """The Tools page: your tools (the list), then Upgrade and Enchant as tabs of the same page."""

    id = "tools"
    label = "Tools"
    emoji = emojis.Lazy("ui_anvil", "🧰")
    description = "Your tools: upgrade and enchant them"
    links = ("inventory",)
    panes = {"tools": ToolsPane, "upgrade": UpgradePane, "enchant": EnchantPane}
