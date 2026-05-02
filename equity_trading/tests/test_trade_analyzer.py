import numpy as np
import pandas as pd
import pytest

from equity_trading.src.phase0.trade_analyzer import analyze_trades


def _make_bars(n: int = 200) -> pd.DataFrame:
    np.random.seed(42)
    closes = 100.0 + np.cumsum(np.random.randn(n) * 0.1)
    return pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes, "volume": [10000] * n},
        index=pd.date_range("2024-01-15 14:30", periods=n, freq="5min", tz="UTC"),
    )


def _make_daily(n: int = 250) -> pd.DataFrame:
    return pd.DataFrame(
        {"close": list(np.linspace(80, 120, n))},
        index=pd.date_range("2023-01-01", periods=n, freq="1D", tz="UTC"),
    )


def _make_trades_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=[
        "entry_ts", "exit_ts", "entry_price", "exit_price",
        "exit_type", "bars_held", "pnl_pct",
    ])


def test_analyze_empty_trades_returns_zero_record():
    bars = _make_bars()
    daily = _make_daily()
    trades = _make_trades_df([])
    out = analyze_trades(trades, bars, daily)
    assert out["n_trades"] == 0
    assert out["n_wins"] == 0
    assert pd.isna(out["win_rate"])


def test_analyze_basic_summary():
    bars = _make_bars()
    daily = _make_daily()
    trades = _make_trades_df([
        {"entry_ts": bars.index[10], "exit_ts": bars.index[11],
         "entry_price": 100.0, "exit_price": 100.5,
         "exit_type": "target", "bars_held": 1, "pnl_pct": 0.0005},
        {"entry_ts": bars.index[20], "exit_ts": bars.index[21],
         "entry_price": 100.0, "exit_price": 99.8,
         "exit_type": "stop", "bars_held": 1, "pnl_pct": -0.002},
    ])
    out = analyze_trades(trades, bars, daily)
    assert out["n_trades"] == 2
    assert out["n_wins"] == 1
    assert out["win_rate"] == pytest.approx(0.5)
    assert out["exit_breakdown"]["target"] == 1
    assert out["exit_breakdown"]["stop"] == 1
    assert out["exit_breakdown"]["time"] == 0


def test_analyze_hour_breakdown():
    bars = _make_bars()
    daily = _make_daily()
    # Build trades at distinct NY hours by selecting bars at known timestamps.
    # bars index starts at 2024-01-15 14:30 UTC = 09:30 NY (winter).
    # 5min increments: bar 0 = 09:30, bar 12 = 10:30, bar 24 = 11:30, etc.
    rows = []
    for bi in [0, 12, 24]:
        rows.append({
            "entry_ts": bars.index[bi],
            "exit_ts": bars.index[bi + 1],
            "entry_price": 100.0, "exit_price": 100.5,
            "exit_type": "target", "bars_held": 1, "pnl_pct": 0.0005,
        })
    trades = _make_trades_df(rows)
    out = analyze_trades(trades, bars, daily)
    hod = out["wr_by_hour_of_day"]
    assert isinstance(hod, pd.DataFrame)
    assert {"hour", "n_trades", "n_wins", "win_rate", "avg_pnl_pct"}.issubset(hod.columns)
    # Three distinct hours represented (9, 10, 11 NY)
    assert set(hod["hour"]) == {9, 10, 11}


def test_analyze_spy_regime_optional():
    bars = _make_bars()
    daily = _make_daily()
    trades = _make_trades_df([
        {"entry_ts": bars.index[10], "exit_ts": bars.index[11],
         "entry_price": 100.0, "exit_price": 100.5,
         "exit_type": "target", "bars_held": 1, "pnl_pct": 0.0005},
    ])
    # Without spy_daily -> key absent
    out = analyze_trades(trades, bars, daily)
    assert "wr_by_spy_regime" not in out
    # With spy_daily -> key present
    spy = _make_daily()  # arbitrary; first row's prev-close is undefined -> up regime by convention
    out2 = analyze_trades(trades, bars, daily, spy_daily=spy)
    assert "wr_by_spy_regime" in out2
    assert isinstance(out2["wr_by_spy_regime"], pd.DataFrame)
