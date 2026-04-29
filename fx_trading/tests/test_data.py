import pandas as pd
from src.data.loader import DataLoader
from src.data.preprocessor import Preprocessor


def test_load_csv():
    loader = DataLoader(data_dir="data")
    df = loader.load_csv("sample", "usdjpy_1h")
    assert isinstance(df, pd.DataFrame)
    assert "datetime" in df.columns
    assert len(df) == 10


def test_preprocessor_sorts_and_drops_na():
    df = pd.DataFrame({
        "datetime": ["2024-01-02", "2024-01-01", "2024-01-03"],
        "open": [1.0, 2.0, None],
        "high": [1.1, 2.1, 3.1],
        "low": [0.9, 1.9, 2.9],
        "close": [1.05, 2.05, 3.05],
        "volume": [100, 200, 300],
    })
    pre = Preprocessor()
    result = pre.process(df)
    assert len(result) == 2
    assert result.iloc[0]["datetime"] == pd.Timestamp("2024-01-01")
    assert result.iloc[1]["datetime"] == pd.Timestamp("2024-01-02")
