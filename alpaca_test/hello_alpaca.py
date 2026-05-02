"""Alpaca Paper Trading 接続確認スクリプト.

実行手順:
    1. cp .env.example .env
    2. .env に Paper Trading の API キーを記入
    3. pip install -r requirements.txt
    4. python hello_alpaca.py            # 読み取り専用（口座情報・気配値）
    5. python hello_alpaca.py --order    # 1株のテスト成行注文も実行
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--order",
        action="store_true",
        help="AAPL 1株の成行買いテスト注文も発注する（Paper環境のみ）",
    )
    parser.add_argument(
        "--symbol",
        default="AAPL",
        help="クォート取得とテスト発注に使う銘柄（デフォルト: AAPL）",
    )
    args = parser.parse_args()

    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        print(f"[ERROR] .env が見つかりません: {env_path}")
        print("       .env.example をコピーして API キーを記入してください。")
        return 1
    load_dotenv(env_path)

    api_key = os.environ.get("ALPACA_API_KEY")
    secret = os.environ.get("ALPACA_SECRET_KEY")
    base_url = os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

    if not api_key or not secret or api_key.startswith("PK...your"):
        print("[ERROR] ALPACA_API_KEY / ALPACA_SECRET_KEY が未設定です。")
        print("       .env を編集して Paper Trading の鍵を貼り付けてください。")
        return 1

    if "paper" not in base_url:
        print(f"[ERROR] 安全のため Paper 環境以外は拒否します: {base_url}")
        return 1

    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockLatestQuoteRequest
    from alpaca.trading.client import TradingClient
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.requests import MarketOrderRequest

    trading = TradingClient(api_key, secret, paper=True)
    data = StockHistoricalDataClient(api_key, secret)

    print("=" * 60)
    print("  Alpaca Paper Trading 接続テスト")
    print("=" * 60)

    print("\n[1/3] 口座情報を取得中...")
    account = trading.get_account()
    print(f"  口座番号       : {account.account_number}")
    print(f"  ステータス     : {account.status}")
    print(f"  通貨           : {account.currency}")
    print(f"  現金残高       : {account.cash}")
    print(f"  時価評価額     : {account.equity}")
    print(f"  購買力         : {account.buying_power}")
    print(f"  パターンデイトレ: {account.pattern_day_trader}")

    print(f"\n[2/3] {args.symbol} の最新気配値を取得中...")
    quote_req = StockLatestQuoteRequest(symbol_or_symbols=args.symbol)
    quotes = data.get_stock_latest_quote(quote_req)
    q = quotes[args.symbol]
    print(f"  Bid {q.bid_price} x {q.bid_size}")
    print(f"  Ask {q.ask_price} x {q.ask_size}")
    print(f"  時刻: {q.timestamp}")

    if args.order:
        print(f"\n[3/3] {args.symbol} 1 株を成行買いで発注（Paper）...")
        order = trading.submit_order(
            order_data=MarketOrderRequest(
                symbol=args.symbol,
                qty=1,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
            )
        )
        print(f"  Order ID : {order.id}")
        print(f"  Status   : {order.status}")
        print(f"  Submitted: {order.submitted_at}")
        print("\n  ※ 米国市場の取引時間外に発注した場合は status=accepted/new となり、")
        print("    翌営業日の寄付で約定します（ギャップに注意）。")
        print("    時間外で確実に約定させたい場合は MarketOrder ではなく")
        print("    LimitOrderRequest + extended_hours=True を使ってください。")
    else:
        print("\n[3/3] テスト発注はスキップ（--order を付けると発注）")

    print("\n[OK] 接続テスト完了")
    return 0


if __name__ == "__main__":
    sys.exit(main())
