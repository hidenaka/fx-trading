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
from equity_trading.src.live.orb_runner import run_orb
from equity_trading.src.live.pre_fomc_runner import run_pre_fomc, run_fomc_close
from equity_trading.src.state.migrations import init_database


DEFAULT_DB_PATH = "equity_trading/data/trades.sqlite"
DEFAULT_CACHE_DIR = "equity_trading/data/prices"
# Long-data (7-yr) validated: drop XLK gap_fill (sample artifact in 2024-2026),
# keep IWM (modest +EV on 7-yr), add DIA. QQQ is the standout (EV +18.35).
DEFAULT_SYMBOLS = ["SPY", "QQQ", "DIA", "IWM"]
# 敏腕モード: TECL (3x XLK) pre-FOMC with VIX > 22 filter — backtest WR 0.700,
# avg +1.555% (n=10) vs unfiltered TECL pre-FOMC drift.
PRE_FOMC_SYMBOL = "TECL"
PRE_FOMC_VIX_MIN = 22.0
VIX_PARQUET_RELATIVE = "VIX_1day_2019-05-01_2026-05-01.parquet"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Equity bot CLI")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--morning", action="store_true", help="Run gap_fill at market open")
    mode.add_argument("--intraday", action="store_true", help="Run mean_reversion (every 5min)")
    mode.add_argument("--eod", action="store_true", help="Close positions, write summary")
    mode.add_argument("--pre-fomc", action="store_true",
                      help=f"Place pre-FOMC long {PRE_FOMC_SYMBOL} at ~12:30 ET on day before FOMC")
    mode.add_argument("--fomc-close", action="store_true",
                      help="Close hold-overnight positions at ~13:55 ET on FOMC day")
    mode.add_argument("--orb", action="store_true",
                      help="Run Opening Range Breakout sweep (TECL/TQQQ/TNA, every 5min after 10:30 ET)")
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
        elif args.pre_fomc:
            print(f"[run_bot] Pre-FOMC entry check at {now_utc.isoformat()}")
            vix_path = cache_dir / VIX_PARQUET_RELATIVE
            vix_daily = None
            if vix_path.exists():
                import pandas as pd
                vix_daily = pd.read_parquet(vix_path)
            else:
                print(f"  [warn] VIX cache not found at {vix_path}; running without VIX filter")
            summary = run_pre_fomc(
                symbol=PRE_FOMC_SYMBOL,
                db_path=db_path,
                broker=broker,
                fetcher=fetcher,
                now_utc=now_utc,
                vix_min=PRE_FOMC_VIX_MIN if vix_daily is not None else None,
                vix_daily=vix_daily,
            )
            print(f"  Entries placed: {summary.get('entries_placed', 0)}")
            if summary.get("halted"):
                print("  Circuit halted.")
            if summary.get("errors"):
                for e in summary["errors"]:
                    print(f"  [warn] {e}")
        elif args.orb:
            print(f"[run_bot] ORB sweep at {now_utc.isoformat()}")
            summary = run_orb(
                db_path=db_path,
                broker=broker,
                fetcher=fetcher,
                now_utc=now_utc,
            )
            print(f"  Entries placed: {summary.get('entries_placed', 0)}")
            if summary.get("halted"):
                print("  Circuit halted.")
            if summary.get("errors"):
                for e in summary["errors"]:
                    print(f"  [warn] {e}")
        elif args.fomc_close:
            print(f"[run_bot] FOMC closer at {now_utc.isoformat()}")
            summary = run_fomc_close(
                db_path=db_path,
                broker=broker,
                fetcher=fetcher,
                now_utc=now_utc,
            )
            print(f"  Positions closed: {summary.get('positions_closed', 0)}")
            if summary.get("errors"):
                for e in summary["errors"]:
                    print(f"  [warn] {e}")
        return 0
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
