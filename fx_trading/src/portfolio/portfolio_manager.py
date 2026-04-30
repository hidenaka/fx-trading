import pandas as pd
from typing import Dict, Any
from src.portfolio.market_regime import MarketRegimeDetector
from src.portfolio.strategy_selector import StrategySelector
from src.portfolio.position_sizer import PositionSizer
from src.strategies.factory import StrategyFactory

class PortfolioManager:
    def __init__(self, confidence_threshold: int = 2):
        self.regime_detector = MarketRegimeDetector()
        self.strategy_selector = StrategySelector()
        self.position_sizer = PositionSizer()
        self.confidence_threshold = confidence_threshold

    def generate_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        # Detect market regime
        regime = self.regime_detector.detect(df)
        
        # Select strategies based on regime
        strategy_names = self.strategy_selector.select(regime)
        
        # Generate signals from each strategy
        signals = {}
        for name in strategy_names:
            try:
                strategy = StrategyFactory.create(name)
                result = strategy.generate_signals(df.copy())
                latest_signal = int(result.iloc[-1]["signal"])
                signals[name] = latest_signal
            except Exception:
                signals[name] = 0
        
        # Aggregate signals
        aggregated = self._aggregate_signals(signals)
        
        return {
            "signal": aggregated,
            "regime": regime,
            "strategies_used": strategy_names,
            "individual_signals": signals,
        }

    def _aggregate_signals(self, signals: Dict[str, int]) -> int:
        buy_votes = sum(1 for s in signals.values() if s == 1)
        sell_votes = sum(1 for s in signals.values() if s == -1)
        
        if buy_votes >= self.confidence_threshold and buy_votes > sell_votes:
            return 1
        elif sell_votes >= self.confidence_threshold and sell_votes > buy_votes:
            return -1
        else:
            return 0

    def calculate_position(self, capital: float, entry_price: float, stop_loss: float,
                           win_rate: float = 0.5, avg_win: float = 1.0, avg_loss: float = 1.0,
                           current_volatility: float = 0.02) -> float:
        return self.position_sizer.calculate_lot(
            capital, entry_price, stop_loss,
            win_rate, avg_win, avg_loss, current_volatility
        )
