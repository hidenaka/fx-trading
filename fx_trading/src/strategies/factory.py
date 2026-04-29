from typing import Dict, Type, List
from .base import Strategy
from .ma_macd import MaMacdStrategy
from .ma_cross import MaCrossStrategy
from .dow_theory import DowTheoryStrategy
from .stochastic import StochasticStrategy

class StrategyFactory:
    _registry: Dict[str, Type[Strategy]] = {
        "ma_macd": MaMacdStrategy,
        "ma_cross": MaCrossStrategy,
        "dow_theory": DowTheoryStrategy,
        "stochastic": StochasticStrategy,
    }

    @classmethod
    def available_strategies(cls) -> List[str]:
        return list(cls._registry.keys())

    @classmethod
    def create(cls, name: str, **kwargs) -> Strategy:
        if name not in cls._registry:
            raise ValueError(f"Unknown strategy: {name}. Available: {cls.available_strategies()}")
        return cls._registry[name](**kwargs)

    @classmethod
    def register(cls, name: str, strategy_class: Type[Strategy]):
        cls._registry[name] = strategy_class
