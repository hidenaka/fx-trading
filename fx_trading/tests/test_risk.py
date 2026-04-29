import pytest
from src.risk.manager import RiskManager

def test_calculate_lot_basic():
    rm = RiskManager(capital=1_000_000, risk_per_trade=0.01)
    lot = rm.calculate_lot(entry_price=150.0, stop_loss=149.0)
    expected_risk = 1_000_000 * 0.01
    expected_lot = expected_risk / 1.0
    assert lot == pytest.approx(expected_lot)

def test_calculate_lot_zero_diff_returns_zero():
    rm = RiskManager(capital=1_000_000, risk_per_trade=0.01)
    lot = rm.calculate_lot(entry_price=150.0, stop_loss=150.0)
    assert lot == 0.0

def test_update_capital():
    rm = RiskManager(capital=1_000_000, risk_per_trade=0.01)
    rm.update_capital(50000)
    assert rm.capital == 1_050_000
    rm.update_capital(-30000)
    assert rm.capital == 1_020_000
