import pandas as pd
from pathlib import Path


class DataLoader:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)

    def load_csv(self, symbol: str, timeframe: str) -> pd.DataFrame:
        path = self.data_dir / f"{symbol}_{timeframe}.csv"
        df = pd.read_csv(path, parse_dates=["datetime"])
        return df

    def load_multiple(self, pairs: list, timeframe: str) -> dict:
        """Returns dict of {pair_name: DataFrame}"""
        result = {}
        for pair in pairs:
            result[pair] = self.load_csv(pair.lower(), timeframe)
        return result
