from src.selector.ranker import StrategyRanker

def test_ranker_sorts_by_composite_score():
    results = [
        {"name": "A", "profit_factor": 2.0, "win_rate": 0.6, "max_drawdown": 0.1, "total_trades": 50},
        {"name": "B", "profit_factor": 1.5, "win_rate": 0.55, "max_drawdown": 0.05, "total_trades": 100},
        {"name": "C", "profit_factor": 3.0, "win_rate": 0.7, "max_drawdown": 0.2, "total_trades": 30},
    ]
    ranker = StrategyRanker()
    ranked = ranker.rank(results)
    assert ranked[0]["name"] == "C"

def test_ranker_filters_min_trades():
    results = [
        {"name": "A", "profit_factor": 2.0, "win_rate": 0.6, "max_drawdown": 0.1, "total_trades": 5},
        {"name": "B", "profit_factor": 1.5, "win_rate": 0.55, "max_drawdown": 0.05, "total_trades": 100},
    ]
    ranker = StrategyRanker(min_trades=10)
    ranked = ranker.rank(results)
    assert len(ranked) == 1
    assert ranked[0]["name"] == "B"
