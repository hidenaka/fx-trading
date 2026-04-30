import datetime
from typing import Optional, List, Union
from src.config.settings import Settings
from src.broker.oanda_client import OandaClient
from src.broker.order_builder import OrderBuilder
from src.risk.manager import RiskManager
from src.strategies.factory import StrategyFactory
from src.strategies.base import Strategy
from src.safety.circuit_breaker import CircuitBreaker
from src.monitoring.logger import TradeLogger
from src.portfolio.portfolio_manager import PortfolioManager

class PollingRunner:
    def __init__(
        self,
        config: Optional[Settings] = None,
        strategies: Optional[List[Union[str, Strategy]]] = None,
    ):
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
        default_instrument = getattr(self.config, "currency_pair", None) or self.config.currency_pairs[0]
        self.order_builder = OrderBuilder(instrument=default_instrument)
        self.risk_manager = RiskManager(
            capital=self.config.initial_capital,
            risk_per_trade=self.config.risk_per_trade,
        )
        self.portfolio_manager = PortfolioManager()
        self.dry_run = False

        if strategies is None:
            strategies = ["ma_macd"]

        self.strategies: List[Strategy] = []
        for s in strategies:
            if isinstance(s, str):
                self.strategies.append(StrategyFactory.create(s))
            else:
                self.strategies.append(s)

    def _aggregate_signals(self, df) -> int:
        """Aggregate signals from all strategies by majority vote."""
        signals = []
        for strategy in self.strategies:
            sig_df = strategy.generate_signals(df.copy())
            signal = int(sig_df.iloc[-1]["signal"])
            signals.append(signal)

        buy_votes = sum(1 for s in signals if s == 1)
        sell_votes = sum(1 for s in signals if s == -1)
        neutral_votes = sum(1 for s in signals if s == 0)

        if buy_votes > sell_votes and buy_votes > neutral_votes:
            return 1
        elif sell_votes > buy_votes and sell_votes > neutral_votes:
            return -1
        else:
            return 0

    def run_cycle(self, pair: Optional[str] = None) -> bool:
        instrument = pair or getattr(self.config, "currency_pair", None) or self.config.currency_pairs[0]
        now = datetime.datetime.now()
        
        # 1. Check circuit breaker
        if not self.circuit_breaker.is_trading_allowed(now):
            self.logger.log_info("Trading not allowed by circuit breaker")
            return False
        
        try:
            # 2. Get current price and positions
            price = self.client.get_current_price(instrument)
            positions = self.client.get_open_positions()
            
            # Filter positions for this instrument
            pair_positions = [p for p in positions if p.get("instrument") == instrument]
            
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
            
            # 4. Generate signals from all strategies and aggregate
            signal = self._aggregate_signals(df)
            
            # Use pair-specific order builder if needed
            order_builder = self.order_builder
            if pair and pair != getattr(self.config, "currency_pair", None):
                order_builder = OrderBuilder(instrument=pair)
            
            # 5. Check positions and act
            if not pair_positions:
                # No position - check entry signal
                if signal != 0:
                    entry_price = price["ask"] if signal == 1 else price["bid"]
                    stop_loss = entry_price * 0.99 if signal == 1 else entry_price * 1.01
                    take_profit = entry_price * 1.02 if signal == 1 else entry_price * 0.98
                    units = int(self.risk_manager.calculate_lot(entry_price, stop_loss))
                    
                    if units > 0:
                        order = order_builder.build_market_order(
                            direction=signal,
                            units=units,
                            stop_loss=stop_loss,
                            take_profit=take_profit,
                        )
                        result = self.client.place_order(order)
                        self.logger.log_trade(
                            instrument,
                            "BUY" if signal == 1 else "SELL",
                            units,
                            entry_price,
                        )
                        self.logger.log_info(f"Order placed: {result}")
            else:
                # Have position - check exit signal
                current_pos = pair_positions[0]
                long_units = float(current_pos.get("long", {}).get("units", 0))
                short_units = float(current_pos.get("short", {}).get("units", 0))
                current_direction = 1 if long_units > 0 else -1 if short_units < 0 else 0
                
                # Exit if signal changes direction
                if signal != 0 and signal != current_direction:
                    self.client.close_position(instrument)
                    self.logger.log_trade(
                        instrument,
                        "CLOSE",
                        0,
                        price["bid"] if current_direction == 1 else price["ask"],
                    )
            
            return True
            
        except Exception as e:
            self.logger.log_error(f"Error in trading cycle: {e}")
            return False
    
    def run_all_pairs(self) -> dict:
        results = {}
        for pair in self.config.currency_pairs:
            results[pair] = self.run_cycle(pair=pair)
        return results

    def run_portfolio_cycle(self):
        """Run one cycle using PortfolioManager for all pairs."""
        import pandas as pd
        results = {}
        
        for pair in self.config.currency_pairs:
            try:
                # Load recent data
                df = pd.read_csv(f"data/{pair.lower()}_h1.csv", parse_dates=["datetime"])
                recent_df = df.tail(50).copy()
                
                # Generate signal using PortfolioManager
                result = self.portfolio_manager.generate_signal(recent_df)
                signal = result["signal"]
                
                if signal != 0:
                    latest_price = recent_df.iloc[-1]["close"]
                    stop_loss = latest_price * 0.99 if signal == 1 else latest_price * 1.01
                    lot = self.portfolio_manager.calculate_position(
                        self.config.initial_capital,
                        latest_price,
                        stop_loss,
                    )
                    print(f"[Portfolio] {pair}: {'BUY' if signal == 1 else 'SELL'} @ {latest_price:.3f}, Lot={lot:.2f}, Regime={result['regime']}")
                    
                    if not self.dry_run:
                        # Actually place order
                        pass  # TODO: integrate with broker
                
                results[pair] = result
            except Exception as e:
                print(f"[Portfolio] Error processing {pair}: {e}")
                results[pair] = {"signal": 0, "error": str(e)}
        
        return results
