from enum import Enum
from dataclasses import dataclass
from typing import List

class Tier(str, Enum):
    BASE = "BASE"
    SILVER = "SILVER"
    GOLD = "GOLD"
    PLATINUM = "PLATINUM"

@dataclass(frozen=True)
class TierDefinition:
    name: Tier
    multiplier: float
    qualifying_threshold_points: int

# Tier definitions ordered from highest threshold to lowest
TIER_DEFINITIONS: List[TierDefinition] = [
    TierDefinition(name=Tier.PLATINUM, multiplier=2.0, qualifying_threshold_points=5000),
    TierDefinition(name=Tier.GOLD, multiplier=1.5, qualifying_threshold_points=1500),
    TierDefinition(name=Tier.SILVER, multiplier=1.25, qualifying_threshold_points=500),
    TierDefinition(name=Tier.BASE, multiplier=1.0, qualifying_threshold_points=0),
]

TIER_MAP = {t.name: t for t in TIER_DEFINITIONS}

def evaluate_tier(lifetime_points: int) -> Tier:
    """
    Evaluates tier based on cumulative lifetime points earned.
    Backward compatible: existing members qualify for PLATINUM only when lifetime >= 5000.
    """
    if lifetime_points < 0:
        return Tier.BASE
    
    for t_def in TIER_DEFINITIONS:
        if lifetime_points >= t_def.qualifying_threshold_points:
            return t_def.name
    return Tier.BASE

def get_tier_multiplier(tier: Tier) -> float:
    """Returns the points multiplier for a given tier."""
    if isinstance(tier, str):
        tier = Tier(tier)
    t_def = TIER_MAP.get(tier)
    if not t_def:
        return 1.0
    return t_def.multiplier

def next_tier_info(current_lifetime_points: int):
    """
    Returns progress information towards the next tier.
    """
    current_tier = evaluate_tier(current_lifetime_points)
    if current_tier == Tier.PLATINUM:
        return {
            "current_tier": Tier.PLATINUM.value,
            "next_tier": None,
            "points_needed": 0,
            "progress_percent": 100.0
        }
    
    if current_tier == Tier.BASE:
        target = TIER_MAP[Tier.SILVER]
        needed = max(0, target.qualifying_threshold_points - current_lifetime_points)
        progress = min(100.0, (current_lifetime_points / target.qualifying_threshold_points) * 100.0)
        return {
            "current_tier": Tier.BASE.value,
            "next_tier": Tier.SILVER.value,
            "points_needed": needed,
            "progress_percent": round(progress, 1)
        }
    elif current_tier == Tier.SILVER:
        target = TIER_MAP[Tier.GOLD]
        prev_threshold = TIER_MAP[Tier.SILVER].qualifying_threshold_points
        needed = max(0, target.qualifying_threshold_points - current_lifetime_points)
        range_points = target.qualifying_threshold_points - prev_threshold
        earned_in_range = current_lifetime_points - prev_threshold
        progress = min(100.0, (earned_in_range / range_points) * 100.0)
        return {
            "current_tier": Tier.SILVER.value,
            "next_tier": Tier.GOLD.value,
            "points_needed": needed,
            "progress_percent": round(progress, 1)
        }
    else: # GOLD
        target = TIER_MAP[Tier.PLATINUM]
        prev_threshold = TIER_MAP[Tier.GOLD].qualifying_threshold_points
        needed = max(0, target.qualifying_threshold_points - current_lifetime_points)
        range_points = target.qualifying_threshold_points - prev_threshold
        earned_in_range = current_lifetime_points - prev_threshold
        progress = min(100.0, (earned_in_range / range_points) * 100.0)
        return {
            "current_tier": Tier.GOLD.value,
            "next_tier": Tier.PLATINUM.value,
            "points_needed": needed,
            "progress_percent": round(progress, 1)
        }
