"""5戦略 × 5ETF × パラメータグリッドのマルチ戦略ランナー."""
from __future__ import annotations

import json
from typing import Sequence

import pandas as pd

from equity_trading.src.phase0.strategy_simulator import simulate_strategy
from equity_trading.src.strategy.base import TradingStrategy


def run_all_strategies(
    strategies: Sequence[TradingStrategy],
    symbols: Sequence[str],
    data_map: dict[tuple[str, int], pd.DataFrame],
    atr_map: dict[str, float],
    param_grid: dict[str, list[dict]],
) -> dict[str, pd.DataFrame]:
    """全戦略 × 全ETF × パラメータでシミュレーションを実行.

    Args:
        strategies: TradingStrategy インスタンスのリスト
        symbols: 検証対象のETFティッカー
        data_map: collect_phase0_data の戻り値（{(symbol, timeframe): DataFrame}）
        atr_map: {symbol: atr_median_pct}
        param_grid: {strategy_name: [params_dict, ...]}

    Returns:
        {strategy_name: DataFrame} の辞書。
        各 DataFrame の列：strategy, symbol, params, trade_count, win_count, win_rate, avg_pnl_pct
    """
    results: dict[str, list[dict]] = {s.name: [] for s in strategies}
    spy_5min = data_map.get(("SPY", 5))

    for strategy in strategies:
        param_list = param_grid.get(strategy.name, [{}])
        for symbol in symbols:
            bars_5 = data_map[(symbol, 5)]
            daily = data_map[(symbol, 1440)]
            atr_pct = atr_map[symbol]
            for params in param_list:
                serialized = json.dumps(params, sort_keys=True)
                augmented = {**params}
                if spy_5min is not None:
                    augmented["_spy_5min"] = spy_5min
                augmented["_daily"] = daily
                summary = simulate_strategy(
                    strategy=strategy,
                    bars_5min=bars_5,
                    daily=daily,
                    atr_pct=atr_pct,
                    params=augmented,
                )
                summary["strategy"] = strategy.name
                summary["symbol"] = symbol
                summary["params"] = serialized
                results[strategy.name].append(summary)

    return {
        name: pd.DataFrame(rows)[
            ["strategy", "symbol", "params", "trade_count", "win_count", "win_rate", "avg_pnl_pct"]
        ]
        for name, rows in results.items()
    }
