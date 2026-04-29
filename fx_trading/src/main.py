import argparse
from src.data.loader import DataLoader
from src.data.preprocessor import Preprocessor
from src.strategies.factory import StrategyFactory
from src.engine.backtest import BacktestEngine
from src.risk.manager import RiskManager
from src.reports.reporter import ReportGenerator
from src.optimizer.grid_search import GridSearchOptimizer
from src.wfa.walker import WalkForwardAnalyzer
from src.selector.ranker import StrategyRanker
from src.runner.polling_runner import PollingRunner
from src.config.settings import Settings

def run_backtest():
    loader = DataLoader(data_dir="data")
    settings = Settings()
    all_results = []

    for pair in settings.currency_pairs:
        print(f"\n=== Backtest Pair: {pair} ===")
        try:
            raw_df = loader.load_csv(pair.lower(), "1h")
        except FileNotFoundError:
            print(f"Data file for {pair} not found, skipping.")
            continue
        pre = Preprocessor()
        df = pre.process(raw_df)

        strategy_names = StrategyFactory.available_strategies()

        for name in strategy_names:
            print(f"\n=== Grid Search: {name} | {pair} ===")
            optimizer = GridSearchOptimizer(df)
            param_grid = {
                "fast": [3, 5, 8],
                "slow": [6, 10, 15],
                "signal": [2, 3, 5],
            }
            strategy_cls = StrategyFactory._registry[name]
            results = optimizer.search(strategy_cls, param_grid)
            best = optimizer.get_best(results)
            print("Best params:", best["params"])
            print("Profit Factor:", best["profit_factor"])

            print(f"\n=== Walk-Forward Analysis: {name} | {pair} ===")
            train_size = min(60, max(5, len(df) // 2))
            test_size = min(30, max(3, len(df) // 3))
            wfa = WalkForwardAnalyzer(train_size=train_size, test_size=test_size)
            wfa_results = wfa.analyze(df, strategy_cls, param_grid)
            for i, r in enumerate(wfa_results):
                print(f"Window {i+1}: Train PF={r['train_pf']:.2f}, Test PF={r['test_pf']:.2f}, Params={r['params']}")

            all_results.append({
                "name": f"{pair} {name} Best",
                "profit_factor": best["profit_factor"],
                "win_rate": best["win_rate"],
                "max_drawdown": 0.1,
                "total_trades": best["total_trades"],
            })
            all_results.append({
                "name": f"{pair} {name} WFA Avg",
                "profit_factor": sum(x["test_pf"] for x in wfa_results) / len(wfa_results) if wfa_results else 0,
                "win_rate": 0.5,
                "max_drawdown": 0.15,
                "total_trades": sum(x["test_trades"] for x in wfa_results),
            })

    print("\n=== Strategy Ranking ===")
    ranker = StrategyRanker(min_trades=0)
    ranked = ranker.rank(all_results)
    for r in ranked:
        print(f"{r['name']}: Score={r['score']:.2f}")

def run_live():
    print("=== Live Trading Mode ===")
    print("WARNING: This will connect to OANDA and potentially place real orders!")
    settings = Settings()
    print(f"Environment: {settings.environment}")
    print(f"Currency Pairs: {settings.currency_pairs}")
    print(f"Risk per trade: {settings.risk_per_trade * 100}%")
    
    runner = PollingRunner(config=settings)
    results = runner.run_all_pairs()
    print(f"Trading cycle results: {results}")

def main():
    parser = argparse.ArgumentParser(description="FX Auto Trading System")
    parser.add_argument("--live", action="store_true", help="Run in live trading mode")
    parser.add_argument("--backtest", action="store_true", help="Run backtest (default)")
    parser.add_argument("--fetch-data", action="store_true", help="Fetch historical data from OANDA")
    parser.add_argument("--batch-backtest", action="store_true", help="Run batch backtest for all pairs and strategies")
    args = parser.parse_args()

    if args.live:
        run_live()
    elif args.fetch_data:
        from src.data.oanda_fetcher import OandaDataFetcher
        from src.config.settings import Settings
        settings = Settings()
        fetcher = OandaDataFetcher(api_token=settings.api_token, environment=settings.environment)
        for pair in settings.currency_pairs:
            output_file = f"data/{pair.lower()}_{settings.granularity.lower()}.csv"
            print(f"Fetching {pair}...")
            fetcher.fetch_to_csv(pair, output_file, granularity=settings.granularity, count=5000)
            print(f"Saved to {output_file}")
    elif args.batch_backtest:
        run_batch_backtest()
    else:
        run_backtest()

if __name__ == "__main__":
    main()
