# Equity Bot — Operations Runbook (敏腕モード / Plan 2.5)

> **モード**: 敏腕モード (3x レバレッジ ETF + VIX フィルター)
> **想定リターン**: 年 +13%（25%×3 setup; 95% CI に基づく）
> **想定 Max DD**: -16.77%（7-yr バックテスト最悪期間）
> **資金前提**: 初期 ¥100,000 + 毎月 ¥50,000 の積立

## What this bot does

Runs scheduled jobs against Alpaca **Paper** account using **3x leveraged ETFs**:

- **Morning** (~9:31 ET): scans SPY/QQQ/DIA/IWM for gap-fill setups (legacy strategy, low-EV anchor).
- **ORB** (every 5 min, 10:35-15:50 ET): scans **TECL/TQQQ/TNA** for 60-min Opening Range breakouts. **敏腕モードの主戦場**.
- **Intraday** (every 5 min, 9:35-15:50 ET): legacy XLK mean-reversion (optional; can skip).
- **Pre-FOMC** (~12:30 ET, only on the trading day before each FOMC): places long **TECL** if prior-day VIX close > 22. Position is `hold_overnight=1` and survives EOD.
- **EOD** (~15:55 ET): closes still-open positions with `hold_overnight=0` at market.
- **FOMC Close** (~13:55 ET on FOMC days): closes `hold_overnight=1` positions before the 14:00 ET statement.

## Validated edge (7-yr RTH backtest, 2019-05 → 2026-05)

### 敏腕コア戦略

| Strategy | Symbol | n | WR | EV (sum %) | Avg/trade |
|----------|--------|---|------|------------|-----------|
| **ORB** | TECL | 486 | 0.543 | +108.38 | +0.223% |
| **ORB** | TQQQ | 531 | 0.565 | +76.96 | +0.145% |
| **ORB** | TNA | 369 | 0.534 | +62.06 | +0.168% |
| **Pre-FOMC drift (VIX > 22)** | TECL | 10 | 0.700 | +15.55 | +1.555% |
| **Pre-FOMC drift** | UPRO | 57 | 0.649 | +30.83 | +0.541% |
| **Pre-FOMC drift** | UDOW | 57 | 0.649 | +30.83 | +0.541% |
| **Last-Hour Momentum** | UPRO | – | – | +EV | – |
| **Last-Hour Momentum** | UDOW | – | – | +EV | – |

### Legacy non-leveraged (gap_fill, optional)

| Strategy | Symbol | n | WR | EV |
|----------|--------|---|------|-----|
| gap_fill | QQQ (0.3%) | 213 | 0.573 | +18.35 |
| gap_fill | IWM (1.0%) | 33 | 0.576 | +4.97 |
| gap_fill | SPY (0.5%) | 81 | 0.494 | +3.08 |
| gap_fill | DIA (0.5%) | 75 | 0.453 | +3.02 |

**Sizing (敏腕モード)**: 25% of account equity per trade, **max 3 concurrent positions**. Same-symbol re-entry blocked while a position is open.

**Halt rule**: realized loss > 2% of equity in a day → new entries suppressed (also blocks Pre-FOMC, ORB).

## Projected portfolio return (Scenario A 推奨, 7-yr backtest)

| Scenario | Annualized | Max DD | Trades/yr |
|----------|-----------:|-------:|----------:|
| **A: 25%×3 (敏腕推奨)** | **+13.0%** | **-16.77%** | ~213 |
| B: 50%×2 (強気) | +20.5% | -32.4% | ~213 |
| C: 100%×1 sequential | +27.1% | -49.2% | ~213 |

### 月次積立シミュレーション (Scenario A, 7-yr)

| 投入総額 | 最終残高 (USD) | 最終残高 (JPY) | 含み益 | Max DD |
|---------:|---------------:|---------------:|------:|-------:|
| ¥4,300,000 (≈$27,920) | $41,373 | ¥6,371,482 | +48.2% | -16.77% |

詳細年次表 → `equity_trading/phase0/monthly_dca_projection.md`

## First-time setup

1. `cd /Users/hideakimacbookair/自動トレード`
2. `equity_trading/.env` に有効な Paper API キーがあるか確認 (`ALPACA_BASE_URL=https://paper-api.alpaca.markets`).
3. **VIX キャッシュを確認/再生成** (Pre-FOMC が VIX フィルターで使う):
   ```
   ls -la equity_trading/data/prices/VIX_1day_2019-05-01_2026-05-01.parquet
   # 見つからなければ:
   python3 equity_trading/scripts/save_vix_history.py
   ```
4. **Leveraged ETF データのバックフィル** (初回のみ):
   ```
   python3 equity_trading/scripts/backfill_leveraged_etfs.py
   ```
   想定: TQQQ/UPRO/TNA/TECL/UDOW で各約 200-330k の 5min バー。
5. 接続確認:
   ```
   python3 equity_trading/scripts/run_bot.py --check
   ```

## Daily routine (manual, Monday-Friday only)

NY 時刻の壁時計に合わせて以下を実行 (`nohup` か tmux 等で detach 推奨)。

### Every trading day (敏腕モード フル)

| Time (NY) | Command |
|-----------|---------|
| 09:31 | `python3 equity_trading/scripts/run_bot.py --morning` |
| 10:35-15:50, every 5 min | `python3 equity_trading/scripts/run_bot.py --orb` |
| 15:55 | `python3 equity_trading/scripts/run_bot.py --eod` |

### ORB ループヘルパー (10:35-15:50 ET, ~63 反復)

```
for i in $(seq 1 63); do
  python3 equity_trading/scripts/run_bot.py --orb
  sleep 300
done
```

### Pre-FOMC days (年 8 回)

FOMC 発表日の **直前の取引日** にも実行:

| Time (NY) | Command |
|-----------|---------|
| 12:30 | `python3 equity_trading/scripts/run_bot.py --pre-fomc` |

VIX 前日終値 ≤ 22 ならスキップされる（fil­ter on）。ポジションは `hold_overnight=1` で EOD を生き残る。

### FOMC announcement days

FOMC 発表日には 14:00 ET 声明発表の前に必ず実行:

| Time (NY) | Command |
|-----------|---------|
| 13:55 | `python3 equity_trading/scripts/run_bot.py --fomc-close` |

### FOMC schedule (current edition)

`equity_trading/src/strategy/strategies/pre_fomc.py::DEFAULT_FOMC_DATES`. 2026-04-29 まで:

```
2025: Jan 29, Mar 19, May 7, Jun 18, Jul 30, Sep 17, Oct 29, Dec 10
2026: Jan 28, Mar 18, Apr 29
```

## Reading the daily summary

EOD 後に Markdown サマリが標準出力に出る。SQLite が source of truth:

- `equity_trading/data/trades.sqlite`
- テーブル: `positions`, `bot_runs`, `daily_pnl`

```
sqlite3 equity_trading/data/trades.sqlite \
  "SELECT trade_date, realized_pnl_usd, n_entries, n_exits FROM daily_pnl ORDER BY trade_date DESC LIMIT 7"
```

## What can go wrong

1. **Insufficient bars エラー**: Alpaca が想定より少ないバーを返した。寄り直後に多発。1分待って再実行。
2. **Circuit halt**: 当日損失 > 2% で停止。`bot_runs.error_message` に記録。翌日まで新規エントリ無し。
3. **VIX cache 欠落**: Pre-FOMC 実行時に warn が出る。`save_vix_history.py` を再実行。
4. **PDT 抵触**: $25k 未満で過剰に day-trade すると Alpaca が拒否。Scenario A の 25%×3 + ORB 1日 1-2 銘柄なら通常は安全。
5. **休場日に `--morning`/`--orb` を実行**: bot は祝日カレンダーをチェックしない。土日と米連邦祝日は手動で skip。

## トラブル時の調査クエリ

```
sqlite3 equity_trading/data/trades.sqlite \
  "SELECT id, run_type, started_at_utc, status, error_message FROM bot_runs ORDER BY id DESC LIMIT 20"
```

## リスク開示 (敏腕モード)

- **3x レバレッジ ETF は 1日で -10% 以上動く**。Decay (volatility drag) は通常 RTH のみ保有なら軽微。
- **Max DD -16.77% を 1度は経験する想定** (7-yr で最悪は 2022 年の利上げ局面類似のパターン)。
- **VIX > 30 局面ではポジションサイズを半分に** することを検討（任意ガード）。
- 年率 +13% の中央値は安定収益ではない。**個別年で -10% も普通に起きる**。長期視点が必要。

## When to evaluate

4-12 週運用したら以下と比較:

| 戦略 | Expected WR | Expected avg P&L |
|------|------------:|------------------:|
| ORB TECL | ~0.54 | +0.22% |
| ORB TQQQ | ~0.57 | +0.15% |
| ORB TNA | ~0.53 | +0.17% |
| Pre-FOMC TECL (VIX>22) | ~0.70 | +1.56% |
| Pre-FOMC UPRO/UDOW | ~0.65 | +0.54% |

実測 WR/EV が ±10 pt 以内 → 戦略は generalize. 大幅に下回る → `run_phase0_diagnostic.py` で原因究明.
