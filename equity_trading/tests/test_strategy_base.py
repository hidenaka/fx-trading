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
