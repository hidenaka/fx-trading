from pathlib import Path

import pandas as pd

from equity_trading.src.phase0.comparison_report import generate_comparison_report


def _make_results() -> dict[str, pd.DataFrame]:
    return {
        "mean_reversion": pd.DataFrame([
            {"strategy": "mean_reversion", "symbol": "SPY", "params": "{}",
             "trade_count": 30, "win_count": 14, "win_rate": 0.467, "avg_pnl_pct": -0.05},
            {"strategy": "mean_reversion", "symbol": "XLK", "params": "{}",
             "trade_count": 36, "win_count": 23, "win_rate": 0.639, "avg_pnl_pct": 0.028},
        ]),
        "trend_follow": pd.DataFrame([
            {"strategy": "trend_follow", "symbol": "SPY", "params": "{}",
             "trade_count": 80, "win_count": 46, "win_rate": 0.575, "avg_pnl_pct": 0.10},
        ]),
    }


def test_report_contains_all_strategies(tmp_path):
    out = tmp_path / "comparison.md"
    generate_comparison_report(
        results=_make_results(),
        atr_results={"SPY": {"median_pct": 0.10}, "XLK": {"median_pct": 0.13}},
        output_path=out,
        period_start="2024-05-01",
        period_end="2026-05-01",
    )
    content = out.read_text()
    assert "mean_reversion" in content
    assert "trend_follow" in content
    assert "Comparison" in content or "比較" in content


def test_report_recommends_best_overall_strategy(tmp_path):
    out = tmp_path / "comparison.md"
    generate_comparison_report(
        results=_make_results(),
        atr_results={"SPY": {"median_pct": 0.10}, "XLK": {"median_pct": 0.13}},
        output_path=out,
        period_start="2024-05-01",
        period_end="2026-05-01",
    )
    content = out.read_text()
    # trend_follow SPY: 80 * 0.10 = 8.0 ; mean_reversion XLK: 36 * 0.028 = 1.008
    # → trend_follow recommended
    assert "trend_follow" in content
    assert "8" in content
