import discord

from cococap import emojis
from cococap.registry import get_registry
from cococap.services import mastery
from cococap.services.mastery import MasteryError
from cococap.ui import Page, Screen
from cococap.ui.components import bits, button, row, sep, text



class MasteryScreen(Screen):
    """A skill's Mastery tree: spend points on the nodes of the playstyle you like."""

    id = "mastery"
    label = "Mastery"
    emoji = emojis.Lazy("star", "🌟")
    description = "Spend mastery points on how you play a skill"
    links = ("mining", "fish", "farm", "forage")

    def __init__(self, nav):
        super().__init__(nav)
        self.skill = "mining"

    async def build(self) -> Page:
        reg = get_registry()
        tree = mastery.tree_for(self.skill, reg)
        owned, level, free = await mastery.status(self.user, self.skill, reg)
        body = [*self.note_block(),
                text(f"### {emojis.skill(self.skill, '🌟')} {self.skill.title()} Mastery  ·  lv {level}\n"
                     f"**{free}** point(s) free  ·  {mastery.points_spent(owned, reg)} spent  ·  1 point per {reg.mastery.points_every_levels} levels\n"
                     "-# You cannot take every branch: choose how you play.")]
        take = []
        for branch in tree.branches:
            lines = [f"### {branch.emoji} {branch.name}\n-# {branch.description}"]
            next_node = None
            for state in mastery.branch_state(branch, owned, level, free):
                node = state.node
                mark = emojis.icon("check", "✅") if state.owned else emojis.icon("unlock", "🔓") if state.available else emojis.icon("lock", "🔒")
                why = f"  *({state.reason})*" if state.reason and state.reason != "locked" and not state.owned else ""
                lines.append(f"{mark} **{node.name}** · {node.cost}pt · lv{node.level} · {node.description}{why}")
                if next_node is None and not state.owned:
                    next_node = state
            body.append(text("\n".join(lines)))
            if next_node is not None:
                take.append(button(f"{branch.name}: {next_node.node.name}"[:80], emoji=branch.emoji, style=discord.ButtonStyle.success,
                                   disabled=not next_node.available, on_click=self._take(next_node.node.id)))
        body += [sep(), *([row(*take)] if take else [])]
        body.append(row(*(button(skill.title(), emoji=emojis.skill(skill) or None, style=discord.ButtonStyle.primary if skill == self.skill else discord.ButtonStyle.secondary,
                                 on_click=self._switch(skill)) for skill in [t.skill for t in reg.mastery.trees]),
                        button(f"Respec ({bits(reg.mastery.respec_bits)} bits)", emoji=emojis.icon("again", "♻️"), disabled=not owned, on_click=self._respec)))
        return Page("Mastery", body, accent=0xD4A017)

    def _take(self, node_id: str):
        async def go(interaction: discord.Interaction) -> None:
            try:
                node = await mastery.buy(self.user, self.skill, node_id)
            except MasteryError as error:
                return await self.refresh(interaction, str(error))
            await self.refresh(interaction, f"{emojis.icon('star', '🌟')} You took **{node.name}**!")

        return go

    def _switch(self, skill: str):
        async def go(interaction: discord.Interaction) -> None:
            self.skill = skill
            await self.refresh(interaction)

        return go

    async def _respec(self, interaction: discord.Interaction) -> None:
        try:
            given = await mastery.respec(self.user, self.skill)
        except MasteryError as error:
            return await self.refresh(interaction, str(error))
        await self.refresh(interaction, f"{emojis.icon('again', '♻️')} Your tree is cleared: {given} point(s) back.")
