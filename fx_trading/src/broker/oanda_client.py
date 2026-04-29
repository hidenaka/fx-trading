import requests
import time
from typing import Dict, List, Optional

class OandaClient:
    def __init__(self, api_token: str, account_id: str, environment: str = "practice"):
        self.api_token = api_token
        self.account_id = account_id
        self.environment = environment
        if environment == "live":
            self.base_url = "https://api-fxtrade.oanda.com/v3"
        else:
            self.base_url = "https://api-fxpractice.oanda.com/v3"
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        url = f"{self.base_url}/{endpoint}"
        response = requests.get(url, headers=self.headers, params=params, timeout=30)
        if response.status_code == 429:
            time.sleep(1)
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
        if response.status_code >= 400:
            raise RuntimeError(f"OANDA API error: {response.status_code} {response.text}")
        return response.json()

    def _post(self, endpoint: str, data: Dict) -> Dict:
        url = f"{self.base_url}/{endpoint}"
        response = requests.post(url, headers=self.headers, json=data, timeout=30)
        if response.status_code == 429:
            time.sleep(1)
            response = requests.post(url, headers=self.headers, json=data, timeout=30)
        if response.status_code >= 400:
            raise RuntimeError(f"OANDA API error: {response.status_code} {response.text}")
        return response.json()

    def get_account_summary(self) -> Dict:
        return self._get(f"accounts/{self.account_id}/summary")

    def get_current_price(self, instrument: str) -> Dict:
        result = self._get(f"accounts/{self.account_id}/pricing", params={"instruments": instrument})
        price = result["prices"][0]
        return {
            "bid": float(price["closeoutBid"]),
            "ask": float(price["closeoutAsk"]),
            "instrument": price["instrument"],
        }

    def get_multiple_prices(self, instruments: list) -> dict:
        """Returns dict of {instrument: {bid, ask}}"""
        instrument_str = ",".join(instruments)
        result = self._get(f"accounts/{self.account_id}/pricing", params={"instruments": instrument_str})
        prices = {}
        for price in result["prices"]:
            prices[price["instrument"]] = {
                "bid": float(price["closeoutBid"]),
                "ask": float(price["closeoutAsk"]),
            }
        return prices

    def get_open_positions(self) -> List[Dict]:
        result = self._get(f"accounts/{self.account_id}/openPositions")
        return result.get("positions", [])

    def place_order(self, order: Dict) -> Dict:
        return self._post(f"accounts/{self.account_id}/orders", {"order": order})

    def close_position(self, instrument: str, long_units: str = "ALL", short_units: str = "ALL") -> Dict:
        data = {}
        if long_units:
            data["longUnits"] = long_units
        if short_units:
            data["shortUnits"] = short_units
        return self._put(f"accounts/{self.account_id}/positions/{instrument}/close", data)

    def _put(self, endpoint: str, data: Dict) -> Dict:
        url = f"{self.base_url}/{endpoint}"
        response = requests.put(url, headers=self.headers, json=data, timeout=30)
        if response.status_code >= 400:
            raise RuntimeError(f"OANDA API error: {response.status_code} {response.text}")
        return response.json()
