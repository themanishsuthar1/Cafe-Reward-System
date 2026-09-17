from src.domain.tier import Tier, evaluate_tier, get_tier_multiplier, next_tier_info

def test_tier_evaluation_base():
    assert evaluate_tier(0) == Tier.BASE
    assert evaluate_tier(499) == Tier.BASE
    assert get_tier_multiplier(Tier.BASE) == 1.0

def test_tier_evaluation_silver_boundary():
    # Exactly at threshold 500
    assert evaluate_tier(500) == Tier.SILVER
    assert evaluate_tier(1499) == Tier.SILVER
    assert get_tier_multiplier(Tier.SILVER) == 1.25

def test_tier_evaluation_gold_boundary():
    # Exactly at threshold 1500
    assert evaluate_tier(1500) == Tier.GOLD
    assert evaluate_tier(4999) == Tier.GOLD
    assert evaluate_tier(5000) == Tier.PLATINUM
    assert evaluate_tier(10000) == Tier.PLATINUM
    assert get_tier_multiplier(Tier.GOLD) == 1.5
    assert get_tier_multiplier(Tier.PLATINUM) == 2.0

def test_next_tier_info():
    base_info = next_tier_info(250)
    assert base_info["current_tier"] == Tier.BASE
    assert base_info["next_tier"] == Tier.SILVER
    assert base_info["points_needed"] == 250
    assert base_info["progress_percent"] == 50.0

    silver_info = next_tier_info(1000)
    assert silver_info["current_tier"] == Tier.SILVER
    assert silver_info["next_tier"] == Tier.GOLD
    assert silver_info["points_needed"] == 500
    assert silver_info["progress_percent"] == 50.0

    gold_info = next_tier_info(2000)
    assert gold_info["current_tier"] == Tier.GOLD
    assert gold_info["next_tier"] == Tier.PLATINUM
    assert gold_info["points_needed"] == 3000

    plat_info = next_tier_info(6000)
    assert plat_info["current_tier"] == Tier.PLATINUM
    assert plat_info["next_tier"] is None
    assert plat_info["points_needed"] == 0

