import itertools
from typing import List, Dict, Type
from src.engine.backtest import BacktestEngine
from src.risk.manager import RiskManager
from src.reports.reporter import ReportGenerator

class GridSearchOptimizer:
    def __init__(self, df):
        self.df = df

    def search(self, strategy_class: Type, param_grid: Dict) -> List[Dict]:
        keys = list(param_grid.keys())
        values = [param_grid[k] for k in keys]
        results = []

        for combo in itertools.product(*values):
            params = dict(zip(keys, combo))
            strategy = strategy_class(**params)
            engine = BacktestEngine(initial_capital=1_000_000)
            risk = RiskManager(capital=1_000_000, risk_per_trade=0.01)
            trades = engine.run(self.df.copy(), strategy, risk)
            reporter = ReportGenerator(initial_capital=1_000_000)
            report = reporter.generate(trades)
            results.append({
                "params": params,
                "total_trades": report["total_trades"],
                "win_rate": report["win_rate"],
                "profit_factor": report["profit_factor"],
                "total_pnl": report["total_pnl"],
            })

        return results

    def get_best(self, results: List[Dict], metric: str = "profit_factor") -> Dict:
        valid = [r for r in results if r[metric] != float("inf") and r[metric] is not None]
        if not valid:
            return results[0] if results else {}
        return max(valid, key=lambda x: x[metric])
