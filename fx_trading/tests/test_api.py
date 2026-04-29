import json
import os
import tempfile
from src.api.data_exporter import DataExporter

def test_exporter_creates_json_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        exporter = DataExporter(output_dir=tmpdir)
        data = {
            "total_pnl": 5000,
            "win_rate": 0.6,
            "trades": [{"instrument": "USD_JPY", "pnl": 100}],
        }
        filepath = exporter.export_backtest_result("test_strategy", data)
        assert os.path.exists(filepath)
        with open(filepath) as f:
            loaded = json.load(f)
        assert loaded["total_pnl"] == 5000

def test_exporter_exports_portfolio():
    with tempfile.TemporaryDirectory() as tmpdir:
        exporter = DataExporter(output_dir=tmpdir)
        portfolio = {
            "capital": 1000000,
            "positions": [{"instrument": "USD_JPY", "units": 1000}],
            "daily_pnl": 2000,
        }
        filepath = exporter.export_portfolio(portfolio)
        assert os.path.exists(filepath)
