"""米国市場（NYSE）の祝日・取引日・前場短縮判定."""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from functools import lru_cache

import pandas as pd
import pandas_market_calendars as mcal


_NYSE = mcal.get_calendar("NYSE")


@lru_cache(maxsize=1024)
def _schedule_for_date(d: date) -> pd.Series | None:
    """指定日のNYSE schedule（market_open, market_close）を返す。非取引日は None."""
    schedule = _NYSE.schedule(start_date=d.isoformat(), end_date=d.isoformat())
    if len(schedule) == 0:
        return None
    return schedule.iloc[0]


def is_trading_day(d: date) -> bool:
    """米国市場の取引日か（週末・祝日でない）."""
    return _schedule_for_date(d) is not None


def market_open_utc(d: date) -> datetime:
    """指定日の市場オープン時刻（UTC）. 非取引日は ValueError."""
    s = _schedule_for_date(d)
    if s is None:
        raise ValueError(f"{d} is not a trading day")
    open_ts: pd.Timestamp = s["market_open"]
    return open_ts.to_pydatetime().astimezone(timezone.utc)


def market_close_utc(d: date) -> datetime:
    """指定日の市場クローズ時刻（UTC）. 非取引日は ValueError."""
    s = _schedule_for_date(d)
    if s is None:
        raise ValueError(f"{d} is not a trading day")
    close_ts: pd.Timestamp = s["market_close"]
    return close_ts.to_pydatetime().astimezone(timezone.utc)


def is_early_close_day(d: date) -> bool:
    """前場短縮日（13:00 ET クローズ）か.

    通常16:00 ETクローズに対して、年8日程度ある13:00 ETクローズ日を判定.
    """
    s = _schedule_for_date(d)
    if s is None:
        return False
    close_ts: pd.Timestamp = s["market_close"]
    close_et = close_ts.tz_convert("America/New_York")
    return close_et.time() < time(15, 0)
