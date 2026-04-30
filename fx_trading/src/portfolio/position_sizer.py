class PositionSizer:
    def __init__(self, volatility_target: float = 0.05, kelly_fraction: float = 0.5):
        self.volatility_target = volatility_target
        self._kelly_fraction = kelly_fraction

    def kelly_fraction(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        b = avg_win / avg_loss if avg_loss != 0 else 0
        p = win_rate
        q = 1 - p
        f = (b * p - q) / b if b != 0 else 0
        return round(max(0.0, min(f, 1.0)), 10)

    def calculate_lot(self, capital: float, entry_price: float, stop_loss: float,
                     win_rate: float = 0.5, avg_win: float = 1.0, avg_loss: float = 1.0,
                     current_volatility: float = 0.02) -> float:
        kelly = self.kelly_fraction(win_rate, avg_win, avg_loss)
        kelly = kelly * self._kelly_fraction  # half-kelly or custom fraction
        
        # Volatility adjustment
        vol_ratio = self.volatility_target / current_volatility if current_volatility > 0 else 1.0
        vol_adjustment = min(vol_ratio, 1.0)  # cap at 1x
        
        risk_amount = capital * kelly * vol_adjustment
        price_diff = abs(entry_price - stop_loss)
        
        if price_diff == 0:
            return 0.0
        
        lot = risk_amount / price_diff
        return lot
