from typing import List, Dict, Type
import math
import pandas as pd
from src.optimizer.grid_search import GridSearchOptimizer
from src.engine.backtest import BacktestEngine
from src.risk.manager import RiskManager
from src.reports.reporter import ReportGenerator


class WalkForwardAnalyzer:
    DEFAULT_CAPITAL = 1_000_000
    DEFAULT_RISK = 0.01

    def __init__(self, train_size: int, test_size: int, capital: float = DEFAULT_CAPITAL,
                 risk_per_trade: float = DEFAULT_RISK):
        self.train_size = train_size
        self.test_size = test_size
        self.capital = capital
        self.risk_per_trade = risk_per_trade

    def split(self, df: pd.DataFrame) -> List[Dict]:
        windows = []
        start = 0
        while start + self.train_size + self.test_size <= len(df):
            train = df.iloc[start : start + self.train_size].copy()
            test = df.iloc[start + self.train_size : start + self.train_size + self.test_size].copy()
            windows.append({"train": train, "test": test})
            start += self.test_size
        return windows

    def _run_test(self, test_df: pd.DataFrame, strategy_class: Type, params: Dict):
        strategy = strategy_class(**params)
        engine = BacktestEngine(initial_capital=self.capital)
        risk = RiskManager(capital=self.capital, risk_per_trade=self.risk_per_trade)
        trades = engine.run(test_df.copy(), strategy, risk)
        report = ReportGenerator(initial_capital=self.capital).generate(trades)
        return trades, report

    @staticmethod
    def _efficiency(train_pf: float, test_pf: float) -> float:
        # WFA efficiency = OOS PF / IS PF. Values << 1 imply overfit on train.
        if train_pf is None or train_pf <= 0 or math.isinf(train_pf):
            return 0.0
        if test_pf is None or math.isinf(test_pf):
            return 0.0
        return test_pf / train_pf

    def analyze(self, df: pd.DataFrame, strategy_class: Type, param_grid: Dict) -> List[Dict]:
        windows = self.split(df)
        results = []
        for window in windows:
            train_optimizer = GridSearchOptimizer(window["train"])
            train_results = train_optimizer.search(strategy_class, param_grid)
            best_train = train_optimizer.get_best(train_results, metric="profit_factor")

            test_trades, test_report = self._run_test(window["test"], strategy_class, best_train["params"])

            train_pf = best_train["profit_factor"]
            test_pf = test_report["profit_factor"]

            results.append({
                "train_pf": train_pf,
                "test_pf": test_pf,
                "params": best_train["params"],
                "train_trades": best_train["total_trades"],
                "test_trades": test_report["total_trades"],
                "test_pnl": test_report["total_pnl"],
                "test_win_rate": test_report["win_rate"],
                "test_trades_obj": test_trades,
                "wfa_efficiency": self._efficiency(train_pf, test_pf),
            })
        return results

    def summarize(self, results: List[Dict]) -> Dict:
        if not results:
            return {
                "windows": 0,
                "oos_total_trades": 0,
                "oos_profit_factor": 0.0,
                "oos_win_rate": 0.0,
                "oos_total_pnl": 0.0,
                "avg_wfa_efficiency": 0.0,
                "param_change_ratio": 0.0,
            }

        all_oos_trades = [t for r in results for t in r["test_trades_obj"]]
        aggregate = ReportGenerator(initial_capital=self.capital).generate(all_oos_trades)

        finite_eff = [r["wfa_efficiency"] for r in results if r["wfa_efficiency"] > 0]
        avg_eff = sum(finite_eff) / len(finite_eff) if finite_eff else 0.0

        if len(results) > 1:
            changes = sum(
                1 for i in range(1, len(results))
                if results[i]["params"] != results[i - 1]["params"]
            )
            param_change_ratio = changes / (len(results) - 1)
        else:
            param_change_ratio = 0.0

        return {
            "windows": len(results),
            "oos_total_trades": aggregate["total_trades"],
            "oos_profit_factor": aggregate["profit_factor"],
            "oos_win_rate": aggregate["win_rate"],
            "oos_total_pnl": aggregate["total_pnl"],
            "avg_wfa_efficiency": avg_eff,
            "param_change_ratio": param_change_ratio,
        }
