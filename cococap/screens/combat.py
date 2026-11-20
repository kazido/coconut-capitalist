"""The Combat page: Explore a zone (random fights) and see your Class (what your weapon makes you), as tabs of one page."""

import discord

from cococap import emojis
from cococap.registry import get_registry
from cococap.services import areas, combat, dungeon
from cococap.services.party import Party
from cococap.ui import Page, Screen
from cococap.ui.components import button, row, select, sep, text, xp_bar
from cococap.ui.tabs import TabsScreen
from cococap.user import User


BARE = "bare"
WEAPON_GLYPHS = {"sword": "⚔️", "bow": "🏹", "staff": "🪄", "shield": "🛡️", None: "👊"}


def weapon_emoji(kind: str | None) -> str:
    """The icon for a weapon kind (None = bare hands): its ui_weapon_<kind> emoji, else a plain glyph."""
    return emojis.icon(f"weapon_{kind or 'unarmed'}", WEAPON_GLYPHS[kind])


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
        xp = (await self.user.skill("combat")).xp
        level = User.xp_to_level(xp)
        overflow, needed = User.xp_for_next_level(xp)
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
            text(f"**Level {level}**  {xp_bar(overflow / needed if needed else 0)}  {overflow:,}/{needed:,} xp"),
            text(f"### {emojis.icon('sword', '⚔️')} Combat\n{emojis.icon('heart', '❤️')} **{me.max_hp}**  {emojis.icon('sword', '⚔️')} **{me.attack}**  "
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


class DungeonsPane(Screen):
    """Spend a tier key to walk a dungeon alone, or lead your whole party in."""

    label = "Dungeons"
    emoji = emojis.Lazy("ui_skull", "💀")
    description = "Tier dungeons: walk the grid, fight, beat the boss"

    def __init__(self, nav):
        super().__init__(nav)
        self.tier: int | None = None

    async def build(self) -> Page:
        reg = get_registry()
        level = User.xp_to_level((await self.user.skill("combat")).xp)
        owned = await self.user.items()
        lines, held = [], []
        for t in reg.combat.dungeons.values():
            have = owned.get(t.key, 0)
            lines.append(f"**T{t.tier}**  {reg.item(t.key).display} ×{have}" + (f"  ·  combat lv {t.min_level}" if t.min_level else ""))
            if have:
                held.append(t.tier)
        body = [*self.note_block(), text("### Dungeons\n" + "\n".join(lines))]
        if dungeon.run_of(self.user.id) is not None:
            body.append(row(button("Back to the dungeon", style=discord.ButtonStyle.danger, on_click=self._to_dungeon)))
            return Page("Dungeons", body, accent=0xC0392B)
        if self.tier not in held:
            self.tier = held[-1] if held else None
        if held:
            body.append(row(select("Which dungeon...", [discord.SelectOption(label=f"T{n}", value=str(n), default=n == self.tier) for n in held], self._pick)))
        t = reg.combat.dungeons.get(self.tier)
        body.append(row(button("Enter", style=discord.ButtonStyle.danger, disabled=t is None or level < t.min_level, on_click=self._enter)))
        return Page("Dungeons", body, accent=0xC0392B)

    async def _pick(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.tier = int(values[0])
        await self.refresh(interaction)

    async def _enter(self, interaction: discord.Interaction) -> None:
        users = [self.user]
        party = await Party.for_user(self.user.id)
        if party is not None and len(party.members) > 1:
            if not party.is_owner(self.user.id):
                await self.refresh(interaction, "Only the party leader can lead you in.")
                return
            users += [await User.get(i) for i in party.members if i != self.user.id]
        await dungeon.enter(users, self.tier)
        await self.go(interaction, "dungeon")

    async def _to_dungeon(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "dungeon")


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
        # Quick class switch: bare hands, plus every class you own a weapon for (picking one equips your best weapon of that kind).
        have = await combat.best_weapons(self.user, reg)
        options = [discord.SelectOption(label="Bare hands", value=BARE, emoji=weapon_emoji(None), default=cls is None)]
        options += [discord.SelectOption(label=f"{c.name} ({c.weapon})", value=cid, emoji=weapon_emoji(c.weapon), default=c is cls)
                    for cid, c in rules.classes.items() if c.weapon in have]
        switch = row(select("Change class...", options, self._pick)) if len(options) > 1 else None
        if cls is None:
            body.append(text(f"### Bare hands  ·  class level {(await combat.current_class(self.user, reg))[1]}\nEquip a sword, bow, staff or shield to pick a class. Weapons are smithed in **Smithing**.\n"
                             + "\n".join(f"**{rules.skills[s].name}**: {rules.skills[s].description}" for s in rules.kits["default"])))
            if switch:
                body.append(switch)
            return Page("Class", body, accent=0xC0392B)
        res = cls.resource.title()
        key, class_level = await combat.current_class(self.user, reg)
        overflow, needed = User.xp_for_next_level((await self.user.skill("combat")).class_xp.get(key, 0))
        body.append(text(f"### {cls.name}  ·  {kind}\n**Class level {class_level}**  {xp_bar(overflow / needed if needed else 0)}  {overflow:,}/{needed:,} xp\n"
                         f"{cls.description}\n**{res}** (max {cls.resource_max})"))
        lines = []
        for k in cls.kit:
            sk = rules.skills[k.skill]
            facts = [f"{sk.cost} {res.lower()}" if sk.cost else None, f"recharge {sk.cooldown}" if sk.cooldown else None]
            line = f"**{sk.name}**: {sk.description}" + (f" *({', '.join(f for f in facts if f)})*" if any(facts) else "")
            lines.append(line if k.level <= class_level else f"{emojis.icon('lock', '🔒')} ~~{sk.name}~~ unlocks at class level {k.level}")
        body.append(sep())
        body.append(text("\n".join(lines)))
        if switch:
            body.append(switch)
        return Page("Class", body, accent=0xC0392B)

    async def _pick(self, interaction: discord.Interaction, values: list[str]) -> None:
        await combat.switch_class(self.user, None if values[0] == BARE else values[0])
        await self.refresh(interaction)


class CombatScreen(TabsScreen):
    id = "combat"
    label = "Combat"
    emoji = emojis.Lazy("ui_sword", "⚔️")
    description = "Explore zones, fight monsters and pick a class"
    links = ("bestiary", "fight", "dungeon")
    panes = {"explore": ExplorePane, "dungeons": DungeonsPane, "class": ClassPane}
