import pandas as pd
import numpy as np
from typing import Tuple

class FeatureEngineer:
    FEATURE_COLS = [
        "returns", "dist_sma5", "dist_sma10",
        "volatility", "range", "volume_change", "rsi",
        "macd_hist", "bb_upper_1", "bb_lower_1", "bb_upper_2", "bb_lower_2",
        "atr_14", "doji", "hammer",
    ]

    def __init__(self, lookback: int = 10):
        self.lookback = lookback

    def _compute_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        df["returns"] = df["close"].pct_change()

        df["sma_5"] = df["close"].rolling(window=5).mean()
        df["sma_10"] = df["close"].rolling(window=10).mean()
        df["sma_20"] = df["close"].rolling(window=20).mean()

        df["dist_sma5"] = (df["close"] - df["sma_5"]) / df["sma_5"]
        df["dist_sma10"] = (df["close"] - df["sma_10"]) / df["sma_10"]

        df["volatility"] = df["returns"].rolling(window=10).std()
        df["range"] = (df["high"] - df["low"]) / df["close"]
        df["volume_change"] = df["volume"].pct_change()

        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        df["rsi"] = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))

        ema_12 = df["close"].ewm(span=12, adjust=False).mean()
        ema_26 = df["close"].ewm(span=26, adjust=False).mean()
        df["macd"] = ema_12 - ema_26
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]

        bb_mid = df["close"].rolling(window=20).mean()
        bb_std = df["close"].rolling(window=20).std()
        df["bb_upper_1"] = bb_mid + 1 * bb_std
        df["bb_lower_1"] = bb_mid - 1 * bb_std
        df["bb_upper_2"] = bb_mid + 2 * bb_std
        df["bb_lower_2"] = bb_mid - 2 * bb_std

        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["atr_14"] = tr.rolling(window=14).mean()

        body = (df["close"] - df["open"]).abs()
        range_hl = df["high"] - df["low"]
        upper_shadow = df["high"] - df[["open", "close"]].max(axis=1)
        lower_shadow = df[["open", "close"]].min(axis=1) - df["low"]

        df["doji"] = (body <= 0.1 * range_hl).astype(int)
        df["hammer"] = ((body <= 0.3 * range_hl) & (lower_shadow >= 2 * body) & (upper_shadow <= body)).astype(int)

        return df

    def make_features(self, df: pd.DataFrame) -> pd.DataFrame:
        # Inference path: keep the latest bar so the model can predict on it.
        feats = self._compute_features(df)[self.FEATURE_COLS]
        return feats.dropna()

    def prepare(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        # Training path: target requires the next bar's close; the last row has
        # no future, so we mark its target NaN and drop it via dropna.
        feats = self._compute_features(df)
        next_close = feats["close"].shift(-1)
        target = (next_close > feats["close"]).astype(float)
        target[next_close.isna()] = np.nan

        combined = feats[self.FEATURE_COLS].copy()
        combined["target"] = target
        combined = combined.dropna()

        X = combined[self.FEATURE_COLS]
        y = combined["target"].astype(int)
        return X, y
