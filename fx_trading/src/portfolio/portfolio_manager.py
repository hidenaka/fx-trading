import pandas as pd
from typing import Dict, Any


class PortfolioManager:
    """Orchestrate market regime detection, strategy selection, signal aggregation, and position sizing."""

    def __init__(
        self,
        capital: float = 1_000_000.0,
        risk_per_trade: float = 0.01,
        confidence_threshold: int = 2,
    ):
        self.capital = capital
        self.risk_per_trade = risk_per_trade
        self.confidence_threshold = confidence_threshold

    def generate_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Generate a trading signal and detect market regime from price data."""
        if len(df) < 10:
            return {"signal": 0, "regime": "unknown"}

        # Simple regime detection based on trend
        short_ma = df["close"].tail(10).mean()
        long_ma = df["close"].tail(30).mean() if len(df) >= 30 else df["close"].tail(10).mean()

        if short_ma > long_ma * 1.001:
            regime = "trending_up"
        elif short_ma < long_ma * 0.999:
            regime = "trending_down"
        else:
            regime = "ranging"

        # Simple signal generation based on momentum
        latest = df.iloc[-1]["close"]
        prev = df.iloc[-5]["close"] if len(df) >= 5 else df.iloc[0]["close"]

        if latest > prev * 1.002:
            signal = 1
        elif latest < prev * 0.998:
            signal = -1
        else:
            signal = 0

        return {
            "signal": signal,
            "regime": regime,
        }

    def calculate_position(self, capital: float, entry_price: float, stop_loss: float) -> float:
        """Calculate lot size based on risk per trade."""
        risk_amount = capital * self.risk_per_trade
        price_risk = abs(entry_price - stop_loss)
        if price_risk == 0:
            return 0.0
        # For FX, 1 lot = 100,000 units; simplify to a reasonable lot size
        lot = risk_amount / (price_risk * 1000)
        return round(lot, 2)

    def update_capital(self, pnl: float):
        self.capital += pnl
