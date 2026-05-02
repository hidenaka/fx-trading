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
    # Bar 5: low dips to 99.45 (intra-bar) but close recovers to 99.80 (above stop=99.70).
    # With realistic low/high-based exit, custom stop should trigger via the bar low.
    closes = np.full(n, 100.0)
    closes[5:] = 99.80
    opens = np.full(n, 100.0)
    opens[5:] = 99.95  # No gap-through stop; intra-bar low triggers it.
    highs = closes + 0.05
    lows = np.full(n, 99.95)
    lows[5] = 99.45  # only this bar dips below stop
    lows[6:] = 99.75
    bars = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": [10000] * n},
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
        atr_pct=0.10,
        params={},
        max_hold_bars=50,
        return_trades=True,
    )
    assert summary["trade_count"] == 1
    # Custom stop = 100 * 0.997 = 99.70. Bar 5 low (99.45) <= stop, open (99.95) > stop → fill at stop_price.
    # Pnl = (99.70 - 100)/100 - cost = -0.003 - 0.001 = -0.004 = -0.4%
    assert trades.iloc[0]["exit_type"] == "stop"
    assert summary["avg_pnl_pct"] == pytest.approx(-0.4, abs=0.01)


# === New tests for realistic low/high/gap-based exit modeling ===


def _bars_from_arrays(opens, highs, lows, closes):
    n = len(closes)
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": [10000] * n},
        index=pd.date_range("2024-01-01 14:30", periods=n, freq="5min", tz="UTC"),
    )


def _flat_daily(n_days: int = 250) -> pd.DataFrame:
    return pd.DataFrame(
        {"close": [100.0] * n_days},
        index=pd.date_range("2023-01-01", periods=n_days, freq="1D", tz="UTC"),
    )


class _SignalAtZero(MeanReversionStrategy):
    """Fires entry signal at bar 0 only (entry fills at bar 1 close)."""

    name = "signal_at_zero"

    def compute_entry_signal(self, bars_5min, daily, atr_pct, params):
        sig = pd.Series([False] * len(bars_5min), index=bars_5min.index, dtype=bool)
        sig.iloc[0] = True
        return sig

    def compute_exit_levels(self, bars_5min, entry_idx, entry_price, atr_pct, params):
        # stop=99.70, target=101.0 (entry=100)
        return entry_price * 0.997, entry_price * 1.01


def test_stop_triggered_by_bar_low_even_when_close_recovers():
    """Bar low dips below stop, close recovers above. Should still trigger stop."""
    n = 30
    opens = np.full(n, 100.0)
    closes = np.full(n, 100.0)
    highs = np.full(n, 100.05)
    lows = np.full(n, 99.95)
    # Bar 5: low=99.50 (below stop=99.70), close=99.85 (above stop), open=99.90 (above stop)
    opens[5] = 99.90
    lows[5] = 99.50
    closes[5] = 99.85
    highs[5] = 99.95

    bars = _bars_from_arrays(opens, highs, lows, closes)
    summary, trades = simulate_strategy(
        strategy=_SignalAtZero(), bars_5min=bars, daily=_flat_daily(),
        atr_pct=0.10, params={}, max_hold_bars=20, return_trades=True,
    )
    assert summary["trade_count"] == 1
    assert trades.iloc[0]["exit_type"] == "stop"
    # Fill at stop_price=99.70 (low penetrated, but no gap through)
    assert trades.iloc[0]["exit_price"] == pytest.approx(99.70, abs=0.01)
    # pnl = -0.3% - 0.1% cost = -0.4%
    assert summary["avg_pnl_pct"] == pytest.approx(-0.4, abs=0.01)


def test_target_triggered_by_bar_high_even_when_close_pulls_back():
    """Bar high spikes above target, close pulls back below. Should still trigger target."""
    n = 30
    opens = np.full(n, 100.0)
    closes = np.full(n, 100.0)
    highs = np.full(n, 100.05)
    lows = np.full(n, 99.95)
    # Bar 5: high=101.20 (above target=101.0), close=100.50, open=100.10
    opens[5] = 100.10
    highs[5] = 101.20
    closes[5] = 100.50
    lows[5] = 100.05

    bars = _bars_from_arrays(opens, highs, lows, closes)
    summary, trades = simulate_strategy(
        strategy=_SignalAtZero(), bars_5min=bars, daily=_flat_daily(),
        atr_pct=0.10, params={}, max_hold_bars=20, return_trades=True,
    )
    assert summary["trade_count"] == 1
    assert trades.iloc[0]["exit_type"] == "target"
    # Fill at target_price=101.0
    assert trades.iloc[0]["exit_price"] == pytest.approx(101.0, abs=0.01)
    # pnl = +1.0% - 0.1% cost = +0.9%
    assert summary["avg_pnl_pct"] == pytest.approx(0.9, abs=0.01)


def test_gap_down_through_stop_fills_at_open_worse_than_stop():
    """Open gaps below stop. Fill at open (worse than stop_price)."""
    n = 30
    opens = np.full(n, 100.0)
    closes = np.full(n, 100.0)
    highs = np.full(n, 100.05)
    lows = np.full(n, 99.95)
    # Bar 5: gap-down to open=99.40 (below stop=99.70)
    opens[5] = 99.40
    closes[5] = 99.45
    highs[5] = 99.50
    lows[5] = 99.30

    bars = _bars_from_arrays(opens, highs, lows, closes)
    summary, trades = simulate_strategy(
        strategy=_SignalAtZero(), bars_5min=bars, daily=_flat_daily(),
        atr_pct=0.10, params={}, max_hold_bars=20, return_trades=True,
    )
    assert summary["trade_count"] == 1
    assert trades.iloc[0]["exit_type"] == "stop"
    # Fill at open=99.40 (worse than stop_price=99.70)
    assert trades.iloc[0]["exit_price"] == pytest.approx(99.40, abs=0.01)
    # pnl = (99.40-100)/100 - 0.1% = -0.6% - 0.1% = -0.7%
    assert summary["avg_pnl_pct"] == pytest.approx(-0.7, abs=0.01)


def test_gap_up_through_target_fills_at_open_better_than_target():
    """Open gaps above target. Fill at open (better than target_price)."""
    n = 30
    opens = np.full(n, 100.0)
    closes = np.full(n, 100.0)
    highs = np.full(n, 100.05)
    lows = np.full(n, 99.95)
    # Bar 5: gap-up to open=101.50 (above target=101.0)
    opens[5] = 101.50
    closes[5] = 101.40
    highs[5] = 101.60
    lows[5] = 101.30

    bars = _bars_from_arrays(opens, highs, lows, closes)
    summary, trades = simulate_strategy(
        strategy=_SignalAtZero(), bars_5min=bars, daily=_flat_daily(),
        atr_pct=0.10, params={}, max_hold_bars=20, return_trades=True,
    )
    assert summary["trade_count"] == 1
    assert trades.iloc[0]["exit_type"] == "target"
    # Fill at open=101.50 (better than target_price=101.0)
    assert trades.iloc[0]["exit_price"] == pytest.approx(101.50, abs=0.01)
    # pnl = +1.5% - 0.1% = +1.4%
    assert summary["avg_pnl_pct"] == pytest.approx(1.4, abs=0.01)


def test_simultaneous_low_below_stop_and_high_above_target_stop_wins():
    """If both stop and target are touched in same bar, stop wins (conservative)."""
    n = 30
    opens = np.full(n, 100.0)
    closes = np.full(n, 100.0)
    highs = np.full(n, 100.05)
    lows = np.full(n, 99.95)
    # Bar 5: low=99.50 (below stop), high=101.50 (above target), open=100.0 (between)
    opens[5] = 100.0
    closes[5] = 100.0
    lows[5] = 99.50
    highs[5] = 101.50

    bars = _bars_from_arrays(opens, highs, lows, closes)
    summary, trades = simulate_strategy(
        strategy=_SignalAtZero(), bars_5min=bars, daily=_flat_daily(),
        atr_pct=0.10, params={}, max_hold_bars=20, return_trades=True,
    )
    assert summary["trade_count"] == 1
    # Conservative: stop wins
    assert trades.iloc[0]["exit_type"] == "stop"
    assert trades.iloc[0]["exit_price"] == pytest.approx(99.70, abs=0.01)


def test_entry_bar_low_high_does_not_trigger_exit():
    """Entry bar's low/high happened BEFORE entry fill; must not trigger exit."""
    n = 30
    opens = np.full(n, 100.0)
    closes = np.full(n, 100.0)
    highs = np.full(n, 100.05)
    lows = np.full(n, 99.95)
    # Bar 1 (entry bar): low=99.40 (below stop=99.70), high=101.50 (above target=101.0)
    # These should NOT trigger exit because entry fills at close=100.
    lows[1] = 99.40
    highs[1] = 101.50
    closes[1] = 100.0  # entry price
    opens[1] = 100.0

    bars = _bars_from_arrays(opens, highs, lows, closes)
    summary, trades = simulate_strategy(
        strategy=_SignalAtZero(), bars_5min=bars, daily=_flat_daily(),
        atr_pct=0.10, params={}, max_hold_bars=20, return_trades=True,
    )
    # No exit triggered on entry bar; flat afterwards → time exit at bar 21
    assert summary["trade_count"] == 1
    assert trades.iloc[0]["exit_type"] == "time"
