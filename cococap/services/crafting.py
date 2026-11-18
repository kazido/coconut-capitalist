"""The Workbench: make things from materials (configs/recipes.toml). No Discord here.

A craft takes the recipe's bits and items and gives the output in one go: if anything is short, nothing is taken.
"""

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


async def craftable_count(user: User, recipe: Recipe) -> int:
    """How many times you could craft it right now ("max"): limited by every input and the bits (0 if your level is too low)."""
    if await skill_level(user, recipe) < recipe.min_level:
        return 0
    await user.refresh()
    owned = await user.items()
    counts = [owned.get(item_id, 0) // need for item_id, need in recipe.inputs.items()]
    if recipe.bits:
        counts.append(user.purse // recipe.bits)
    return min(counts)


async def craft(user: User, recipe_id: str, times: int = 1, registry: Registry | None = None) -> Crafted:
    """Craft `times` of a recipe: bits and items are taken together and the output given, or nothing happens."""
    reg = registry or get_registry()
    recipe = find(recipe_id, reg)
    if times < 1:
        raise CraftError("Craft at least one.")
    level = await skill_level(user, recipe)
    if level < recipe.min_level:
        raise CraftError(f"{recipe.name} needs {recipe.skill} level {recipe.min_level} (you are level {level}).")
    bits = recipe.bits * times
    inputs = {item_id: need * times for item_id, need in recipe.inputs.items()}
    await payment.pay(user, bits, inputs, reg, CraftError)
    made = {recipe.output: recipe.quantity * times}
    try:
        await user.add_item(recipe.output, made[recipe.output])
    except Exception:
        await payment.refund(user, bits, inputs)
        raise
    return Crafted(recipe, times, made, bits)


