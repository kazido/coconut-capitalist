"""One-time reset of OLD upgrade-chain tools into smithed tools (plan: docs/plans/tools-smithing.md).

Every player gets this once: old tools (no parts) are deleted, each tool kind the player had upgraded comes back as a set of
parts (configs/smithing.toml [[legacy_grant]]), enchants come back as scrolls, and the four starters come back as free
smithed tier-1 tools. The `legacy_tools_reset` stat makes it run only once.
"""

import random
from dataclasses import dataclass

from cococap.constants import STARTER_TOOLS
from cococap.models.instance import ItemInstance
from cococap.registry import Registry, get_registry
from cococap.services.equipment import EquipmentError, equip, skill_for_tool
from cococap.services.smithing import PART_TYPES, _rules
from cococap.user import User

RESET_STAT = "legacy_tools_reset"
# How far a tool got on its kind's chain. Higher wins when a player owns several old tools of one kind.
_STEP_RANK = {None: 0, "starter": 0, "plain": 1, "fork": 2, "fork_up": 3}


@dataclass(frozen=True)
class LegacyReset:
    kinds: tuple[str, ...]  # tool kinds that had old tools
    parts_given: int
    scrolls_given: int


def _chain(reg: Registry, starter: str) -> dict[str, str]:
    """Every tool on this starter's upgrade chain -> its step. A plain upgrade is 'plain', the first fork tool is 'fork',
    and any upgrade after a fork is 'fork_up'. Walks the `upgrade` and `fork` links from the data, never by id."""
    steps: dict[str, str] = {starter: "starter"}
    todo = [(starter, False)]  # (template, is it on a fork branch)
    while todo:
        tid, forked = todo.pop()
        tool = reg.item(tid).tool
        if tool is None:
            continue
        edges = []
        if tool.upgrade:
            edges.append((tool.upgrade.to, False))
        if tool.fork:
            edges.append((tool.fork.to, True))
        for target, is_fork in edges:
            if target in steps:
                continue
            step = "fork" if is_fork else ("fork_up" if forked else "plain")
            steps[target] = step
            todo.append((target, is_fork or forked))
    return steps


def _scroll_for(reg: Registry, enchant: str) -> str | None:
    return next((i.id for i in reg.items.values() if i.scroll and i.scroll.enchant == enchant), None)


async def give_starter_tool(user: User, item_id: str, registry: Registry | None = None) -> ItemInstance:
    """A free starter, made by the game as a smithed tier-1 tool: three tier-1 parts, Crude quality, no traits."""
    reg = registry or get_registry()
    rules = _rules(reg)
    parts = {slot: {"tier": 1, "trait": None} for slot in PART_TYPES}
    return await user.give_instance(item_id, parts=parts, quality=rules.grades[0].name)


async def reset_player(user: User, rng: random.Random, registry: Registry | None = None) -> LegacyReset | None:
    """Run the one-time reset for this player. Returns None if it already ran (and changes nothing)."""
    if await user.get_stat(RESET_STAT):
        return None
    reg = registry or get_registry()
    rules = _rules(reg)
    chains = {reg.item(s).tool.kind: _chain(reg, s) for s in STARTER_TOOLS}
    rows = {g.step: g for g in rules.legacy_grants}

    old: list[ItemInstance] = []
    best: dict[str, str | None] = {}  # kind -> the best step reached on that kind's chain
    scrolls_given = 0
    for inst in await user.instances():
        item = reg.find_item(inst.template_id)
        if item is None or item.tool is None or inst.parts:
            continue
        kind = item.tool.kind
        old.append(inst)
        step = chains.get(kind, {}).get(inst.template_id)
        if kind not in best or _STEP_RANK[step] > _STEP_RANK[best[kind]]:
            best[kind] = step
        for enchant, level in inst.enchants.items():
            scroll = _scroll_for(reg, enchant)
            if scroll and level > 0:
                await user.add_item(scroll, level)
                scrolls_given += level

    # Old tools go first: deleting one also clears any skill that had it equipped.
    for inst in old:
        kind = reg.item(inst.template_id).tool.kind
        skill = skill_for_tool(kind)
        if skill and (await user.skill(skill)).equipped_instance_id == inst.id:
            await user.equip(skill, None)
        await user.delete_instance(inst.id)

    parts_given = 0
    for kind, step in best.items():
        row = rows.get(step)
        if row is None:  # a starter, or a tool that is not on any chain: nothing to give back
            continue
        pool = [t.id for t in rules.traits_for(kind)]
        for slot in PART_TYPES:
            traits = rng.sample(pool, min(row.traits, len(pool)))
            await user.give_instance(f"part_{slot}", rolled={"tier": row.tier}, traits=traits)
            parts_given += 1

    # Starters: one for each kind the player has no tool of now (smithed ones count as a tool).
    have = {reg.item(i.template_id).tool.kind for i in await user.instances() if reg.find_item(i.template_id) and reg.item(i.template_id).tool}
    for starter in STARTER_TOOLS:
        kind = reg.item(starter).tool.kind
        if kind in have:
            continue
        made = await give_starter_tool(user, starter, reg)
        await user.set_stat(f"starter_claimed_{starter}", 1)
        skill = skill_for_tool(kind)
        if skill and await user.equipped_instance(skill) is None:
            try:
                await equip(user, skill, made.id, reg)
            except EquipmentError:
                pass  # e.g. a level requirement: they can equip it later

    await user.set_stat(RESET_STAT, 1)
    return LegacyReset(
        kinds=tuple(sorted({reg.item(i.template_id).tool.kind for i in old})),
        parts_given=parts_given,
        scrolls_given=scrolls_given,
    )
