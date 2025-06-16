# Nodes are the heart of the game.
# A player will spend most of their time using the /explore command which will place them on a randomly generated map.
# The map will be littered with different nodes, each node being an opportunity for the player to participate in the different skills the bot has to offer.
# Nodes can be four difficulties, Tier I - IV
# The higher tiers are rarer, but have greater challenge and rewards.
# Each skill node has a base loot table, with the higher tiers adding special rewards to the loot table.

import random


class Node:
    """Base node, used to structure the tiered nodes. Should not be used directly."""

    def __init__(self):
        self.display_name: str
        self.description: str
        self.skill: str
        self.odds: int  # Odds of rolling this tier node when generated, out of 1,000. (5 = 0.5%, 600 = 60%)
        self.difficulty: int  # The difficulty of the node (used to scale up tree height, fish commands, monster hp, etc.)
        self.players: list

    def roll_table(self):
        return random.choices(self.loot_table.keys())

    def start(self):
        pass

    def update(self):
        pass

    def get_embed(self):
        pass


class Tier1Node(Node):
    def __init__(self):
        super().__init__()
