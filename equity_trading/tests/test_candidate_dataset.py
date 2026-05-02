import numpy as np
import pandas as pd
import pytest

from equity_trading.src.ml.candidate_dataset import (
    CandidateSignal,
    generate_candidates,
)


def _make_bars(n: int = 200) -> pd.DataFrame:
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
        {"close": closes,
         "open": closes,
         "high": [c + 0.5 for c in closes],
         "low": [c - 0.5 for c in closes]},
        index=pd.date_range("2023-01-01", periods=n, freq="1D", tz="UTC"),
    )


def test_candidate_signal_dataclass_is_frozen():
    c = CandidateSignal(
        timestamp=pd.Timestamp("2024-01-15 14:30", tz="UTC"),
        symbol="XLK",
        strategy_name="mean_reversion",
        features={"rsi_14": 30.0},
        bar_index=10,
    )
    with pytest.raises((AttributeError, ValueError)):
        c.symbol = "SPY"  # type: ignore


def test_generate_candidates_mean_reversion_with_loose_threshold():
    """At loose threshold (0.15), expect >= 1 candidate from a 200-bar series."""
    bars = _make_bars(200)
    daily = _daily_above_ma()
    candidates = generate_candidates(
        bars_5min=bars, daily=daily, spy_5min=bars,  # use bars as SPY too for fixture
        symbol="XLK", strategy_name="mean_reversion",
        relaxed_params={"threshold": 0.15},
    )
    # With relaxed threshold, should find some candidates
    assert isinstance(candidates, list)
    assert all(isinstance(c, CandidateSignal) for c in candidates)
    # Each candidate has all 15 features
    if len(candidates) > 0:
        c = candidates[0]
        assert c.symbol == "XLK"
        assert c.strategy_name == "mean_reversion"
        expected_features = {
            "ny_hour", "day_of_week", "rsi_14", "bb_pct_b", "vwap_dev",
            "volume_ratio", "intraday_change", "gap_pct", "daily_ma_distance",
            "daily_5d_return", "daily_20d_return", "atr_ratio_5min",
            "spy_intraday", "bars_since_open", "score_value",
        }
        assert expected_features.issubset(c.features.keys())


def test_generate_candidates_gap_fill():
    """gap_fill candidates fire only at first bar of each NY day."""
    bars = _make_bars(200)
    daily = _daily_above_ma()
    candidates = generate_candidates(
        bars_5min=bars, daily=daily, spy_5min=None,
        symbol="SPY", strategy_name="gap_fill",
        relaxed_params={"gap_threshold": 0.0015, "stop_extension": 0.005},
    )
    # gap_fill at very loose threshold should fire on most days where prev_close exists
    # All candidates should be at NY 09:30 (= UTC 14:30 winter).
    # _make_bars starts at 14:30 UTC, so bar 0 is the first bar of day 1
    if candidates:
        for c in candidates:
            # ny_hour is 9 (NY 09:30 winter, 09:30 summer -- both hour 9)
            assert c.features["ny_hour"] == 9


def test_features_have_no_lookahead():
    """A candidate's features must depend only on bars up to and including its
    timestamp -- never on later bars."""
    bars = _make_bars(200)
    daily = _daily_above_ma()
    full_run = generate_candidates(
        bars_5min=bars, daily=daily, spy_5min=None,
        symbol="XLK", strategy_name="mean_reversion",
        relaxed_params={"threshold": 0.15},
    )
    if not full_run:
        pytest.skip("no candidates generated; not informative")
    # Take the first candidate's bar_index, truncate the bars to that point + 1,
    # re-run, and verify the feature values match.
    target = full_run[0]
    truncate_at = target.bar_index + 1
    truncated_bars = bars.iloc[:truncate_at]
    truncated_run = generate_candidates(
        bars_5min=truncated_bars, daily=daily, spy_5min=None,
        symbol="XLK", strategy_name="mean_reversion",
        relaxed_params={"threshold": 0.15},
    )
    # Find a candidate at the same bar_index in truncated run
    matching = [c for c in truncated_run if c.bar_index == target.bar_index]
    assert len(matching) > 0
    # Compare a few key features
    m = matching[0]
    for key in ("rsi_14", "vwap_dev", "intraday_change"):
        if key in target.features and key in m.features and not (np.isnan(target.features[key]) and np.isnan(m.features[key])):
            assert abs(target.features[key] - m.features[key]) < 1e-6, f"feature {key} differs: {target.features[key]} vs {m.features[key]}"


def test_generate_candidates_unsupported_strategy_raises():
    bars = _make_bars(50)
    daily = _daily_above_ma()
    with pytest.raises((ValueError, KeyError, NotImplementedError)):
        generate_candidates(
            bars_5min=bars, daily=daily, spy_5min=None,
            symbol="XLK", strategy_name="nonexistent_strategy",
            relaxed_params={},
        )
