# Equity Bot — Operations Runbook (敏腕モード v2 / Plan 2.5.2)

> **モード**: 敏腕モード v2 (ORB + LHM、3x レバレッジ ETF、V0 ORB exit)
> **想定リターン**: **年 +13.75%**（7年バックテスト、V0 ORB exit）
> **想定 Max DD**: **-16.33%**（7-yr バックテスト最悪期間）
>
> **2026-05-03 v2.1 撤回**: V2.1 (ORB exit `stop_mult=0.25 / target_mult=2.0`) を
> validation framework で初の holdout 検証にかけたところ **REJECT**:
> - OOS: variant -13.78% vs baseline -12.80% (FAIL)
> - Tail risk: worst trade -5.74%, MaxDD 31.78% (FAIL)
> - Sample size: 652 trades (PASS)
>
> 7年 in-sample で観測された +18.66%/yr は**過適合**であり、デプロイすべきでないと
> framework が判断。デフォルトを V0 (stop_mult=0, target_mult=1) に戻した。
> `stop_mult` / `target_mult` のパラメータ化自体は variant 探索のため保持。
> 詳細: `equity_trading/phase0/validation/2026-05-03_orb_v2_1.md`
>
> **資金前提**: 初期 ¥100,000 + 毎月 ¥50,000 の積立
>
> **2026-05-02 改訂**: Pre-FOMC drift を構成から外しました。7年集計では +EV だが
> 2024-2026 窓で WR 0/5 まで劣化しており、ポートフォリオ全体の最悪窓を
> -4.96%/yr → +6.70%/yr に改善する効果がありました。`--pre-fomc` CLI は
> コードとしては残しますが、**敏腕モード v2 では使用しません**.

## 2026-05-04 Phase A search outcome

Post-warmup-fix baseline (`orb_default_v0`) holdout was -22.60%/yr / -42.02% MaxDD,
prompting Phase A variant search per
`docs/superpowers/specs/2026-05-04-strategy-rethink-design.md`.

**Step 1 (6 candidates) result**: see
`equity_trading/phase0/phase_a_search_2026-05-04.md`. **0 candidates pass**
the survival threshold (ann ≥ -3%/yr, MaxDD ≤ 20%, worst trade ≤ 5%,
Sharpe ≥ -0.3) on internal valid2 (2022-01 → 2024-04).

Best variant: `orb_default_v0_capped_size12_vix22` (ann -9.70%/yr,
MaxDD -21.12%, worst -5.10%, Sharpe -3.16, 797 trades). Catastrophic
stop and 12.5% sizing reduce magnitude but cannot close the gap to
positive expectancy in the 2022 hike-cycle regime.

**Holdout test of winner**: skipped (Task 8 condition not met — no
candidate passed valid2).

**Deploy candidate**: none. **Next step** per spec §8: escalate to
Phase A step 2 (12 candidates with target_mult ∈ {1.0, 1.5}), then
step 3 (24 with daily_halt_pct), or open Phase B brainstorm if
step 2/3 also produce 0 passers.

## What this bot does

Runs scheduled jobs against Alpaca **Paper** account using **3x leveraged ETFs**:

- **Morning** (~9:31 ET): scans SPY/QQQ/DIA/IWM for gap-fill setups (legacy strategy, low-EV anchor).
- **ORB** (every 5 min, 10:35-15:50 ET): scans **TECL/TQQQ/TNA** for 60-min Opening Range breakouts. **敏腕モードの主戦場 #1**.
- **LHM (Last-Hour Momentum)**: 戦略コードはあり、敏腕モードに含まれるが**専用のCLIランナーは未実装**。
   現状は `--orb` ループに統合された形で発火する設計を予定（次の実装課題）。
- **EOD** (~15:55 ET): closes still-open positions at market.
- **(Disabled) Pre-FOMC / FOMC Close**: コードは残るが敏腕モード v2 では使用しない。

## Strategy change validation (敏腕 v3 framework)

Before deploying any strategy variant change to paper trading, run the
validation framework:

```
python3 -m equity_trading.src.validation \
    --variant equity_trading/configs/<new_variant>.yaml \
    --baseline equity_trading/configs/<current_baseline>.yaml \
    --output equity_trading/phase0/validation/$(date +%Y-%m-%d)_<variant_id>.md
```

The framework:
1. Verifies `data/prices/manifest.json` matches on-disk parquets (rejects start otherwise)
2. Reads variant + baseline strategy configs (YAML, single source of truth)
3. Loads `data/prices/holdout/` via `EvaluationContext` (every read is logged to `holdout_access.jsonl`)
4. Runs portfolio simulation on holdout for both variant and baseline
5. Runs three required gates: OOS comparison, tail risk, sample size
6. Writes a markdown report with PASS/FAIL/WARN per gate and a headline (APPROVE / REVIEW / REJECT)

Required gate thresholds (from variant config):
- **OOS**: variant annualized return must be ≥ baseline; variant drawdown must be ≤ 1.2x baseline
- **Tail risk**: worst single trade ≤ 5% loss, portfolio MaxDD ≤ 20%, 30-day rolling ≤ 10%
- **Sample size**: ≥ 30 trades on holdout

A REJECT result blocks deployment. Iterate on `data/prices/train/` only;
**never modify code based on holdout observations** (that is the curve-fit
trap this framework prevents).

After deployment, the holdout is "burned" — accumulate new paper-trade
data and refresh the holdout cutoff before the next variant test.

(Real-world demonstration: see `equity_trading/phase0/validation/2026-05-03_orb_v2_1.md`
for the first validation run, which REJECTED an in-sample-optimized variant —
exactly what this framework is designed to catch.)

## 多窓検証 (敏腕モード v2 構成、2026-05-02)

複数窓で同じ構成を回し、最悪窓でもプラスを維持する組み合わせを採用：

| 構成 | W90 ann | W1Y ann | W2Y ann | W7Y ann | 最悪 | 最悪DD |
|------|--------:|--------:|--------:|--------:|-----:|-------:|
| V0 (旧 / Pre-FOMC込) | -4.96% | +4.84% | +12.60% | +13.04% | -4.96% | -16.81% |
| **V3 = 敏腕 v2 (LHM+ORB)** | **+7.49%** | **+6.70%** | **+12.55%** | **+11.07%** | **+6.70%** | -19.69% |
| V1 LHM-only | +21.78% | +3.73% | +1.20% | +1.53% | +1.20% | -14.60% |
| V2 ORB-only | -11.41% | +4.91% | +11.16% | +8.26% | -11.41% | -19.09% |

→ V3 が**4窓全てで正リターン** 維持の唯一の組み合わせ。

### 敏腕コア戦略 (7年バックテスト)

| Strategy | Symbol | n | WR | EV (sum %) | Avg/trade |
|----------|--------|---|------|------------|-----------|
| **ORB** | TECL | 486 | 0.543 | +108.38 | +0.223% |
| **ORB** | TQQQ | 531 | 0.565 | +76.96 | +0.145% |
| **ORB** | TNA | 369 | 0.534 | +62.06 | +0.168% |
| **Last-Hour Momentum** | UPRO | ~470 | ~0.55 | +positive | +small |
| **Last-Hour Momentum** | UDOW | ~470 | ~0.55 | +positive | +small |

### Legacy non-leveraged (gap_fill, optional)

| Strategy | Symbol | n | WR | EV |
|----------|--------|---|------|-----|
| gap_fill | QQQ (0.3%) | 213 | 0.573 | +18.35 |
| gap_fill | IWM (1.0%) | 33 | 0.576 | +4.97 |
| gap_fill | SPY (0.5%) | 81 | 0.494 | +3.08 |
| gap_fill | DIA (0.5%) | 75 | 0.453 | +3.02 |

**Sizing (敏腕モード)**: 25% of account equity per trade, **max 3 concurrent positions**. Same-symbol re-entry blocked while a position is open.

**Halt rule**: realized loss > 2% of equity in a day → new entries suppressed (also blocks Pre-FOMC, ORB).

## Projected portfolio return (敏腕 v2 = LHM+ORB, V0 exit)

7年フル replay（$100k 初期 + ¥50,000/月 12回 = 投入総額 $127,300）:

| Scenario | 終了残高 | 純損益 | 7-yr Ann | Max DD |
|----------|---------:|------:|--------:|-------:|
| **A: 25%×3 (敏腕推奨, V0 exit)** | **$246,440** | **+$119,140** | **+13.75%** | **-16.33%** |

> 注: V2.1 (stop_mult=0.25 / target_mult=2.0) は 7年 in-sample で +18.66%/yr に
> 見えたが、holdout で REJECT されたため採用しない。詳細は冒頭参照。

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

### Pre-FOMC は使用しない (敏腕 v2)

`--pre-fomc` / `--fomc-close` CLI はコードとして残るが、**敏腕モード v2 では実行しない**。
2024-2026 の直近窓で WR 0/5 まで劣化しており、ポートフォリオ全体の安定性を
落としているため。日次ルーチンには含めない。

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
