import pandas as pd
from src.engine.backtest import BacktestEngine
from src.engine.cost_model import CostModel
from src.strategies.ma_macd import MaMacdStrategy
from src.risk.manager import RiskManager


def test_zero_cost_model_does_not_alter_price():
    cm = CostModel()
    assert cm.adjust_entry(150.0, 1) == 150.0
    assert cm.adjust_exit(150.0, 1) == 150.0
    assert cm.swap_pnl(1000, 1, 5) == 0.0


def test_spread_charges_buy_higher_sell_lower():
    cm = CostModel(spread_pips=2.0, pip_size=0.01)
    # Buy: pay ask = mid + half-spread; close-long: receive bid = mid - half-spread.
    assert cm.adjust_entry(150.0, 1) == 150.01
    assert cm.adjust_exit(150.0, 1) == 149.99
    # Short: sell bid; close-short: buy ask.
    assert cm.adjust_entry(150.0, -1) == 149.99
    assert cm.adjust_exit(150.0, -1) == 150.01


def test_slippage_widens_per_side_cost():
    cm_no_slip = CostModel(spread_pips=2.0, slippage_pips=0.0, pip_size=0.01)
    cm_slip = CostModel(spread_pips=2.0, slippage_pips=1.0, pip_size=0.01)
    assert cm_slip.adjust_entry(150.0, 1) > cm_no_slip.adjust_entry(150.0, 1)


def test_swap_accrues_per_day():
    cm = CostModel(swap_long_per_unit_per_day=-0.5)
    assert cm.swap_pnl(1000, 1, days_held=2.0) == -1000.0
    # Short uses the short rate (zero by default).
    assert cm.swap_pnl(1000, -1, days_held=2.0) == 0.0


def test_engine_with_cost_model_reduces_pnl():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=30, freq="h"),
        "open": [150.0] * 30,
        "high": [151.0] * 30,
        "low": [149.0] * 30,
        "close": [150.0 + i * 0.05 for i in range(30)],
        "volume": [1000] * 30,
    })
    strategy_args = dict(fast=3, slow=6, signal=2)

    free_engine = BacktestEngine(initial_capital=1_000_000, cost_model=CostModel())
    free_trades = free_engine.run(
        df.copy(),
        MaMacdStrategy(**strategy_args),
        RiskManager(capital=1_000_000, risk_per_trade=0.01),
    )

    costly_engine = BacktestEngine(
        initial_capital=1_000_000,
        cost_model=CostModel(spread_pips=2.0, slippage_pips=0.5, pip_size=0.01),
    )
    costly_trades = costly_engine.run(
        df.copy(),
        MaMacdStrategy(**strategy_args),
        RiskManager(capital=1_000_000, risk_per_trade=0.01),
    )

    # Same trade count (signals don't depend on cost), but PnL must be worse.
    assert len(free_trades) == len(costly_trades)
    if free_trades:
        free_pnl = sum(t.pnl for t in free_trades if t.pnl is not None)
        costly_pnl = sum(t.pnl for t in costly_trades if t.pnl is not None)
        assert costly_pnl < free_pnl


def test_default_engine_is_zero_cost_for_backwards_compat():
    engine = BacktestEngine()
    assert isinstance(engine.cost_model, CostModel)
    assert engine.cost_model.spread_pips == 0.0
    assert engine.cost_model.slippage_pips == 0.0
