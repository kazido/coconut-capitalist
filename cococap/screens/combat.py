"""The Combat page: Explore a zone (random fights) and see your Class (what your weapon makes you), as tabs of one page."""

import discord

from cococap import emojis
from cococap.registry import get_registry
from cococap.services import areas, combat
from cococap.ui import Page, Screen
from cococap.ui.components import button, row, select, sep, text
from cococap.ui.tabs import TabsScreen
from cococap.user import User


class ExplorePane(Screen):
    """Pick an open zone and fight what turns up; key fights (the Gravewarden) are listed below."""

    label = "Explore"
    emoji = emojis.Lazy("ui_sword", "⚔️")
    description = "Fight monsters in the zones you have opened"

    def __init__(self, nav):
        super().__init__(nav)
        self.zone: str | None = None

    async def build(self) -> Page:
        reg = get_registry()
        level = User.xp_to_level((await self.user.skill("combat")).xp)
        zones = await areas.open_location_list(self.user, "combat", reg)
        ids = [z.id for z in zones]
        if self.zone is None:
            self.zone = self.user.settings.zones.get("combat")
        if self.zone not in ids:
            self.zone = ids[-1]  # an unknown or closed zone falls back to the highest open one
        here = zones[ids.index(self.zone)]
        rules = reg.combat.zones[self.zone]
        foes = ", ".join(f"{reg.enemies[e].emoji} {reg.enemies[e].name}" for e in rules.enemies)
        me = await combat.build_player(self.user)
        body = [
            *self.note_block(),
            text(f"### {emojis.icon('sword', '⚔️')} Combat  ·  Lv {level}\n{emojis.icon('heart', '❤️')} **{me.max_hp}**  {emojis.icon('sword', '⚔️')} **{me.attack}**  "
                 f"{emojis.icon('shield', '🛡️')} **{me.defense}**  {emojis.icon('bolt', '⚡')} **{me.speed}**"),
            sep(),
            text(f"### {here.emoji} {here.name}\nUp to **{rules.max_foes}** at a time: {foes}"
                 + (f"\n-# Something bigger sometimes lurks here ({reg.enemies[rules.rare].name})." if rules.rare else "")),
        ]
        if (hint := await areas.next_location_hint(self.user, "combat", reg)) is not None:
            body.append(text(f"-# Next zone: {hint}."))
        if len(zones) > 1:
            body.append(row(select(
                "Where to fight...",
                [discord.SelectOption(label=z.name, value=z.id, emoji=z.emoji, default=z.id == self.zone) for z in zones],
                self._pick_zone,
            )))
        body.append(row(button("Explore", emoji=emojis.icon("sword", "⚔️"), style=discord.ButtonStyle.danger, on_click=self._explore),
                        button("Bestiary", emoji=emojis.icon("book", "📖"), on_click=self._to_bestiary)))
        owned = await self.user.items()
        for enc in (e for e in reg.combat.encounters if e.key):
            key = reg.item(enc.key)
            foes = ", ".join(reg.enemies[e].emoji + " " + reg.enemies[e].name for e in enc.enemies)
            have = owned.get(enc.key, 0)
            line = f"**{enc.name}**\n{foes}\n{key.display} ×{have}" + ("" if have else " · needs a key (monsters drop them)")
            if level < enc.min_level:
                line += f"\n{emojis.icon('lock', '🔒')} Combat level {enc.min_level}"
            body.append(sep())
            body.append(text(line))
            body.append(row(button("Fight", style=discord.ButtonStyle.danger, disabled=level < enc.min_level or not have, on_click=self._key_fight(enc.id))))
        return Page("Combat", body, accent=0xC0392B)

    async def _pick_zone(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.zone = values[0]
        await self.user.set_zone("combat", values[0])
        await self.refresh(interaction)

    async def _explore(self, interaction: discord.Interaction) -> None:
        battle = await combat.explore(self.user, self.zone)
        await self.go(interaction, "fight", battle=battle, zone=self.zone, encounter=None, picking=None)

    def _key_fight(self, encounter_id: str):
        async def start(interaction: discord.Interaction) -> None:
            battle = await combat.start_fight(self.user, encounter_id)
            await self.go(interaction, "fight", battle=battle, zone=None, encounter=encounter_id, picking=None)

        return start

    async def _to_bestiary(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "bestiary")


class ClassPane(Screen):
    """What your weapon makes you: the class, its resource and its skills."""

    label = "Class"
    emoji = emojis.Lazy("ui_skills", "🎓")
    description = "Your weapon picks your class"

    async def build(self) -> Page:
        reg = get_registry()
        rules = reg.combat
        level = User.xp_to_level((await self.user.skill("combat")).xp)
        instance = await self.user.equipped_instance("combat")
        kind = reg.item(instance.template_id).tool.kind if instance is not None else None
        cls = combat.class_for(kind, reg)
        body = [*self.note_block()]
        if cls is None:
            body.append(text("### Bare hands\nEquip a sword, bow, staff or shield to pick a class. Weapons are smithed in **Smithing**.\n"
                             + "\n".join(f"**{rules.skills[s].name}**: {rules.skills[s].description}" for s in rules.kits["default"])))
            return Page("Class", body, accent=0xC0392B)
        res = cls.resource.title()
        body.append(text(f"### {cls.name}  ·  {kind}\n{cls.description}\n**{res}** (max {cls.resource_max})"))
        lines = []
        for k in cls.kit:
            sk = rules.skills[k.skill]
            facts = [f"{sk.cost} {res.lower()}" if sk.cost else None, f"recharge {sk.cooldown}" if sk.cooldown else None]
            line = f"**{sk.name}**: {sk.description}" + (f" *({', '.join(f for f in facts if f)})*" if any(facts) else "")
            lines.append(line if k.level <= level else f"{emojis.icon('lock', '🔒')} ~~{sk.name}~~ unlocks at combat level {k.level}")
        body.append(sep())
        body.append(text("\n".join(lines)))
        return Page("Class", body, accent=0xC0392B)


class CombatScreen(TabsScreen):
    id = "combat"
    label = "Combat"
    emoji = emojis.Lazy("ui_sword", "⚔️")
    description = "Explore zones, fight monsters and pick a class"
    links = ("bestiary", "fight")
    panes = {"explore": ExplorePane, "class": ClassPane}
