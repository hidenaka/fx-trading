from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score
import pandas as pd
import numpy as np
from typing import Dict, Any

class MLTrainer:
    def __init__(self, model_type: str = "logistic_regression"):
        self.model_type = model_type
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
