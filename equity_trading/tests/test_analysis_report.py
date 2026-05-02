import pandas as pd

from equity_trading.src.phase0.analysis_report import generate_analysis_report


def test_analysis_report_contains_all_keys(tmp_path):
    out = tmp_path / "analysis.md"
    sample = {
        "n_trades": 36,
        "n_wins": 23,
        "win_rate": 0.639,
        "avg_pnl_pct": 0.028,
        "total_pnl_pct": 1.008,
        "exit_breakdown": {"stop": 5, "target": 8, "time": 23},
        "avg_pnl_by_exit_type": {"stop": -0.192, "target": 0.046, "time": 0.030},
        "wr_by_hour_of_day": pd.DataFrame([
            {"hour": 9, "n_trades": 5, "n_wins": 4, "win_rate": 0.80, "avg_pnl_pct": 0.05},
            {"hour": 10, "n_trades": 8, "n_wins": 5, "win_rate": 0.625, "avg_pnl_pct": 0.02},
        ]),
        "wr_by_day_open_change": pd.DataFrame([
            {"bucket": "< -1%", "n_trades": 2, "win_rate": 0.5, "avg_pnl_pct": 0.0},
            {"bucket": "-1%..0%", "n_trades": 30, "win_rate": 0.66, "avg_pnl_pct": 0.03},
        ]),
        "wr_by_spy_regime": pd.DataFrame([
            {"regime": "up", "n_trades": 25, "win_rate": 0.68, "avg_pnl_pct": 0.04},
            {"regime": "down", "n_trades": 11, "win_rate": 0.55, "avg_pnl_pct": 0.0},
        ]),
        "wr_by_holding_bars": pd.DataFrame([
            {"bucket": "1-3", "n_trades": 10, "win_rate": 0.4, "avg_pnl_pct": -0.05},
            {"bucket": "40-78", "n_trades": 20, "win_rate": 0.75, "avg_pnl_pct": 0.06},
        ]),
    }
    analyses = {("mean_reversion", "XLK"): sample}
    generate_analysis_report(
        analyses=analyses,
        output_path=out,
        period_start="2024-05-01",
        period_end="2026-05-01",
    )
    content = out.read_text()
    assert "mean_reversion" in content
    assert "XLK" in content
    assert "stop" in content.lower() or "Stop" in content
    assert "Hour" in content or "hour" in content
