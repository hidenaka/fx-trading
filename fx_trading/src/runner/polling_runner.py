import datetime
from typing import Optional
from src.config.settings import Settings
from src.broker.oanda_client import OandaClient
from src.broker.order_builder import OrderBuilder
from src.risk.manager import RiskManager
from src.strategies.ma_macd import MaMacdStrategy
from src.safety.circuit_breaker import CircuitBreaker
from src.monitoring.logger import TradeLogger

class PollingRunner:
    def __init__(self, config: Optional[Settings] = None):
        self.config = config or Settings()
        self.client = OandaClient(
            api_token=self.config.api_token,
            account_id=self.config.account_id,
            environment=self.config.environment,
        )
        self.circuit_breaker = CircuitBreaker(
            max_daily_loss_pct=self.config.max_daily_loss_pct,
            trading_start_hour=self.config.trading_start_hour,
            trading_end_hour=self.config.trading_end_hour,
            initial_capital=self.config.initial_capital,
        )
        self.logger = TradeLogger()
        self.order_builder = OrderBuilder(instrument=self.config.currency_pair)
        self.risk_manager = RiskManager(
            capital=self.config.initial_capital,
            risk_per_trade=self.config.risk_per_trade,
        )
        self.strategy = MaMacdStrategy(fast=3, slow=6, signal=2)

    def run_cycle(self) -> bool:
        now = datetime.datetime.now()
        
        # 1. Check circuit breaker
        if not self.circuit_breaker.is_trading_allowed(now):
            self.logger.log_info("Trading not allowed by circuit breaker")
            return False
        
        try:
            # 2. Get current price and positions
            price = self.client.get_current_price(self.config.currency_pair)
            positions = self.client.get_open_positions()
            
            # 3. Build minimal dataframe for signal generation
            import pandas as pd
            df = pd.DataFrame({
                "datetime": [now],
                "open": [price["bid"]],
                "high": [price["ask"]],
                "low": [price["bid"]],
                "close": [price["ask"]],
                "volume": [1],
            })
            
            # 4. Generate signals (in real system, we'd fetch more history)
            df = self.strategy.generate_signals(df)
            signal = int(df.iloc[-1]["signal"])
            
            # 5. Check positions and act
            if not positions:
                # No position - check entry signal
                if signal != 0:
                    entry_price = price["ask"] if signal == 1 else price["bid"]
                    stop_loss = entry_price * 0.99 if signal == 1 else entry_price * 1.01
                    take_profit = entry_price * 1.02 if signal == 1 else entry_price * 0.98
                    units = int(self.risk_manager.calculate_lot(entry_price, stop_loss))
                    
                    if units > 0:
                        order = self.order_builder.build_market_order(
                            direction=signal,
                            units=units,
                            stop_loss=stop_loss,
                            take_profit=take_profit,
                        )
                        result = self.client.place_order(order)
                        self.logger.log_trade(
                            self.config.currency_pair,
                            "BUY" if signal == 1 else "SELL",
                            units,
                            entry_price,
                        )
                        self.logger.log_info(f"Order placed: {result}")
            else:
                # Have position - check exit signal
                current_pos = positions[0]
                long_units = float(current_pos.get("long", {}).get("units", 0))
                short_units = float(current_pos.get("short", {}).get("units", 0))
                current_direction = 1 if long_units > 0 else -1 if short_units < 0 else 0
                
                # Exit if signal changes direction
                if signal != 0 and signal != current_direction:
                    self.client.close_position(self.config.currency_pair)
                    self.logger.log_trade(
                        self.config.currency_pair,
                        "CLOSE",
                        0,
                        price["bid"] if current_direction == 1 else price["ask"],
                    )
            
            return True
            
        except Exception as e:
            self.logger.log_error(f"Error in trading cycle: {e}")
            return False
