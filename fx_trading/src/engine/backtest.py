import pandas as pd
from typing import List
from dataclasses import dataclass, field


@dataclass
class Trade:
    entry_time: pd.Timestamp
    entry_price: float
    direction: int
    lot: float
    exit_time: pd.Timestamp = field(default=None)
    exit_price: float = field(default=None)
    pnl: float = field(default=None)


class BacktestEngine:
    def __init__(self, initial_capital: float = 1_000_000):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.trades: List[Trade] = []

    def run(self, df: pd.DataFrame, strategy, risk_manager):
        df = strategy.generate_signals(df)
        position = 0
        current_trade = None

        for i in range(1, len(df)):
            row = df.iloc[i]
            if position == 0 and row["signal"] != 0:
                direction = int(row["signal"])
                stop = row["close"] * 0.99 if direction == 1 else row["close"] * 1.01
                lot = risk_manager.calculate_lot(row["close"], stop)
                current_trade = Trade(
                    entry_time=row["datetime"],
                    entry_price=row["close"],
                    direction=direction,
                    lot=lot,
                )
                position = direction
            elif position != 0 and row["signal"] != position:
                current_trade.exit_time = row["datetime"]
                current_trade.exit_price = row["close"]
                current_trade.pnl = (current_trade.exit_price - current_trade.entry_price) * current_trade.lot * current_trade.direction
                self.trades.append(current_trade)
                risk_manager.update_capital(current_trade.pnl)
                self.capital = risk_manager.capital
                position = 0
                current_trade = None

        return self.trades
