import pandas as pd
from .base import Strategy

class DowTheoryStrategy(Strategy):
    def __init__(self, lookback: int = 5):
        self.lookback = lookback

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["higher_high"] = df["high"] > df["high"].shift(1).rolling(window=self.lookback).max()
        df["lower_low"] = df["low"] < df["low"].shift(1).rolling(window=self.lookback).min()
        df["signal"] = 0
        df.loc[df["higher_high"], "signal"] = 1
        df.loc[df["lower_low"], "signal"] = -1
        return df
