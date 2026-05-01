import json
import logging
from io import StringIO

from equity_trading.src.monitor.logger import setup_logger, JsonFormatter


def test_logger_outputs_json_with_utc_timestamp():
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("test_logger_utc")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    logger.info("hello", extra={"foo": "bar"})

    line = stream.getvalue().strip()
    parsed = json.loads(line)
    assert parsed["level"] == "INFO"
    assert parsed["message"] == "hello"
    assert parsed["foo"] == "bar"
    assert parsed["timestamp"].endswith("Z") or "+00:00" in parsed["timestamp"]


def test_setup_logger_creates_named_logger():
    logger = setup_logger("equity_trading.test")
    assert logger.name == "equity_trading.test"
    assert logger.level == logging.INFO
