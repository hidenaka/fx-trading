import pandas as pd
import numpy as np
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
