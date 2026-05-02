"""ML predict_proba を使った戦略フィルタ・ラッパー."""
from __future__ import annotations

import numpy as np
import pandas as pd

from equity_trading.src.ml.candidate_dataset import _precompute_feature_arrays
from equity_trading.src.strategy.base import TradingStrategy


class MLFilterStrategy(TradingStrategy):
    """Wraps a base strategy with an ML probability gate.

    Only forwards entry signals when model.predict_proba(features)[:, 1] >= threshold.
    All exit logic delegates to the base strategy.
    """

    def __init__(
        self,
        base: TradingStrategy,
        model,
        feature_names: list[str],
        prob_threshold: float = 0.5,
        spy_5min_for_features: pd.DataFrame | None = None,
        scaler=None,
    ) -> None:
        self._base = base
        self._model = model
        self._feature_names = list(feature_names)
        self._prob_threshold = float(prob_threshold)
        self._spy_5min = spy_5min_for_features
        self._scaler = scaler
        # Instance attribute — shadows the class-level `name = ""`
        self.name = f"ml_filtered_{base.name}"

    def compute_entry_signal(
        self,
        bars_5min: pd.DataFrame,
        daily: pd.DataFrame,
        atr_pct: float,
        params: dict,
    ) -> pd.Series:
        base_signal = self._base.compute_entry_signal(bars_5min, daily, atr_pct, params)
        true_idx = np.where(base_signal.to_numpy())[0]
        if len(true_idx) == 0:
            return base_signal

        feature_arrays = _precompute_feature_arrays(
            bars_5min, daily, self._spy_5min, self._base.name, params,
        )

        rows = []
        for i in true_idx:
            row = []
            for fn in self._feature_names:
                arr = feature_arrays.get(fn)
                v = arr[i] if arr is not None else 0.0
                if v is None or (isinstance(v, float) and np.isnan(v)):
                    v = 0.0
                row.append(float(v))
            rows.append(row)
        X = np.array(rows, dtype=float)

        if self._scaler is not None:
            X = self._scaler.transform(X)

        probs = self._model.predict_proba(X)[:, 1]
        keep_mask = probs >= self._prob_threshold

        new_signal = pd.Series(False, index=bars_5min.index, dtype=bool)
        for ki, kept in enumerate(keep_mask):
            if kept:
                new_signal.iloc[int(true_idx[ki])] = True
        return new_signal.astype(bool)

    def compute_exit_levels(
        self,
        bars_5min: pd.DataFrame,
        entry_idx: int,
        entry_price: float,
        atr_pct: float,
        params: dict,
    ) -> tuple[float, float]:
        return self._base.compute_exit_levels(
            bars_5min=bars_5min,
            entry_idx=entry_idx,
            entry_price=entry_price,
            atr_pct=atr_pct,
            params=params,
        )
