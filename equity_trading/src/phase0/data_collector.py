"""Phase 0：過去データ収集（5ETF × 複数時間足）."""
from __future__ import annotations

from datetime import datetime
from typing import Sequence

import pandas as pd

from equity_trading.src.data.price_fetcher import PriceFetcher


def collect_phase0_data(
    fetcher: PriceFetcher,
    symbols: Sequence[str],
    start: datetime,
    end: datetime,
    timeframes: Sequence[int],
) -> dict[tuple[str, int], pd.DataFrame]:
    """各 ETF × 各時間足で過去データを取得し、辞書で返す.

    Args:
        fetcher: PriceFetcher インスタンス（キャッシュ機能あり）
        symbols: ETF ティッカーリスト
        start: 開始時刻（UTC tz aware）
        end: 終了時刻（UTC tz aware）
        timeframes: タイムフレーム（分単位）リスト。例 [1, 5, 1440]

    Returns:
        {(symbol, timeframe_minutes): DataFrame} の辞書
    """
    result: dict[tuple[str, int], pd.DataFrame] = {}
    for symbol in symbols:
        for tf in timeframes:
            df = fetcher.fetch(
                symbol=symbol,
                start=start,
                end=end,
                timeframe_minutes=tf,
            )
            result[(symbol, tf)] = df
    return result
