"""Load and cross-validate the game data in ``configs/*.toml``."""

import os
import tomllib
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from .models import AreaRules, ScrollRules, ShipmentRules, ToolRules, MasteryRules, CombatRules, DropTable, EconomyRules, BestiaryRules, Enchant, Enemy, FarmingRules, FishingRules, ForagingRules, Item, MiningRules, Pet, Rank, Recipe, Skill

CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs"


class RegistryError(Exception):
    """The game data is invalid. The message names the file and entry."""


class UnknownItem(KeyError):
    pass


class UnknownEnchant(KeyError):
    pass


def _merge(base: dict, over: dict) -> dict:
    """`over` laid on top of `base`: tables merge key by key, anything else (numbers, lists) is replaced."""
    out = dict(base)
    for key, value in over.items():
        out[key] = _merge(out[key], value) if isinstance(value, dict) and isinstance(out.get(key), dict) else value
    return out


def _read(config_dir: Path, name: str) -> dict:
    """A data file. Your own tuning can live in ``configs/local/<name>.toml`` (git-ignored): it is laid over the shared file when the bot
    runs, so you never have uncommitted edits in the shared ones. Tests ignore it (they set COCOCAP_NO_LOCAL_CONFIG)."""
    path = config_dir / f"{name}.toml"
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
        local = config_dir / "local" / f"{name}.toml"
        if local.is_file() and not os.environ.get("COCOCAP_NO_LOCAL_CONFIG"):
            with local.open("rb") as f:
                data = _merge(data, tomllib.load(f))
        return data
    except FileNotFoundError:
        raise RegistryError(f"missing data file: {path}") from None
    except tomllib.TOMLDecodeError as e:
        raise RegistryError(f"{path.name}: {e}") from e


def _build(model, filename: str, entries: Iterable[tuple[str, dict]]) -> list:
    built = []
    for key, fields in entries:
        try:
            built.append(model(**fields))
        except ValidationError as e:
            problems = "; ".join(f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors())
            raise RegistryError(f"{filename}.toml [{key}]: {problems}") from e
    return built


class Registry:
    """Read-only lookup of every item, pet, enemy and rank."""

    def __init__(
        self,
        items: list[Item],
        pets: list[Pet],
        enemies: list[Enemy],
        ranks: list[Rank],
        enchants: list[Enchant] | None = None,
        mining: MiningRules | None = None,
        economy: EconomyRules | None = None,
        farming: FarmingRules | None = None,
        foraging: ForagingRules | None = None,
        fishing: FishingRules | None = None,
        combat: CombatRules | None = None,
        drop_tables: list[DropTable] | None = None,
        bestiary: BestiaryRules | None = None,
        mastery: MasteryRules | None = None,
        tools: ToolRules | None = None,
        shipments: ShipmentRules | None = None,
        scrolls: ScrollRules | None = None,
        recipes: list[Recipe] | None = None,
        areas: AreaRules | None = None,
    ):
        self.areas = areas
        self.items: dict[str, Item] = {i.id: i for i in items}
        self.pets: dict[str, Pet] = {p.id: p for p in pets}
        self.enemies: dict[str, Enemy] = {e.id: e for e in enemies}
        self.ranks: dict[int, Rank] = {r.rank_id: r for r in ranks}
        self.enchants: dict[str, Enchant] = {e.id: e for e in enchants or []}
        self.mining = mining
        self.economy = economy
        self.farming = farming
        self.foraging = foraging
        self.fishing = fishing
        self.combat = combat
        self.bestiary = bestiary
        self.mastery = mastery
        self.tools = tools
        self.shipments = shipments
        self.scrolls = scrolls
        self.recipes: dict[str, Recipe] = {r.id: r for r in recipes or []}
        self.drop_tables: dict[str, DropTable] = {t.id: t for t in drop_tables or []}
        self._validate()

    # --- lookups -------------------------------------------------------------------------
    def item(self, item_id: str) -> Item:
        try:
            return self.items[item_id]
        except KeyError:
            raise UnknownItem(item_id) from None

    def find_item(self, item_id: str) -> Item | None:
        return self.items.get(item_id)

    def items_for_skill(self, skill: Skill | None) -> list[Item]:
        return [i for i in self.items.values() if i.skill == skill]

    def shop_items(self) -> list[Item]:
        return [i for i in self.items.values() if i.buyable]

    def enchant(self, enchant_id: str) -> Enchant:
        try:
            return self.enchants[enchant_id]
        except KeyError:
            raise UnknownEnchant(enchant_id) from None

    def rank(self, rank_id: int) -> Rank:
        return self.ranks[rank_id]

    def next_rank(self, rank_id: int) -> Rank | None:
        return self.ranks.get(rank_id + 1)

    def recipe(self, recipe_id: str) -> Recipe:
        try:
            return self.recipes[recipe_id]
        except KeyError:
            raise UnknownItem(recipe_id) from None

    # --- validation ----------------------------------------------------------------------
    def _validate_recipes(self) -> list[str]:
        problems = []
        for r in self.recipes.values():
            out = self.items.get(r.output)
            if out is None:
                problems.append(f"recipes.toml [{r.id}]: unknown output item '{r.output}'")
            elif out.is_instance:
                problems.append(f"recipes.toml [{r.id}]: output '{r.output}' is a tool (tools are not crafted here)")
            problems += [f"recipes.toml [{r.id}]: unknown input item '{i}'" for i in r.inputs if i not in self.items]
            problems += [f"recipes.toml [{r.id}]: input '{i}' is a tool" for i in r.inputs if i in self.items and self.items[i].is_instance]
            if r.output in r.inputs:
                problems.append(f"recipes.toml [{r.id}]: consumes its own output '{r.output}'")
        return problems

    def _validate_areas(self, rules: AreaRules) -> list[str]:
        problems = []
        for area in rules.areas:
            problems += [f"areas.toml [{area.id}]: unknown fuel item '{i}'" for i in area.fuel if i not in self.items]
        for n, tier in enumerate(rules.ship_tiers, 1):
            problems += [f"areas.toml ship tier {n}: unknown part '{i}'" for i in tier.parts if i not in self.items]
            problems += [f"areas.toml ship tier {n}: unknown skill '{s}'" for s in tier.skill_floors if s not in ("mining", "fishing", "foraging", "farming")]
        return problems

    def _validate_mining(self, rules: MiningRules) -> list[str]:
        return _validate_mining_items(self, rules)

    def _validate(self) -> None:
        problems: list[str] = []
        for item in self.items.values():
            if item.crop:
                seed = self.items.get(item.crop.seed)
                if seed is None or seed.seed is None:
                    problems.append(f"{item.id}: crop.seed '{item.crop.seed}' is not a seed item")
                elif seed.seed.grows_into != item.id:
                    problems.append(f"{item.id}: seed '{seed.id}' grows into '{seed.seed.grows_into}'")
            if item.tool and item.tool.upgrade:
                up = item.tool.upgrade
                target = self.items.get(up.to)
                if target is None or target.tool is None or target.tool.kind != item.tool.kind:
                    problems.append(f"{item.id}: upgrade target '{up.to}' is not a {item.tool.kind}")
                elif target.tool.power <= item.tool.power:
                    problems.append(f"{item.id}: upgrade target '{up.to}' must be stronger")
                problems += [f"{item.id}: upgrade needs unknown item '{m}'" for m in up.items if m not in self.items]
            if item.tool and item.tool.fork:
                fork = item.tool.fork
                target = self.items.get(fork.to)
                if target is None or target.tool is None or target.tool.kind != item.tool.kind or target.tool.power <= item.tool.power:
                    problems.append(f"{item.id}: fork target '{fork.to}' must be a stronger {item.tool.kind}")
                if item.tool.upgrade is None:
                    problems.append(f"{item.id}: a fork needs a normal upgrade as the other path")
                problems += [f"{item.id}: fork needs unknown item '{m}'" for m in fork.items if m not in self.items]
            if item.scroll and item.scroll.enchant not in self.enchants:
                problems.append(f"{item.id}: scroll of unknown enchant '{item.scroll.enchant}'")
            if item.seed:
                crop = self.items.get(item.seed.grows_into)
                if crop is None or crop.crop is None:
                    problems.append(f"{item.id}: seed.grows_into '{item.seed.grows_into}' is not a crop")
        problems += self._validate_recipes()
        if self.scrolls is not None:
            for skill in ("mining", "foraging", "farming"):
                problems += [f"scrolls.toml [{skill}]: '{i}' is not a scroll item" for i in getattr(self.scrolls, skill).pool
                             if i not in self.items or self.items[i].category != "scroll"]
        if self.mining is not None:
            problems += self._validate_mining(self.mining)
        if self.fishing is not None:
            fish = [i for i in self.items.values() if i.skill == "fishing" and i.category == "fish" and i.drop]
            problems += [f"{i.id}: every fish needs a [size]" for i in fish if i.size is None]
            problems += [f"{i.id}: fish of rarity {self.fishing.reel.mystery_from_rarity}+ need a [reel] tell for their ❓"
                         for i in fish if i.rarity >= self.fishing.reel.mystery_from_rarity and i.reel is None]
            if not any(i.drop.rate == 1 for i in fish):
                problems.append("fishing: at least one fish needs drop rate 1 so every cast catches something")
            cb = self.fishing.community.book
            problems += [f"fishing.toml community book: '{f}' is not a fish" for f in cb.fish
                         if f not in self.items or self.items[f].category != "fish"]
            problems += [f"fishing.toml community book: no need for rarity {self.items[f].rarity}" for f in cb.fish
                         if f in self.items and (self.items[f].rarity not in cb.need_base or self.items[f].rarity not in cb.need_step)]
            for w in self.fishing.waters:
                problems += [f"fishing.toml water '{w.id}': '{f}' is not a fish" for f in w.fish
                             if f not in self.items or self.items[f].category != "fish"]
            if self.fishing.waters[0].min_level != 1:
                problems.append("fishing.toml: the first water must be open from level 1")
            levels = [w.min_level for w in self.fishing.waters]
            if levels != sorted(levels):
                problems.append("fishing.toml: waters must be listed shallowest first")
            pots = self.fishing.pots
            problems += [f"fishing.toml pots: unknown item '{i}'" for i in (*pots.craft_items, *(m for lv in pots.levels for m in lv.upgrade_items))
                         if i not in self.items]
            if pots.slot_levels != sorted(pots.slot_levels) or pots.slot_levels[0] < pots.min_level:
                problems.append("fishing.toml pots: slot_levels must be ascending and start at min_level")
            intervals = [lv.interval_minutes for lv in pots.levels]
            capacities = [lv.capacity for lv in pots.levels]
            if intervals != sorted(intervals, reverse=True) or capacities != sorted(capacities):
                problems.append("fishing.toml pots: each pot level must catch faster and hold more than the one before")
            if not any(i.bait for i in self.items.values()):
                problems.append("fishing.toml pots: there needs to be at least one bait item")
            problems += [f"fishing.toml boss: unknown loot item '{row.item}'" for row in self.fishing.boss.loot
                         if row.item not in self.items]
            problems += [f"fishing.toml treasure: unknown loot item '{row.item}'" for row in self.fishing.treasure.loot
                         if row.item not in self.items]
        if self.foraging is not None:
            problems += [f"foraging.toml rotate: unknown wedge item '{w.item}'" for w in self.foraging.rotate.wedges if w.item not in self.items]
        if self.foraging is not None:
            for sp in self.foraging.species:
                for d in sp.drops:
                    if d.item not in self.items:
                        problems.append(f"foraging.toml species '{sp.id}': unknown drop item '{d.item}'")
                    elif self.items[d.item].skill != "foraging":
                        problems.append(f"foraging.toml species '{sp.id}': drop '{d.item}' must be a foraging item")
        if self.areas is not None:
            problems += self._validate_areas(self.areas)
        if self.farming is not None and self.farming.deed_item not in self.items:
            problems.append(f"farming.toml: unknown deed item '{self.farming.deed_item}'")
        for table in self.drop_tables.values():
            problems += [f"drops.toml [{table.id}]: unknown item '{e.item}'" for e in table.entries if e.item and e.item not in self.items]
        for enemy in self.enemies.values():
            if enemy.drops and enemy.drops not in self.drop_tables:
                problems.append(f"enemies.toml [{enemy.id}]: unknown drop table '{enemy.drops}'")
        if self.combat is not None:
            problems += _validate_combat(self, self.combat)
        orb_ids = {i for i in self.items if i.startswith("key_orb_")}
        if set(self.economy.pets.orbs) != orb_ids:
            problems.append(f"economy.toml [pets.orbs] must have one odds table per orb item (ids starting key_orb_): {sorted(orb_ids)}")
        for orb_id, weights in self.economy.pets.orbs.items():
            if sum(weights.values()) <= 0 or any(w < 0 for w in weights.values()) or any(not 1 <= r <= 5 for r in weights):
                problems.append(f"economy.toml [pets.orbs.{orb_id}]: weights must be >= 0, add up to something, and be for rarities 1-5")
        for pet in self.pets.values():
            if pet.rarity not in self.economy.pets.xp_scale:
                problems.append(f"economy.toml [pets.xp_scale] has no scale for rarity {pet.rarity} ({pet.id})")
        expected = list(range(len(self.ranks)))
        if sorted(self.ranks) != expected:
            problems.append(f"ranks must be numbered 0..{len(self.ranks) - 1} without gaps")
        if problems:
            raise RegistryError("; ".join(problems))


def _validate_combat(reg: "Registry", rules: CombatRules) -> list[str]:
    problems = []
    for key, skill in rules.skills.items():
        if key != skill.id:
            problems.append(f"combat.toml skill '{key}' has id '{skill.id}'")
    for enemy in reg.enemies.values():
        every = [*enemy.skills, *(s for ph in enemy.phases for s in ph.skills or [])]
        problems += [f"enemies.toml [{enemy.id}]: unknown skill '{s}'" for s in every if s not in rules.skills]
    for kit, skills in rules.kits.items():
        if kit != "default" and (kit not in reg.items or reg.items[kit].tool is None or reg.items[kit].tool.kind != "sword"):
            problems.append(f"combat.toml kits: '{kit}' is not a sword")
        problems += [f"combat.toml kits.{kit}: unknown skill '{s}'" for s in skills if s not in rules.skills]
        if len(skills) > 5:
            problems.append(f"combat.toml kits.{kit}: at most 5 skills (they are one row of buttons)")
        if not skills or rules.skills.get(skills[0]) and rules.skills[skills[0]].cooldown:
            problems.append(f"combat.toml kits.{kit}: the first skill must have no cooldown")
    if "default" not in rules.kits:
        problems.append("combat.toml kits: a 'default' kit is needed")
    for enc in rules.encounters:
        problems += [f"combat.toml encounter '{enc.id}': unknown enemy '{e}'" for e in enc.enemies if e not in reg.enemies]
        if enc.key and (enc.key not in reg.items or reg.items[enc.key].category != "key_item"):
            problems.append(f"combat.toml encounter '{enc.id}': key '{enc.key}' is not a key_item")
    return problems


BOMB_ITEM = "tool_scarab_bomb"  # the consumable that clears a row (see services.mining.use_bomb)


def _validate_mining_items(reg: "Registry", rules: MiningRules) -> list[str]:
    problems = []

    def need(item_id: str, where: str) -> None:
        if item_id not in reg.items:
            problems.append(f"mining.toml {where}: unknown item '{item_id}'")

    for row, table in enumerate(rules.depth_tables):
        previous_rate = None
        for item_id in table:
            need(item_id, f"depth_tables[{row}]")
            item = reg.items.get(item_id)
            if item is None:
                continue
            if item.drop is None:
                problems.append(f"mining.toml depth_tables[{row}]: '{item_id}' has no drop table")
                continue
            if previous_rate is not None and item.drop.rate > previous_rate:
                problems.append(
                    f"mining.toml depth_tables[{row}]: '{item_id}' (1/{item.drop.rate}) must come "
                    f"before more common items (list rarest first)"
                )
            previous_rate = item.drop.rate
    in_tables = {i for table in rules.depth_tables for i in table}
    for t in rules.mine_types:
        for item_id in (*t.ore_boost, *t.ore_yield):
            need(item_id, f"mine type '{t.id}' ore_boost/ore_yield")
            if item_id in reg.items and item_id not in in_tables:
                problems.append(f"mining.toml mine type '{t.id}': '{item_id}' is in no depth table, so boosting it would do nothing")
    mini = rules.mini_wyrmhole
    for item_id in (*(i for r in mini.rows for i in r.pool), *mini.last_row_bonus, *rules.wyrmhole.pool, rules.wyrmhole.implosion_item, *rules.reactor.core_gems,
                    *rules.magnet.values, *(i for prize in rules.scarab.prizes for i in prize.items), BOMB_ITEM,
                    *rules.descent.hardness, *rules.descent.vault_ore):
        need(item_id, "item reference")
    return problems


STAR_MARKS = {2: "★★", 3: "★★★"}


def star_variants(items: list[Item], rules) -> list[Item]:
    """The 2- and 3-star versions of every starrable material: `<id>_s2`, `<id>_s3`. Own stacks, never in a drop pool (`drop` is None: stars are
    rolled by the star service when the base item drops), not sold in shops, sell price = base x the star multiplier."""
    by_id = {i.id: i for i in items}
    out = []
    for item_id in rules.starrable:
        base = by_id.get(item_id)
        if base is None:
            raise RegistryError(f"economy.toml [stars]: starrable item '{item_id}' does not exist")
        if base.category != "material" or base.tool or base.stars != 1:
            raise RegistryError(f"economy.toml [stars]: '{item_id}' must be a plain material")
        for stars in (2, 3):
            vid = f"{item_id}_s{stars}"
            if vid in by_id:
                raise RegistryError(f"economy.toml [stars]: '{vid}' already exists as an item")
            out.append(base.model_copy(update={
                "id": vid, "name": f"{base.name} {STAR_MARKS[stars]}", "stars": stars, "star_of": item_id, "drop": None, "price": 0,
                "sell_price": round(base.sell_price * rules.sell_multipliers[stars - 1]) if base.sell_price else 0,
                "wiki": f"{base.wiki} A {stars}-star version: same use, better quality, its own stack (it does not stack with the plain one).".strip(),
            }))
    return out


def load_registry(config_dir: Path = CONFIG_DIR) -> Registry:
    items = _build(Item, "items", ((k, {"id": k, **v}) for k, v in _read(config_dir, "items").items()))
    pets = _build(Pet, "pets", ((k, {"id": k, **v}) for k, v in _read(config_dir, "pets").items()))
    enemies = _build(Enemy, "enemies", ((k, {"id": k, **v}) for k, v in _read(config_dir, "enemies").items()))
    ranks = _build(Rank, "ranks", ((k, {"rank_id": int(k), **v}) for k, v in _read(config_dir, "ranks").items()))
    enchants = _build(Enchant, "enchants", ((k, {"id": k, **v}) for k, v in _read(config_dir, "enchants").items()))
    mining = _build(MiningRules, "mining", [("mining", _read(config_dir, "mining"))])[0]
    economy = _build(EconomyRules, "economy", [("economy", _read(config_dir, "economy"))])[0]
    items = items + star_variants(items, economy.stars)
    farming = _build(FarmingRules, "farming", [("farming", _read(config_dir, "farming"))])[0]
    foraging = _build(ForagingRules, "foraging", [("foraging", _read(config_dir, "foraging"))])[0]
    fishing = _build(FishingRules, "fishing", [("fishing", _read(config_dir, "fishing"))])[0]
    raw = _read(config_dir, "combat")
    raw["skills"] = {k: {"id": k, **v} for k, v in raw.get("skills", {}).items()}
    raw["encounters"] = [{"id": k, **v} for k, v in raw.get("encounters", {}).items()]
    combat = _build(CombatRules, "combat", [("combat", raw)])[0]
    drops = _build(DropTable, "drops", ((k, {"id": k, **v}) for k, v in _read(config_dir, "drops").items()))
    bestiary = _build(BestiaryRules, "bestiary", [("bestiary", _read(config_dir, "bestiary"))])[0]
    mastery = _build(MasteryRules, "mastery", [("mastery", _read(config_dir, "mastery"))])[0]
    tools = _build(ToolRules, "tools", [("tools", _read(config_dir, "tools"))])[0]
    shipments = _build(ShipmentRules, "shipments", [("shipments", _read(config_dir, "shipments"))])[0]
    scrolls = _build(ScrollRules, "scrolls", [("scrolls", _read(config_dir, "scrolls"))])[0]
    recipes = _build(Recipe, "recipes", ((k, {"id": k, **v}) for k, v in _read(config_dir, "recipes").items()))
    raw_areas = _read(config_dir, "areas")
    areas = _build(AreaRules, "areas", [("areas", {"areas": [{"id": k, **v} for k, v in raw_areas.get("area", {}).items()], "ship_tiers": raw_areas.get("ship_tier", []), "location_levels": raw_areas.get("locations", {}).get("min_levels", [])})])[0]
    return Registry(items, pets, enemies, ranks, enchants, mining, economy, farming, foraging, fishing, combat, drops, bestiary, mastery, tools, shipments, scrolls, recipes, areas)


@lru_cache(maxsize=1)
def get_registry() -> Registry:
    """The process-wide registry, loaded (and validated) on first use."""
    return load_registry()
