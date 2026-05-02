import numpy as np
import pandas as pd
import pytest

from equity_trading.src.live.signal_evaluator import LiveSignal, evaluate_live_signal
from equity_trading.src.strategy.strategies.mean_reversion import MeanReversionStrategy


def _make_bars(n: int = 100) -> pd.DataFrame:
    np.random.seed(42)
    closes = 100.0 + np.cumsum(np.random.randn(n) * 0.1)
    return pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes, "volume": [10000] * n},
        index=pd.date_range("2024-01-15 14:30", periods=n, freq="5min", tz="UTC"),
    )


def _daily_above_ma(n: int = 250) -> pd.DataFrame:
    closes = pd.Series(100.0 + np.linspace(0, 20, n))
    return pd.DataFrame(
        {"close": closes.values},
        index=pd.date_range("2023-01-01", periods=n, freq="1D", tz="UTC"),
    )


def test_live_signal_no_entry_returns_should_enter_false():
    """A strategy that never signals returns False everywhere."""
    class ZeroStrategy(MeanReversionStrategy):
        name = "zero"

        def compute_entry_signal(self, bars_5min, daily, atr_pct, params):
            return pd.Series([False] * len(bars_5min), index=bars_5min.index, dtype=bool)

    sig = evaluate_live_signal(
        strategy=ZeroStrategy(),
        bars_5min=_make_bars(),
        daily=_daily_above_ma(),
        atr_pct=0.10,
        params={},
    )
    assert sig.should_enter is False
    assert sig.stop_price is None
    assert sig.target_price is None
    assert sig.entry_reference_price is None


def test_live_signal_entry_at_last_bar_returns_levels():
    """Strategy signals True at last bar → levels populated."""
    class LastBarStrategy(MeanReversionStrategy):
        name = "last_bar"

        def compute_entry_signal(self, bars_5min, daily, atr_pct, params):
            sig = pd.Series([False] * len(bars_5min), index=bars_5min.index, dtype=bool)
            sig.iloc[-1] = True
            return sig

    bars = _make_bars()
    sig = evaluate_live_signal(
        strategy=LastBarStrategy(),
        bars_5min=bars,
        daily=_daily_above_ma(),
        atr_pct=0.10,
        params={},
    )
    assert sig.should_enter is True
    assert sig.entry_reference_price == pytest.approx(bars["close"].iloc[-1])
    # Default ATR-scaled exits: 0.10 * 1.5 / 100 = 0.0015 stop, 0.10 * 2.4 / 100 = 0.0024 target
    expected_stop = bars["close"].iloc[-1] * (1 - 0.0015)
    expected_target = bars["close"].iloc[-1] * (1 + 0.0024)
    assert sig.stop_price == pytest.approx(expected_stop, abs=1e-6)
    assert sig.target_price == pytest.approx(expected_target, abs=1e-6)


def test_live_signal_specific_bar_index():
    """bar_index=0 evaluates the first bar (for gap_fill semantics)."""
    class FirstBarStrategy(MeanReversionStrategy):
        name = "first_bar"

        def compute_entry_signal(self, bars_5min, daily, atr_pct, params):
            sig = pd.Series([False] * len(bars_5min), index=bars_5min.index, dtype=bool)
            sig.iloc[0] = True
            return sig

    bars = _make_bars()
    sig = evaluate_live_signal(
        strategy=FirstBarStrategy(),
        bars_5min=bars,
        daily=_daily_above_ma(),
        atr_pct=0.10,
        params={},
        bar_index=0,
    )
    assert sig.should_enter is True
    assert sig.entry_reference_price == pytest.approx(bars["close"].iloc[0])


def test_live_signal_dataclass_is_frozen():
    """LiveSignal is immutable."""
    sig = LiveSignal(False, None, None, None)
    with pytest.raises((AttributeError, ValueError)):
        sig.should_enter = True  # type: ignore
