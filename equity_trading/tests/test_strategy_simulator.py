import numpy as np
import pandas as pd
import pytest

from equity_trading.src.phase0.strategy_simulator import simulate_strategy
from equity_trading.src.strategy.strategies.mean_reversion import MeanReversionStrategy


def _make_bars(n: int = 200) -> pd.DataFrame:
    np.random.seed(42)
    closes = 100.0 + np.cumsum(np.random.randn(n) * 0.1)
    return pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes, "volume": [10000] * n},
        index=pd.date_range("2024-01-01 14:30", periods=n, freq="5min", tz="UTC"),
    )


def _make_daily(n: int = 250) -> pd.DataFrame:
    return pd.DataFrame(
        {"close": list(np.linspace(80, 120, n))},
        index=pd.date_range("2023-01-01", periods=n, freq="1D", tz="UTC"),
    )


def test_simulate_strategy_returns_dict():
    s = MeanReversionStrategy()
    bars = _make_bars()
    daily = _make_daily()
    result = simulate_strategy(
        strategy=s,
        bars_5min=bars,
        daily=daily,
        atr_pct=0.10,
        params={"threshold": 0.5},
    )
    assert "trade_count" in result
    assert "win_count" in result
    assert "win_rate" in result
    assert "avg_pnl_pct" in result


def test_simulate_strategy_zero_signal_returns_zero_trades():
    """全シグナルが False の戦略は trade_count=0."""
    class ZeroStrategy(MeanReversionStrategy):
        name = "zero"

        def compute_entry_signal(self, bars_5min, daily, atr_pct, params):
            return pd.Series([False] * len(bars_5min), index=bars_5min.index, dtype=bool)

    s = ZeroStrategy()
    result = simulate_strategy(
        strategy=s,
        bars_5min=_make_bars(),
        daily=_make_daily(),
        atr_pct=0.10,
        params={},
    )
    assert result["trade_count"] == 0


def test_simulate_strategy_max_hold_bars_caps_at_n_bars():
    """Time-exit fires at exactly max_hold_bars after entry fill, not max_hold_bars+1."""
    n = 100
    # Flat price → stop/target never trigger; only time-exit fires.
    closes = np.full(n, 100.0)
    bars = pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes, "volume": [10000] * n},
        index=pd.date_range("2024-01-01 14:30", periods=n, freq="5min", tz="UTC"),
    )
    daily = pd.DataFrame(
        {"close": [100.0] * 250},
        index=pd.date_range("2023-01-01", periods=250, freq="1D", tz="UTC"),
    )

    class AlwaysOnceStrategy(MeanReversionStrategy):
        """Signal True at bar 0 only, so we have one trade entered at bar 1."""
        name = "always_once"

        def compute_entry_signal(self, bars_5min, daily, atr_pct, params):
            sig = pd.Series([False] * len(bars_5min), index=bars_5min.index, dtype=bool)
            sig.iloc[0] = True
            return sig

    s = AlwaysOnceStrategy()
    result = simulate_strategy(
        strategy=s,
        bars_5min=bars,
        daily=daily,
        atr_pct=0.10,
        params={},
        max_hold_bars=10,
    )
    # 1 trade, time-exited after 10 bars at flat price → pnl = -cost (not 0)
    assert result["trade_count"] == 1
    # avg_pnl_pct in percent: at flat price, only cost subtracts; cost_pct default 0.10 → -0.10%
    assert result["avg_pnl_pct"] == pytest.approx(-0.10, abs=0.001)
