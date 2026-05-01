from pathlib import Path

import pandas as pd

from equity_trading.src.phase0.report_generator import generate_calibration_report


def test_report_contains_atr_table_and_threshold_results(tmp_path):
    atr_results = {
        "SPY": {"median_pct": 0.10, "mean_pct": 0.12, "p25_pct": 0.08, "p75_pct": 0.14},
        "QQQ": {"median_pct": 0.13, "mean_pct": 0.15, "p25_pct": 0.10, "p75_pct": 0.18},
    }
    sweep_results = {
        "SPY": pd.DataFrame({
            "threshold": [0.5, 0.6],
            "trade_count": [120, 50],
            "win_count": [70, 30],
            "win_rate": [0.583, 0.6],
            "avg_pnl_pct": [0.05, 0.08],
        }),
        "QQQ": pd.DataFrame({
            "threshold": [0.5, 0.6],
            "trade_count": [100, 40],
            "win_count": [55, 22],
            "win_rate": [0.55, 0.55],
            "avg_pnl_pct": [0.04, 0.06],
        }),
    }
    out_path = tmp_path / "calibration_report.md"
    generate_calibration_report(
        atr_results=atr_results,
        sweep_results=sweep_results,
        output_path=out_path,
        period_start="2024-01-01",
        period_end="2024-12-31",
    )
    content = out_path.read_text()
    assert "Phase 0" in content
    assert "ATR" in content
    assert "SPY" in content
    assert "QQQ" in content
    assert "0.10" in content
    assert "Threshold" in content or "閾値" in content


def test_report_recommends_threshold_with_highest_expected_value(tmp_path):
    atr_results = {"SPY": {"median_pct": 0.10, "mean_pct": 0.10, "p25_pct": 0.08, "p75_pct": 0.12}}
    sweep_results = {
        "SPY": pd.DataFrame({
            "threshold": [0.5, 0.6, 0.7],
            "trade_count": [200, 100, 30],
            "win_count": [105, 55, 18],
            "win_rate": [0.525, 0.55, 0.60],
            "avg_pnl_pct": [0.02, 0.05, 0.10],
        }),
    }
    out_path = tmp_path / "report.md"
    generate_calibration_report(
        atr_results=atr_results,
        sweep_results=sweep_results,
        output_path=out_path,
        period_start="2024-01-01",
        period_end="2024-12-31",
    )
    content = out_path.read_text()
    # 期待値（avg_pnl_pct × trade_count）
    # 0.5: 4.0、0.6: 5.0、0.7: 3.0 → 0.6 推奨
    assert "0.6" in content
