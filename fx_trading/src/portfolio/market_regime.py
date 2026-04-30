import pandas as pd
import numpy as np

class MarketRegimeDetector:
    def __init__(self, lookback: int = 14, trend_threshold: float = 25.0, ranging_threshold: float = 20.0):
        self.lookback = lookback
        self.trend_threshold = trend_threshold
        self.ranging_threshold = ranging_threshold

    def _calculate_adx(self, df: pd.DataFrame) -> float:
        df = df.copy()
        # True Range
        df["tr1"] = df["high"] - df["low"]
        df["tr2"] = abs(df["high"] - df["close"].shift(1))
        df["tr3"] = abs(df["low"] - df["close"].shift(1))
        df["tr"] = df[["tr1", "tr2", "tr3"]].max(axis=1)
        
        # +DM, -DM
        df["plus_dm"] = df["high"].diff()
        df["minus_dm"] = -df["low"].diff()
        df["plus_dm"] = df["plus_dm"].where(df["plus_dm"] > 0, 0)
        df["minus_dm"] = df["minus_dm"].where(df["minus_dm"] > 0, 0)
        
        # Smooth TR and DM
        atr = df["tr"].rolling(window=self.lookback).mean()
        plus_di = 100 * (df["plus_dm"].rolling(window=self.lookback).mean() / atr)
        minus_di = 100 * (df["minus_dm"].rolling(window=self.lookback).mean() / atr)
        
        # DX and ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=self.lookback).mean()
        
        return adx.iloc[-1] if not adx.empty else 0.0

    def detect(self, df: pd.DataFrame) -> str:
        if len(df) < self.lookback * 2:
            return "neutral"
        
        adx = self._calculate_adx(df)
        
        if pd.isna(adx):
            return "neutral"
        
        if adx >= self.trend_threshold:
            return "trending"
        elif adx <= self.ranging_threshold:
            return "ranging"
        else:
            return "neutral"
