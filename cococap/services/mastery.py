"""Mastery: a small tree per skill. One point per `points_every_levels` skill levels, spent on nodes that bend how the skill plays.

Each branch is a line of nodes (each needs the one before it and a skill level); the branches are different playstyles with
trade-offs, so no one has them all. The nodes' effects are plain tool-style stats (see ``equipment.equipped_stats``), and nothing
here touches xp. A respec clears the tree for bits.
"""

from dataclasses import dataclass

from cococap.errors import GameRuleError
from cococap.registry import Registry, get_registry
from cococap.registry.models import MasteryBranch, MasteryNode, MasteryTree
from cococap.user import InsufficientFunds, User


class MasteryError(GameRuleError):
    """A rule was broken; the message is safe to show the player."""


def points_earned(level: int, registry: Registry | None = None) -> int:
    return level // (registry or get_registry()).mastery.points_every_levels


def points_spent(owned: list[str], registry: Registry | None = None) -> int:
    rules = (registry or get_registry()).mastery
    return sum(rules.node(n).cost for n in owned if _known(rules, n))


def _known(rules, node_id: str) -> bool:
    return any(n.id == node_id for t in rules.trees for b in t.branches for n in b.nodes)


def tree_for(skill: str, registry: Registry | None = None) -> MasteryTree | None:
    return (registry or get_registry()).mastery.tree(skill)


@dataclass(frozen=True)
class NodeState:
    node: MasteryNode
    owned: bool
    available: bool  # the next one in its branch, and you have the level and the points
    reason: str = ""  # why not (when it is the next one but you cannot buy it yet)


def branch_state(branch: MasteryBranch, owned: list[str], level: int, free: int) -> list[NodeState]:
    states, prior_owned = [], True
    for node in branch.nodes:
        have = node.id in owned
        reason = ""
        if not have and prior_owned:
            if level < node.level:
                reason = f"needs level {node.level}"
            elif free < node.cost:
                reason = f"needs {node.cost} points"
        states.append(NodeState(node, have, not have and prior_owned and not reason, reason if prior_owned else "locked"))
        prior_owned = have
    return states


def stats(owned: list[str], registry: Registry | None = None) -> dict[str, float]:
    """The summed effects of the nodes you own."""
    rules = (registry or get_registry()).mastery
    total: dict[str, float] = {}
    for node_id in owned:
        if _known(rules, node_id):
            for effect in rules.node(node_id).effects:
                total[effect.stat] = total.get(effect.stat, 0.0) + effect.amount
    return total


async def status(user: User, skill: str, registry: Registry | None = None) -> tuple[list[str], int, int]:
    """(nodes owned, skill level, points free)."""
    reg = registry or get_registry()
    data = await user.skill(skill)
    level = User.xp_to_level(data.xp)
    return list(data.mastery), level, points_earned(level, reg) - points_spent(data.mastery, reg)


async def buy(user: User, skill: str, node_id: str, registry: Registry | None = None) -> MasteryNode:
    reg = registry or get_registry()
    tree = tree_for(skill, reg)
    if tree is None:
        raise MasteryError("That skill has no Mastery tree yet.")
    found = next(((b, n) for b in tree.branches for n in b.nodes if n.id == node_id), None)
    if found is None:
        raise MasteryError("There is no such node.")
    branch, node = found
    outcome: dict = {}

    def write(data) -> None:
        level = User.xp_to_level(data.xp)
        free = points_earned(level, reg) - points_spent(data.mastery, reg)
        states = {s.node.id: s for s in branch_state(branch, data.mastery, level, free)}
        state = states[node_id]
        if state.owned:
            outcome["error"] = "You already have that."
        elif not state.available:
            outcome["error"] = f"You cannot take that yet: {state.reason}." if state.reason != "locked" else "Take the node before it first."
        else:
            data.mastery.append(node_id)

    await user.update_skill(skill, write)
    if "error" in outcome:
        raise MasteryError(outcome["error"])
    return node


async def respec(user: User, skill: str, registry: Registry | None = None) -> int:
    """Clear the tree for bits. Returns the points given back."""
    reg = registry or get_registry()
    owned = (await user.skill(skill)).mastery
    if not owned:
        raise MasteryError("You have nothing to take back.")
    given = points_spent(owned, reg)
    try:
        await user.remove_bits(reg.mastery.respec_bits)
    except InsufficientFunds:
        raise MasteryError(f"A respec costs {reg.mastery.respec_bits:,} bits.") from None
    await user.update_skill(skill, lambda data: data.mastery.clear())
    return given
