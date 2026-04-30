
from src.portfolio.rebalancer import Rebalancer

def test_rebalancer_calculates_weights():
    performance = {
        "ma_macd": {"return": 0.15, "sharpe": 1.2},
        "ma_cross": {"return": 0.20, "sharpe": 1.5},
        "dow_theory": {"return": 0.05, "sharpe": 0.8},
    }
    reb = Rebalancer()
    weights = reb.calculate_weights(performance)
    assert abs(sum(weights.values()) - 1.0) < 0.01
    assert weights["ma_cross"] > weights["dow_theory"]  # Better performance gets more weight

def test_rebalancer_skips_broken_strategies():
    performance = {
        "ma_macd": {"return": 0.15, "sharpe": 1.2},
        "broken": {"return": -0.30, "sharpe": -0.5},
    }
    reb = Rebalancer(min_sharpe=0.0)
    weights = reb.calculate_weights(performance)
    assert "broken" not in weights or weights["broken"] == 0.0
