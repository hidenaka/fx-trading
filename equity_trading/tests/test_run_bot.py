"""Run-bot CLI smoke tests with mocked Alpaca."""
import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


@pytest.fixture
def paper_env(monkeypatch, tmp_path):
    """Set Paper env vars + isolated cache + db."""
    monkeypatch.setenv("ALPACA_API_KEY", "PKTEST")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "secret")
    monkeypatch.setenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
    return tmp_path


def test_run_bot_rejects_non_paper(monkeypatch, capsys):
    monkeypatch.setenv("ALPACA_API_KEY", "PKLIVE")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "s")
    monkeypatch.setenv("ALPACA_BASE_URL", "https://api.alpaca.markets")  # NO paper-api
    from equity_trading.scripts.run_bot import main
    rc = main(["--morning"])
    assert rc != 0
    out = capsys.readouterr().out + capsys.readouterr().err
    # Either 'paper' or 'refuse' or 'reject' should appear
    assert "paper" in out.lower() or "live" in out.lower() or "refus" in out.lower()


def test_run_bot_morning_mode_dispatches(paper_env, monkeypatch):
    """--morning mode calls run_morning."""
    from equity_trading.scripts import run_bot

    called = {"morning": False, "intraday": False, "eod": False}

    def fake_morning(*args, **kwargs):
        called["morning"] = True
        return {"entries_placed": 0, "errors": []}
    def fake_intraday(*args, **kwargs):
        called["intraday"] = True
        return {"entries_placed": 0, "errors": []}
    def fake_eod(*args, **kwargs):
        called["eod"] = True
        return {"positions_closed": 0, "errors": [], "summary_md": "# OK\n"}

    monkeypatch.setattr(run_bot, "run_morning", fake_morning)
    monkeypatch.setattr(run_bot, "run_intraday", fake_intraday)
    monkeypatch.setattr(run_bot, "run_eod", fake_eod)

    with patch(
        "equity_trading.src.broker.alpaca_client.TradingClient"
    ), patch(
        "equity_trading.src.broker.alpaca_client.StockHistoricalDataClient"
    ):
        rc = run_bot.main(["--morning", "--db-path", str(paper_env / "t.db")])

    assert rc == 0
    assert called == {"morning": True, "intraday": False, "eod": False}


def test_run_bot_intraday_mode_dispatches(paper_env, monkeypatch):
    from equity_trading.scripts import run_bot

    called = {"morning": False, "intraday": False, "eod": False}
    monkeypatch.setattr(run_bot, "run_morning", lambda *a, **k: called.update(morning=True))
    monkeypatch.setattr(run_bot, "run_intraday", lambda *a, **k: called.update(intraday=True) or {"entries_placed": 0, "errors": []})
    monkeypatch.setattr(run_bot, "run_eod", lambda *a, **k: called.update(eod=True))

    with patch("equity_trading.src.broker.alpaca_client.TradingClient"), patch(
        "equity_trading.src.broker.alpaca_client.StockHistoricalDataClient"
    ):
        rc = run_bot.main(["--intraday", "--db-path", str(paper_env / "t.db")])
    assert rc == 0
    assert called["intraday"] is True


def test_run_bot_eod_mode_dispatches(paper_env, monkeypatch):
    from equity_trading.scripts import run_bot

    called = {"eod": False}
    monkeypatch.setattr(run_bot, "run_morning", lambda *a, **k: None)
    monkeypatch.setattr(run_bot, "run_intraday", lambda *a, **k: None)
    monkeypatch.setattr(run_bot, "run_eod", lambda *a, **k: (
        called.update(eod=True) or {"positions_closed": 0, "errors": [], "summary_md": "# OK\n"}
    ))

    with patch("equity_trading.src.broker.alpaca_client.TradingClient"), patch(
        "equity_trading.src.broker.alpaca_client.StockHistoricalDataClient"
    ):
        rc = run_bot.main(["--eod", "--db-path", str(paper_env / "t.db")])
    assert rc == 0
    assert called["eod"] is True
