"""The Workbench: make things from materials (configs/recipes.toml). No Discord here.

A craft takes the recipe's bits and items and gives the output in one go: if anything is short, nothing is taken.
"""

from collections import Counter
from dataclasses import dataclass

from cococap.errors import GameRuleError
from cococap.registry import Recipe, Registry, get_registry
from cococap.services import payment
from cococap.user import User


class CraftError(GameRuleError):
    """A rule was broken; the message is safe to show the player."""


@dataclass(frozen=True)
class Crafted:
    recipe: Recipe
    times: int
    items: dict[str, int]  # what was made
    bits: int  # the bits it cost


def recipes(registry: Registry | None = None) -> list[Recipe]:
    return list((registry or get_registry()).recipes.values())


def find(recipe_id: str, registry: Registry | None = None) -> Recipe:
    recipe = (registry or get_registry()).recipes.get(recipe_id)
    if recipe is None:
        raise CraftError("There is no such recipe.")
    return recipe


async def skill_level(user: User, recipe: Recipe) -> int:
    return User.xp_to_level((await user.skill(recipe.skill)).xp) if recipe.skill else 0


MAX_DEPTH = 8  # how many recipes deep auto-craft will go (the chain is Twilight -> ... -> Void: 6)


def plan(reg: Registry, recipe: Recipe, times: int, owned: dict[str, int], auto: bool) -> tuple[int, dict[str, int]]:
    """(bits, items to pay) for `times` crafts. With `auto`, an input you are short of that has its own recipe (no level needed)
    is made from ITS inputs too, and what you already hold is used first. Short items stay in the total so `pay` can name them."""
    held, need, bits = dict(owned), Counter(), recipe.bits * times

    def want(item_id: str, qty: int, depth: int) -> None:
        nonlocal bits
        take = min(held.get(item_id, 0), qty)
        held[item_id] = held.get(item_id, 0) - take
        need[item_id] += take
        short = qty - take
        sub = next((r for r in reg.recipes.values() if r.output == item_id and not r.min_level), None) if auto and short and depth < MAX_DEPTH else None
        if sub is None:
            need[item_id] += short
            return
        n = -(-short // sub.quantity)
        bits += sub.bits * n
        for i, q in sub.inputs.items():
            want(i, q * n, depth + 1)

    for item_id, q in recipe.inputs.items():
        want(item_id, q * times, 0)
    return bits, {k: v for k, v in need.items() if v}


def _affordable(reg: Registry, recipe: Recipe, times: int, owned: dict[str, int], purse: int, auto: bool) -> bool:
    bits, need = plan(reg, recipe, times, owned, auto)
    return bits <= purse and all(owned.get(i, 0) >= q for i, q in need.items())


async def craftable_count(user: User, recipe: Recipe, auto: bool | None = None) -> int:
    """How many times you could craft it right now ("max"): limited by every input and the bits (0 if your level is too low)."""
    if await skill_level(user, recipe) < recipe.min_level:
        return 0
    await user.refresh()
    owned, reg = await user.items(), get_registry()
    auto = user.settings.auto_craft if auto is None else auto
    if not auto:
        counts = [owned.get(item_id, 0) // need for item_id, need in recipe.inputs.items()]
        if recipe.bits:
            counts.append(user.purse // recipe.bits)
        return min(counts)
    lo, hi = 0, 1
    while hi <= 100_000 and _affordable(reg, recipe, hi, owned, user.purse, True):
        lo, hi = hi, hi * 2
    while hi - lo > 1:  # lo is affordable, hi is not (or the cap)
        mid = (lo + hi) // 2
        lo, hi = (mid, hi) if _affordable(reg, recipe, mid, owned, user.purse, True) else (lo, mid)
    return lo


async def craft(user: User, recipe_id: str, times: int = 1, registry: Registry | None = None, auto: bool | None = None) -> Crafted:
    """Craft `times` of a recipe: bits and items are taken together and the output given, or nothing happens.
    `auto` (default: the player's Settings choice) also makes missing craftable inputs, all paid in the same single step."""
    reg = registry or get_registry()
    recipe = find(recipe_id, reg)
    if times < 1:
        raise CraftError("Craft at least one.")
    level = await skill_level(user, recipe)
    if level < recipe.min_level:
        raise CraftError(f"{recipe.name} needs {recipe.skill} level {recipe.min_level} (you are level {level}).")
    await user.refresh()
    bits, inputs = plan(reg, recipe, times, await user.items(), user.settings.auto_craft if auto is None else auto)
    await payment.pay(user, bits, inputs, reg, CraftError)
    made = {recipe.output: recipe.quantity * times}
    try:
        await user.add_item(recipe.output, made[recipe.output])
    except Exception:
        await payment.refund(user, bits, inputs)
        raise
    from cococap.services import smithing  # (here to avoid an import cycle)
    await smithing.add_smithing_xp(user, reg.smithing.levels.xp_per_craft * times)
    return Crafted(recipe, times, made, bits)


