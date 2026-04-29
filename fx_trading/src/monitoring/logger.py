import logging
import os
from datetime import datetime

class TradeLogger:
    def __init__(self, log_file: str = "logs/trades.log", error_file: str = None):
        if error_file is None:
            error_file = log_file
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        os.makedirs(os.path.dirname(error_file), exist_ok=True)
        
        self.trade_logger = logging.getLogger("trade_logger")
        self.trade_logger.setLevel(logging.INFO)
        self.trade_logger.handlers.clear()
        handler = logging.FileHandler(log_file)
        handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
        self.trade_logger.addHandler(handler)
        
        self.error_logger = logging.getLogger("error_logger")
        self.error_logger.setLevel(logging.ERROR)
        self.error_logger.handlers.clear()
        handler = logging.FileHandler(error_file)
        handler.setFormatter(logging.Formatter("%(asctime)s | ERROR | %(message)s"))
        self.error_logger.addHandler(handler)

    def log_trade(self, instrument: str, direction: str, units: int, price: float):
        self.trade_logger.info(f"TRADE | {instrument} | {direction} | units={units} | price={price}")

    def log_error(self, message: str):
        self.error_logger.error(message)

    def log_info(self, message: str):
        self.trade_logger.info(f"INFO | {message}")
