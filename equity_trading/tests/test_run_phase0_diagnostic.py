"""診断ランナーの E2E スモーク。実データではなくダミーで配線確認."""
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


def _make_bars(n: int, freq: str = "5min") -> pd.DataFrame:
    np.random.seed(42)
    closes = 100.0 + np.cumsum(np.random.randn(n) * 0.1)
    return pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes, "volume": [10000] * n},
        index=pd.date_range("2024-01-15 14:30", periods=n, freq=freq, tz="UTC"),
    )


def test_diagnostic_main_creates_report(tmp_path):
    cache_dir = tmp_path / "prices"
    cache_dir.mkdir()
    # Write tiny parquet caches with the names the script will look up.
    bars5 = _make_bars(500, "5min")
    bars1d = _make_bars(500, "1D")
    for sym in ["SPY", "XLK"]:
        # Match the cache naming convention used by PriceFetcher / _load_cached_bars:
        # {symbol}_{timeframe}_{start_YYYYMMDDTHHmm}_{end_YYYYMMDDTHHmm}.parquet
        bars5.to_parquet(cache_dir / f"{sym}_5min_2024-05-01T0000_2026-05-01T0000.parquet")
        bars1d.to_parquet(cache_dir / f"{sym}_1day_2024-05-01T0000_2026-05-01T0000.parquet")

    from equity_trading.scripts.run_phase0_diagnostic import main

    report_path = tmp_path / "analysis_report.md"
    main(
        cache_dir=cache_dir,
        report_path=report_path,
        period_start=datetime(2024, 5, 1, tzinfo=timezone.utc),
        period_end=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    assert report_path.exists()
    content = report_path.read_text()
    assert "mean_reversion" in content
    assert "XLK" in content
