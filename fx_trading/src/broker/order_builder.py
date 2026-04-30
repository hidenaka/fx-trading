from typing import Optional

class OrderBuilder:
    def __init__(self, instrument: str):
        self.instrument = instrument

    def build_market_order(self, direction: int, units: int,
                           stop_loss: float,
                           take_profit: Optional[float] = None) -> dict:
        # Stop-loss is mandatory. An order without one can run indefinitely
        # against the position — the largest source of blow-up risk we have.
        if stop_loss is None:
            raise ValueError("stop_loss is required for every market order")
        if direction == 1 and stop_loss <= 0:
            raise ValueError("long stop_loss must be positive")
        if direction == -1 and stop_loss <= 0:
            raise ValueError("short stop_loss must be positive")

        order = {
            "type": "MARKET",
            "instrument": self.instrument,
            "units": str(units * direction),
            "stopLossOnFill": {"price": f"{stop_loss:.2f}"},
        }
        if take_profit is not None:
            order["takeProfitOnFill"] = {"price": f"{take_profit:.2f}"}
        return order
