from src.data.loader import DataLoader
from src.data.preprocessor import Preprocessor
from src.strategies.ma_macd import MaMacdStrategy
from src.engine.backtest import BacktestEngine
from src.risk.manager import RiskManager
from src.reports.reporter import ReportGenerator
from src.optimizer.grid_search import GridSearchOptimizer
from src.wfa.walker import WalkForwardAnalyzer
from src.selector.ranker import StrategyRanker

def main():
    loader = DataLoader(data_dir="data")
    raw_df = loader.load_csv("sample", "usdjpy_1h")
    pre = Preprocessor()
    df = pre.process(raw_df)

    print("=== Grid Search ===")
    optimizer = GridSearchOptimizer(df)
    param_grid = {
        "fast": [3, 5, 8],
        "slow": [6, 10, 15],
        "signal": [2, 3, 5],
    }
    results = optimizer.search(MaMacdStrategy, param_grid)
    best = optimizer.get_best(results)
    print("Best params:", best["params"])
    print("Profit Factor:", best["profit_factor"])

    print("\n=== Walk-Forward Analysis ===")
    train_size = min(60, max(5, len(df) // 2))
    test_size = min(30, max(3, len(df) // 3))
    wfa = WalkForwardAnalyzer(train_size=train_size, test_size=test_size)
    wfa_results = wfa.analyze(df, MaMacdStrategy, param_grid)
    for i, r in enumerate(wfa_results):
        print(f"Window {i+1}: Train PF={r['train_pf']:.2f}, Test PF={r['test_pf']:.2f}, Params={r['params']}")

    print("\n=== Strategy Ranking ===")
    rank_inputs = [
        {"name": "MA+MACD Best", "profit_factor": best["profit_factor"], "win_rate": best["win_rate"],
         "max_drawdown": 0.1, "total_trades": best["total_trades"]},
        {"name": "MA+MACD WFA Avg", "profit_factor": sum(x["test_pf"] for x in wfa_results) / len(wfa_results),
         "win_rate": 0.5, "max_drawdown": 0.15, "total_trades": sum(x["test_trades"] for x in wfa_results)},
    ]
    ranker = StrategyRanker(min_trades=0)
    ranked = ranker.rank(rank_inputs)
    for r in ranked:
        print(f"{r['name']}: Score={r['score']:.2f}")

if __name__ == "__main__":
    main()
