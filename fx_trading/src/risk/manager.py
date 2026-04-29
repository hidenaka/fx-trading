class RiskManager:
    def __init__(self, capital: float, risk_per_trade: float = 0.01):
        self.capital = capital
        self.risk_per_trade = risk_per_trade

    def calculate_lot(self, entry_price: float, stop_loss: float) -> float:
        risk_amount = self.capital * self.risk_per_trade
        price_diff = abs(entry_price - stop_loss)
        if price_diff == 0:
            return 0.0
        lot = risk_amount / price_diff
        return lot

    def update_capital(self, pnl: float):
        self.capital += pnl
