import os
import tempfile
from src.monitoring.logger import TradeLogger

def test_logger_creates_log_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = os.path.join(tmpdir, "trades.log")
        logger = TradeLogger(log_file=log_file)
        logger.log_trade("USD_JPY", "BUY", 1000, 150.0)
        assert os.path.exists(log_file)
        with open(log_file) as f:
            content = f.read()
        assert "USD_JPY" in content
        assert "BUY" in content

def test_logger_logs_error():
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = os.path.join(tmpdir, "errors.log")
        logger = TradeLogger(log_file=log_file)
        logger.log_error("API connection failed")
        with open(log_file) as f:
            content = f.read()
        assert "ERROR" in content
        assert "API connection failed" in content
