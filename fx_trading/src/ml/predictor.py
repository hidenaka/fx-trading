import numpy as np
import pandas as pd
from typing import Optional

class MLPredictor:
    def __init__(self, model):
        self.model = model

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return self.model.predict(X)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        if hasattr(self.model, 'predict_proba'):
            return self.model.predict_proba(X)
        # Fallback for models without probability
        preds = self.model.predict(X)
        proba = np.zeros((len(preds), 2))
        proba[np.arange(len(preds)), preds] = 1.0
        return proba

    def predict_direction(self, X: pd.DataFrame) -> int:
        proba = self.predict_proba(X)
        # Return 1 if probability of class 1 > 0.5, -1 otherwise
        return 1 if proba[-1, 1] > 0.5 else -1
