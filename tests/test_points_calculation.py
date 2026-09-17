import pytest
from src.domain.points import calculate_points_earned

def test_points_calculation_base_tier():
    # $10 spent at 1.0x multiplier = 10 points
    assert calculate_points_earned(10.0, 1.0) == 10
    # $10.99 spent at 1.0x = 10.99 -> floor is 10 points
    assert calculate_points_earned(10.99, 1.0) == 10

def test_points_calculation_silver_multiplier():
    # $20.00 spent at 1.25x = 25 points
    assert calculate_points_earned(20.0, 1.25) == 25
    # $15.50 spent at 1.25x = 19.375 -> floor is 19 points
    assert calculate_points_earned(15.50, 1.25) == 19

def test_points_calculation_gold_multiplier():
    # $50.00 spent at 1.5x = 75 points
    assert calculate_points_earned(50.0, 1.5) == 75
    # $10.33 spent at 1.5x = 15.495 -> floor is 15 points
    assert calculate_points_earned(10.33, 1.5) == 15

def test_points_calculation_invalid_input():
    with pytest.raises(ValueError):
        calculate_points_earned(0, 1.0)
    with pytest.raises(ValueError):
        calculate_points_earned(-10.0, 1.0)
    with pytest.raises(ValueError):
        calculate_points_earned(10.0, 0)
