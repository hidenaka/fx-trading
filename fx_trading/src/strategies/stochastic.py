import pandas as pd
from .base import Strategy

class StochasticStrategy(Strategy):
    def __init__(self, k_period: int = 14, d_period: int = 3,
                 overbought: float = 80.0, oversold: float = 20.0):
        self.k_period = k_period
        self.d_period = d_period
        self.overbought = overbought
        self.oversold = oversold

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        low_min = df["low"].rolling(window=self.k_period).min()
        high_max = df["high"].rolling(window=self.k_period).max()
        
        # Avoid division by zero
        denominator = high_max - low_min
        denominator = denominator.replace(0, pd.NA)
        
        df["stoch_k"] = 100 * ((df["close"] - low_min) / denominator)
        df["stoch_d"] = df["stoch_k"].rolling(window=self.d_period).mean()
        
        df["signal"] = 0
        # Buy: %K crosses above %D from oversold
        buy_condition = (df["stoch_k"] > df["stoch_d"]) & (df["stoch_k"].shift(1) <= df["stoch_d"].shift(1)) & (df["stoch_k"] < self.oversold)
        df.loc[buy_condition, "signal"] = 1
        
        # Sell: %K crosses below %D from overbought
        sell_condition = (df["stoch_k"] < df["stoch_d"]) & (df["stoch_k"].shift(1) >= df["stoch_d"].shift(1)) & (df["stoch_k"] > self.overbought)
        df.loc[sell_condition, "signal"] = -1
        
        return df
