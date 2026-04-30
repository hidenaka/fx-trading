from typing import List


class StrategySelector:
    def __init__(self):
        self._registry = {
            "trending": ["ma_macd", "ma_cross", "dow_theory"],
            "ranging": ["stochastic", "ml_strategy"],
            "neutral": ["ma_macd", "stochastic"],  # conservative default
        }

    def select(self, regime: str) -> List[str]:
        return self._registry.get(regime, self._registry["neutral"])

    def available_regimes(self) -> List[str]:
        return list(self._registry.keys())
