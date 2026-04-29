from typing import List, Dict, Type
import pandas as pd
from src.optimizer.grid_search import GridSearchOptimizer

class WalkForwardAnalyzer:
    def __init__(self, train_size: int, test_size: int):
        self.train_size = train_size
        self.test_size = test_size

    def split(self, df: pd.DataFrame) -> List[Dict]:
        windows = []
        start = 0
        while start + self.train_size + self.test_size <= len(df):
            train = df.iloc[start : start + self.train_size].copy()
            test = df.iloc[start + self.train_size : start + self.train_size + self.test_size].copy()
            windows.append({"train": train, "test": test})
            start += self.test_size
        return windows

    def analyze(self, df: pd.DataFrame, strategy_class: Type, param_grid: Dict) -> List[Dict]:
        windows = self.split(df)
        results = []
        for window in windows:
            train_optimizer = GridSearchOptimizer(window["train"])
            train_results = train_optimizer.search(strategy_class, param_grid)
            best_train = train_optimizer.get_best(train_results, metric="profit_factor")

            test_optimizer = GridSearchOptimizer(window["test"])
            test_results = test_optimizer.search(strategy_class, {"fast": [best_train["params"]["fast"]],
                                                                   "slow": [best_train["params"]["slow"]],
                                                                   "signal": [best_train["params"]["signal"]]})
            best_test = test_optimizer.get_best(test_results, metric="profit_factor")

            results.append({
                "train_pf": best_train["profit_factor"],
                "test_pf": best_test["profit_factor"],
                "params": best_train["params"],
                "train_trades": best_train["total_trades"],
                "test_trades": best_test["total_trades"],
            })
        return results
