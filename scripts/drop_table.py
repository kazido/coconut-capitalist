"""Every item that can drop, in one table: where to edit its drop rate and what it is worth.

    .venv/Scripts/python.exe -m scripts.drop_table              # all skills, sorted by skill then rarity then rate
    .venv/Scripts/python.exe -m scripts.drop_table mining       # one skill
    .venv/Scripts/python.exe -m scripts.drop_table --csv > drops.csv   # for a spreadsheet

The numbers come from `configs/items.toml`: each item's `[<id>.drop]` table (`rate` = 1 in this many drop rolls, `min`/`max` = how many
you get) plus its `rarity` and `sell_price`. Edit them THERE. The columns "worth/roll" (value of one roll: price x average amount / rate) and
"rolls/find" are for comparing items at a glance. Other places that decide what you find (they are not in this table):
  - which items a mine row can hold: `tables` under `[[mines]]` in `configs/mining.toml`
  - which fish bite in each water: `[waters.fish]` in `configs/fishing.toml`, boss and chest loot in `fishing.toml`
  - the old enemy drop tables: `configs/drops.toml`
  - scroll rates: `configs/scrolls.toml`
"""

import sys

from cococap.registry import get_registry


def rows(skill: str | None) -> list[dict]:
    reg = get_registry()
    out = []
    for item in reg.items.values():
        if item.drop is None or (skill and item.skill != skill):
            continue
        average = (item.drop.min + item.drop.max) / 2
        out.append({
            "id": item.id, "skill": item.skill or "-", "rarity": item.rarity, "rate": item.drop.rate, "min": item.drop.min, "max": item.drop.max,
            "price": item.sell_price, "worth_per_roll": item.sell_price * average / item.drop.rate,
        })
    return sorted(out, key=lambda r: (r["skill"], r["rarity"], r["rate"], r["id"]))


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    table = rows(args[0] if args else None)
    columns = ["id", "skill", "rarity", "rate", "min", "max", "price", "worth_per_roll"]
    if "--csv" in sys.argv:
        print(",".join(columns))
        for r in table:
            print(",".join(f"{r[c]:.2f}" if isinstance(r[c], float) else str(r[c]) for c in columns))
        return
    print(f"{'item':<32}{'skill':<10}{'rar':>4}{'1 in':>9}{'amount':>9}{'sells':>10}{'worth/roll':>12}")
    for r in table:
        print(f"{r['id']:<32}{r['skill']:<10}{r['rarity']:>4}{r['rate']:>9,}{str(r['min']) + '-' + str(r['max']):>9}{r['price']:>10,}{r['worth_per_roll']:>12.1f}")


if __name__ == "__main__":
    main()
