from typing import Optional

class OrderBuilder:
    def __init__(self, instrument: str):
        self.instrument = instrument

    def build_market_order(self, direction: int, units: int,
                           stop_loss: Optional[float] = None,
                           take_profit: Optional[float] = None) -> dict:
        order = {
            "type": "MARKET",
            "instrument": self.instrument,
            "units": str(units * direction),
        }
        if stop_loss is not None:
            order["stopLossOnFill"] = {"price": f"{stop_loss:.2f}"}
        if take_profit is not None:
            order["takeProfitOnFill"] = {"price": f"{take_profit:.2f}"}
        return order
