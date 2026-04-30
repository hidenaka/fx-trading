import pandas as pd
from typing import Dict
from datetime import datetime

class Rebalancer:
    def __init__(self, min_sharpe: float = 0.5, rebalance_day: str = "Friday"):
        self.min_sharpe = min_sharpe
        self.rebalance_day = rebalance_day

    def should_rebalance(self) -> bool:
        today = datetime.now().strftime("%A")
        return today == self.rebalance_day

    def calculate_weights(self, performance: Dict[str, Dict[str, float]]) -> Dict[str, float]:
        # Filter out underperforming strategies
        valid = {
            name: data for name, data in performance.items()
            if data.get("sharpe", 0) >= self.min_sharpe
        }
        
        if not valid:
            return {}
        
        # Calculate weights based on Sharpe ratio
        total_sharpe = sum(data["sharpe"] for data in valid.values())
        if total_sharpe == 0:
            return {name: 1.0 / len(valid) for name in valid}
        
        weights = {
            name: data["sharpe"] / total_sharpe
            for name, data in valid.items()
        }
        
        return weights
