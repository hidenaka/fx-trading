import numpy as np
import pandas as pd

from equity_trading.src.phase0.signal_simulator import (
    sweep_thresholds,
    simulate_one_threshold,
)


def _make_bars_with_clear_dip(n: int = 200) -> pd.DataFrame:
    """中盤に明確な「過売り→反発」がある合成データ."""
    np.random.seed(42)
    closes = []
    base = 100.0
    for i in range(n):
        if 80 <= i < 100:
            base -= 0.05
        elif 100 <= i < 120:
            base += 0.05
        closes.append(base + np.random.randn() * 0.02)
    closes = np.array(closes)
    return pd.DataFrame(
        {
            "open": closes,
            "high": closes + 0.02,
            "low": closes - 0.02,
            "close": closes,
            "volume": [10000] * n,
        },
        index=pd.date_range("2024-01-01", periods=n, freq="5min", tz="UTC"),
    )


def test_simulate_one_threshold_returns_summary():
    bars = _make_bars_with_clear_dip(200)
    daily = bars.resample("1D").last().ffill()
    summary = simulate_one_threshold(
        bars_5min=bars,
        daily=daily,
        threshold=0.5,
        atr_pct=0.10,
        stop_multiplier=1.5,
        target_multiplier=2.4,
    )
    assert "trade_count" in summary
    assert "win_count" in summary
    assert "win_rate" in summary
    if summary["trade_count"] > 0:
        assert 0.0 <= summary["win_rate"] <= 1.0


def test_sweep_thresholds_returns_dataframe():
    bars = _make_bars_with_clear_dip(200)
    daily = bars.resample("1D").last().ffill()
    df_results = sweep_thresholds(
        bars_5min=bars,
        daily=daily,
        thresholds=[0.40, 0.50, 0.60, 0.70],
        atr_pct=0.10,
    )
    assert isinstance(df_results, pd.DataFrame)
    assert "threshold" in df_results.columns
    assert "trade_count" in df_results.columns
    assert "win_rate" in df_results.columns
    assert len(df_results) == 4
