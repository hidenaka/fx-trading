import numpy as np
import pandas as pd
import pytest

from equity_trading.src.strategy.strategies.gap_fill import GapFillStrategy


def _daily(close_series: list[float], start: str = "2024-01-10") -> pd.DataFrame:
    """Daily bars for past N days; close_series ends at <today-1>."""
    n = len(close_series)
    return pd.DataFrame(
        {"close": close_series},
        index=pd.date_range(start, periods=n, freq="1D", tz="UTC"),
    )


def _intraday_for_day(open_price: float, n: int = 50, day: str = "2024-01-15") -> pd.DataFrame:
    closes = np.full(n, open_price)
    return pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes, "volume": [10000] * n},
        index=pd.date_range(f"{day} 14:30", periods=n, freq="5min", tz="UTC"),
    )


def test_gap_fill_has_correct_name():
    assert GapFillStrategy().name == "gap_fill"


def test_gap_fill_no_signal_on_normal_day():
    """Today's open ≈ prev close → no gap → no signal."""
    s = GapFillStrategy()
    bars = _intraday_for_day(open_price=100.0)
    # Daily: 251 days so last bar is 2024-01-15; bar at index -2 (2024-01-14) close = 100.0
    daily_closes = list(np.linspace(80, 100, 250)) + [100.0]
    daily = _daily(daily_closes, start="2023-05-10")
    # 2024-01-15 intraday open 100 vs 2024-01-14 close 100 → 0% gap
    signal = s.compute_entry_signal(bars, daily, atr_pct=0.10, params={"gap_threshold": 0.005})
    assert not signal.any()


def test_gap_fill_signals_on_gap_down_day_at_first_bar():
    """Today opens 99.0, yesterday closed 100.0 → 1% gap-down → signal at bar 0 only."""
    s = GapFillStrategy()
    bars = _intraday_for_day(open_price=99.0)
    # Daily: 251 days; 2024-01-14 close = 100.0, 2024-01-15 close = 100.0
    daily_closes = list(np.linspace(80, 100, 250)) + [100.0]
    daily = _daily(daily_closes, start="2023-05-10")
    signal = s.compute_entry_signal(bars, daily, atr_pct=0.10, params={"gap_threshold": 0.005})
    # First bar fires
    assert signal.iloc[0] == True
    # No other bars
    assert signal.iloc[1:].sum() == 0


def test_gap_fill_no_signal_on_gap_up():
    """Gap-up should NOT fire (long-only fade strategy)."""
    s = GapFillStrategy()
    bars = _intraday_for_day(open_price=101.0)  # gap up vs 100.0
    daily_closes = list(np.linspace(80, 100, 250)) + [100.0]
    daily = _daily(daily_closes, start="2023-05-10")
    signal = s.compute_entry_signal(bars, daily, atr_pct=0.10, params={"gap_threshold": 0.005})
    assert not signal.any()


def test_gap_fill_compute_exit_levels_targets_prev_close():
    """Target = prev_close, Stop = today_open × (1 - stop_extension)."""
    s = GapFillStrategy()
    bars = _intraday_for_day(open_price=99.0)
    daily_closes = list(np.linspace(80, 100, 250)) + [100.0]
    daily = _daily(daily_closes, start="2023-05-10")

    stop, target = s.compute_exit_levels(
        bars_5min=bars, entry_idx=0, entry_price=99.0, atr_pct=0.10,
        params={"gap_threshold": 0.005, "stop_extension": 0.005, "_daily": daily},
    )
    # Target = prev close = 100.0
    # Stop = 99.0 * (1 - 0.005) = 98.505
    assert target == pytest.approx(100.0, abs=1e-6)
    assert stop == pytest.approx(98.505, abs=1e-6)
