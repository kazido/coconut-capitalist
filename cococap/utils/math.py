import math

def clamp(val, mn, mx):
    return mn if val < mn else min(val, mx)