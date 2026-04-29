import pandas as pd


class Preprocessor:
    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.sort_values("datetime").reset_index(drop=True)
        df = df.dropna().reset_index(drop=True)
        return df
