"""Risk profile section computations."""
from __future__ import annotations

import pandas as pd


def _make_trades(rows):
    df = pd.DataFrame(rows)
    df["entry_ts"] = pd.to_datetime(df["entry_ts"], utc=True)
    df["exit_ts"] = pd.to_datetime(df["exit_ts"], utc=True)
    return df


def test_symbol_contribution_basic():
    from equity_trading.src.validation.risk_profile import compute_symbol_contribution
    trades = _make_trades([
        {"entry_ts": "2024-06-01", "exit_ts": "2024-06-01 16:00",
         "symbol": "TECL", "pnl_pct": 0.01, "position_dollars": 25000},
        {"entry_ts": "2024-06-02", "exit_ts": "2024-06-02 16:00",
         "symbol": "TECL", "pnl_pct": -0.005, "position_dollars": 25000},
        {"entry_ts": "2024-06-03", "exit_ts": "2024-06-03 16:00",
         "symbol": "TQQQ", "pnl_pct": 0.02, "position_dollars": 25000},
    ])
    df = compute_symbol_contribution(trades)
    tecl = df[df["symbol"] == "TECL"].iloc[0]
    tqqq = df[df["symbol"] == "TQQQ"].iloc[0]
    # TECL: 250 - 125 = 125 P&L; TQQQ: 500 P&L
    assert abs(tecl["gross_pnl_dollars"] - 125.0) < 0.01
    assert abs(tqqq["gross_pnl_dollars"] - 500.0) < 0.01
    total = 125.0 + 500.0
    # pct_of_total uses absolute values, so TECL has 125/625 = 20%
    assert abs(tecl["pct_of_total"] - 125.0 / total * 100) < 0.01


def test_pairwise_correlation_diagonal_one():
    from equity_trading.src.validation.risk_profile import compute_pairwise_correlation
    trades = _make_trades([
        {"entry_ts": "2024-06-01", "exit_ts": "2024-06-01 16:00",
         "symbol": "TECL", "pnl_pct": 0.01, "position_dollars": 25000},
        {"entry_ts": "2024-06-01", "exit_ts": "2024-06-01 16:00",
         "symbol": "TQQQ", "pnl_pct": 0.012, "position_dollars": 25000},
        {"entry_ts": "2024-06-02", "exit_ts": "2024-06-02 16:00",
         "symbol": "TECL", "pnl_pct": -0.005, "position_dollars": 25000},
        {"entry_ts": "2024-06-02", "exit_ts": "2024-06-02 16:00",
         "symbol": "TQQQ", "pnl_pct": -0.004, "position_dollars": 25000},
    ])
    corr = compute_pairwise_correlation(trades)
    assert abs(corr.loc["TECL", "TECL"] - 1.0) < 1e-9
    assert abs(corr.loc["TQQQ", "TQQQ"] - 1.0) < 1e-9
    assert abs(corr.loc["TECL", "TQQQ"] - corr.loc["TQQQ", "TECL"]) < 1e-9


def test_stress_overlap_counts_simultaneous_holdings():
    from equity_trading.src.validation.risk_profile import compute_stress_overlap
    trades = _make_trades([
        {"entry_ts": "2024-06-01 10:00", "exit_ts": "2024-06-01 15:00",
         "symbol": "TECL", "pnl_pct": -0.02, "position_dollars": 25000},
        {"entry_ts": "2024-06-01 10:30", "exit_ts": "2024-06-01 15:00",
         "symbol": "TQQQ", "pnl_pct": -0.01, "position_dollars": 25000},
        {"entry_ts": "2024-06-01 10:30", "exit_ts": "2024-06-01 15:00",
         "symbol": "TNA", "pnl_pct": -0.015, "position_dollars": 25000},
    ])
    result = compute_stress_overlap(trades, min_concurrent=3)
    assert result["overlap_windows"] == 1
    assert result["all_losing_windows"] == 1


def test_render_risk_profile_section_contains_all_subsections():
    from equity_trading.src.validation.risk_profile import render_risk_profile_md
    trades = _make_trades([
        {"entry_ts": "2024-06-01", "exit_ts": "2024-06-01 16:00",
         "symbol": "TECL", "pnl_pct": 0.01, "position_dollars": 25000},
        {"entry_ts": "2024-06-02", "exit_ts": "2024-06-02 16:00",
         "symbol": "TQQQ", "pnl_pct": -0.01, "position_dollars": 25000},
    ])
    md = render_risk_profile_md(trades)
    assert "## Risk profile" in md
    assert "Symbol contribution" in md
    assert "correlation" in md.lower()
    assert "Stress overlap" in md
