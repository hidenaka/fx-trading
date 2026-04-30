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
from src.risk.exposure_manager import ExposureManager


def _cfg(config, name, default, cast):
    # Safe config read: getattr returns auto-attrs on MagicMock test doubles,
    # so we additionally try to coerce to the expected type and fall back on
    # failure. Real Settings objects always pass through cleanly.
    value = getattr(config, name, default)
    try:
        return cast(value)
    except (TypeError, ValueError):
        return default


def _extract_realized_pnl(close_response: dict) -> float:
    # OANDA's close_position returns long/short fill transactions; each carries
    # a `pl` field with realized PnL in account currency. SL/TP-driven exits
    # are NOT routed through here — they need a separate transaction-history
    # reconciler to keep the circuit breaker in sync.
    if not isinstance(close_response, dict):
        return 0.0
    pnl = 0.0
    for key in ("longOrderFillTransaction", "shortOrderFillTransaction"):
        fill = close_response.get(key) or {}
        try:
            pnl += float(fill.get("pl", 0) or 0)
        except (ValueError, TypeError):
            continue
    return pnl


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
            max_daily_loss_pct=_cfg(self.config, "max_daily_loss_pct", 5.0, float),
            trading_start_hour=_cfg(self.config, "trading_start_hour", 0, int),
            trading_end_hour=_cfg(self.config, "trading_end_hour", 24, int),
            initial_capital=_cfg(self.config, "initial_capital", 1_000_000, float),
            max_drawdown_pct=_cfg(self.config, "max_drawdown_pct", 15.0, float),
            max_consecutive_losses=_cfg(self.config, "max_consecutive_losses", 5, int),
        )
        self.logger = TradeLogger()
        default_instrument = getattr(self.config, "currency_pair", None) or self.config.currency_pairs[0]
        self.order_builder = OrderBuilder(instrument=default_instrument)
        self.risk_manager = RiskManager(
            capital=self.config.initial_capital,
            risk_per_trade=self.config.risk_per_trade,
        )
        self.portfolio_manager = PortfolioManager()
        self.exposure_manager = ExposureManager(
            max_positions=_cfg(self.config, "max_open_positions", 3, int),
            max_positions_per_currency=_cfg(self.config, "max_positions_per_currency", 2, int),
        )
        self.dry_run = False
        # Cursor for OANDA's transactions/sinceid stream. "0" tells the broker
        # to return every transaction the account has ever had on first call,
        # which is fine for practice/fresh accounts but expensive on live
        # accounts with long history. Production should override this by
        # priming from the broker's lastTransactionID at startup.
        self.last_transaction_id = "0"

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
        
        # 0. Pull broker fills that happened outside our control (SL/TP) so
        # the circuit breaker has the full PnL picture before deciding.
        self._reconcile_realized_pnl(now)

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
            
            # Sync exposure manager with broker truth so externally-closed
            # positions (SL/TP) don't leave stale slots blocking new entries.
            self._sync_exposure_from_broker(positions)

            # 5. Check positions and act
            if not pair_positions:
                # No position - check entry signal
                if signal != 0:
                    if not self.exposure_manager.can_open(instrument, signal):
                        self.logger.log_info(
                            f"Exposure limit blocks entry on {instrument} (signal={signal})"
                        )
                        return True

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
                        self.exposure_manager.register(instrument, signal)
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
                    close_response = self.client.close_position(instrument)
                    realized_pnl = _extract_realized_pnl(close_response)
                    self.circuit_breaker.record_pnl(realized_pnl, now=now)
                    # Advance cursor past this fill so the reconcile loop on
                    # the next cycle does not re-apply the same PnL.
                    fill_id = (
                        close_response.get("longOrderFillTransaction", {}).get("id")
                        or close_response.get("shortOrderFillTransaction", {}).get("id")
                    )
                    if fill_id:
                        self.last_transaction_id = str(fill_id)
                    self.exposure_manager.unregister(instrument)
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
    
    def _sync_exposure_from_broker(self, broker_positions: list) -> None:
        # Replace local view with what the broker reports as actually open.
        live = {}
        for pos in broker_positions:
            inst = pos.get("instrument")
            if not inst:
                continue
            try:
                long_units = float(pos.get("long", {}).get("units", 0) or 0)
                short_units = float(pos.get("short", {}).get("units", 0) or 0)
            except (TypeError, ValueError):
                continue
            if long_units > 0:
                live[inst] = 1
            elif short_units < 0:
                live[inst] = -1
        self.exposure_manager.open_positions = live

    def _reconcile_realized_pnl(self, now: datetime.datetime) -> None:
        # Pulls every fill since the last cursor and feeds non-zero PnL into
        # the circuit breaker. SL/TP fills go through here even though the
        # runner never calls close_position for them.
        try:
            response = self.client.get_transactions_since(self.last_transaction_id)
        except Exception as exc:
            self.logger.log_error(f"Transaction reconcile failed: {exc}")
            return
        for txn in response.get("transactions", []) or []:
            if txn.get("type") != "ORDER_FILL":
                continue
            try:
                pl = float(txn.get("pl", 0) or 0)
            except (TypeError, ValueError):
                continue
            if pl == 0:
                continue
            self.circuit_breaker.record_pnl(pl, now=now)
        new_cursor = response.get("lastTransactionID")
        if new_cursor:
            self.last_transaction_id = str(new_cursor)

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
