"""Phase A search runner."""
from __future__ import annotations

import pandas as pd
import pytest


def test_eval_threshold_all_pass():
    from equity_trading.scripts.run_phase_a_search import _eval_threshold
    summary = {"annualized_pct": 0.5, "max_dd_pct": -10.0, "sharpe": 0.1}
    assert _eval_threshold(summary, worst_trade_pct=-3.0) == []


def test_eval_threshold_ann_fail():
    from equity_trading.scripts.run_phase_a_search import _eval_threshold
    summary = {"annualized_pct": -5.0, "max_dd_pct": -10.0, "sharpe": 0.0}
    assert "ann" in _eval_threshold(summary, worst_trade_pct=-3.0)


def test_eval_threshold_dd_fail():
    from equity_trading.scripts.run_phase_a_search import _eval_threshold
    summary = {"annualized_pct": 0.0, "max_dd_pct": -25.0, "sharpe": 0.0}
    assert "MaxDD" in _eval_threshold(summary, worst_trade_pct=-3.0)


def test_eval_threshold_worst_fail():
    from equity_trading.scripts.run_phase_a_search import _eval_threshold
    summary = {"annualized_pct": 0.0, "max_dd_pct": -10.0, "sharpe": 0.0}
    assert "worst" in _eval_threshold(summary, worst_trade_pct=-7.0)


def test_eval_threshold_sharpe_fail():
    from equity_trading.scripts.run_phase_a_search import _eval_threshold
    summary = {"annualized_pct": 0.0, "max_dd_pct": -10.0, "sharpe": -0.5}
    assert "Sharpe" in _eval_threshold(summary, worst_trade_pct=-3.0)


def test_render_md_no_candidate_passes():
    from equity_trading.scripts.run_phase_a_search import _render_md
    rows = [
        {"variant_id": "v_a", "ann": -5.0, "dd": -22.0, "worst": -6.0, "sharpe": -0.4,
         "n": 100, "fails": ["ann", "MaxDD", "worst", "Sharpe"]},
    ]
    md = _render_md(rows)
    assert "## No candidate passes" in md
    assert "v_a" in md


def test_render_md_top_by_ann():
    from equity_trading.scripts.run_phase_a_search import _render_md
    rows = [
        {"variant_id": "v_a", "ann": -1.0, "dd": -10.0, "worst": -3.0, "sharpe": -0.1,
         "n": 100, "fails": []},
        {"variant_id": "v_b", "ann": +0.5, "dd": -8.0, "worst": -3.5, "sharpe": +0.05,
         "n": 90, "fails": []},
    ]
    md = _render_md(rows)
    assert "## Top by ann return" in md
    assert "v_b" in md  # v_b has higher ann


def test_search_does_not_read_holdout(tmp_path, monkeypatch):
    """Phase A search must not call EvaluationContext.load_holdout_bars or
    instantiate EvaluationContext."""
    import equity_trading.src.validation.data as D

    holdout_calls: list = []

    class _ForbiddenCtx:
        def __init__(self, *a, **kw):
            holdout_calls.append("init")
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def load_holdout_bars(self, *a, **kw):
            holdout_calls.append("load")

    monkeypatch.setattr(D, "EvaluationContext", _ForbiddenCtx)

    # Stub load_train2/valid2 + simulate to avoid needing real data
    import equity_trading.src.validation.internal_split as IS
    monkeypatch.setattr(IS, "load_train2_bars", lambda r, s, timeframe_minutes: pd.DataFrame())
    monkeypatch.setattr(IS, "load_valid2_bars", lambda r, s, timeframe_minutes: pd.DataFrame())
    import equity_trading.src.validation.runner as R
    monkeypatch.setattr(
        R, "simulate_strategy",
        lambda **kw: ({"trade_count": 0}, pd.DataFrame(
            columns=["entry_ts", "exit_ts", "pnl_pct"])),
    )

    # Build minimal phase_a dir with one yaml
    pa = tmp_path / "phase_a"
    pa.mkdir()
    (pa / "v_test.yaml").write_text(
        "variant_id: v_test\n"
        "description: ''\n"
        "strategies:\n"
        "  - class: OpeningRangeBreakoutStrategy\n"
        "    symbols: [TECL]\n"
        "    params: { or_window_bars: 12, stop_mult: 0.0, target_mult: 1.0,\n"
        "              cost_pct: 0.10, catastrophic_stop_pct: 5.0 }\n"
        "portfolio: { position_size_pct: 0.25, max_concurrent: 3, starting_equity_usd: 100000 }\n"
        "gates:\n"
        "  oos: { holdout_start: '2024-05-01', holdout_end: '2026-05-01', min_outperformance_pct: 0.0 }\n"
        "  tail_risk: { max_single_trade_loss_pct: 5.0, max_portfolio_dd_pct: 20.0, max_rolling_30d_loss_pct: 10.0 }\n"
        "  sample_size: { min_holdout_trades: 30 }\n"
    )
    out = tmp_path / "out.md"
    fake_vix = pd.DataFrame({"close": [20.0]},
                             index=pd.date_range("2022-01-01", periods=1, freq="1D", tz="UTC"))

    from equity_trading.scripts.run_phase_a_search import run_search
    run_search(configs_dir=pa, data_root=tmp_path, output=out, vix_daily=fake_vix)
    assert holdout_calls == [], f"Phase A search touched holdout: {holdout_calls}"
