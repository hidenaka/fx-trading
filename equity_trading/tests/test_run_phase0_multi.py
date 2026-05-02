"""マルチ戦略 Phase 0 CLI の E2E テスト（モック）."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd


def _make_bars(n: int, freq: str = "5min") -> pd.DataFrame:
    np.random.seed(42)
    closes = 100.0 + np.cumsum(np.random.randn(n) * 0.1)
    return pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes, "volume": [10000] * n},
        index=pd.date_range("2024-01-01", periods=n, freq=freq, tz="UTC"),
    )


def test_run_phase0_multi_e2e_creates_report(tmp_path, monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "PKTEST")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "secret")
    monkeypatch.setenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

    project_root = tmp_path / "project"
    (project_root / "data" / "prices").mkdir(parents=True)
    (project_root / "phase0").mkdir(parents=True)

    bars_5min = _make_bars(500, freq="5min")
    bars_daily = _make_bars(500, freq="1D")

    with patch(
        "equity_trading.src.broker.alpaca_client.StockHistoricalDataClient"
    ) as mock_data, patch(
        "equity_trading.src.broker.alpaca_client.TradingClient"
    ):
        def fake_get_bars(req):
            if hasattr(req, "timeframe") and "Day" in str(req.timeframe):
                return type("X", (), {"df": bars_daily})()
            return type("X", (), {"df": bars_5min})()
        mock_data.return_value.get_stock_bars.side_effect = fake_get_bars

        from equity_trading.scripts.run_phase0_multi import main

        report_path = project_root / "phase0" / "comparison_report.md"
        cache_dir = project_root / "data" / "prices"

        main(
            symbols=["SPY"],
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2024, 1, 31, tzinfo=timezone.utc),
            cache_dir=cache_dir,
            report_path=report_path,
        )

    assert report_path.exists()
    content = report_path.read_text()
    assert "mean_reversion" in content
    assert "trend_follow" in content
    assert "momentum_breakout" in content
    assert "env_dependent_reversion" in content
    assert "multi_timeframe" in content
