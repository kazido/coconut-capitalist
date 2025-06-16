from nodes import Node
from enum import Enum


class Emojis(Enum):
    # Used when creating mining embeds
    SELECTED_COLUMN = ":small_red_triangle_down:"
    NOTCH = ":black_small_square:"
    CELL = "<:cell:1280658009306959893>"
    CELL_EMPTY = "<:cell_empty:1280658029703860244>"
    WYRMHOLE = "<a:wyrmhole:1280656910290260038>"
    
class ReactorSlots(Enum):
    # Used to place gems into reactor for boosts
    SLOT1 = "core_slot1"
    SLOT2 = "core_slot2"
    SLOT3 = "core_slot3"
    SLOT4 = "core_slot4"


class Mineshaft:
    # A logical mineshaft with depths and loot tables
    # Each level's loot table contains item_ids. Must manually verify that item_ids are valid.
    # To verify that item_ids are valid, look under 
    LEVEL1 = ["copper_ore"]
    LEVEL2 = ["iron_ore"].extend(LEVEL1)
    LEVEL3 = ["gold_ore", "dusty_dandelion.seed"].extend(LEVEL2)
    LEVEL4 = ["sanity", "rage", "peace", "balance"].extend(LEVEL3)
    LEVEL5 = ["spirit_of_the_mines"].extend(LEVEL4)

    depths = [LEVEL1, LEVEL2, LEVEL3, LEVEL4, LEVEL5]

    def __init__(self) -> None:
        self.cols = []  # columns that hold 5 nodes each
        self._generate_columns()

    def _generate_columns(self):
        for _ in range(len(self.depths)):
            # for each row, generate a column and add it to the list
            for level in range(self.depths):
                node = self._create_node(depth=self.depths[level])
                self.cols.append(node)

    def _create_node(self, depth: list):
        # creates a node with loot based on the passed level
        for item_id in depth:
            item = fetch(item_id)
            quantity = roll_item(item)
            if quantity:
                return item, quantity
        # if nothing was rolled, return no item and no quantity
        return None, 0

class MiningNode(Node):
    