import os

import pytest

from equity_trading.src.config import Config, load_config, ConfigError


# テスト間で前のテストが設定した環境変数が残らないようにするためのキー一覧
_ENV_KEYS = [
    "ALPACA_API_KEY",
    "ALPACA_SECRET_KEY",
    "ALPACA_BASE_URL",
    "DATA_PLAN",
    "CONFIRM_LIVE",
    "INITIAL_CAPITAL_USD",
    "RISK_PER_TRADE",
    "MAX_POSITION_PCT",
    "MAX_CONCURRENT_POSITIONS",
    "MAX_TECH_EXPOSURE",
    "DAILY_LOSS_LIMIT",
    "WEEKLY_LOSS_LIMIT",
    "MONTHLY_LOSS_LIMIT",
    "CUMULATIVE_DD_LIMIT",
    "COST_WARN_THRESHOLD",
    "COST_HALT_THRESHOLD",
    "HEALTHCHECKS_INTRADAY_URL",
    "HEALTHCHECKS_EOD_URL",
    "HEALTHCHECKS_MONTHLY_URL",
    "SLACK_WEBHOOK_URL",
    "NOTIFICATION_EMAIL",
]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """各テスト前に関連環境変数をクリアして独立性を担保."""
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_load_config_from_env(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ALPACA_API_KEY=PKABCDEF\n"
        "ALPACA_SECRET_KEY=secret123\n"
        "ALPACA_BASE_URL=https://paper-api.alpaca.markets\n"
        "DATA_PLAN=free\n"
        "CONFIRM_LIVE=false\n"
        "INITIAL_CAPITAL_USD=100000\n"
        "RISK_PER_TRADE=0.005\n"
        "MAX_POSITION_PCT=0.25\n"
        "MAX_CONCURRENT_POSITIONS=3\n"
        "MAX_TECH_EXPOSURE=0.40\n"
        "DAILY_LOSS_LIMIT=0.02\n"
        "WEEKLY_LOSS_LIMIT=0.05\n"
        "MONTHLY_LOSS_LIMIT=0.08\n"
        "CUMULATIVE_DD_LIMIT=0.20\n"
        "COST_WARN_THRESHOLD=0.0013\n"
        "COST_HALT_THRESHOLD=0.0018\n"
    )
    cfg = load_config(env_path=env_file)
    assert cfg.alpaca_api_key == "PKABCDEF"
    assert cfg.alpaca_base_url == "https://paper-api.alpaca.markets"
    assert cfg.data_plan == "free"
    assert cfg.confirm_live is False
    assert cfg.initial_capital_usd == 100000.0
    assert cfg.risk_per_trade == 0.005
    assert cfg.max_position_pct == 0.25


def test_load_config_validates_risk_per_trade_too_high(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ALPACA_API_KEY=PKABCDEF\n"
        "ALPACA_SECRET_KEY=secret123\n"
        "ALPACA_BASE_URL=https://paper-api.alpaca.markets\n"
        "RISK_PER_TRADE=0.10\n"
    )
    with pytest.raises(ConfigError, match="RISK_PER_TRADE"):
        load_config(env_path=env_file)


def test_load_config_rejects_live_url_without_confirm(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ALPACA_API_KEY=PKABCDEF\n"
        "ALPACA_SECRET_KEY=secret123\n"
        "ALPACA_BASE_URL=https://api.alpaca.markets\n"
        "CONFIRM_LIVE=false\n"
    )
    with pytest.raises(ConfigError, match="CONFIRM_LIVE"):
        load_config(env_path=env_file)


def test_load_config_missing_api_key(tmp_path, monkeypatch):
    # 既存の環境変数をクリア
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("")
    with pytest.raises(ConfigError, match="ALPACA_API_KEY"):
        load_config(env_path=env_file)
