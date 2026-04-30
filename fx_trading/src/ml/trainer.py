from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
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

    def _create_model(self):
        if self.model_type == "logistic_regression":
            return LogisticRegression(max_iter=1000, random_state=42)
        elif self.model_type == "random_forest":
            return RandomForestClassifier(n_estimators=100, random_state=42)
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")

    def train(self, X: pd.DataFrame, y: pd.Series) -> Any:
        self.model = self._create_model()
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

    def train_with_grid_search(self, X: pd.DataFrame, y: pd.Series) -> Tuple[Any, Dict[str, Any]]:
        if self.model_type == "logistic_regression":
            param_grid = {"C": [0.01, 0.1, 1, 10], "max_iter": [1000]}
            model = LogisticRegression(random_state=42)
        elif self.model_type == "random_forest":
            param_grid = {"n_estimators": [50, 100, 200], "max_depth": [3, 5, 10]}
            model = RandomForestClassifier(random_state=42)
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")

        grid = GridSearchCV(model, param_grid, cv=self.cv, scoring="accuracy")
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
