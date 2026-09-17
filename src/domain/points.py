import math

def calculate_points_earned(amount_spent: float, multiplier: float) -> int:
    """
    Calculates points earned for a purchase amount given the active tier multiplier.
    Rounding rule: floor (round down to nearest whole point).
    E.g. $10.50 spent at 1.25x multiplier = 13.125 -> 13 points.
    """
    if amount_spent <= 0:
        raise ValueError("Amount spent must be greater than zero.")
    if multiplier <= 0:
        raise ValueError("Multiplier must be greater than zero.")
    
    raw_points = amount_spent * multiplier
    return math.floor(raw_points)
