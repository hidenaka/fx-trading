import requests
from typing import Optional

class SlackNotifier:
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url

    def _send(self, message: str) -> bool:
        if not self.webhook_url:
            return False
        try:
            response = requests.post(
                self.webhook_url,
                json={"text": message},
                timeout=10,
            )
            if response.status_code == 429:
                import time
                time.sleep(1)
                response = requests.post(
                    self.webhook_url,
                    json={"text": message},
                    timeout=10,
                )
            return response.status_code == 200
        except Exception:
            return False

    def notify_trade(self, instrument: str, direction: str, units: int, price: float):
        emoji = "🟢" if direction == "BUY" else "🔴" if direction == "SELL" else "⚪"
        message = f"{emoji} *TRADE* | {instrument} | {direction} | units={units} | price={price}"
        self._send(message)

    def notify_error(self, error_message: str):
        message = f"🚨 *ERROR* | {error_message}"
        self._send(message)

    def notify_circuit_breaker(self, reason: str):
        message = f"⛔ *CIRCUIT BREAKER* | {reason}"
        self._send(message)
