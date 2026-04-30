from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple

class MLTrainer:
    def __init__(self, model_type: str = "logistic_regression", cv=None):
        self.model_type = model_type
        # Time-series CV is required: a random K-Fold leaks future bars into
        # training folds and inflates the reported score.
        self.cv = cv if cv is not None else TimeSeriesSplit(n_splits=5)
        self.model = None

    def _create_pipeline(self) -> Pipeline:
        if self.model_type == "logistic_regression":
            clf = LogisticRegression(max_iter=1000, random_state=42)
        elif self.model_type == "random_forest":
            clf = RandomForestClassifier(n_estimators=100, random_state=42)
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")
        # StandardScaler is fit per CV fold via Pipeline, avoiding the
        # train/validation leak you'd get from scaling the full X up front.
        return Pipeline([("scaler", StandardScaler()), ("clf", clf)])

    def train(self, X: pd.DataFrame, y: pd.Series) -> Pipeline:
        self.model = self._create_pipeline()
        self.model.fit(X, y)
        return self.model

    def evaluate(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        if self.model is None:
            raise RuntimeError("Model not trained yet")
        preds = self.model.predict(X)
        return {
            "accuracy": accuracy_score(y, preds),
            "precision": precision_score(y, preds, zero_division=0),
            "recall": recall_score(y, preds, zero_division=0),
        }

    def train_with_grid_search(self, X: pd.DataFrame, y: pd.Series) -> Tuple[Pipeline, Dict[str, Any]]:
        pipeline = self._create_pipeline()
        if self.model_type == "logistic_regression":
            param_grid = {"clf__C": [0.01, 0.1, 1, 10]}
        elif self.model_type == "random_forest":
            param_grid = {"clf__n_estimators": [50, 100, 200], "clf__max_depth": [3, 5, 10]}
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")

        grid = GridSearchCV(pipeline, param_grid, cv=self.cv, scoring="accuracy")
        grid.fit(X, y)
        self.model = grid.best_estimator_
        return self.model, grid.best_params_

    @staticmethod
    def chronological_split(
        X: pd.DataFrame, y: pd.Series, test_size: float = 0.2
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
        if not 0 < test_size < 1:
            raise ValueError("test_size must be in (0, 1)")
        n = len(X)
        split = int(n * (1 - test_size))
        X_train, X_test = X.iloc[:split], X.iloc[split:]
        y_train, y_test = y.iloc[:split], y.iloc[split:]
        return X_train, X_test, y_train, y_test
