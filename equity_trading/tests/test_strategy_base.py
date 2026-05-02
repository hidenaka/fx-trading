import pandas as pd
import pytest

from equity_trading.src.strategy.base import TradingStrategy, StrategyResult


def test_strategy_base_is_abstract():
    with pytest.raises(TypeError):
        TradingStrategy()


def test_strategy_subclass_must_implement_compute_entry_signal():
    class IncompleteStrategy(TradingStrategy):
        name = "incomplete"

    with pytest.raises(TypeError):
        IncompleteStrategy()


def test_strategy_subclass_with_implementation_works():
    class DummyStrategy(TradingStrategy):
        name = "dummy"

        def compute_entry_signal(self, bars_5min, daily, atr_pct, params):
            return pd.Series([False] * len(bars_5min), index=bars_5min.index)

    s = DummyStrategy()
    assert s.name == "dummy"
    bars = pd.DataFrame(
        {"close": [100.0, 101.0]},
        index=pd.date_range("2024-01-01", periods=2, freq="5min", tz="UTC"),
    )
    daily = pd.DataFrame(
        {"close": [100.0]},
        index=pd.date_range("2024-01-01", periods=1, freq="1D", tz="UTC"),
    )
    signal = s.compute_entry_signal(bars, daily, atr_pct=0.10, params={})
    assert len(signal) == 2


def test_strategy_result_dataclass():
    r = StrategyResult(
        strategy_name="test",
        symbol="SPY",
        threshold=0.6,
        trade_count=10,
        win_count=6,
        win_rate=0.6,
        avg_pnl_pct=0.05,
    )
    assert r.expected_value == pytest.approx(10 * 0.05)


def test_compute_exit_levels_default_atr_scaled():
    class DummyStrategy(TradingStrategy):
        name = "dummy"

        def compute_entry_signal(self, bars_5min, daily, atr_pct, params):
            return pd.Series([False] * len(bars_5min), index=bars_5min.index, dtype=bool)

    bars = pd.DataFrame(
        {"close": [100.0, 101.0]},
        index=pd.date_range("2024-01-01", periods=2, freq="5min", tz="UTC"),
    )
    s = DummyStrategy()
    stop, target = s.compute_exit_levels(
        bars_5min=bars, entry_idx=0, entry_price=100.0, atr_pct=0.10, params={},
    )
    # Default multipliers: stop 1.5, target 2.4
    # stop_pct = 0.10 * 1.5 / 100 = 0.0015 -> 100 * (1 - 0.0015) = 99.85
    # target_pct = 0.10 * 2.4 / 100 = 0.0024 -> 100 * (1 + 0.0024) = 100.24
    assert stop == pytest.approx(99.85, abs=1e-9)
    assert target == pytest.approx(100.24, abs=1e-9)


def test_compute_exit_levels_respects_param_multipliers():
    class DummyStrategy(TradingStrategy):
        name = "dummy"

        def compute_entry_signal(self, bars_5min, daily, atr_pct, params):
            return pd.Series([False] * len(bars_5min), index=bars_5min.index, dtype=bool)

    bars = pd.DataFrame(
        {"close": [100.0]},
        index=pd.date_range("2024-01-01", periods=1, freq="5min", tz="UTC"),
    )
    s = DummyStrategy()
    stop, target = s.compute_exit_levels(
        bars_5min=bars, entry_idx=0, entry_price=200.0, atr_pct=0.20,
        params={"stop_multiplier": 2.0, "target_multiplier": 4.0},
    )
    # stop_pct = 0.20 * 2.0 / 100 = 0.004 -> 200 * 0.996 = 199.2
    # target_pct = 0.20 * 4.0 / 100 = 0.008 -> 200 * 1.008 = 201.6
    assert stop == pytest.approx(199.2, abs=1e-9)
    assert target == pytest.approx(201.6, abs=1e-9)


def test_compute_exit_levels_overridable():
    """Subclass can override compute_exit_levels independently."""
    class CustomExitStrategy(TradingStrategy):
        name = "custom_exit"

        def compute_entry_signal(self, bars_5min, daily, atr_pct, params):
            return pd.Series([False] * len(bars_5min), index=bars_5min.index, dtype=bool)

        def compute_exit_levels(self, bars_5min, entry_idx, entry_price, atr_pct, params):
            # Fixed dollar offsets, ignoring ATR
            return entry_price - 1.0, entry_price + 2.0

    bars = pd.DataFrame(
        {"close": [50.0]},
        index=pd.date_range("2024-01-01", periods=1, freq="5min", tz="UTC"),
    )
    s = CustomExitStrategy()
    stop, target = s.compute_exit_levels(
        bars_5min=bars, entry_idx=0, entry_price=50.0, atr_pct=999.0, params={},
    )
    assert stop == pytest.approx(49.0)
    assert target == pytest.approx(52.0)
