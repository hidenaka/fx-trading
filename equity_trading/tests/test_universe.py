from equity_trading.src.strategy.universe import (
    UNIVERSE,
    EtfMeta,
    get_etf_meta,
    liquidity_priority,
    macro_defense_followers,
)


def test_universe_contains_5_etfs():
    assert {e.symbol for e in UNIVERSE} == {"SPY", "QQQ", "IWM", "DIA", "XLK"}


def test_get_etf_meta_returns_correct_metadata():
    spy = get_etf_meta("SPY")
    assert spy.symbol == "SPY"
    assert spy.tech_pct == 0.30
    assert spy.sector_class == "broad"


def test_liquidity_priority_order():
    assert liquidity_priority() == ["SPY", "QQQ", "XLK", "IWM", "DIA"]


def test_macro_defense_followers_excludes_spy_and_iwm_specially():
    followers = macro_defense_followers()
    assert set(followers) == {"QQQ", "XLK", "DIA", "IWM"}


def test_get_etf_meta_unknown_raises():
    import pytest
    with pytest.raises(KeyError):
        get_etf_meta("AAPL")


def test_etf_meta_is_immutable():
    spy = get_etf_meta("SPY")
    import dataclasses
    assert dataclasses.is_dataclass(spy)
    import pytest
    with pytest.raises(dataclasses.FrozenInstanceError):
        spy.tech_pct = 0.50
