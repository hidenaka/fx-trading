import pandas as pd
from src.reports.reporter import ReportGenerator
from src.engine.backtest import Trade

def test_generate_report_basic():
    trades = [
        Trade(entry_time=pd.Timestamp("2024-01-01"), entry_price=150.0, direction=1, lot=1.0,
              exit_time=pd.Timestamp("2024-01-02"), exit_price=151.0, pnl=1000.0),
        Trade(entry_time=pd.Timestamp("2024-01-03"), entry_price=151.0, direction=-1, lot=1.0,
              exit_time=pd.Timestamp("2024-01-04"), exit_price=150.0, pnl=1000.0),
    ]
    reporter = ReportGenerator(initial_capital=1_000_000)
    report = reporter.generate(trades)
    assert report["total_trades"] == 2
    assert report["win_rate"] == 1.0
    assert report["profit_factor"] == float("inf")

def test_generate_report_with_loss():
    trades = [
        Trade(entry_time=pd.Timestamp("2024-01-01"), entry_price=150.0, direction=1, lot=1.0,
              exit_time=pd.Timestamp("2024-01-02"), exit_price=149.0, pnl=-1000.0),
    ]
    reporter = ReportGenerator(initial_capital=1_000_000)
    report = reporter.generate(trades)
    assert report["total_trades"] == 1
    assert report["win_rate"] == 0.0
    assert report["profit_factor"] == 0.0
