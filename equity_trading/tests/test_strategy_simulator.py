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


def test_simulate_strategy_returns_trades_dataframe_when_requested():
    n = 50
    closes = np.full(n, 100.0)
    bars = pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes, "volume": [10000] * n},
        index=pd.date_range("2024-01-01 14:30", periods=n, freq="5min", tz="UTC"),
    )
    daily = pd.DataFrame(
        {"close": [100.0] * 250},
        index=pd.date_range("2023-01-01", periods=250, freq="1D", tz="UTC"),
    )

    class TwoSignalsStrategy(MeanReversionStrategy):
        name = "two_signals"

        def compute_entry_signal(self, bars_5min, daily, atr_pct, params):
            sig = pd.Series([False] * len(bars_5min), index=bars_5min.index, dtype=bool)
            sig.iloc[0] = True
            sig.iloc[20] = True
            return sig

    summary, trades = simulate_strategy(
        strategy=TwoSignalsStrategy(),
        bars_5min=bars,
        daily=daily,
        atr_pct=0.10,
        params={},
        max_hold_bars=5,
        return_trades=True,
    )
    assert isinstance(summary, dict)
    assert isinstance(trades, pd.DataFrame)
    expected_cols = {"entry_ts", "exit_ts", "entry_price", "exit_price",
                     "exit_type", "bars_held", "pnl_pct"}
    assert expected_cols.issubset(trades.columns)
    assert len(trades) == summary["trade_count"]
    # All exits should be 'time' for flat price (no stop/target hit)
    assert (trades["exit_type"] == "time").all()
    # bars_held should equal max_hold_bars on time exits
    assert (trades["bars_held"] == 5).all()


def test_simulate_strategy_default_return_unchanged():
    """Returning a plain dict (not a tuple) is preserved by default."""
    n = 50
    closes = np.full(n, 100.0)
    bars = pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes, "volume": [10000] * n},
        index=pd.date_range("2024-01-01 14:30", periods=n, freq="5min", tz="UTC"),
    )
    daily = pd.DataFrame(
        {"close": [100.0] * 250},
        index=pd.date_range("2023-01-01", periods=250, freq="1D", tz="UTC"),
    )

    class ZeroStrategy(MeanReversionStrategy):
        name = "zero"

        def compute_entry_signal(self, bars_5min, daily, atr_pct, params):
            return pd.Series([False] * len(bars_5min), index=bars_5min.index, dtype=bool)

    result = simulate_strategy(
        strategy=ZeroStrategy(),
        bars_5min=bars, daily=daily, atr_pct=0.10, params={},
    )
    # Backwards compat: dict, not tuple
    assert isinstance(result, dict)
    assert result["trade_count"] == 0


def test_simulate_strategy_calls_compute_exit_levels():
    """The simulator must invoke strategy.compute_exit_levels per entry."""
    n = 60
    closes = np.full(n, 100.0)
    bars = pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes, "volume": [10000] * n},
        index=pd.date_range("2024-01-01 14:30", periods=n, freq="5min", tz="UTC"),
    )
    daily = pd.DataFrame(
        {"close": [100.0] * 250},
        index=pd.date_range("2023-01-01", periods=250, freq="1D", tz="UTC"),
    )

    call_log: list = []

    class SpyStrategy(MeanReversionStrategy):
        name = "spy"

        def compute_entry_signal(self, bars_5min, daily, atr_pct, params):
            sig = pd.Series([False] * len(bars_5min), index=bars_5min.index, dtype=bool)
            sig.iloc[0] = True
            return sig

        def compute_exit_levels(self, bars_5min, entry_idx, entry_price, atr_pct, params):
            call_log.append({"entry_idx": entry_idx, "entry_price": entry_price, "atr_pct": atr_pct})
            return super().compute_exit_levels(bars_5min, entry_idx, entry_price, atr_pct, params)

    summary = simulate_strategy(
        strategy=SpyStrategy(),
        bars_5min=bars,
        daily=daily,
        atr_pct=0.10,
        params={},
        max_hold_bars=5,
    )
    assert summary["trade_count"] == 1
    assert len(call_log) == 1
    # Entry idx is bar 1 (filled on bar after signal)
    assert call_log[0]["entry_idx"] == 1
    assert call_log[0]["entry_price"] == 100.0
    assert call_log[0]["atr_pct"] == 0.10


def test_simulate_strategy_custom_exit_changes_outcome():
    """Tight custom stop fires while default ATR stop wouldn't."""
    n = 60
    # Drop by 0.5% on bar 5
    closes = np.full(n, 100.0)
    closes[5:] = 99.50  # -0.5%
    bars = pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes, "volume": [10000] * n},
        index=pd.date_range("2024-01-01 14:30", periods=n, freq="5min", tz="UTC"),
    )
    daily = pd.DataFrame(
        {"close": [100.0] * 250},
        index=pd.date_range("2023-01-01", periods=250, freq="1D", tz="UTC"),
    )

    class TightStopStrategy(MeanReversionStrategy):
        name = "tight"

        def compute_entry_signal(self, bars_5min, daily, atr_pct, params):
            sig = pd.Series([False] * len(bars_5min), index=bars_5min.index, dtype=bool)
            sig.iloc[0] = True
            return sig

        def compute_exit_levels(self, bars_5min, entry_idx, entry_price, atr_pct, params):
            # 0.3% stop, 1% target  (tighter than default 0.15% stop / 0.24% target so this hits)
            return entry_price * 0.997, entry_price * 1.01

    summary, trades = simulate_strategy(
        strategy=TightStopStrategy(),
        bars_5min=bars,
        daily=daily,
        atr_pct=0.10,  # default stop = 0.10*1.5/100 = 0.15% (would also stop at -0.5%)
        params={},
        max_hold_bars=50,
        return_trades=True,
    )
    assert summary["trade_count"] == 1
    # Both default and custom stop would fire at -0.5%; but verify the exit price uses CUSTOM stop, not default
    # Custom stop = 100 * 0.997 = 99.70. Pnl = (99.70 - 100)/100 - cost = -0.003 - 0.001 = -0.004 = -0.4%
    assert trades.iloc[0]["exit_type"] == "stop"
    # avg_pnl_pct = -0.4% (not -0.25% which is default ATR stop at 0.10*1.5/100 = 0.0015 = 0.15%)
    assert summary["avg_pnl_pct"] == pytest.approx(-0.4, abs=0.01)
