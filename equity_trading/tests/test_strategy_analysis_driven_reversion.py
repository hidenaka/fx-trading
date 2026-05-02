import numpy as np
import pandas as pd

from equity_trading.src.strategy.strategies.analysis_driven_reversion import (
    AnalysisDrivenReversionStrategy,
)


def _make_bars(n: int, start: str = "2024-01-15 14:30") -> pd.DataFrame:
    np.random.seed(42)
    closes = 100.0 + np.cumsum(np.random.randn(n) * 0.1)
    return pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes, "volume": [10000] * n},
        index=pd.date_range(start, periods=n, freq="5min", tz="UTC"),
    )


def _daily_above_ma(n: int = 250) -> pd.DataFrame:
    closes = pd.Series(100.0 + np.linspace(0, 20, n))
    return pd.DataFrame(
        {"close": closes.values},
        index=pd.date_range("2023-01-01", periods=n, freq="1D", tz="UTC"),
    )


def test_analysis_driven_has_correct_name():
    assert AnalysisDrivenReversionStrategy().name == "analysis_driven_reversion"


def test_returns_bool_series():
    s = AnalysisDrivenReversionStrategy()
    bars = _make_bars(100)
    daily = _daily_above_ma()
    signal = s.compute_entry_signal(bars, daily, atr_pct=0.10, params={"threshold": 0.3})
    assert len(signal) == len(bars)
    assert signal.dtype == bool or signal.dtype == "bool"


def test_blocks_ny_lunch_hours_11_and_12():
    """NY 11-12時に出るシグナルは抑制される（SPYフィルタはオフ）."""
    s = AnalysisDrivenReversionStrategy()
    # 5min bars 14:30 UTC = 09:30 NY (winter). To hit NY 11:00 UTC = 16:00.
    # We'll drop a forced-True signal at NY 11:30 and confirm it gets blocked.
    n = 200
    closes = np.full(n, 100.0)
    bars = pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes, "volume": [10000] * n},
        index=pd.date_range("2024-01-15 14:30", periods=n, freq="5min", tz="UTC"),
    )

    # We need to inject a base-signal True at a NY 11-12 hour. Easiest: use the
    # strategy's own logic and check the post-filter signal.
    # NY 11:00 = 16:00 UTC = bar (16:00 - 14:30) / 5min = 18 bars in.
    # NY 12:00 = 17:00 UTC = bar 30.
    daily = _daily_above_ma()
    signal = s.compute_entry_signal(
        bars, daily, atr_pct=0.10,
        params={"threshold": 0.0, "block_lunch_hours": [11, 12]},  # threshold 0 → all bars trigger base
    )
    # With threshold=0, the base mean_reversion signal would fire on every bar
    # where 200d MA filter is True. But the lunch filter should still block
    # NY hours 11 and 12.
    ny_hours = signal.index.tz_convert("America/New_York").hour
    blocked_mask = pd.Series(ny_hours, index=bars.index).isin([11, 12])
    # No signal on any NY 11-12 bar
    assert not signal[blocked_mask].any()


def test_blocks_when_spy_intraday_negative():
    """SPY 5min が同日寄り比でマイナスのときは抑制."""
    s = AnalysisDrivenReversionStrategy()
    n = 50
    # Bars at NY 09:30+ (so not lunch hours)
    closes = np.full(n, 100.0)
    bars = pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes, "volume": [10000] * n},
        index=pd.date_range("2024-01-15 14:30", periods=n, freq="5min", tz="UTC"),
    )
    daily = _daily_above_ma()
    # SPY 5min: opens at 100 then drops to 99.5 → intraday -0.5%
    spy_closes = np.linspace(100.0, 99.5, n)
    spy = pd.DataFrame(
        {"open": [100.0] + list(spy_closes[:-1]), "high": spy_closes + 0.05, "low": spy_closes - 0.05,
         "close": spy_closes, "volume": [50000] * n},
        index=bars.index,
    )

    signal = s.compute_entry_signal(
        bars, daily, atr_pct=0.10,
        params={"threshold": 0.0, "require_spy_up": True, "_spy_5min": spy},
    )
    # SPY is down all day → no signals at all
    assert not signal.any()


def test_allows_when_spy_intraday_positive_and_outside_lunch():
    """SPY 上昇 + ランチ外なら base 信号は通る."""
    s = AnalysisDrivenReversionStrategy()
    # 12 bars at NY 10:00-10:55 (15:00-15:55 UTC, winter), all outside NY 11-12
    n = 12
    closes = np.full(n, 100.0)
    bars = pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes, "volume": [10000] * n},
        index=pd.date_range("2024-01-15 15:00", periods=n, freq="5min", tz="UTC"),  # NY 10:00-10:55
    )
    daily = _daily_above_ma()
    spy_closes = np.linspace(100.0, 100.5, 12)  # SPY rising
    spy = pd.DataFrame(
        {"open": [100.0] * 12, "high": spy_closes + 0.05, "low": spy_closes - 0.05,
         "close": spy_closes, "volume": [50000] * 12},
        index=bars.index,
    )

    signal = s.compute_entry_signal(
        bars, daily, atr_pct=0.10,
        params={"threshold": 0.0, "require_spy_up": True, "_spy_5min": spy},
    )
    # threshold=0 + 200d MA above + SPY up + outside lunch → at least one signal
    assert signal.any()
