import pandas as pd
import numpy as np
from typing import Tuple

class FeatureEngineer:
    def __init__(self, lookback: int = 10):
        self.lookback = lookback

    def prepare(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        df = df.copy()
        
        # Returns
        df["returns"] = df["close"].pct_change()
        
        # Moving averages
        df["sma_5"] = df["close"].rolling(window=5).mean()
        df["sma_10"] = df["close"].rolling(window=10).mean()
        df["sma_20"] = df["close"].rolling(window=20).mean()
        
        # Distance from MAs
        df["dist_sma5"] = (df["close"] - df["sma_5"]) / df["sma_5"]
        df["dist_sma10"] = (df["close"] - df["sma_10"]) / df["sma_10"]
        
        # Volatility
        df["volatility"] = df["returns"].rolling(window=10).std()
        
        # Price range
        df["range"] = (df["high"] - df["low"]) / df["close"]
        
        # Volume change
        df["volume_change"] = df["volume"].pct_change()
        
        # RSI-like feature
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        df["rsi"] = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))
        
        # Target: 1 if next close is higher, 0 otherwise
        df["target"] = (df["close"].shift(-1) > df["close"]).astype(int)
        
        # Select feature columns
        feature_cols = [
            "returns", "dist_sma5", "dist_sma10", 
            "volatility", "range", "volume_change", "rsi"
        ]
        
        # Drop NaN rows
        df = df.dropna()
        
        X = df[feature_cols]
        y = df["target"]
        
        return X, y
