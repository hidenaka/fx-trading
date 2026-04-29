from typing import List, Dict

class StrategyRanker:
    def __init__(self, min_trades: int = 20):
        self.min_trades = min_trades

    def rank(self, results: List[Dict]) -> List[Dict]:
        filtered = [r for r in results if r.get("total_trades", 0) >= self.min_trades]
        for r in filtered:
            pf = r.get("profit_factor", 0)
            wr = r.get("win_rate", 0)
            mdd = r.get("max_drawdown", 1)
            if pf == float("inf") or pf is None:
                pf = 0
            if mdd == 0:
                mdd = 1e-6
            r["score"] = (pf * 0.5) + (wr * 2.0) + ((1 / mdd) * 0.05)

        ranked = sorted(filtered, key=lambda x: x["score"], reverse=True)
        return ranked
