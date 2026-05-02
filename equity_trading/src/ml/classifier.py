"""ML 分類器学習・walk-forward 評価."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

from equity_trading.src.ml.outcome_labeler import LabeledCandidate
from equity_trading.src.ml.walk_forward import WalkForwardSplit


MIN_TRAIN = 30
MIN_TEST = 10


@dataclass(frozen=True)
class FoldMetrics:
    fold_id: int
    n_train: int
    n_test: int
    baseline_test_wr: float
    auc: float
    wr_at_p_50: float
    n_kept_at_p_50: int
    wr_at_p_60: float
    n_kept_at_p_60: int
    wr_at_p_70: float
    n_kept_at_p_70: int


@dataclass(frozen=True)
class TrainingResult:
    model_name: str
    folds: list[FoldMetrics]
    feature_names: list[str]
    feature_importance: dict
    n_total_train: int
    n_total_test: int


def train_walk_forward(
    labeled: list[LabeledCandidate],
    feature_names: list[str],
    splits: list[WalkForwardSplit],
    model_name: str = "gbm",
) -> TrainingResult:
    if model_name not in {"logreg", "gbm"}:
        raise ValueError(f"unknown model_name: {model_name}")

    fold_metrics: list[FoldMetrics] = []
    last_importance = {f: 0.0 for f in feature_names}
    n_total_train = 0
    n_total_test = 0

    for split in splits:
        if len(split.train_indices) < MIN_TRAIN or len(split.test_indices) < MIN_TEST:
            continue

        X_train = _build_X(labeled, split.train_indices, feature_names)
        y_train = np.array([labeled[i].win for i in split.train_indices], dtype=int)
        X_test = _build_X(labeled, split.test_indices, feature_names)
        y_test = np.array([labeled[i].win for i in split.test_indices], dtype=int)

        # Need both classes in train for fitting
        if len(np.unique(y_train)) < 2:
            continue

        if model_name == "logreg":
            scaler = StandardScaler()
            X_train_s = scaler.fit_transform(X_train)
            X_test_s = scaler.transform(X_test)
            model = LogisticRegression(C=1.0, max_iter=1000, class_weight="balanced")
            model.fit(X_train_s, y_train)
            p = model.predict_proba(X_test_s)[:, 1]
            importance = {f: abs(float(c)) for f, c in zip(feature_names, model.coef_[0])}
        else:  # gbm
            model = GradientBoostingClassifier(
                n_estimators=50, max_depth=3, learning_rate=0.05, random_state=42,
            )
            model.fit(X_train, y_train)
            p = model.predict_proba(X_test)[:, 1]
            importance = {f: float(v) for f, v in zip(feature_names, model.feature_importances_)}

        # AUC
        try:
            auc = float(roc_auc_score(y_test, p))
        except ValueError:
            auc = float("nan")

        baseline_wr = float(y_test.mean())

        wr_50, n_50 = _wr_at_threshold(y_test, p, 0.50)
        wr_60, n_60 = _wr_at_threshold(y_test, p, 0.60)
        wr_70, n_70 = _wr_at_threshold(y_test, p, 0.70)

        fold_metrics.append(FoldMetrics(
            fold_id=split.fold_id,
            n_train=len(split.train_indices),
            n_test=len(split.test_indices),
            baseline_test_wr=baseline_wr,
            auc=auc,
            wr_at_p_50=wr_50, n_kept_at_p_50=n_50,
            wr_at_p_60=wr_60, n_kept_at_p_60=n_60,
            wr_at_p_70=wr_70, n_kept_at_p_70=n_70,
        ))
        last_importance = importance
        n_total_train += len(split.train_indices)
        n_total_test += len(split.test_indices)

    return TrainingResult(
        model_name=model_name,
        folds=fold_metrics,
        feature_names=list(feature_names),
        feature_importance=last_importance,
        n_total_train=n_total_train,
        n_total_test=n_total_test,
    )


def _build_X(labeled: list[LabeledCandidate], indices: list[int],
             feature_names: list[str]) -> np.ndarray:
    rows = []
    for i in indices:
        feats = labeled[i].signal.features
        row = []
        for fn in feature_names:
            v = feats.get(fn, 0.0)
            if v is None or (isinstance(v, float) and np.isnan(v)):
                v = 0.0
            row.append(float(v))
        rows.append(row)
    return np.array(rows, dtype=float)


def _wr_at_threshold(y: np.ndarray, p: np.ndarray, thresh: float) -> tuple[float, int]:
    mask = p >= thresh
    n = int(mask.sum())
    if n == 0:
        return float("nan"), 0
    wr = float(y[mask].mean())
    return wr, n
