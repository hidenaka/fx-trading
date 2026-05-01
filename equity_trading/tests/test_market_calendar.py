from datetime import date, datetime, timezone

import pytest

from equity_trading.src.data.market_calendar import (
    is_trading_day,
    market_close_utc,
    market_open_utc,
    is_early_close_day,
)


def test_is_trading_day_for_typical_weekday():
    assert is_trading_day(date(2026, 5, 4)) is True


def test_is_not_trading_day_for_saturday():
    assert is_trading_day(date(2026, 5, 9)) is False


def test_is_not_trading_day_for_us_holiday():
    assert is_trading_day(date(2026, 7, 4)) is False  # Saturday


def test_market_open_utc_for_winter_day():
    open_utc = market_open_utc(date(2026, 1, 5))
    assert open_utc.hour == 14
    assert open_utc.minute == 30


def test_market_open_utc_for_summer_day():
    open_utc = market_open_utc(date(2026, 6, 1))
    assert open_utc.hour == 13
    assert open_utc.minute == 30


def test_market_close_utc_for_normal_day():
    close_utc = market_close_utc(date(2026, 6, 1))
    assert close_utc.hour == 20
    assert close_utc.minute == 0


def test_is_early_close_day_for_thanksgiving_friday():
    assert is_early_close_day(date(2026, 11, 27)) is True


def test_is_early_close_day_for_normal_day():
    assert is_early_close_day(date(2026, 6, 1)) is False
