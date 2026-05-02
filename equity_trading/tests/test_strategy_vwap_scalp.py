import numpy as np
import pandas as pd

from equity_trading.src.strategy.strategies.vwap_scalp import VWAPScalpStrategy


def _daily_above_ma(n: int = 250) -> pd.DataFrame:
    closes = pd.Series(100.0 + np.linspace(0, 20, n))
    return pd.DataFrame(
        {"close": closes.values},
        index=pd.date_range("2023-01-01", periods=n, freq="1D", tz="UTC"),
    )


def _daily_below_ma(n: int = 250) -> pd.DataFrame:
    return pd.DataFrame(
        {"close": [50.0] * n},
        index=pd.date_range("2023-01-01", periods=n, freq="1D", tz="UTC"),
    )


def _bars(closes: np.ndarray, volumes: list[int] | None = None) -> pd.DataFrame:
    n = len(closes)
    if volumes is None:
        volumes = [10000] * n
    return pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes, "volume": volumes},
        index=pd.date_range("2024-01-15 14:30", periods=n, freq="5min", tz="UTC"),
    )


def test_vwap_scalp_has_correct_name():
    assert VWAPScalpStrategy().name == "vwap_scalp"


def test_vwap_scalp_returns_bool_series():
    s = VWAPScalpStrategy()
    np.random.seed(42)
    closes = 100.0 + np.cumsum(np.random.randn(100) * 0.1)
    signal = s.compute_entry_signal(_bars(closes), _daily_above_ma(), atr_pct=0.10, params={"k_entry": 1.5})
    assert len(signal) == 100
    assert signal.dtype == bool or signal.dtype == "bool"


def test_vwap_scalp_no_signal_when_below_200ma():
    s = VWAPScalpStrategy()
    closes = np.full(100, 100.0)
    signal = s.compute_entry_signal(_bars(closes), _daily_below_ma(), atr_pct=0.10, params={"k_entry": 1.5})
    assert not signal.any()


def test_vwap_scalp_signal_when_close_well_below_vwap():
    """Volume-weighted: heavy volume at high price → high VWAP. Then a sharp drop in close fires the signal."""
    s = VWAPScalpStrategy()
    n = 30
    # Bars 0..14: close 100, 15..29: close 99 (1% drop). Heavy volume on the high-priced bars to anchor VWAP up.
    closes = np.array([100.0] * 15 + [99.0] * 15)
    volumes = [50000] * 15 + [10000] * 15
    bars = _bars(closes, volumes=volumes)
    signal = s.compute_entry_signal(bars, _daily_above_ma(), atr_pct=0.05, params={"k_entry": 1.0})
    # In the latter half, close (99) is well below VWAP (~99.7+); deviation > 1.0 * 0.05% = 0.05%
    # In fraction: deviation_required = atr_pct/100 * k_entry = 0.0005. Actual dev (vwap-close)/close ~ 0.7/99 = ~0.007 (0.7%) >> 0.05%
    assert signal.iloc[20:].any()


def test_vwap_scalp_no_signal_when_close_at_or_above_vwap():
    """Close >= VWAP -> never fire."""
    s = VWAPScalpStrategy()
    closes = np.full(50, 100.0)  # Constant; VWAP == close -> deviation 0
    signal = s.compute_entry_signal(_bars(closes), _daily_above_ma(), atr_pct=0.10, params={"k_entry": 1.0})
    assert not signal.any()
