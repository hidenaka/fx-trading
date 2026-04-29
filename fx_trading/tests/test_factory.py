from src.strategies.factory import StrategyFactory
from src.strategies.ma_macd import MaMacdStrategy

def test_factory_lists_available_strategies():
    available = StrategyFactory.available_strategies()
    assert "ma_macd" in available
    assert isinstance(available, list)

def test_factory_creates_ma_macd():
    strategy = StrategyFactory.create("ma_macd")
    assert isinstance(strategy, MaMacdStrategy)

def test_factory_raises_on_unknown_strategy():
    try:
        StrategyFactory.create("unknown_strategy")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass
