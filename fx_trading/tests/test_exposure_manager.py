import pytest
from src.risk.exposure_manager import ExposureManager


def test_can_open_initially():
    em = ExposureManager()
    assert em.can_open("USD_JPY", 1) is True


def test_blocks_pyramiding_same_pair():
    em = ExposureManager()
    em.register("USD_JPY", 1)
    assert em.can_open("USD_JPY", 1) is False
    assert em.can_open("USD_JPY", -1) is False


def test_total_position_limit():
    em = ExposureManager(max_positions=2, max_positions_per_currency=99)
    em.register("USD_JPY", 1)
    em.register("EUR_GBP", 1)
    assert em.can_open("AUD_NZD", 1) is False


def test_blocks_stacking_long_usd_via_correlated_pairs():
    em = ExposureManager(max_positions=5, max_positions_per_currency=2)
    em.register("USD_JPY", 1)  # long USD
    em.register("USD_CAD", 1)  # long USD again -> 2 long USD
    # Third long-USD pair must be rejected even though pair itself is new.
    assert em.can_open("USD_CHF", 1) is False
    # Going short USD via EUR_USD long is fine (effectively long EUR / short USD).
    assert em.can_open("EUR_USD", 1) is True


def test_blocks_stacking_via_quote_currency():
    em = ExposureManager(max_positions=5, max_positions_per_currency=2)
    # Long EUR_USD = short USD; long GBP_USD = short USD; both short USD via quote.
    em.register("EUR_USD", 1)
    em.register("GBP_USD", 1)
    assert em.can_open("AUD_USD", 1) is False  # would be 3rd short-USD position


def test_unregister_releases_slot():
    em = ExposureManager(max_positions=2, max_positions_per_currency=99)
    em.register("USD_JPY", 1)
    em.register("EUR_GBP", 1)
    assert em.can_open("AUD_NZD", 1) is False
    em.unregister("USD_JPY")
    assert em.can_open("AUD_NZD", 1) is True


def test_currency_count_distinguishes_direction():
    em = ExposureManager()
    em.register("USD_JPY", 1)   # long USD
    em.register("EUR_USD", 1)   # short USD (USD is quote, long pair)
    assert em.currency_position_count("USD", 1) == 1   # one long USD
    assert em.currency_position_count("USD", -1) == 1  # one short USD


def test_invalid_direction_rejected():
    em = ExposureManager()
    with pytest.raises(ValueError):
        em.register("USD_JPY", 0)
    with pytest.raises(ValueError):
        em.can_open("USD_JPY", 2)


def test_invalid_pair_format_rejected():
    em = ExposureManager()
    with pytest.raises(ValueError):
        em.register("USDJPY", 1)
