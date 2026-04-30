import pandas as pd
from typing import List, Optional
from dataclasses import dataclass, field
from src.engine.cost_model import CostModel


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
    def __init__(self, initial_capital: float = 1_000_000, mode: str = "backtest",
                 broker=None, cost_model: Optional[CostModel] = None):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.trades: List[Trade] = []
        self.mode = mode
        self.broker = broker
        self.cost_model = cost_model if cost_model is not None else CostModel()

    def run(self, df: pd.DataFrame, strategy, risk_manager):
        df = strategy.generate_signals(df)
        position = 0
        current_trade = None

        for i in range(1, len(df)):
            row = df.iloc[i]
            
            if self.mode == "live" and self.broker is not None:
                # In live mode, check broker for actual position
                open_positions = self.broker.get_open_positions()
                # Simplified: if we have open positions, set position accordingly
                if open_positions:
                    pos = open_positions[0]
                    if float(pos.get("long", {}).get("units", 0)) > 0:
                        position = 1
                    elif float(pos.get("short", {}).get("units", 0)) < 0:
                        position = -1
                else:
                    position = 0
            
            if position == 0 and row["signal"] != 0:
                direction = int(row["signal"])
                entry_price = self.cost_model.adjust_entry(row["close"], direction)
                stop = entry_price * 0.99 if direction == 1 else entry_price * 1.01
                lot = risk_manager.calculate_lot(entry_price, stop)
                current_trade = Trade(
                    entry_time=row["datetime"],
                    entry_price=entry_price,
                    direction=direction,
                    lot=lot,
                )
                position = direction
            elif position != 0 and row["signal"] != position:
                exit_price = self.cost_model.adjust_exit(row["close"], current_trade.direction)
                current_trade.exit_time = row["datetime"]
                current_trade.exit_price = exit_price
                price_pnl = (exit_price - current_trade.entry_price) * current_trade.lot * current_trade.direction
                days_held = (current_trade.exit_time - current_trade.entry_time).total_seconds() / 86400.0
                swap_pnl = self.cost_model.swap_pnl(current_trade.lot, current_trade.direction, days_held)
                current_trade.pnl = price_pnl + swap_pnl
                self.trades.append(current_trade)
                risk_manager.update_capital(current_trade.pnl)
                self.capital = risk_manager.capital
                position = 0
                current_trade = None

        return self.trades
