from random import randint

def double_chop():
    """Axe has a 10% chance to swing twice."""
    roll = randint(1, 10)
    if roll == 1:
        return True
    return False