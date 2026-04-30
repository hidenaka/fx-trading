from typing import Dict, Tuple


class ExposureManager:
    # Tracks open positions and limits stacking exposure on a single currency.
    # Each FX pair is a long-base/short-quote bet (or the inverse for shorts);
    # opening multiple correlated pairs that share a currency in the same
    # direction silently doubles risk on that currency. We block that here.

    def __init__(self, max_positions: int = 3, max_positions_per_currency: int = 2):
        if max_positions <= 0:
            raise ValueError("max_positions must be positive")
        if max_positions_per_currency <= 0:
            raise ValueError("max_positions_per_currency must be positive")
        self.max_positions = max_positions
        self.max_positions_per_currency = max_positions_per_currency
        self.open_positions: Dict[str, int] = {}

    @staticmethod
    def _currencies(pair: str) -> Tuple[str, str]:
        parts = pair.split("_")
        if len(parts) != 2:
            raise ValueError(f"Pair must be in BASE_QUOTE format: {pair}")
        return parts[0], parts[1]

    def register(self, pair: str, direction: int) -> None:
        if direction not in (1, -1):
            raise ValueError("direction must be 1 (long) or -1 (short)")
        self._currencies(pair)  # validate format
        self.open_positions[pair] = direction

    def unregister(self, pair: str) -> None:
        self.open_positions.pop(pair, None)

    def currency_position_count(self, currency: str, currency_direction: int) -> int:
        # Counts how many open pairs are net long (or short) the given currency.
        count = 0
        for pair, pair_dir in self.open_positions.items():
            base, quote = self._currencies(pair)
            if base == currency and pair_dir == currency_direction:
                count += 1
            elif quote == currency and -pair_dir == currency_direction:
                count += 1
        return count

    def can_open(self, pair: str, direction: int) -> bool:
        if direction not in (1, -1):
            raise ValueError("direction must be 1 (long) or -1 (short)")
        if pair in self.open_positions:
            # No pyramiding — caller should close before re-entering.
            return False
        if len(self.open_positions) >= self.max_positions:
            return False

        base, quote = self._currencies(pair)
        # Long pair = long base + short quote; short pair = short base + long quote.
        base_currency_dir = direction
        quote_currency_dir = -direction

        if self.currency_position_count(base, base_currency_dir) >= self.max_positions_per_currency:
            return False
        if self.currency_position_count(quote, quote_currency_dir) >= self.max_positions_per_currency:
            return False

        return True
