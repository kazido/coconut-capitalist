"""Load and cross-validate the game data in ``configs/*.toml``."""

import tomllib
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from .models import EconomyRules, Enchant, Enemy, FarmingRules, FishingRules, ForagingRules, Item, MiningRules, Pet, Rank, Skill

CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs"


class RegistryError(Exception):
    """The game data is invalid. The message names the file and entry."""


class UnknownItem(KeyError):
    pass


class UnknownEnchant(KeyError):
    pass


def _read(config_dir: Path, name: str) -> dict:
    path = config_dir / f"{name}.toml"
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
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
    ):
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

    # --- validation ----------------------------------------------------------------------
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
            if item.seed:
                crop = self.items.get(item.seed.grows_into)
                if crop is None or crop.crop is None:
                    problems.append(f"{item.id}: seed.grows_into '{item.seed.grows_into}' is not a crop")
        if self.mining is not None:
            problems += self._validate_mining(self.mining)
        if self.fishing is not None:
            fish = [i for i in self.items.values() if i.skill == "fishing" and i.category == "fish" and i.drop]
            problems += [f"{i.id}: every fish needs a [size]" for i in fish if i.size is None]
            if not any(i.drop.rate == 1 for i in fish):
                problems.append("fishing: at least one fish needs drop rate 1 so every cast catches something")
            cb = self.fishing.community.book
            problems += [f"fishing.toml community book: '{f}' is not a fish" for f in cb.fish
                         if f not in self.items or self.items[f].category != "fish"]
            problems += [f"fishing.toml community book: no need for rarity {self.items[f].rarity}" for f in cb.fish
                         if f in self.items and (self.items[f].rarity not in cb.need_base or self.items[f].rarity not in cb.need_step)]
            problems += [f"fishing.toml treasure: unknown loot item '{row.item}'" for row in self.fishing.treasure.loot
                         if row.item not in self.items]
        if self.farming is not None and self.farming.deed_item not in self.items:
            problems.append(f"farming.toml: unknown deed item '{self.farming.deed_item}'")
        expected = list(range(len(self.ranks)))
        if sorted(self.ranks) != expected:
            problems.append(f"ranks must be numbered 0..{len(self.ranks) - 1} without gaps")
        if problems:
            raise RegistryError("; ".join(problems))


BOMB_ITEM = "scarab_bomb"  # the consumable that clears a row (see services.mining.use_bomb)


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
    for item_id in (*rules.wyrmhole.pool, rules.wyrmhole.implosion_item, *rules.reactor.core_gems,
                    *rules.magnet.values, rules.scarab.reward_item, BOMB_ITEM,
                    *rules.descent.hardness, *rules.descent.vault_ore):
        need(item_id, "item reference")
    return problems


def load_registry(config_dir: Path = CONFIG_DIR) -> Registry:
    items = _build(Item, "items", ((k, {"id": k, **v}) for k, v in _read(config_dir, "items").items()))
    pets = _build(Pet, "pets", ((k, {"id": k, **v}) for k, v in _read(config_dir, "pets").items()))
    enemies = _build(Enemy, "enemies", ((k, {"id": k, **v}) for k, v in _read(config_dir, "enemies").items()))
    ranks = _build(Rank, "ranks", ((k, {"rank_id": int(k), **v}) for k, v in _read(config_dir, "ranks").items()))
    enchants = _build(Enchant, "enchants", ((k, {"id": k, **v}) for k, v in _read(config_dir, "enchants").items()))
    mining = _build(MiningRules, "mining", [("mining", _read(config_dir, "mining"))])[0]
    economy = _build(EconomyRules, "economy", [("economy", _read(config_dir, "economy"))])[0]
    farming = _build(FarmingRules, "farming", [("farming", _read(config_dir, "farming"))])[0]
    foraging = _build(ForagingRules, "foraging", [("foraging", _read(config_dir, "foraging"))])[0]
    fishing = _build(FishingRules, "fishing", [("fishing", _read(config_dir, "fishing"))])[0]
    return Registry(items, pets, enemies, ranks, enchants, mining, economy, farming, foraging, fishing)


@lru_cache(maxsize=1)
def get_registry() -> Registry:
    """The process-wide registry, loaded (and validated) on first use."""
    return load_registry()
