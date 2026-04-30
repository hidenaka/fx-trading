import pandas as pd
import numpy as np
from sklearn.model_selection import TimeSeriesSplit
from src.ml.predictor import MLPredictor
from src.ml.trainer import MLTrainer
from src.ml.feature_engineer import FeatureEngineer

def test_feature_engineer_creates_features():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=50, freq="h"),
        "open": np.random.randn(50).cumsum() + 150,
        "high": np.random.randn(50).cumsum() + 151,
        "low": np.random.randn(50).cumsum() + 149,
        "close": np.random.randn(50).cumsum() + 150,
        "volume": np.random.randint(1000, 2000, 50),
    })
    fe = FeatureEngineer()
    X, y = fe.prepare(df)
    assert X.shape[0] > 0
    assert X.shape[1] >= 5  # At least 5 features
    assert len(y) == X.shape[0]
    assert set(y.unique()).issubset({0, 1})  # Binary classification

def test_feature_engineer_returns_dataframe():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=50, freq="h"),
        "open": [150.0] * 50,
        "high": [151.0] * 50,
        "low": [149.0] * 50,
        "close": [150.0 + i * 0.01 for i in range(50)],
        "volume": [1000] * 50,
    })
    fe = FeatureEngineer()
    X, y = fe.prepare(df)
    assert isinstance(X, pd.DataFrame)

def test_predictor_trains_and_predicts():
    # Create synthetic data
    np.random.seed(42)
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=100, freq="h"),
        "open": np.random.randn(100).cumsum() + 150,
        "high": np.random.randn(100).cumsum() + 151,
        "low": np.random.randn(100).cumsum() + 149,
        "close": np.random.randn(100).cumsum() + 150,
        "volume": np.random.randint(1000, 2000, 100),
    })
    fe = FeatureEngineer()
    X, y = fe.prepare(df)
    
    trainer = MLTrainer()
    model = trainer.train(X, y)
    
    predictor = MLPredictor(model)
    proba = predictor.predict_proba(X.iloc[:5])
    assert proba.shape == (5, 2)  # Binary classification
    assert (proba >= 0).all() and (proba <= 1).all()

def test_trainer_evaluates_model():
    np.random.seed(42)
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=100, freq="h"),
        "open": np.random.randn(100).cumsum() + 150,
        "high": np.random.randn(100).cumsum() + 151,
        "low": np.random.randn(100).cumsum() + 149,
        "close": np.random.randn(100).cumsum() + 150,
        "volume": np.random.randint(1000, 2000, 100),
    })
    fe = FeatureEngineer()
    X, y = fe.prepare(df)
    
    trainer = MLTrainer()
    model = trainer.train(X, y)
    metrics = trainer.evaluate(X, y)
    assert "accuracy" in metrics
    assert 0 <= metrics["accuracy"] <= 1

def test_feature_engineer_has_macd_features():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=50, freq="h"),
        "open": np.random.randn(50).cumsum() + 150,
        "high": np.random.randn(50).cumsum() + 151,
        "low": np.random.randn(50).cumsum() + 149,
        "close": np.random.randn(50).cumsum() + 150,
        "volume": np.random.randint(1000, 2000, 50),
    })
    fe = FeatureEngineer()
    X, y = fe.prepare(df)
    assert "macd_hist" in X.columns
    assert X["macd_hist"].notna().sum() > 0

def test_feature_engineer_has_bollinger_bands():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=50, freq="h"),
        "open": np.random.randn(50).cumsum() + 150,
        "high": np.random.randn(50).cumsum() + 151,
        "low": np.random.randn(50).cumsum() + 149,
        "close": np.random.randn(50).cumsum() + 150,
        "volume": np.random.randint(1000, 2000, 50),
    })
    fe = FeatureEngineer()
    X, y = fe.prepare(df)
    for col in ["bb_upper_1", "bb_lower_1", "bb_upper_2", "bb_lower_2"]:
        assert col in X.columns
    # Verify band ordering
    valid = X.dropna()
    assert (valid["bb_upper_2"] >= valid["bb_upper_1"]).all()
    assert (valid["bb_upper_1"] >= valid["bb_lower_1"]).all()
    assert (valid["bb_lower_1"] >= valid["bb_lower_2"]).all()

def test_feature_engineer_has_atr():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=50, freq="h"),
        "open": np.random.randn(50).cumsum() + 150,
        "high": np.random.randn(50).cumsum() + 151,
        "low": np.random.randn(50).cumsum() + 149,
        "close": np.random.randn(50).cumsum() + 150,
        "volume": np.random.randint(1000, 2000, 50),
    })
    fe = FeatureEngineer()
    X, y = fe.prepare(df)
    assert "atr_14" in X.columns
    assert (X["atr_14"] >= 0).all()

def test_feature_engineer_has_pattern_features():
    # Create a doji: open == close
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=50, freq="h"),
        "open": [150.0] * 50,
        "high": [151.0] * 50,
        "low": [149.0] * 50,
        "close": [150.0] * 50,
        "volume": [1000] * 50,
    })
    fe = FeatureEngineer()
    X, y = fe.prepare(df)
    assert "doji" in X.columns
    assert "hammer" in X.columns
    # With open == close and range > 0, doji should be 1
    assert (X["doji"] == 1).all()

def _synth_df(n=120, seed=42):
    np.random.seed(seed)
    return pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=n, freq="h"),
        "open": np.random.randn(n).cumsum() + 150,
        "high": np.random.randn(n).cumsum() + 151,
        "low": np.random.randn(n).cumsum() + 149,
        "close": np.random.randn(n).cumsum() + 150,
        "volume": np.random.randint(1000, 2000, n),
    })

def test_make_features_keeps_latest_bar():
    df = _synth_df(n=120)
    fe = FeatureEngineer()
    X = fe.make_features(df)
    X_train, _ = fe.prepare(df)
    # Inference path must include one more recent bar than the training path,
    # because training drops the last row (no future label available).
    assert len(X) == len(X_train) + 1
    assert X.index[-1] > X_train.index[-1]

def test_prepare_does_not_include_fake_last_label():
    # Construct a strictly increasing series so the real next-bar direction
    # is always 1; if the buggy path leaks, the last training label would be 0.
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=60, freq="h"),
        "open": [150.0 + i * 0.01 for i in range(60)],
        "high": [151.0 + i * 0.01 for i in range(60)],
        "low": [149.0 + i * 0.01 for i in range(60)],
        "close": [150.0 + i * 0.01 for i in range(60)],
        "volume": [1000] * 60,
    })
    fe = FeatureEngineer()
    _, y = fe.prepare(df)
    # Every retained label must reflect a real next-bar comparison (all 1 here).
    assert (y == 1).all()

def test_trainer_uses_time_series_split_by_default():
    trainer = MLTrainer()
    assert isinstance(trainer.cv, TimeSeriesSplit)

def test_trainer_grid_search_uses_configured_cv():
    df = _synth_df(n=200)
    fe = FeatureEngineer()
    X, y = fe.prepare(df)
    trainer = MLTrainer(cv=TimeSeriesSplit(n_splits=4))
    model, _ = trainer.train_with_grid_search(X, y)
    assert model is not None
    assert trainer.cv.n_splits == 4

def test_chronological_split_preserves_order():
    df = _synth_df(n=100)
    fe = FeatureEngineer()
    X, y = fe.prepare(df)
    X_tr, X_te, y_tr, y_te = MLTrainer.chronological_split(X, y, test_size=0.25)
    assert len(X_tr) + len(X_te) == len(X)
    assert len(y_tr) + len(y_te) == len(y)
    # Train must come strictly before test (no shuffling).
    assert X_tr.index.max() < X_te.index.min()

def test_oos_evaluation_differs_from_in_sample():
    # On random data, in-sample accuracy should be noticeably higher than OOS.
    # If they match closely we likely have leakage somewhere.
    df = _synth_df(n=300)
    fe = FeatureEngineer()
    X, y = fe.prepare(df)
    X_tr, X_te, y_tr, y_te = MLTrainer.chronological_split(X, y, test_size=0.3)
    trainer = MLTrainer(model_type="random_forest")
    trainer.train(X_tr, y_tr)
    in_sample = trainer.evaluate(X_tr, y_tr)["accuracy"]
    oos = trainer.evaluate(X_te, y_te)["accuracy"]
    assert in_sample > oos  # random data: model overfits train, OOS near chance

def test_trainer_grid_search():
    np.random.seed(42)
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=100, freq="h"),
        "open": np.random.randn(100).cumsum() + 150,
        "high": np.random.randn(100).cumsum() + 151,
        "low": np.random.randn(100).cumsum() + 149,
        "close": np.random.randn(100).cumsum() + 150,
        "volume": np.random.randint(1000, 2000, 100),
    })
    fe = FeatureEngineer()
    X, y = fe.prepare(df)

    trainer = MLTrainer(model_type="logistic_regression")
    model, best_params = trainer.train_with_grid_search(X, y)
    assert model is not None
    assert "C" in best_params
    assert trainer.model is model
