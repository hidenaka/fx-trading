import pandas as pd
from src.strategies.base import Strategy
from src.ml.feature_engineer import FeatureEngineer
from src.ml.predictor import MLPredictor

class MLStrategy(Strategy):
    def __init__(self, model=None):
        self.model = model
        self.fe = FeatureEngineer()
        self.predictor = MLPredictor(model) if model else None

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        if self.predictor is None or len(df) < 20:
            df["signal"] = 0
            return df
        
        try:
            X = self.fe.make_features(df)
            if len(X) == 0:
                df["signal"] = 0
                return df
            
            # Get prediction for the latest row
            direction = self.predictor.predict_direction(X)
            
            # Set signal only on the last row
            df["signal"] = 0
            df.iloc[-1, df.columns.get_loc("signal")] = direction
            
        except Exception:
            df["signal"] = 0
        
        return df
