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

            wfa_summary = wfa.summarize(wfa_results)
            print(
                f"\n--- WFA Summary ({name} | {pair}) ---\n"
                f"  Windows:           {wfa_summary['windows']}\n"
                f"  OOS trades:        {wfa_summary['oos_total_trades']}\n"
                f"  OOS profit factor: {wfa_summary['oos_profit_factor']:.2f}\n"
                f"  OOS win rate:      {wfa_summary['oos_win_rate']:.2%}\n"
                f"  OOS total PnL:     {wfa_summary['oos_total_pnl']:.2f}\n"
                f"  Avg WFA efficiency:{wfa_summary['avg_wfa_efficiency']:.2f}  (test_pf / train_pf)\n"
                f"  Param change ratio:{wfa_summary['param_change_ratio']:.2%}  (instability indicator)"
            )

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

def run_live(dry_run=False):
    if dry_run:
        print("=== DRY RUN Mode ===")
        print("This simulates live trading WITHOUT placing actual orders.")
    else:
        print("=== Live Trading Mode ===")
        print("WARNING: This will connect to OANDA and potentially place real orders!")
    
    settings = Settings()
    print(f"Environment: {settings.environment}")
    print(f"Currency Pairs: {settings.currency_pairs}")
    print(f"Risk per trade: {settings.risk_per_trade * 100}%")
    
    if dry_run:
        run_dry_trading(settings)
    else:
        runner = PollingRunner(config=settings)
        results = runner.run_all_pairs()
        print(f"Trading cycle results: {results}")

def run_dry_trading(settings):
    import pandas as pd
    from src.monitoring.logger import TradeLogger
    
    logger = TradeLogger()
    print("\n--- Dry Run Trading Cycle ---")
    all_signals = {}
    
    for pair in settings.currency_pairs:
        print(f"\n[Pair: {pair}]")
        
        # Load latest data from CSV (simulate recent prices)
        try:
            df = pd.read_csv(f"data/{pair.lower()}_h1.csv", parse_dates=["datetime"])
        except FileNotFoundError:
            print(f"  No data file found for {pair}, trying alternative...")
            try:
                df = pd.read_csv("data/usdjpy_1h_realistic.csv", parse_dates=["datetime"])
            except FileNotFoundError:
                print(f"  No data file found for {pair}, skipping.")
                continue
        
        # Use last 50 bars as "recent" data
        recent_df = df.tail(50).copy()
        
        # Generate signals from all strategies
        strategies = StrategyFactory.available_strategies()
        signals = {}
        
        for name in strategies:
            try:
                strategy = StrategyFactory.create(name)
                result = strategy.generate_signals(recent_df.copy())
                latest_signal = int(result.iloc[-1]["signal"])
                signals[name] = latest_signal
                if latest_signal != 0:
                    print(f"  Strategy '{name}': Signal={'BUY' if latest_signal == 1 else 'SELL'}")
            except Exception as e:
                signals[name] = 0
        
        all_signals[pair] = signals
        
        # Aggregate signals (majority vote)
        buy_votes = sum(1 for s in signals.values() if s == 1)
        sell_votes = sum(1 for s in signals.values() if s == -1)
        
        latest_price = recent_df.iloc[-1]["close"]
        
        if buy_votes > sell_votes and buy_votes >= 2:
            print(f"  >> ACTION: Would place BUY order @ {latest_price:.3f} (votes: {buy_votes} buy, {sell_votes} sell)")
            logger.log_trade(pair, "BUY", 1000, latest_price)
        elif sell_votes > buy_votes and sell_votes >= 2:
            print(f"  >> ACTION: Would place SELL order @ {latest_price:.3f} (votes: {buy_votes} buy, {sell_votes} sell)")
            logger.log_trade(pair, "SELL", 1000, latest_price)
        else:
            print(f"  >> No clear signal (votes: {buy_votes} buy, {sell_votes} sell). No action taken.")
    
    # Export portfolio state for dashboard
    from src.api.data_exporter import DataExporter
    exporter = DataExporter(output_dir="dashboard/data")
    exporter.export_portfolio({
        "capital": settings.initial_capital,
        "daily_pnl": 0,
        "positions": [],
        "signals": all_signals,
        "timestamp": pd.Timestamp.now().isoformat(),
    })
    print("\n[Dry run complete. No actual orders placed.]")
    print("[Portfolio state exported to dashboard/data/portfolio.json]")

def run_portfolio():
    print("=== Portfolio Strategy Mode ===")
    settings = Settings()
    print(f"Pairs: {settings.currency_pairs}")
    
    runner = PollingRunner(config=settings)
    results = runner.run_portfolio_cycle()
    print(f"\nPortfolio results: {results}")

def run_batch_backtest():
    from src.api.data_exporter import DataExporter
    
    loader = DataLoader(data_dir="data")
    settings = Settings()
    exporter = DataExporter(output_dir="dashboard/data")
    all_results = []
    
    strategy_names = StrategyFactory.available_strategies()
    
    for pair in settings.currency_pairs:
        print(f"\n=== Batch Backtest: {pair} ===")
        try:
            raw_df = loader.load_csv(pair.lower(), "1h")
        except FileNotFoundError:
            print(f"Data file for {pair} not found, skipping.")
            continue
        
        pre = Preprocessor()
        df = pre.process(raw_df)
        
        for name in strategy_names:
            strategy = StrategyFactory.create(name)
            risk = RiskManager(capital=settings.initial_capital, risk_per_trade=settings.risk_per_trade)
            engine = BacktestEngine(initial_capital=settings.initial_capital)
            trades = engine.run(df, strategy, risk)

            report = ReportGenerator(initial_capital=settings.initial_capital).generate(trades)
            pf = report["profit_factor"]
            pf_value = float("inf") if pf == float("inf") else round(pf, 4)
            result = {
                "pair": pair,
                "strategy": name,
                "total_trades": report["total_trades"],
                "win_rate": round(report["win_rate"], 4),
                "profit_factor": pf_value,
                "total_pnl": round(report["total_pnl"], 2),
                "max_drawdown_pct": round(report["max_drawdown_pct"], 2),
                "max_drawdown_abs": round(report["max_drawdown_abs"], 2),
                "sharpe_ratio": round(report["sharpe_ratio"], 3),
                "sortino_ratio": round(report["sortino_ratio"], 3),
                "avg_holding_hours": round(report["avg_holding_hours"], 2),
                "final_capital": round(engine.capital, 2),
            }
            all_results.append(result)
            print(
                f"{name:20s} | Trades: {result['total_trades']:3d} | "
                f"Win Rate: {result['win_rate']:.2%} | PF: {result['profit_factor']:.2f} | "
                f"Sharpe: {result['sharpe_ratio']:.2f} | "
                f"MaxDD: {result['max_drawdown_pct']:.2f}% | "
                f"Capital: ¥{result['final_capital']:,.0f}"
            )
    
    exporter.export_backtest_result("batch", {
        "results": all_results,
        "timestamp": pd.Timestamp.now().isoformat(),
    })
    print(f"\nBatch backtest results saved to dashboard/data/")
    
    # Summary table
    print("\n=== Batch Backtest Summary ===")
    header = f"{'Pair':<12} {'Strategy':<15} {'Trades':>6} {'Win%':>8} {'PF':>8} {'Sharpe':>8} {'MaxDD%':>8} {'Capital':>15}"
    print(header)
    print("-" * len(header))
    for r in all_results:
        print(
            f"{r['pair']:<12} {r['strategy']:<15} {r['total_trades']:>6} "
            f"{r['win_rate']:>7.1%} {r['profit_factor']:>8.2f} "
            f"{r['sharpe_ratio']:>8.2f} {r['max_drawdown_pct']:>7.2f}% "
            f"¥{r['final_capital']:>13,.0f}"
        )

def main():
    parser = argparse.ArgumentParser(description="FX Auto Trading System")
    parser.add_argument("--live", action="store_true", help="Run in live trading mode")
    parser.add_argument("--dry-run", action="store_true", help="Simulate live trading without placing orders")
    parser.add_argument("--backtest", action="store_true", help="Run backtest (default)")
    parser.add_argument("--fetch-data", action="store_true", help="Fetch historical data from OANDA")
    parser.add_argument("--batch-backtest", action="store_true", help="Run batch backtest for all pairs and strategies")
    parser.add_argument("--portfolio", action="store_true", help="Run portfolio strategy mode")
    args = parser.parse_args()

    if args.dry_run:
        run_live(dry_run=True)
    elif args.live:
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
    elif args.portfolio:
        run_portfolio()
    else:
        run_backtest()

if __name__ == "__main__":
    main()
