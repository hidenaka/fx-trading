from dataclasses import dataclass


@dataclass
class CostModel:
    spread_pips: float = 0.0
    slippage_pips: float = 0.0
    swap_long_per_unit_per_day: float = 0.0
    swap_short_per_unit_per_day: float = 0.0
    pip_size: float = 0.01  # 0.01 for JPY-quoted pairs, 0.0001 for others.

    def _per_side_cost(self) -> float:
        # Half the spread is paid per fill (cross the bid/ask once), and
        # slippage is added on top of each fill.
        return (self.spread_pips / 2.0 + self.slippage_pips) * self.pip_size

    def adjust_entry(self, mid_price: float, direction: int) -> float:
        return mid_price + direction * self._per_side_cost()

    def adjust_exit(self, mid_price: float, direction: int) -> float:
        return mid_price - direction * self._per_side_cost()

    def swap_pnl(self, lot: float, direction: int, days_held: float) -> float:
        if days_held <= 0:
            return 0.0
        rate = self.swap_long_per_unit_per_day if direction == 1 else self.swap_short_per_unit_per_day
        return rate * lot * days_held

    @classmethod
    def oanda_jpy_typical(cls) -> "CostModel":
        # Rough OANDA spreads/swaps for major JPY pairs. Override in production
        # with broker-specific values pulled from the live feed.
        return cls(
            spread_pips=1.2,
            slippage_pips=0.3,
            swap_long_per_unit_per_day=0.0,
            swap_short_per_unit_per_day=0.0,
            pip_size=0.01,
        )
