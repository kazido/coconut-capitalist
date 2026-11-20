"""Turn a player's inventory into display lines. Pure functions of data, no Discord."""

from cococap import emojis
from cococap.models.instance import ItemInstance
from cococap.registry import get_registry
from cococap.services import smithing

PER_PAGE = 15


def _stack_rows(items: dict[str, int], filter: str | None = None) -> list[tuple]:
    """(sort name, key "item:<id>", line) per stack. Ids missing from the registry are still listed, never crash."""
    reg = get_registry()
    needle = filter.lower() if filter else None
    rows = []
    for item_id, quantity in items.items():
        if quantity <= 0:
            continue
        item = reg.find_item(item_id)
        if item is None:
            if needle is None or needle in item_id.lower():
                rows.append((item_id, f"item:{item_id}", f"{emojis.icon('unknown', '❔')} {quantity:,} {item_id} *(unknown item)*"))
            continue
        if needle and not any(
            needle in field for field in (item.name.lower(), item.id, item.skill or "", item.category)
        ):
            continue
        line = f"{item.emoji or emojis.icon('pip', '▫️')} {quantity:,} {item.name}"
        rows.append((item.name.lower(), f"item:{item.id}", line))
    return sorted(rows)


def inventory_lines(items: dict[str, int], filter: str | None = None) -> list[str]:
    """One display line per stack in `items` ({item_id: quantity}), sorted by item name.

    `filter` matches (case-insensitively) an item's name, id, skill or category.
    """
    return [line for _, _, line in _stack_rows(items, filter)]


def instance_label(instance: ItemInstance) -> str:
    """e.g. "Starter Axe [Soloist]". (You own one tool of each kind, so there is nothing to tell apart by number.)"""
    reg = get_registry()
    template = reg.item(instance.template_id)
    enchants = ", ".join(
        f"{reg.enchants[e].name if e in reg.enchants else e}"
        + (f" {lvl}" if lvl > 1 else "")
        for e, lvl in sorted(instance.enchants.items())
    )
    return template.name + (f" [{enchants}]" if enchants else "")


def instance_lines(instances: list[ItemInstance], equipped_ids: set[int], filter: str | None = None) -> list[str]:
    reg = get_registry()
    needle = filter.lower() if filter else None
    rows = []
    for inst in instances:
        template = reg.find_item(inst.template_id)
        if template is None:
            continue
        label = instance_label(inst)
        if needle and not any(
            needle in field for field in (label.lower(), template.id, template.skill or "", "tool")
        ):
            continue
        mark = f" {emojis.icon('check', '✅')}" if inst.id in equipped_ids else ""
        rows.append((label.lower(), f"{template.emoji or emojis.icon('sword', '🗡️')} {label}{mark}"))
    return [line for _, line in sorted(rows)]




def _part_rows(instances: list[ItemInstance]) -> list[tuple]:
    reg = get_registry()
    rows = []
    for inst in instances:
        if not inst.template_id.startswith("part_") or reg.find_item(inst.template_id) is None:
            continue
        tier = int(inst.rolled.get("tier", 1))
        traits = smithing.trait_icons(inst.traits, reg.smithing)
        label = smithing.part_label(inst.template_id.removeprefix("part_"), tier, bool(inst.rolled.get("restricted")))
        slot = inst.template_id.removeprefix("part_")
        icon = emojis.for_id("item", f"part_{slot}_t{tier}", reg.item(inst.template_id).emoji) or "🧩"
        rows.append(((inst.template_id, -tier), f"part:{inst.id}", f"{icon} {label} {traits}"))
    return sorted(rows)


def part_lines(instances: list[ItemInstance]) -> list[str]:
    """Smithing parts (unique instances: base, trim, accent) as inventory lines, e.g. "Base Part (T2) 💪"."""
    return [line for _, _, line in _part_rows(instances)]


def inventory_entries(items: dict[str, int], instances: list[ItemInstance]) -> list[tuple[str, str]]:
    """(key, line) for everything the Inventory page lists, in page order: stacks ("item:<id>"), then parts ("part:<instance id>")."""
    return [(key, line) for _, key, line in _stack_rows(items)] + [(key, line) for _, key, line in _part_rows(instances)]
