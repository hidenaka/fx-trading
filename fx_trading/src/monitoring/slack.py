import requests


class SlackNotifier:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def _send(self, message: str):
        if not self.webhook_url:
            return
        try:
            requests.post(
                self.webhook_url,
                json={"text": message},
                timeout=5,
            )
        except Exception:
            pass

    def notify_trade(self, instrument: str, direction: str, units: int, price: float):
        message = (
            f"Trade executed: {direction} {units} {instrument} @ {price}"
        )
        self._send(message)

    def notify_error(self, message: str):
        self._send(f"ERROR: {message}")

    def notify_info(self, message: str):
        self._send(f"INFO: {message}")

    def notify_circuit_breaker(self, daily_pnl: float, max_loss_pct: float):
        message = (
            f"Circuit breaker triggered! Daily PnL: {daily_pnl:.2f} "
            f"(max loss: {max_loss_pct}%)"
        )
        self._send(message)
