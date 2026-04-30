#!/usr/bin/env python3
"""
Update dashboard data files for GitHub Pages.
Runs portfolio backtest and generates JSON data files.
"""
import sys
import os
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from src.data.loader import DataLoader
from src.data.preprocessor import Preprocessor
from src.engine.backtest import BacktestEngine
from src.risk.manager import RiskManager
from src.portfolio.backtest_adapter import PortfolioStrategyAdapter
from src.config.settings import Settings


def update_portfolio_data():
    os.environ.setdefault("OANDA_API_TOKEN", "dummy")
    os.environ.setdefault("OANDA_ACCOUNT_ID", "dummy")
    
    settings = Settings()
    script_dir = Path(__file__).parent.parent
    data_dir = script_dir / "dashboard" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    
    all_signals = {}
    equity_curve = []
    total_capital = settings.initial_capital
    total_pnl = 0
    
    for pair in settings.currency_pairs:
        print(f"Processing {pair}...")
        
        loader = DataLoader(data_dir=str(script_dir / "data"))
        try:
            raw_df = loader.load_csv(pair.lower(), "1h")
        except FileNotFoundError:
            print(f"  No data for {pair}, skipping")
            continue
        
        pre = Preprocessor()
        df = pre.process(raw_df)
        
        risk = RiskManager(capital=settings.initial_capital, risk_per_trade=settings.risk_per_trade)
        engine = BacktestEngine(initial_capital=settings.initial_capital)
        strategy = PortfolioStrategyAdapter(confidence_threshold=2)
        
        trades = engine.run(df, strategy, risk)
        
        # Collect signals from last 50 bars
        recent = df.tail(50).copy()
        try:
            from src.portfolio.portfolio_manager import PortfolioManager
            pm = PortfolioManager()
            result = pm.generate_signal(recent)
            all_signals[pair] = result.get("individual_signals", {})
        except Exception as e:
            print(f"  Signal generation failed: {e}")
            all_signals[pair] = {}
        
        # Equity curve points
        capital = settings.initial_capital
        equity_curve.append({"pair": pair, "index": 0, "capital": capital})
        for i, trade in enumerate(trades[:100]):  # Limit points
            if trade.pnl:
                capital += trade.pnl
                equity_curve.append({"pair": pair, "index": i+1, "capital": capital})
        
        total_capital = engine.capital
        total_pnl += (engine.capital - settings.initial_capital)
    
    # Portfolio summary
    portfolio = {
        "capital": total_capital,
        "daily_pnl": total_pnl,
        "positions": [],
        "signals": all_signals,
        "timestamp": datetime.now().isoformat(),
    }
    
    with open(data_dir / "portfolio.json", "w") as f:
        json.dump(portfolio, f, indent=2)
    
    with open(data_dir / "equity_curve.json", "w") as f:
        json.dump(equity_curve, f, indent=2)
    
    print(f"Updated dashboard data in {data_dir}")
    print(f"  Capital: ¥{total_capital:,.0f}")
    print(f"  P&L: ¥{total_pnl:,.0f}")


if __name__ == "__main__":
    update_portfolio_data()
