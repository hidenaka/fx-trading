import numpy as np
import pandas as pd
import pytest

from equity_trading.src.ml.candidate_dataset import CandidateSignal
from equity_trading.src.ml.classifier import (
    FoldMetrics, TrainingResult, train_walk_forward,
)
from equity_trading.src.ml.outcome_labeler import LabeledCandidate
from equity_trading.src.ml.walk_forward import walk_forward_splits


def _synth_labeled(n: int = 500, seed: int = 42) -> list[LabeledCandidate]:
    """Synthetic dataset where outcome depends on `score_value` linearly."""
    rng = np.random.default_rng(seed)
    out = []
    base_ts = pd.Timestamp("2024-01-01", tz="UTC")
    for i in range(n):
        score = float(rng.uniform(0.0, 1.0))
        # Win prob = 0.3 + 0.5 * score (range [0.3, 0.8])
        win = bool(rng.random() < 0.3 + 0.5 * score)
        ts = base_ts + pd.Timedelta(hours=i * 6)  # one signal per 6 hours
        feats = {
            "score_value": score,
            "rsi_14": float(rng.uniform(20, 80)),
            "ny_hour": float(rng.integers(9, 16)),
        }
        sig = CandidateSignal(
            timestamp=ts, symbol="XLK",
            strategy_name="mean_reversion",
            features=feats, bar_index=i,
        )
        out.append(LabeledCandidate(
            signal=sig, win=win,
            pnl_pct=0.005 if win else -0.005,
            exit_type="target" if win else "stop",
            bars_held=10,
        ))
    return out


def test_train_walk_forward_returns_training_result():
    labeled = _synth_labeled(n=500)
    timestamps = [lc.signal.timestamp for lc in labeled]
    splits = walk_forward_splits(
        timestamps=timestamps,
        train_window_days=60, test_window_days=15, step_days=15, purge_gap_days=1,
    )
    assert len(splits) >= 3, f"need ≥3 folds, got {len(splits)}"

    result = train_walk_forward(
        labeled=labeled,
        feature_names=["score_value", "rsi_14", "ny_hour"],
        splits=splits,
        model_name="gbm",
    )
    assert isinstance(result, TrainingResult)
    assert result.model_name == "gbm"
    assert len(result.folds) >= 1
    for f in result.folds:
        assert isinstance(f, FoldMetrics)
        assert 0.0 <= f.auc <= 1.0
        # baseline_test_wr should be in [0, 1]
        assert 0.0 <= f.baseline_test_wr <= 1.0


def test_train_walk_forward_logreg_works():
    labeled = _synth_labeled(n=500)
    timestamps = [lc.signal.timestamp for lc in labeled]
    splits = walk_forward_splits(
        timestamps=timestamps,
        train_window_days=60, test_window_days=15, step_days=15,
    )
    result = train_walk_forward(
        labeled=labeled,
        feature_names=["score_value", "rsi_14", "ny_hour"],
        splits=splits,
        model_name="logreg",
    )
    assert result.model_name == "logreg"
    assert len(result.folds) >= 1


def test_train_walk_forward_filter_increases_wr_for_signal_dependent_data():
    """When the synthetic outcome depends on score_value, the GBM should pick this
    up: WR at high p_win threshold > baseline WR (averaged across folds)."""
    labeled = _synth_labeled(n=600, seed=1)
    timestamps = [lc.signal.timestamp for lc in labeled]
    splits = walk_forward_splits(
        timestamps=timestamps,
        train_window_days=60, test_window_days=15, step_days=15,
    )
    result = train_walk_forward(
        labeled=labeled,
        feature_names=["score_value", "rsi_14", "ny_hour"],
        splits=splits,
        model_name="gbm",
    )
    # Average across folds
    folds_with_p60 = [f for f in result.folds if f.n_kept_at_p_60 >= 5]
    if not folds_with_p60:
        pytest.skip("not enough kept-at-p>=0.6 samples to evaluate")
    avg_baseline = np.mean([f.baseline_test_wr for f in folds_with_p60])
    avg_p60 = np.mean([f.wr_at_p_60 for f in folds_with_p60])
    assert avg_p60 > avg_baseline, f"filter didn't help: baseline {avg_baseline:.3f} vs p>=0.6 {avg_p60:.3f}"


def test_train_walk_forward_skips_tiny_folds():
    """Folds with very few samples should be skipped (or handled gracefully)."""
    labeled = _synth_labeled(n=20, seed=42)
    timestamps = [lc.signal.timestamp for lc in labeled]
    splits = walk_forward_splits(
        timestamps=timestamps,
        train_window_days=60, test_window_days=15, step_days=15,
    )
    result = train_walk_forward(
        labeled=labeled, feature_names=["score_value", "rsi_14", "ny_hour"],
        splits=splits, model_name="gbm",
    )
    # Should not crash, should return TrainingResult (folds may be empty)
    assert isinstance(result, TrainingResult)


def test_train_walk_forward_returns_feature_importance():
    labeled = _synth_labeled(n=500, seed=7)
    timestamps = [lc.signal.timestamp for lc in labeled]
    splits = walk_forward_splits(
        timestamps=timestamps,
        train_window_days=60, test_window_days=15, step_days=15,
    )
    result = train_walk_forward(
        labeled=labeled, feature_names=["score_value", "rsi_14", "ny_hour"],
        splits=splits, model_name="gbm",
    )
    assert set(result.feature_importance.keys()) == {"score_value", "rsi_14", "ny_hour"}
    # In synthetic data, score_value should rank above ny_hour
    assert result.feature_importance["score_value"] >= result.feature_importance["ny_hour"]
