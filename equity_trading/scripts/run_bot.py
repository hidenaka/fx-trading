"""Bot 統合 CLI（Paper Trading MVP）.

実行例:
    cd /Users/hideakimacbookair/自動トレード
    python3 equity_trading/scripts/run_bot.py --morning
    python3 equity_trading/scripts/run_bot.py --intraday
    python3 equity_trading/scripts/run_bot.py --eod
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from equity_trading.src.broker.alpaca_client import AlpacaClient
from equity_trading.src.config import ConfigError, load_config
from equity_trading.src.data.price_fetcher import PriceFetcher
from equity_trading.src.live.eod_runner import run_eod
from equity_trading.src.live.intraday_runner import run_intraday
from equity_trading.src.live.morning_runner import run_morning
from equity_trading.src.state.migrations import init_database


DEFAULT_DB_PATH = "equity_trading/data/trades.sqlite"
DEFAULT_CACHE_DIR = "equity_trading/data/prices"
DEFAULT_SYMBOLS = ["SPY", "QQQ", "IWM", "XLK"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Equity bot CLI")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--morning", action="store_true", help="Run gap_fill at market open")
    mode.add_argument("--intraday", action="store_true", help="Run mean_reversion (every 5min)")
    mode.add_argument("--eod", action="store_true", help="Close positions, write summary")
    mode.add_argument("--check", action="store_true", help="Connectivity check only (no orders, no DB writes)")
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH)
    parser.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR)
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    args = parser.parse_args(argv)

    import os as _os
    project_root = Path(__file__).resolve().parents[1]
    env_path = project_root / ".env"
    # Only load .env if ALPACA_BASE_URL is not already set in the environment.
    # This lets test monkeypatching take precedence over .env values.
    use_env_file = env_path.exists() and "ALPACA_BASE_URL" not in _os.environ
    try:
        cfg = load_config(env_path=env_path if use_env_file else None)
    except ConfigError as exc:
        msg = f"[ERROR] Config error: {exc}"
        print(msg)
        print(msg, file=sys.stderr)
        return 2

    base_url = cfg.alpaca_base_url
    if "paper-api" not in base_url:
        msg = f"[ERROR] Plan 2.0 is Paper-only. Refusing to run against {base_url}"
        print(msg)
        print(msg, file=sys.stderr)
        return 2

    cache_dir = Path(args.cache_dir)
    broker = AlpacaClient(
        api_key=cfg.alpaca_api_key,
        secret_key=cfg.alpaca_secret_key,
        base_url=base_url,
    )

    if args.check:
        account = broker.get_account()
        print(f"[run_bot] Connected to Alpaca Paper")
        print(f"  Account: {account['account_number']}")
        print(f"  Status: {account['status']}")
        print(f"  Equity: ${account['equity']:,.2f}")
        print(f"  Cash: ${account['cash']:,.2f}")
        print(f"  Buying power: ${account['buying_power']:,.2f}")
        print(f"  Pattern day trader: {account['pattern_day_trader']}")
        return 0

    db_path = Path(args.db_path)
    init_database(db_path)

    fetcher = PriceFetcher(broker=broker, cache_dir=cache_dir)

    now_utc = datetime.now(timezone.utc)

    try:
        if args.morning:
            print(f"[run_bot] Morning gap_fill check at {now_utc.isoformat()}")
            summary = run_morning(
                symbols=args.symbols,
                db_path=db_path,
                broker=broker,
                fetcher=fetcher,
                now_utc=now_utc,
            )
            print(f"  Entries placed: {summary.get('entries_placed', 0)}")
            if summary.get("errors"):
                for e in summary["errors"]:
                    print(f"  [warn] {e}")
        elif args.intraday:
            print(f"[run_bot] Intraday mean_reversion check at {now_utc.isoformat()}")
            summary = run_intraday(
                db_path=db_path,
                broker=broker,
                fetcher=fetcher,
                now_utc=now_utc,
            )
            print(f"  Entries placed: {summary.get('entries_placed', 0)}")
            if summary.get("errors"):
                for e in summary["errors"]:
                    print(f"  [warn] {e}")
        elif args.eod:
            print(f"[run_bot] EOD closer at {now_utc.isoformat()}")
            summary = run_eod(
                db_path=db_path,
                broker=broker,
                fetcher=fetcher,
                now_utc=now_utc,
            )
            print(summary.get("summary_md", ""))
        return 0
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
