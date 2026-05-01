"""環境変数から設定値を読み込み・型変換・バリデーション."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(ValueError):
    """設定不備の例外."""


@dataclass(frozen=True)
class Config:
    """全設定値の集約."""

    alpaca_api_key: str
    alpaca_secret_key: str
    alpaca_base_url: str
    data_plan: str
    confirm_live: bool
    initial_capital_usd: float
    risk_per_trade: float
    max_position_pct: float
    max_concurrent_positions: int
    max_tech_exposure: float
    daily_loss_limit: float
    weekly_loss_limit: float
    monthly_loss_limit: float
    cumulative_dd_limit: float
    cost_warn_threshold: float
    cost_halt_threshold: float
    healthchecks_intraday_url: str
    healthchecks_eod_url: str
    healthchecks_monthly_url: str
    slack_webhook_url: str
    notification_email: str


def _get_required(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise ConfigError(f"{key} is required but not set")
    return val


def _get_float(key: str, default: float | None = None) -> float:
    val = os.environ.get(key)
    if val is None or val == "":
        if default is not None:
            return default
        raise ConfigError(f"{key} is required but not set")
    try:
        return float(val)
    except ValueError as e:
        raise ConfigError(f"{key} must be float: {val}") from e


def _get_int(key: str, default: int | None = None) -> int:
    val = os.environ.get(key)
    if val is None or val == "":
        if default is not None:
            return default
        raise ConfigError(f"{key} is required but not set")
    try:
        return int(val)
    except ValueError as e:
        raise ConfigError(f"{key} must be int: {val}") from e


def _get_bool(key: str, default: bool = False) -> bool:
    val = os.environ.get(key, "").lower()
    if val in ("true", "yes", "1"):
        return True
    if val in ("false", "no", "0", ""):
        return default
    raise ConfigError(f"{key} must be true/false: {val}")


def load_config(env_path: Path | str | None = None) -> Config:
    """`.env` を読み込み、Config を返す。バリデーション失敗時は ConfigError."""
    if env_path is not None:
        load_dotenv(env_path, override=True)

    cfg = Config(
        alpaca_api_key=_get_required("ALPACA_API_KEY"),
        alpaca_secret_key=_get_required("ALPACA_SECRET_KEY"),
        alpaca_base_url=_get_required("ALPACA_BASE_URL"),
        data_plan=os.environ.get("DATA_PLAN", "free"),
        confirm_live=_get_bool("CONFIRM_LIVE", default=False),
        initial_capital_usd=_get_float("INITIAL_CAPITAL_USD", default=100000.0),
        risk_per_trade=_get_float("RISK_PER_TRADE", default=0.005),
        max_position_pct=_get_float("MAX_POSITION_PCT", default=0.25),
        max_concurrent_positions=_get_int("MAX_CONCURRENT_POSITIONS", default=3),
        max_tech_exposure=_get_float("MAX_TECH_EXPOSURE", default=0.40),
        daily_loss_limit=_get_float("DAILY_LOSS_LIMIT", default=0.02),
        weekly_loss_limit=_get_float("WEEKLY_LOSS_LIMIT", default=0.05),
        monthly_loss_limit=_get_float("MONTHLY_LOSS_LIMIT", default=0.08),
        cumulative_dd_limit=_get_float("CUMULATIVE_DD_LIMIT", default=0.20),
        cost_warn_threshold=_get_float("COST_WARN_THRESHOLD", default=0.0013),
        cost_halt_threshold=_get_float("COST_HALT_THRESHOLD", default=0.0018),
        healthchecks_intraday_url=os.environ.get("HEALTHCHECKS_INTRADAY_URL", ""),
        healthchecks_eod_url=os.environ.get("HEALTHCHECKS_EOD_URL", ""),
        healthchecks_monthly_url=os.environ.get("HEALTHCHECKS_MONTHLY_URL", ""),
        slack_webhook_url=os.environ.get("SLACK_WEBHOOK_URL", ""),
        notification_email=os.environ.get("NOTIFICATION_EMAIL", ""),
    )

    _validate(cfg)
    return cfg


def _validate(cfg: Config) -> None:
    if cfg.risk_per_trade > 0.05:
        raise ConfigError(
            f"RISK_PER_TRADE too high ({cfg.risk_per_trade}); max 0.05 to prevent runaway risk"
        )
    if cfg.max_position_pct > 1.0 or cfg.max_position_pct <= 0:
        raise ConfigError(f"MAX_POSITION_PCT must be in (0, 1.0]: {cfg.max_position_pct}")
    if cfg.max_concurrent_positions < 1 or cfg.max_concurrent_positions > 10:
        raise ConfigError(
            f"MAX_CONCURRENT_POSITIONS must be 1..10: {cfg.max_concurrent_positions}"
        )
    if cfg.max_tech_exposure <= 0 or cfg.max_tech_exposure > 1.0:
        raise ConfigError(f"MAX_TECH_EXPOSURE must be in (0, 1.0]: {cfg.max_tech_exposure}")
    if cfg.cumulative_dd_limit > 0.50:
        raise ConfigError(f"CUMULATIVE_DD_LIMIT too lax: {cfg.cumulative_dd_limit}")

    is_live_url = "paper-api" not in cfg.alpaca_base_url
    if is_live_url and not cfg.confirm_live:
        raise ConfigError(
            "Live URL detected but CONFIRM_LIVE=false. Set CONFIRM_LIVE=true to confirm Live trading"
        )
