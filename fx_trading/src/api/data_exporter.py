import json
import os
from datetime import datetime
from typing import Dict, Any

class DataExporter:
    def __init__(self, output_dir: str = "dashboard/data"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def export_backtest_result(self, strategy_name: str, data: Dict[str, Any]) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"backtest_{strategy_name}_{timestamp}.json"
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)
        return filepath

    def export_portfolio(self, portfolio: Dict[str, Any]) -> str:
        filepath = os.path.join(self.output_dir, "portfolio.json")
        with open(filepath, "w") as f:
            json.dump(portfolio, f, indent=2, default=str)
        return filepath

    def export_equity_curve(self, equity_data: list) -> str:
        filepath = os.path.join(self.output_dir, "equity_curve.json")
        with open(filepath, "w") as f:
            json.dump(equity_data, f, indent=2, default=str)
        return filepath
