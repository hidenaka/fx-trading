from typing import List, Dict
from src.engine.backtest import Trade

class ReportGenerator:
    def __init__(self, initial_capital: float = 1_000_000):
        self.initial_capital = initial_capital

    def generate(self, trades: List[Trade]) -> Dict:
        total_trades = len(trades)
        if total_trades == 0:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "total_pnl": 0.0,
            }

        wins = [t.pnl for t in trades if t.pnl > 0]
        losses = [t.pnl for t in trades if t.pnl < 0]
        total_pnl = sum(t.pnl for t in trades)
        win_rate = len(wins) / total_trades

        gross_profit = sum(wins) if wins else 0.0
        gross_loss = abs(sum(losses)) if losses else 0.0
        profit_factor = gross_profit / gross_loss if gross_loss != 0 else float("inf")

        return {
            "total_trades": total_trades,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "total_pnl": total_pnl,
        }
