import numpy as np
import pandas as pd
import pytest

from equity_trading.src.ml.candidate_dataset import CandidateSignal, generate_candidates
from equity_trading.src.ml.outcome_labeler import LabeledCandidate, label_candidates


def _make_bars(n: int = 200, drift: float = 0.0) -> pd.DataFrame:
    np.random.seed(42)
    closes = 100.0 + np.cumsum(np.random.randn(n) * 0.1) + np.linspace(0, drift, n)
    return pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes,
         "volume": np.random.randint(5000, 20000, n).astype(float)},
        index=pd.date_range("2024-01-15 14:30", periods=n, freq="5min", tz="UTC"),
    )


def _daily_above_ma(n: int = 250) -> pd.DataFrame:
    closes = list(np.linspace(80, 120, n))
    return pd.DataFrame(
        {"close": closes, "open": closes,
         "high": [c + 0.5 for c in closes], "low": [c - 0.5 for c in closes]},
        index=pd.date_range("2023-01-01", periods=n, freq="1D", tz="UTC"),
    )


def test_labeled_candidate_dataclass_is_frozen():
    sig = CandidateSignal(
        timestamp=pd.Timestamp("2024-01-15 14:30", tz="UTC"),
        symbol="XLK", strategy_name="mean_reversion", features={}, bar_index=10,
    )
    lc = LabeledCandidate(signal=sig, win=True, pnl_pct=0.001, exit_type="target", bars_held=3)
    with pytest.raises((AttributeError, ValueError)):
        lc.win = False  # type: ignore


def test_label_candidates_empty_list_returns_empty():
    bars = _make_bars()
    daily = _daily_above_ma()
    out = label_candidates(
        candidates=[], bars_5min=bars, daily=daily, atr_pct=0.10, base_params={},
    )
    assert out == []


def test_label_candidates_assigns_win_loss_per_outcome():
    """Generate candidates, label them, verify each has reasonable fields."""
    bars = _make_bars(200)
    daily = _daily_above_ma()
    candidates = generate_candidates(
        bars_5min=bars, daily=daily, spy_5min=None,
        symbol="XLK", strategy_name="mean_reversion",
        relaxed_params={"threshold": 0.05},
    )
    labeled = label_candidates(
        candidates=candidates, bars_5min=bars, daily=daily, atr_pct=0.10, base_params={},
    )
    assert len(labeled) <= len(candidates)
    if len(labeled) > 0:
        lc = labeled[0]
        assert isinstance(lc, LabeledCandidate)
        assert isinstance(lc.win, bool)
        assert isinstance(lc.pnl_pct, float)
        assert lc.exit_type in {"stop", "target", "time"}
        # win and pnl_pct must agree
        assert lc.win == (lc.pnl_pct > 0)


def test_label_candidates_skips_signal_at_last_bar():
    """If signal fires at the very last bar, no fill possible → skipped."""
    bars = _make_bars(50)
    daily = _daily_above_ma()
    # Manually create a candidate at the last bar
    last_idx = len(bars) - 1
    candidate = CandidateSignal(
        timestamp=bars.index[last_idx],
        symbol="XLK", strategy_name="mean_reversion",
        features={"score_value": 0.5},
        bar_index=last_idx,
    )
    labeled = label_candidates(
        candidates=[candidate],
        bars_5min=bars, daily=daily, atr_pct=0.10, base_params={},
    )
    # Last-bar entry can't fill (no next bar to fill on)
    assert len(labeled) == 0


def test_simulate_single_trade_helper_works():
    """Direct unit test of the simulator helper."""
    from equity_trading.src.phase0.strategy_simulator import simulate_single_trade
    from equity_trading.src.strategy.strategies.mean_reversion import MeanReversionStrategy

    n = 50
    closes = np.full(n, 100.0)
    closes[5:] = 99.50  # -0.5% drop after bar 5
    bars = pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes,
         "volume": [10000] * n},
        index=pd.date_range("2024-01-01 14:30", periods=n, freq="5min", tz="UTC"),
    )
    s = MeanReversionStrategy()
    # Signal at bar 0; entry fills at bar 1 (closes[1] = 100.0). Default ATR=0.10:
    #   stop_pct = 0.10*1.5/100 = 0.0015 → stop_price = 99.85
    # Bar 5 onwards close = 99.50 < 99.85 → STOP exit at bar 5.
    trade = simulate_single_trade(
        strategy=s, bars_5min=bars, entry_signal_idx=0,
        atr_pct=0.10, params={},
    )
    assert trade is not None
    assert trade["exit_type"] == "stop"
    assert trade["entry_price"] == pytest.approx(100.0)
    # bars_held = 5 - 1 = 4
    assert trade["bars_held"] == 4
