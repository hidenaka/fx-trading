"""
Adapter to use PortfolioManager in the backtest engine.
Creates a Strategy-compatible interface around PortfolioManager.
"""
import pandas as pd
from typing import Dict, Any

from src.strategies.base import Strategy
from src.portfolio.portfolio_manager import PortfolioManager


class PortfolioStrategyAdapter(Strategy):
    """Wrap PortfolioManager so it can be used by BacktestEngine."""

    def __init__(self, confidence_threshold: int = 2):
        self.manager = PortfolioManager(confidence_threshold=confidence_threshold)

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate signals using PortfolioManager for each row.
        For backtest efficiency, we batch-process: generate one signal
        for the whole DataFrame (using the last N bars) and repeat it.
        """
        df = df.copy()
        signals = []

        min_bars = 30
        for i in range(len(df)):
            if i < min_bars:
                signals.append(0)
                continue

            recent = df.iloc[: i + 1].tail(50)
            try:
                result = self.manager.generate_signal(recent)
                signals.append(result["signal"])
            except Exception:
                signals.append(0)

        df["signal"] = signals
        return df
