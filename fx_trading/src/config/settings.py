import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    def __init__(self):
        self.api_token = os.getenv("OANDA_API_TOKEN")
        self.account_id = os.getenv("OANDA_ACCOUNT_ID")
        self.environment = os.getenv("OANDA_ENVIRONMENT", "practice")
        self.risk_per_trade = float(os.getenv("RISK_PER_TRADE", "0.01"))
        self.currency_pair = os.getenv("CURRENCY_PAIR", "USD_JPY")
        self.initial_capital = float(os.getenv("INITIAL_CAPITAL", "1000000"))
        self.max_daily_loss_pct = float(os.getenv("MAX_DAILY_LOSS_PCT", "5.0"))
        self.trading_start_hour = int(os.getenv("TRADING_START_HOUR", "7"))
        self.trading_end_hour = int(os.getenv("TRADING_END_HOUR", "6"))
        self.granularity = os.getenv("GRANULARITY", "H1")
        self.slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        self.validate()

    def validate(self):
        if not self.api_token:
            raise ValueError("OANDA_API_TOKEN is required")
        if not self.account_id:
            raise ValueError("OANDA_ACCOUNT_ID is required")
        if self.environment not in ("practice", "live"):
            raise ValueError("OANDA_ENVIRONMENT must be 'practice' or 'live'")
