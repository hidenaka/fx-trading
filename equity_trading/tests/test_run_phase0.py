"""Phase 0 統合スクリプトの E2E テスト（モック使用）."""
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest


def _make_synthetic_bars(n: int, freq: str = "5min") -> pd.DataFrame:
    np.random.seed(42)
    closes = 100.0 + np.cumsum(np.random.randn(n) * 0.1)
    return pd.DataFrame(
        {
            "open": closes,
            "high": closes + 0.05,
            "low": closes - 0.05,
            "close": closes,
            "volume": [10000] * n,
        },
        index=pd.date_range("2024-01-01", periods=n, freq=freq, tz="UTC"),
    )


def test_run_phase0_e2e_creates_report(tmp_path, monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "PKTEST")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "secret")
    monkeypatch.setenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "data" / "prices").mkdir(parents=True)
    (project_root / "phase0").mkdir()

    bars_5min = _make_synthetic_bars(500, freq="5min")
    bars_daily = _make_synthetic_bars(500, freq="1D")

    with patch(
        "equity_trading.src.broker.alpaca_client.StockHistoricalDataClient"
    ) as mock_data, patch(
        "equity_trading.src.broker.alpaca_client.TradingClient"
    ):
        # MagicMock の get_stock_bars を呼んだら 5min/daily を返す
        def fake_get_bars(req):
            if hasattr(req, 'timeframe') and 'Day' in str(req.timeframe):
                return type("X", (), {"df": bars_daily})()
            return type("X", (), {"df": bars_5min})()
        mock_data.return_value.get_stock_bars.side_effect = fake_get_bars

        from equity_trading.scripts.run_phase0 import main

        report_path = project_root / "phase0" / "calibration_report.md"
        cache_dir = project_root / "data" / "prices"

        main(
            symbols=["SPY"],
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2024, 1, 31, tzinfo=timezone.utc),
            thresholds=[0.5, 0.6],
            cache_dir=cache_dir,
            report_path=report_path,
        )

    assert report_path.exists()
    content = report_path.read_text()
    assert "SPY" in content
    assert "Phase 0" in content
