import numpy as np
import pandas as pd
from unittest.mock import MagicMock

from equity_trading.src.ml.ml_filter_strategy import MLFilterStrategy
from equity_trading.src.strategy.strategies.mean_reversion import MeanReversionStrategy


def _make_bars(n: int = 100) -> pd.DataFrame:
    np.random.seed(42)
    closes = 100.0 + np.cumsum(np.random.randn(n) * 0.1)
    return pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes,
         "volume": np.random.randint(5000, 20000, n).astype(float)},
        index=pd.date_range("2024-01-15 14:30", periods=n, freq="5min", tz="UTC"),
    )


def _daily_above_ma(n: int = 250) -> pd.DataFrame:
    closes = list(np.linspace(80, 120, n))
    return pd.DataFrame(
        {"close": closes, "open": closes,
         "high": [c + 0.5 for c in closes], "low": [c - 0.5 for c in closes]},
        index=pd.date_range("2023-01-01", periods=n, freq="1D", tz="UTC"),
    )


def test_ml_filter_strategy_passes_all_when_model_says_high_prob():
    """Mock model returning p=0.9 for all → no filtering."""
    base = MeanReversionStrategy()
    bars = _make_bars()
    daily = _daily_above_ma()
    # Use consistent params for both raw and filtered
    params = {"threshold": 0.05}
    raw = base.compute_entry_signal(bars, daily, 0.10, params)
    if not raw.any():
        # Make a more permissive synthetic signal by lowering threshold further
        params = {"threshold": 0.0}
        raw = base.compute_entry_signal(bars, daily, 0.10, params)
    assert raw.any(), "fixture must produce at least one base signal"

    model = MagicMock()
    model.predict_proba = MagicMock(side_effect=lambda X: np.column_stack([
        np.full(len(X), 0.1), np.full(len(X), 0.9),
    ]))

    wrapper = MLFilterStrategy(
        base=base, model=model,
        feature_names=["score_value", "rsi_14", "ny_hour"],
        prob_threshold=0.5,
    )
    filtered = wrapper.compute_entry_signal(bars, daily, 0.10, params)
    # All True bars from raw should still be True
    assert filtered.sum() == raw.sum()


def test_ml_filter_strategy_blocks_all_when_model_says_low_prob():
    """Mock model returning p=0.1 for all → all signals blocked."""
    base = MeanReversionStrategy()
    bars = _make_bars()
    daily = _daily_above_ma()
    raw = base.compute_entry_signal(bars, daily, 0.10, {"threshold": 0.0})
    assert raw.any()

    model = MagicMock()
    model.predict_proba = MagicMock(side_effect=lambda X: np.column_stack([
        np.full(len(X), 0.9), np.full(len(X), 0.1),
    ]))

    wrapper = MLFilterStrategy(
        base=base, model=model,
        feature_names=["score_value", "rsi_14", "ny_hour"],
        prob_threshold=0.5,
    )
    filtered = wrapper.compute_entry_signal(bars, daily, 0.10, {"threshold": 0.0})
    assert filtered.sum() == 0


def test_ml_filter_strategy_threshold_partial():
    """Half the signals get p=0.7, half get p=0.3 → at threshold 0.5, half pass."""
    base = MeanReversionStrategy()
    bars = _make_bars()
    daily = _daily_above_ma()
    raw = base.compute_entry_signal(bars, daily, 0.10, {"threshold": 0.0})
    n_raw = int(raw.sum())
    if n_raw < 2:
        import pytest
        pytest.skip(f"need ≥2 base signals, got {n_raw}")

    def fake_predict_proba(X):
        n = len(X)
        probs = np.array([0.7 if i % 2 == 0 else 0.3 for i in range(n)])
        return np.column_stack([1 - probs, probs])

    model = MagicMock()
    model.predict_proba = MagicMock(side_effect=fake_predict_proba)

    wrapper = MLFilterStrategy(
        base=base, model=model,
        feature_names=["score_value", "rsi_14", "ny_hour"],
        prob_threshold=0.5,
    )
    filtered = wrapper.compute_entry_signal(bars, daily, 0.10, {"threshold": 0.0})
    # Half pass (the even-indexed ones get p=0.7)
    expected = (n_raw + 1) // 2  # ceil(n/2)
    assert filtered.sum() == expected


def test_ml_filter_strategy_compute_exit_levels_delegates_to_base():
    """compute_exit_levels passes through unchanged."""
    base = MeanReversionStrategy()
    bars = _make_bars()
    model = MagicMock()
    wrapper = MLFilterStrategy(
        base=base, model=model,
        feature_names=["score_value"], prob_threshold=0.5,
    )
    # Default ATR-scaled exits
    stop, target = wrapper.compute_exit_levels(
        bars_5min=bars, entry_idx=10, entry_price=100.0,
        atr_pct=0.10, params={"stop_multiplier": 1.5, "target_multiplier": 2.4},
    )
    # Same as base: 100 * 0.9985 = 99.85, 100 * 1.0024 = 100.24
    assert abs(stop - 99.85) < 1e-6
    assert abs(target - 100.24) < 1e-6


def test_ml_filter_strategy_no_base_signals_returns_all_false():
    """If base produces no signals, no model calls and return all False."""
    base = MeanReversionStrategy()
    bars = _make_bars()
    daily = _daily_above_ma()
    # High threshold → no signals
    model = MagicMock()
    wrapper = MLFilterStrategy(
        base=base, model=model,
        feature_names=["score_value"], prob_threshold=0.5,
    )
    filtered = wrapper.compute_entry_signal(bars, daily, 0.10, {"threshold": 0.99})
    assert filtered.sum() == 0
    model.predict_proba.assert_not_called()


def test_ml_filter_strategy_name():
    base = MeanReversionStrategy()
    model = MagicMock()
    wrapper = MLFilterStrategy(base=base, model=model, feature_names=["score_value"])
    assert wrapper.name == "ml_filtered_mean_reversion"
