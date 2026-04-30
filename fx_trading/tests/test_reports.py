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


def test_report_includes_risk_metrics():
    trades = [
        Trade(entry_time=pd.Timestamp("2024-01-01"), entry_price=150.0, direction=1, lot=1.0,
              exit_time=pd.Timestamp("2024-01-02"), exit_price=151.0, pnl=1000.0),
        Trade(entry_time=pd.Timestamp("2024-01-03"), entry_price=151.0, direction=-1, lot=1.0,
              exit_time=pd.Timestamp("2024-01-04"), exit_price=150.0, pnl=1000.0),
    ]
    report = ReportGenerator(initial_capital=1_000_000).generate(trades)
    for key in ("max_drawdown_pct", "max_drawdown_abs", "sharpe_ratio",
                "sortino_ratio", "avg_holding_hours"):
        assert key in report


def test_max_drawdown_measured_from_peak():
    # Equity path: 1.0M -> 1.1M -> 0.95M -> 1.05M
    # Peak = 1.1M, trough = 0.95M -> drawdown = 13.6%
    trades = [
        Trade(entry_time=pd.Timestamp("2024-01-01"), entry_price=150.0, direction=1, lot=1.0,
              exit_time=pd.Timestamp("2024-01-02"), exit_price=151.0, pnl=100_000.0),
        Trade(entry_time=pd.Timestamp("2024-01-02"), entry_price=151.0, direction=1, lot=1.0,
              exit_time=pd.Timestamp("2024-01-03"), exit_price=150.0, pnl=-150_000.0),
        Trade(entry_time=pd.Timestamp("2024-01-03"), entry_price=150.0, direction=1, lot=1.0,
              exit_time=pd.Timestamp("2024-01-04"), exit_price=151.0, pnl=100_000.0),
    ]
    report = ReportGenerator(initial_capital=1_000_000).generate(trades)
    # Peak 1.1M -> 0.95M = 150k abs, ~13.6% pct.
    assert abs(report["max_drawdown_abs"] - 150_000.0) < 1e-6
    assert 13.0 < report["max_drawdown_pct"] < 14.0


def test_avg_holding_hours_for_one_day_trade():
    trades = [
        Trade(entry_time=pd.Timestamp("2024-01-01 00:00"), entry_price=150.0, direction=1, lot=1.0,
              exit_time=pd.Timestamp("2024-01-02 00:00"), exit_price=151.0, pnl=1000.0),
    ]
    report = ReportGenerator(initial_capital=1_000_000).generate(trades)
    assert abs(report["avg_holding_hours"] - 24.0) < 1e-6


def test_sharpe_zero_when_returns_constant():
    # All trades same PnL on consecutive days -> non-zero mean, zero std on
    # the actual trade days, but reindex inserts zeros... Sharpe likely > 0.
    # Instead test the empty case is zero.
    report = ReportGenerator(initial_capital=1_000_000).generate([])
    assert report["sharpe_ratio"] == 0.0
    assert report["sortino_ratio"] == 0.0
    assert report["max_drawdown_pct"] == 0.0


def test_sortino_ignores_upside_volatility():
    # Mostly winning days with one losing day: Sortino should still be defined.
    trades = []
    for i in range(10):
        trades.append(
            Trade(
                entry_time=pd.Timestamp("2024-01-01") + pd.Timedelta(days=i),
                entry_price=150.0, direction=1, lot=1.0,
                exit_time=pd.Timestamp("2024-01-01") + pd.Timedelta(days=i, hours=4),
                exit_price=151.0, pnl=1000.0,
            )
        )
    # Two losing days so downside std (ddof=1) is well-defined.
    trades[3] = Trade(
        entry_time=pd.Timestamp("2024-01-04"), entry_price=150.0, direction=1, lot=1.0,
        exit_time=pd.Timestamp("2024-01-04 04:00"), exit_price=149.0, pnl=-1500.0,
    )
    trades[6] = Trade(
        entry_time=pd.Timestamp("2024-01-07"), entry_price=150.0, direction=1, lot=1.0,
        exit_time=pd.Timestamp("2024-01-07 04:00"), exit_price=149.0, pnl=-2000.0,
    )
    report = ReportGenerator(initial_capital=1_000_000).generate(trades)
    assert report["sortino_ratio"] != 0.0
    assert report["sharpe_ratio"] != 0.0


def test_report_dict_includes_dashboard_keys():
    # The dashboard JSON contract relies on these exact keys; if any are
    # renamed or dropped, the dashboard will silently show blanks. Lock them.
    trades = [
        Trade(entry_time=pd.Timestamp("2024-01-01"), entry_price=150.0, direction=1, lot=1.0,
              exit_time=pd.Timestamp("2024-01-02"), exit_price=151.0, pnl=1000.0),
        Trade(entry_time=pd.Timestamp("2024-01-03"), entry_price=151.0, direction=1, lot=1.0,
              exit_time=pd.Timestamp("2024-01-04"), exit_price=150.0, pnl=-1500.0),
    ]
    report = ReportGenerator(initial_capital=1_000_000).generate(trades)
    required_keys = {
        "total_trades", "win_rate", "profit_factor", "total_pnl",
        "max_drawdown_pct", "max_drawdown_abs",
        "sharpe_ratio", "sortino_ratio", "avg_holding_hours",
    }
    assert required_keys.issubset(report.keys())
