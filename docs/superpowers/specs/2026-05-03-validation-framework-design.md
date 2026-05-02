# Validation Framework Design (Plan 2.6 / 敏腕モード v3 基盤)

> **Status**: Approved design (2026-05-03), ready for implementation plan.
> **Owner**: 自動トレード bot プロジェクト
> **Predecessors**: 敏腕モード v2.1 (commit 738c097)

## 1. 問題定義

これまでの開発で構造的に発生した「見落とし」のクラス：

| 種別 | 具体例 | 結果 |
|------|--------|------|
| 過適合 | 7 variants を同じ7年窓で grid search → 最良を選択 | "+18%/yr" の数字が forward に通用しない可能性大 |
| Tail risk 放置 | 単発 -48.94% loss 全 variant 共通 (COVID gap-down) | 25%サイズで -12.2% equity 一発、historical MaxDD の 75% |
| 隠れデータバグ | 90日 backtest で daily lookback 不足 → SMA200 全NaN → ORB全弾き | 「ORB は90日で発火しなかった」という誤った結論 |
| Code/doc/config drift | docstring "30分=6bars" vs 本番 12bars、`stop_mult` と `stop_multiplier` 二重namespace | 後続の修正時にバグ温床 |
| 「動かしていない」を「動く」と表明 | bot 1年作って Alpaca Paper 残高 $100k 完全未稼働 | 実約定検証ゼロのまま「敏腕モード」と命名 |

これらは個別のバグではなく**プロセスの欠陥**。同じ仕組みで開発を続ける限り再発する。

## 2. ゴールと非ゴール

### ゴール

- **戦略変更を入れる前に必ず通る gate** を設けて、上記5種の見落としを構造的に防ぐ
- 1コマンドで全 gate を回し、結果を1枚の markdown レポートに出す
- レポートが git に残り「あの時何を見て deploy したか」を後から追える

### 非ゴール（このspecで作らないもの）

- bot のランタイム改修（kill switch, 自動 halt 等は後続 spec C で扱う）
- 戦略開発ワークフロー全体の改革（spec D で扱う）
- 完全自動の CI ブロック（v1 は人間判断重視）
- 多 universe 対応（3x ETF 5 銘柄に絞る）

## 3. アーキテクチャ概要

```
        ┌─────────────────────────┐
        │ variant config (YAML)   │  ← 戦略パラメータの single source of truth
        └────────────┬────────────┘
                     │
                     v
        ┌─────────────────────────┐
        │ validate CLI            │
        │ (run all gates)         │
        └────────────┬────────────┘
                     │
       ┌─────────────┼─────────────┐
       v             v             v
    [Gate 1]     [Gate 2]     [Gate 3]   ...
    OOS          Tail risk    Sample size
       │             │             │
       └─────────────┼─────────────┘
                     v
        ┌─────────────────────────┐
        │ markdown report         │
        │ + reproducibility       │
        │   manifest              │
        └─────────────────────────┘
```

### 主要コンポーネント

1. **`equity_trading.validation.config`**: variant config YAML loader / schema validator
2. **`equity_trading.validation.data`**: train / holdout データアクセス（EvaluationContext を提供）
3. **`equity_trading.validation.gates`**: 各 gate の実装（gate ごとに 1 ファイル）
4. **`equity_trading.validation.report`**: markdown レポート writer
5. **`equity_trading.validation.cli`**: `python3 -m equity_trading.validation.validate`

## 4. variant config schema

```yaml
# configs/orb_tight_v2_1.yaml (例)
variant_id: orb_tight_v2_1
description: |
  ORB exit ルールを stop=OR_low+0.25R, target=OR_high+2R に変更。
parent_baseline: orb_default_v0
strategies:
  - class: OpeningRangeBreakoutStrategy
    symbols: [TECL, TQQQ, TNA]
    params:
      or_window_bars: 12
      stop_mult: 0.25
      target_mult: 2.0
      cost_pct: 0.10
  - class: LastHourMomentumStrategy
    symbols: [UPRO, UDOW]
    params:
      threshold: 0.003
      _max_hold_bars: 60
      cost_pct: 0.10
portfolio:
  position_size_pct: 0.25
  max_concurrent: 3
  starting_equity_usd: 100000
gates:
  oos:
    holdout_start: "2024-05-01"
    holdout_end: "2026-05-01"
    min_outperformance_pct: 0.0  # baseline と同等以上で OK
  tail_risk:
    max_single_trade_loss_pct: 5.0
    max_portfolio_dd_pct: 20.0
    max_rolling_30d_loss_pct: 10.0
  sample_size:
    min_holdout_trades: 30
```

config が strategy params の **唯一正規源**。コード側はこの config を読むだけで、二重 namespace が発生しない。

## 5. Gates 詳細仕様

### 共通 Gate Result dataclass

```python
@dataclass
class GateResult:
    name: str           # "oos", "tail_risk" など
    status: Status      # Status.PASS / FAIL / WARN
    summary: str        # 1行サマリ（"OOS holdout: variant +12.5% vs baseline +8.3%"）
    detail_md: str      # markdown セクション本文
    metrics: dict       # 数値メトリクス（後で集計用）
```

### Gate 1: OOS (out-of-sample)

**目的**: 過適合検出

**入力**: variant config, baseline config

**処理**:
1. EvaluationContext を開いて holdout データをロード
2. variant と baseline それぞれで portfolio backtest
3. 比較メトリクス: 年率リターン、Sharpe、MaxDD、勝率

**判定**:
- variant の年率 < baseline の年率 - `min_outperformance_pct` → FAIL
- variant の MaxDD > baseline の MaxDD × 1.2 → FAIL（リスクが過剰増加）
- 上記 PASS だが Sharpe が baseline より下回る → WARN
- 上記すべて pass → PASS

### Gate 2: Tail risk

**目的**: 一発退場リスク検出

**処理**:
1. holdout 期間の全 variant trades を取得
2. 単発 trade の最悪 P&L% を計算（trade.pnl_pct の最小値、position 内 return ベース）
3. portfolio equity curve から MaxDD% を計算（peak-to-trough、equity ベース）
4. rolling 30 calendar-day window の最悪 equity 変動率を計算

**判定**（全て絶対値で比較）:
- 単発 trade loss (position return) が `max_single_trade_loss_pct` を超える → FAIL
- portfolio MaxDD (equity curve) が `max_portfolio_dd_pct` を超える → FAIL
- 30-day rolling 損失 (equity curve) が `max_rolling_30d_loss_pct` を超える → WARN

**追加機能（v1必須・レポートのみ、変更は加えない）**: catastrophic stop の効果評価レポート。`stop_price = max(strategy_stop, entry_price * (1 - 0.05))` を適用した parallel シミュレーションも走らせ、「キャップを入れたら最悪 trade と portfolio MaxDD がどう変わるか」をレポートに併記する。これは比較情報の提示であり、実際にキャップを strategy に適用するかは別の判断（次の variant config に取り込むかどうか）。

### Gate 3: Sample size

**目的**: 統計的有意性確保

**処理**: holdout で variant が生成した trade 数をカウント

**判定**:
- n < `min_holdout_trades` → FAIL
- n < `min_holdout_trades` * 1.5 → WARN
- n ≥ `min_holdout_trades` * 1.5 → PASS

### Headline 判定ロジック

```python
def overall_status(gates: list[GateResult]) -> str:
    required = [g for g in gates if g.name in {"oos", "tail_risk", "sample_size"}]
    if any(g.status == FAIL for g in required):
        return "REJECT"
    if any(g.status == WARN for g in gates):
        return "REVIEW"
    return "APPROVE"
```

## 6. データ・アーキテクチャ

### 物理分離

```
equity_trading/data/prices/
├── train/                            # 自由アクセス
│   ├── TECL_5min_2019-05-01_2024-05-01.parquet
│   ├── ...
├── holdout/                          # EvaluationContext 経由のみ
│   ├── TECL_5min_2024-05-01_2026-05-01.parquet
│   ├── ...
├── manifest.json                     # 全ファイルの hash + cutoff date
└── holdout_access.jsonl              # holdout access ログ (append only)
```

### EvaluationContext API

```python
from equity_trading.validation.data import EvaluationContext

with EvaluationContext(variant_id="orb_tight_v2_1", reason="gate:oos") as ctx:
    bars = ctx.load_5min("TECL", start="2024-05-01", end="2026-05-01")
    # ctx exit 時に holdout_access.jsonl に access 記録を書く
```

通常の `PriceFetcher` は train/ のデータしか返さない。holdout は `EvaluationContext` 内でのみ取得可能。これで「うっかり holdout データで学習」を物理的に防ぐ。

### Manifest 検証

`manifest.json` には各 parquet の SHA256 hash と cutoff_date を記録。validate CLI 起動時に：
1. 全ファイルの hash が manifest と一致するか check
2. holdout の最終 timestamp が cutoff_date 以前か check
3. 不一致なら起動拒否（データが書き換わった可能性）

## 7. レポート・フォーマット

`phase0/validation/2026-05-03_<variant_id>_<git_sha>.md` に出力：

```markdown
# Validation Report: orb_tight_v2_1

- **Variant**: orb_tight_v2_1
- **Baseline**: orb_default_v0
- **Generated**: 2026-05-03 14:32 UTC
- **Git SHA**: 738c097
- **Data manifest hash**: abc123...
- **Holdout window**: 2024-05-01 → 2026-05-01

## Headline: ✅ APPROVE / ⚠️  REVIEW / ❌ REJECT

(reason summary)

## Gate Results

### OOS — PASS / FAIL / WARN
(summary)
(detail markdown)

### Tail Risk — ...
...

### Sample Size — ...
...

## Reproducibility

To reproduce this report:
\`\`\`
git checkout 738c097
python3 -m equity_trading.validation.validate \
    --variant configs/orb_tight_v2_1.yaml \
    --baseline configs/orb_default_v0.yaml
\`\`\`

## Decision Log

(空欄。人間が記入する: APPROVED / REJECTED / 理由)
```

## 8. ワークフロー統合

戦略変更の標準サイクル：

1. アイデア → `configs/<variant_id>.yaml` 作成
2. **train/ データのみで** 実装・パラメータ探索（holdout には触らない）
3. `python3 -m equity_trading.validation.validate --variant configs/<id>.yaml --baseline configs/<baseline_id>.yaml`
4. 出力 markdown を読む
5. APPROVE → paper trade に進む。REVIEW → reviewer 相談 or 再設計。REJECT → train/ に戻って再考
6. **全 validation report を git commit**。「あの時何を見て deploy したか」が永久に追える

## 9. v1 スコープ（このspecで実装）

**含む**:
- データ分割（train/holdout 物理分離）
- `manifest.json` + hash 検証
- `EvaluationContext` + `holdout_access.jsonl`
- variant config YAML schema + loader
- CLI エントリーポイント
- Gate 1 (OOS), Gate 2 (Tail risk), Gate 3 (Sample size)
- Markdown report writer + reproducibility manifest
- 既存 ORB v2.1 を最初の victim として走らせ動作確認

**含まない（v2以降に分離）**:
- Gate 4 (regime stratification)
- Gate 5 (reproducibility regression check)
- Gate 6 (doc/code sync linter)
- Gate 7 (live-run gate)
- Gate 8 (block-bootstrap CI)
- Gate 9 (walk-forward stability)

## 10. 既存コードへの影響

### 追加

```
equity_trading/src/validation/
├── __init__.py
├── config.py          # YAML loader
├── data.py            # EvaluationContext
├── gates/
│   ├── __init__.py
│   ├── base.py        # GateResult, Status
│   ├── oos.py
│   ├── tail_risk.py
│   └── sample_size.py
├── report.py          # Markdown writer
└── cli.py             # python3 -m equity_trading.validation.validate

equity_trading/configs/                # 新規
├── orb_default_v0.yaml
├── orb_tight_v2_1.yaml
└── ...

equity_trading/data/prices/manifest.json  # 新規
```

### 既存ファイル変更

- `equity_trading/src/data/price_fetcher.py`: train/ のみ load するよう変更（holdout 直 access を拒否）
- `equity_trading/scripts/run_portfolio_ensemble.py`: variant config を読む形にリファクタ（既存の `SELECTED` リテラルは廃止）
- `equity_trading/data/prices/`: 既存 parquet を train/ と holdout/ に振り分け

## 11. テスト戦略

- 各 gate に unit test（mock data で PASS / FAIL の両方）
- EvaluationContext の access logging を test
- manifest hash 検証の test（書き換え検知）
- end-to-end test: 既存の orb_v0 と orb_v2_1 で full validation を回し、レポートが期待通り生成されるか

## 12. 受け入れ基準

このspec実装が「完了」と言える条件：

1. `python3 -m equity_trading.validation.validate --variant configs/orb_tight_v2_1.yaml --baseline configs/orb_default_v0.yaml` が正常終了し markdown レポートを出力
2. レポートに 3 つの必須 gate の結果と headline 判定が含まれる
3. holdout に train から間違ってアクセスすると例外が出る
4. manifest 改竄を検知して起動拒否する
5. 既存 230 テスト（+ 新規 validation テスト）すべて pass
6. 既存の `run_portfolio_ensemble.py` が config-based で動く
7. RUNBOOK に「戦略変更時の validation 手順」が追記される

## 13. リスクと緩和

| リスク | 緩和 |
|--------|------|
| holdout が短すぎる（2年）統計力不足 | n=30 gate でカバー。将来的に paper trade で蓄積分を holdout 化 |
| variant config の YAML が複雑化 | schema validator で early fail。schema は jsonschema 形式で文書化 |
| EvaluationContext を破る方法（直接 parquet 読み）が残る | code review でブロック。lint rule (forbid raw `pd.read_parquet` outside data/) は v2 で追加 |
| 既存 `run_portfolio_ensemble.py` の SELECTED 撤去で他コードが壊れる | 既存 entry を全 yaml 化、test で網羅 |

## 14. 後続 spec への接続

この validation framework は今後の spec の**前提**になる：

- **spec B (code/doc 同期)**: validation の Gate 6 (doc lint) として組み込み
- **spec C (デプロイ運用)**: APPROVE が出たもののみ paper deploy。Gate 7 (live-run) で paper 実績を validation に取り込む
- **spec D (開発ワークフロー)**: 「変更には validation report の commit が必須」を CI で enforce
