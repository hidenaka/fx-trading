import requests
import pandas as pd
from typing import Optional

class OandaDataFetcher:
    def __init__(self, api_token: str, environment: str = "practice"):
        self.api_token = api_token
        if environment == "live":
            self.base_url = "https://api-fxtrade.oanda.com/v3"
        else:
            self.base_url = "https://api-fxpractice.oanda.com/v3"
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

    def fetch_candles(self, instrument: str, granularity: str = "H1",
                      count: int = 500, from_time: Optional[str] = None,
                      to_time: Optional[str] = None) -> pd.DataFrame:
        url = f"{self.base_url}/instruments/{instrument}/candles"
        params = {
            "granularity": granularity,
            "count": count,
            "price": "M",  # midpoint
        }
        if from_time:
            params["from"] = from_time
        if to_time:
            params["to"] = to_time
        
        response = requests.get(url, headers=self.headers, params=params, timeout=30)
        if response.status_code >= 400:
            raise RuntimeError(f"OANDA API error: {response.status_code} {response.text}")
        
        data = response.json()
        candles = data.get("candles", [])
        
        rows = []
        for candle in candles:
            if not candle.get("complete", True):
                continue
            mid = candle["mid"]
            rows.append({
                "datetime": candle["time"],
                "open": float(mid["o"]),
                "high": float(mid["h"]),
                "low": float(mid["l"]),
                "close": float(mid["c"]),
                "volume": int(candle["volume"]),
            })
        
        df = pd.DataFrame(rows)
        if not df.empty:
            df["datetime"] = pd.to_datetime(df["datetime"])
        return df

    def fetch_to_csv(self, instrument: str, output_path: str,
                     granularity: str = "H1", count: int = 500,
                     from_time: Optional[str] = None,
                     to_time: Optional[str] = None):
        df = self.fetch_candles(instrument, granularity, count, from_time, to_time)
        df.to_csv(output_path, index=False)
        return output_path
