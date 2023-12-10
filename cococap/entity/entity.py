from utils import math

class Entity:
    def __init__(self) -> None:
        self._health: float
        self.dead: bool = False
        self.player: bool = False
        
    
        
    def setHealth(self, f: float):
        self._health = math.clamp(f, 0, )
        
    def getHealth(self):
        return self._health
    
    def die(self):
        self.dead = True
        if not self.player:
            