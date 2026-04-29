import os
from src.config.settings import Settings

def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("OANDA_API_TOKEN", "test-token-123")
    monkeypatch.setenv("OANDA_ACCOUNT_ID", "test-account-456")
    monkeypatch.setenv("OANDA_ENVIRONMENT", "practice")
    settings = Settings()
    assert settings.api_token == "test-token-123"
    assert settings.account_id == "test-account-456"
    assert settings.environment == "practice"

def test_settings_defaults(monkeypatch):
    monkeypatch.setenv("OANDA_API_TOKEN", "dummy-token")
    monkeypatch.setenv("OANDA_ACCOUNT_ID", "dummy-account")
    settings = Settings()
    assert settings.environment == "practice"
    assert settings.risk_per_trade == 0.01
    assert settings.currency_pairs == ["USD_JPY"]

def test_settings_raises_on_missing_token():
    import os
    if "OANDA_API_TOKEN" in os.environ:
        del os.environ["OANDA_API_TOKEN"]
    from src.config.settings import Settings
    try:
        settings = Settings()
        assert False, "Should have raised"
    except ValueError:
        pass
