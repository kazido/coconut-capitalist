from cococap.item.item import Item

class Consumable(Item):
    def __init__(self, func: function) -> None:
        super().__init__()
        self.used: bool = False
        self.func: function = None
        
    def use(self):
        return self.func()