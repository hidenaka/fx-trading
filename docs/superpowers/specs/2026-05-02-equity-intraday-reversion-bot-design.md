# 米国ETFデイトレードBot（マルチシグナル × 短期リバージョン × トレンドフィルター）Design

## Goal

米国主要ETF（SPY/QQQ）を対象に、複数のテクニカルシグナルを組み合わせた短期リバージョン戦略をローカルMacで自動運用し、**年8〜12%リターン・最大ドローダウン-20%以内**で長期複利成長を狙う、感情を排した自動売買Botを構築する。Paper Trading環境で最低3ヶ月の検証を経た上で、合格基準を満たした場合のみLive Tradingへ手動承認で移行する。

## Architecture

シングルプロセス・ステートフルなBotを launchd で常駐させ、Alpaca Paper/Live API と通信する。MacBook（開発）→ Mac Mini（本番）への移管は launchd plist と `.env` のコピーで完結する。複雑な分散構成は採用せず、シンプルさを安定性の源泉とする。状態は SQLite に永続化し、プロセス再起動時に Alpaca 側との状態突合を行う。

戦略・リスク管理・学習ロジックは純粋関数として `broker/` 層から分離し、テストの容易性と将来のブローカー差し替え可能性を担保する。本番（Live）への切り替えは `.env` の `ALPACA_BASE_URL` と確認フラグの変更のみで完結する。

「人間が手動で介入できる余地」を意図的に最小化する。手動売買UIは作らない。緊急停止コマンドのみ提供する。これは「大負けしない」を裏切る最大の敵が人間の感情であるという設計思想に基づく。

## Components

新規ディレクトリ `equity_trading/` を `fx_trading/` と並列で作成する。FX系コードと完全に独立させ、混入を防ぐ。

```
equity_trading/
├── .env.example
├── requirements.txt
├── pyproject.toml
├── README_LIVE.md                    # 本番移行手順・緊急停止手順を冒頭に
├── src/
│   ├── config.py                     # 環境変数・設定値・パラメータの一元管理
│   ├── broker/
│   │   └── alpaca_client.py          # Alpaca SDKラッパー（薄い層）
│   ├── data/
│   │   ├── price_fetcher.py          # 価格取得・キャッシュ
│   │   └── feature_builder.py        # RSI/BB/VWAP/出来高比/200d MA計算
│   ├── strategy/
│   │   ├── intraday_reversion.py     # マルチシグナル戦略本体（純粋関数）
│   │   └── signal_weights.py         # シグナル重み（学習で更新される値）
│   ├── learning/
│   │   ├── parameter_optimizer.py    # 月次WFAでパラメータ最適化
│   │   ├── signal_tracker.py         # シグナル別の勝率・期待値を記録
│   │   ├── weight_updater.py         # 直近成績でシグナル重みを日次更新
│   │   └── promotion_gate.py         # Paper→Live移行可否を判定
│   ├── risk/
│   │   ├── circuit_breaker.py        # 4階層のサーキットブレーカー
│   │   └── position_sizer.py         # 1取引リスク0.7%でサイズ計算
│   ├── execution/
│   │   ├── intraday_loop.py          # 5分間隔のシグナル評価＆発注
│   │   └── exit_manager.py           # 利確・損切り・大引け強制決済
│   ├── state/
│   │   ├── store.py                  # SQLite永続化
│   │   └── migrations.py             # スキーマ管理
│   ├── monitor/
│   │   ├── logger.py                 # 構造化ログ
│   │   ├── dashboard.py              # 日次レポート生成
│   │   └── notifier.py               # Slack/メール通知（任意）
│   └── runner/
│       ├── intraday_runner.py        # 5分ごと：シグナル評価・発注
│       ├── eod_runner.py             # 大引け後：日次集計・重み更新
│       ├── monthly_runner.py         # 月初：WFA最適化・移行ゲート評価
│       └── emergency_stop.py         # 緊急停止
├── scripts/
│   ├── backtest.py                   # バックテストCLI
│   ├── paper_summary.py              # Paper運用累積レポート
│   ├── parameter_history.py          # パラメータ変更履歴
│   ├── promotion_check.py            # 本番移行可否チェック
│   └── emergency_stop_cli.py         # 緊急停止CLI
├── deploy/
│   ├── com.user.equity-bot-intraday.plist
│   ├── com.user.equity-bot-eod.plist
│   └── com.user.equity-bot-monthly.plist
├── tests/
│   ├── test_intraday_reversion.py
│   ├── test_circuit_breaker.py
│   ├── test_parameter_optimizer.py
│   ├── test_signal_tracker.py
│   ├── test_weight_updater.py
│   ├── test_promotion_gate.py
│   ├── test_position_sizer.py
│   └── test_integration_flow.py
└── data/
    ├── prices/                       # 価格キャッシュ（gitignore）
    └── trades.sqlite                 # 取引・パラメータ履歴（gitignore）
```

### モジュールの責任分担

| モジュール | 責任 | 依存 | テスト方針 |
|---|---|---|---|
| `config.py` | 環境変数読込・型変換・バリデーション | なし | 値テスト |
| `broker/alpaca_client.py` | Alpaca APIの薄いラッパー | alpaca-py | モック化 |
| `data/price_fetcher.py` | 価格取得・キャッシュ | alpaca-py | 既知期間テスト |
| `data/feature_builder.py` | 指標計算（純粋関数） | pandas | 既知データで決定論的 |
| `strategy/intraday_reversion.py` | シグナル評価・統合スコア（純粋関数） | pandas | 既知データで決定論的 |
| `learning/*.py` | 学習ロジック | なし（pandas） | 単体・統合テスト |
| `risk/*.py` | リスク管理（純粋関数） | なし | パラメータテスト |
| `execution/*.py` | 注文発注 | broker | モック化 |
| `state/store.py` | SQLite永続化 | sqlite3 | 一時DB |
| `runner/*.py` | スケジューラ・統合 | 全部 | 統合テスト |

設計原則：
- `strategy/` `risk/` `learning/` は純粋関数。副作用なし、テスト容易。
- ブローカーAPIを叩くのは `broker/` のみ。他層からは隠蔽。
- `runner/` だけが各層を統合する責任を持つ。

## Strategy Logic

### 入力
- SPY/QQQ の 1分足・5分足・日足（直近1年分は常時キャッシュ）
- 現在保有ポジション・口座残高
- 現在のシグナル重み（DB から取得）
- 現在のパラメータ（DB から取得、月次最適化で更新）

### エントリー判定（5分間隔）

**1. トレンドフィルター（必須）**
- SPY 日足 > 200日移動平均 → 取引可能
- SPY 日足 < 200日移動平均 → その日は買いを完全停止（現金待機）
- 暴落相場で逆張りして殺されるリスクを構造的に除去する。

**2. シグナル評価（各シグナルが0〜1のスコアを出す）**

| シグナル | スコア計算式 | 初期重み |
|---|---|---|
| RSI過売り | 5分足RSI(14)が30以下 → score = (30 - RSI) / 30 | 0.30 |
| ボリンジャー下抜け | BB(20, 2σ)下限を下抜け → score = 下抜け幅 / σ | 0.25 |
| VWAP乖離 | 当日VWAPからの下方乖離率 / σ | 0.20 |
| 出来高急増 | 直近平均の1.5倍以上 → score = min(出来高比 / 2, 1) | 0.15 |
| 短期勢い反転 | 直近3本の足の傾きがマイナスから反転 | 0.10 |

**統合スコア = Σ(各シグナルのスコア × 重み)**
- 統合スコア ≥ 0.6 ならエントリー
- 重みは学習で動的に更新される（合計は常に1.0）

**3. ポジションサイズ**
- 1取引のリスク = 口座残高の **0.7%**
- 損切り幅から逆算してドル数量を決定
- 最大でも口座残高の **50%** まで

### エグジット判定（既ポジション保有時、毎分）

| 発動条件 | アクション | 優先順位 |
|---|---|---|
| 1日累計損失 ≤ -2% | 全ポジション即時決済＆当日全停止 | 0（最最優先） |
| 連続3敗 | 既ポジは通常エグジット、当日新規停止 | 0 |
| エントリー価格 -0.4% 到達 | 即時損切り（成行） | 1 |
| エントリー価格 +0.5% 到達 | 利確 | 2 |
| 大引け15分前 | 強制決済（オーバーナイト持ち越し禁止） | 3 |

**ペイオフ比は損切り0.4%・利確0.5% で 1.25:1。勝率55%以上で期待値プラスとなる構造。**

## Learning System (Level 1.5)

### A. シグナル重みの動的更新（日次）

`eod_runner` が大引け30分後に実行：
1. 当日のすべての取引について、エントリー判断に寄与したシグナルを記録
2. 過去90日分のデータから各シグナルの期待値を計算
   - 期待値 = 勝率 × 平均利益 - 負率 × 平均損失
3. 期待値を 0〜1 に正規化して新しい重みを生成
4. 指数移動平均で滑らかに更新：`new = 0.8 × old + 0.2 × normalized`
5. 合計が1.0になるよう再正規化

**安全装置：**
- 重みの月次変動 ≤ ±20%
- 取引数30件未満のシグナルは重み変更しない（統計的有意性）
- 全重み合計は常に1.0

### B. パラメータ最適化（月次）

`monthly_runner` が毎月1日 日本時間 7:00 に実行：
1. 過去6ヶ月の価格データ＋取引履歴を取得
2. 以下のパラメータをグリッドサーチ：
   - RSI閾値: [25, 28, 30, 32, 35]
   - BB期間: [15, 20, 25]
   - 損切り幅: [0.3%, 0.4%, 0.5%]
   - 利確幅: [0.4%, 0.5%, 0.6%, 0.8%]
   - 統合スコア閾値: [0.5, 0.6, 0.7]
3. 各組み合わせをバックテスト
   - 評価指標 = シャープレシオ × 0.5 + (1 - MDD率) × 0.3 + 勝率 × 0.2
4. ベスト10%を Walk-Forward Analysis で検証
   - 6ヶ月を 5:1 に分割、各分割で最適化＋検証
5. 全分割で安定上位の組み合わせを採用
6. 新パラメータを DB に保存（旧値は履歴として残す）

### C. Paper→Live 昇格ゲート

`promotion_gate` が以下の全条件を AND で判定：
- Paper運用が累積3ヶ月以上
- 累積取引回数 ≥ 60件
- 勝率 ≥ 55%
- プロフィットファクター ≥ 1.3
- 最大ドローダウン ≥ -15%（つまり-15%より浅い）
- シャープレシオ ≥ 1.0
- パラメータが過去2ヶ月で大幅変動していない（戦略不安定の兆候）
- システムエラー比率 < 5%

**全条件クリア時のみ「本番移行可能」と判定。自動では切り替えない。** 必ず人間が `promotion_check.py` を実行 → レポート確認 → `.env` を手動切り替え。

## Data Flow

### 米国市場時間と日本時間の対応
- 冬時間（11月〜3月）：米東部 9:30〜16:00 = 日本 23:30〜翌6:00
- 夏時間（3月〜11月）：米東部 9:30〜16:00 = 日本 22:30〜翌5:00

### Runner スケジュール

**`intraday_runner`：5分間隔（米国市場時間中のみ）**

```
[起動]
  → 市場オープン確認（クローズ中は即終了）
  → サーキットブレーカー状態確認（停止中は即終了）
  → 現保有ポジション確認
  → ポジションあり？
       YES → エグジット判定（損切り/利確/大引け前/日次損失）
       NO  → エントリー判定（トレンドフィルター→シグナル評価→注文）
  → ログ・状態保存
[終了]
```

1回の実行は10〜30秒程度（API呼び出し3〜5回）。

**`eod_runner`：1日1回（大引け30分後）**
```
当日取引履歴集計 → シグナル寄与度記録 → 重み再計算
→ 翌日用重みを保存 → 日次レポート生成
→ サーキットブレーカー日次リセット
```

**`monthly_runner`：月初1回（毎月1日 7:00）**
```
過去6ヶ月データ取得 → グリッドサーチ → WFA検証
→ 新パラメータ保存 → promotion_gate判定
→ 月次レポート生成
```

### SQLite スキーマ（主要テーブル）

```sql
-- 設定値・パラメータ（学習で更新）
CREATE TABLE parameters (
  key TEXT PRIMARY KEY,
  value_json TEXT NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  source TEXT NOT NULL  -- 'manual' | 'monthly_optimizer' | 'initial'
);

CREATE TABLE parameter_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  key TEXT NOT NULL,
  old_value TEXT,
  new_value TEXT,
  changed_at TIMESTAMP NOT NULL
);

-- シグナル重み（日次更新）
CREATE TABLE signal_weights (
  signal_name TEXT PRIMARY KEY,
  weight REAL NOT NULL,
  updated_at TIMESTAMP NOT NULL
);

-- 取引履歴
CREATE TABLE trades (
  id TEXT PRIMARY KEY,           -- alpaca order id
  symbol TEXT NOT NULL,
  side TEXT NOT NULL,
  quantity REAL,
  entry_price REAL,
  exit_price REAL,
  entry_time TIMESTAMP,
  exit_time TIMESTAMP,
  pnl REAL,
  signals_used_json TEXT,
  exit_reason TEXT  -- 'take_profit' | 'stop_loss' | 'eod' | 'circuit_breaker'
);

-- 日次サマリー
CREATE TABLE daily_summary (
  date TEXT PRIMARY KEY,
  trade_count INTEGER,
  win_count INTEGER,
  total_pnl REAL,
  max_drawdown REAL,
  circuit_breaker_triggered BOOLEAN
);

-- サーキットブレーカー状態
CREATE TABLE circuit_breaker_state (
  id INTEGER PRIMARY KEY,        -- 常に1
  is_halted BOOLEAN,
  halted_at TIMESTAMP,
  reason TEXT,                   -- 'daily_loss' | 'consecutive_losses' | 'cumulative_dd'
  resume_after TIMESTAMP
);
```

## Error Handling

### エラー分類と対応

| カテゴリ | 例 | 対応 | 通知 |
|---|---|---|---|
| API一時エラー | タイムアウト、502/503 | 指数バックオフでリトライ最大3回 | エラーログ |
| APIレート制限 | 429 | 60秒待機後リトライ | 警告ログ |
| API恒久エラー | 401/403 | 即時停止 | 緊急通知 |
| 資金不足 | margin insufficient | 当該注文スキップ | 警告通知 |
| 重複注文 | already filled | 状態同期して冪等処理 | ログのみ |
| データ欠損 | feed古い | 取引スキップ | 警告ログ |
| 市場異常 | halt、ハイ・ボラ | エントリー見送り、既ポジは通常エグジット | 警告通知 |
| DB障害 | ロック・破損 | リトライ後復旧不能なら全停止 | 緊急通知 |
| Botクラッシュ | OOM、未処理例外 | launchd自動再起動、起動時状態整合チェック | 警告通知 |
| 戦略バグ | 暴走（大量注文） | 注文レート制限で阻止、即停止 | 緊急通知 |

### サーキットブレーカー（4階層）

**階層1：取引単位（即時）**
- 1取引の損失が想定の2倍超 → 緊急成行決済
- 注文10秒以内に約定確認できず → キャンセル

**階層2：日次（翌営業日リセット）**
- 当日累計損失 ≤ -2% → 既ポジ即時決済＆当日全停止
- 連続3敗 → 既ポジ通常エグジット、当日新規停止
- 当日取引数 ≥ 20件 → 過剰取引と判定、当日停止
- API失敗率 > 10%（直近1時間） → 当日停止

**階層3：累計（手動リセットのみ）**
- 累計DD ≥ -20% → 全停止、再開不可
  - リセットは `emergency_stop_cli.py --reset` のみ
  - 1営業日経過 + 手動承認が必須

**階層4：システム（即時かつ永続）**
- API認証エラー → 即停止、`.env` 確認後手動再開
- DB破損 → 即停止、バックアップから復元
- Alpaca側で口座制限 → 即停止

### 状態整合性

`intraday_runner` 起動毎に以下を実行：
1. SQLite「現在保有」と Alpaca「実保有」を突合
   - 不一致 → Alpaca側を信頼してSQLite修正、警告ログ
2. 未約定注文の状態確認、30秒以上 pending はキャンセル
3. サーキットブレーカー状態確認、停止中は即終了
4. 最終正常実行から12時間以上経過なら警告（launchd死亡検知）

「孤立ポジション」検出：
- Alpacaに保有あり、SQLiteなし → 緊急停止＆通知
- SQLiteに保有あり、Alpacaなし → SQLite側修正＆ログ

### 「人間が壊さない」ガード
1. 手動売買UIを作らない
2. `.env` の主要パラメータを起動時にバリデーション（例：`risk_per_trade > 0.05` ならエラー）
3. Liveでは `confirm_live=true` 明示しないと起動しない
4. 緊急停止後は「1営業日経過 + 手動承認」で再開
5. パラメータ自動更新の最大変動率を制限

## Testing Strategy

### Layer 1：ユニットテスト（純粋関数モジュール）
- 戦略ロジック：トレンドフィルター・各シグナル・統合スコア計算
- リスク管理：サーキットブレーカー・ポジションサイザー
- 学習：重み更新の滑らかさ・合計1.0保持・統計的有意性
- 目標カバレッジ：純粋関数モジュール 95%以上

### Layer 2：統合テスト（Alpaca モック）
- エントリー → 約定 → 利確 → 状態更新の一連フロー
- サーキットブレーカー発動時の挙動
- 孤立ポジション検出
- DB と Alpaca の状態整合

### Layer 3：バックテスト（過去5〜10年）
- データ：Alpaca から SPY/QQQ の1分足・5分足・日足を取得
- 期間：2018〜2024年など
- 合格基準：
  - 累積リターン > +50%（7年で）
  - シャープレシオ > 0.8
  - 最大ドローダウン > -20%
  - 勝率 > 55%
  - プロフィットファクター > 1.3
  - 連続マイナス月 < 4
  - 月次取引回数 15〜50
- WFA で頑健性検証（カーブフィッティング除外）

**バックテスト罠への対策：**
- 未来データ使用の検出
- 約定価格の現実的再現（成行は次足始値、指値は実約定可能性）
- 取引コスト（スリッページ0.05%）考慮
- 米国祝日・週末の正確なスキップ

### Layer 4：Paper運用（最低3ヶ月必須）
- 監視指標：累積損益、バックテストとの乖離、取引数、API失敗率、クラッシュ
- チェックリスト：
  - 200日MA下では取引していない
  - サーキットブレーカーが想定通り発動した
  - オーバーナイト持ち越しが起きていない
  - シグナル重みが日次で滑らかに更新されている
  - 月次最適化が実行されている
  - DB と Alpaca の状態が常に一致
  - 緊急停止コマンドが動く
  - Mac再起動後に launchd で自動復帰

### Layer 5：本番監視
- 自動レポート：日次・週次・月次
- 自動アラート：想定外挙動、累計DD段階警告、3ヶ月連続マイナス
- 運用ルール：
  - 最初の3ヶ月は資金の20-30%のみ投入
  - 月次レポート必読
  - パラメータ大幅変動は人間が承認
  - 戦略変更は Paper に戻して再検証

## Configuration

### 主要パラメータ（初期値、月次最適化で更新）
- 通貨：USD（Alpaca米国口座）
- 対象：SPY, QQQ
- 1取引リスク：0.7%
- 最大ポジションサイズ：口座残高の50%
- 損切り幅：0.4%
- 利確幅：0.5%
- 統合スコア閾値：0.6
- 日次損失上限：2%
- 連敗停止：3回
- 累計DD停止：20%
- トレンドフィルター：SPY 日足 vs 200日移動平均

### 環境変数（`.env`）
```
ALPACA_API_KEY=
ALPACA_SECRET_KEY=
ALPACA_BASE_URL=https://paper-api.alpaca.markets  # Live移行時のみ変更

CONFIRM_LIVE=false                  # Live起動時のみ true 明示

INITIAL_CAPITAL_USD=100000
RISK_PER_TRADE=0.007
MAX_POSITION_PCT=0.50
DAILY_LOSS_LIMIT=0.02
CUMULATIVE_DD_LIMIT=0.20

SLACK_WEBHOOK_URL=                  # 任意
NOTIFICATION_EMAIL=                 # 任意
```

### 移行運用ルール（Live移行時）
1. promotion_gate の全条件をクリア
2. `promotion_check.py` で最終レポート確認
3. `.env` の `ALPACA_BASE_URL` を Live 用に変更
4. `CONFIRM_LIVE=true` を明示
5. **資金は当初20-30%のみ投入**（残りは手元）
6. 1ヶ月正常稼働を確認後、段階的に増資

## Out of Scope

以下は本設計には含めない：
- 個別株の取引（ETFのみ）
- 暗号資産の取引（将来拡張可能性は残す）
- レバレッジETF（TQQQ等）の取引
- ショート・空売り
- オプション取引
- ML予測モデル（Random Forest, NN等。Level 3 は採用しない）
- 手動売買UI
- 既存 `fx_trading/` のコード変更
- マルチユーザー対応
