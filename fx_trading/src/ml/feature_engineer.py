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
        
        # MACD
        ema_12 = df["close"].ewm(span=12, adjust=False).mean()
        ema_26 = df["close"].ewm(span=26, adjust=False).mean()
        df["macd"] = ema_12 - ema_26
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]
        
        # Bollinger Bands
        bb_mid = df["close"].rolling(window=20).mean()
        bb_std = df["close"].rolling(window=20).std()
        df["bb_upper_1"] = bb_mid + 1 * bb_std
        df["bb_lower_1"] = bb_mid - 1 * bb_std
        df["bb_upper_2"] = bb_mid + 2 * bb_std
        df["bb_lower_2"] = bb_mid - 2 * bb_std
        
        # ATR (Average True Range)
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["atr_14"] = tr.rolling(window=14).mean()
        
        # Price patterns
        body = (df["close"] - df["open"]).abs()
        range_hl = df["high"] - df["low"]
        upper_shadow = df["high"] - df[["open", "close"]].max(axis=1)
        lower_shadow = df[["open", "close"]].min(axis=1) - df["low"]
        
        df["doji"] = (body <= 0.1 * range_hl).astype(int)
        df["hammer"] = ((body <= 0.3 * range_hl) & (lower_shadow >= 2 * body) & (upper_shadow <= body)).astype(int)
        
        # Target: 1 if next close is higher, 0 otherwise
        df["target"] = (df["close"].shift(-1) > df["close"]).astype(int)
        
        # Select feature columns
        feature_cols = [
            "returns", "dist_sma5", "dist_sma10", 
            "volatility", "range", "volume_change", "rsi",
            "macd_hist", "bb_upper_1", "bb_lower_1", "bb_upper_2", "bb_lower_2",
            "atr_14", "doji", "hammer"
        ]
        
        # Drop NaN rows
        df = df.dropna()
        
        X = df[feature_cols]
        y = df["target"]
        
        return X, y
