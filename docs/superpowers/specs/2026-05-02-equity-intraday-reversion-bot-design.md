# 米国ETFデイトレードBot（マルチシグナル × 短期リバージョン × トレンドフィルター）Design v1.0-final

**改訂履歴：**
- v0.9-draft (2026-05-02): 初版
- v1.0-final (2026-05-02): 独立レビューを反映。期待値の数学・スリッページ前提・launchd具体例・米国祝日・サマータイム・SQLite並行性・死活監視・WFA分割・Paper期間・promotion基準・税務/PDT/wash saleリスク等を補強
- v1.0.1 (2026-05-02): 再レビュー指摘の数学的誤りを訂正。損益分岐勝率を46.15%に、目標年6-10%に必要な勝率を47-49%に修正。promotion基準は安全マージンとして勝率57%を維持。Rolling 90日DD分位の定義明確化。ATR3倍判定の責任を flash_crash_guard.py に一元化。「戦略見直しゲート」を削除し、フラッシュクラッシュ多発時の挙動を明示

## Goal

米国主要ETF（SPY/QQQ）を対象に、複数のテクニカルシグナルを組み合わせた短期リバージョン戦略をローカルMacで自動運用し、**スリッページ・スプレッドを正直に織り込んだ上で年6〜10%リターン・最大ドローダウン-20%以内**で長期複利成長を狙う、感情を排した自動売買Botを構築する。Paper Trading環境で**最低6ヶ月・累積120取引以上**の検証を経た上で、信頼区間ベースの合格基準を満たした場合のみLive Tradingへ手動承認で移行する。

**期待値前提（v1.0.1で訂正済み）：**
- 往復取引コスト前提：0.10%（スリッページ + スプレッド + SEC/TAF fee）
- 損切り幅：0.5%、利確幅：0.8%、ペイオフ比 1.6:1
- **損益分岐勝率：46.15%** — 計算: `(損切+コスト) / (利確+損切) = (0.005+0.001) / (0.008+0.005) = 0.4615`
- **年6〜10%リターン達成に必要な勝率：47〜49%** — 月15-50取引、リスク0.7%/取引、複利前提
- **promotion_gate の勝率基準は57%（安全マージン）** — 損益分岐+10pt、運の良いサンプルに本番昇格を許さないため意図的に厳しく
- これは**v0.9のパラメータ（損切0.4%/利確0.5%）ではコスト込み期待値ゼロ近傍だった**問題への対応
- **コストが0.15%超に膨らんだ場合の損益分岐勝率は50.0%**（実測コストが想定を超えた場合の警戒ライン）

## Architecture

シングルプロセス・ステートフルなBotを launchd で常駐させ、Alpaca Paper/Live API と通信する。MacBook（開発）→ Mac Mini（本番）への移管は launchd plist と `.env` のコピー＋DB移行手順（後述）で完結する。複雑な分散構成は採用せず、シンプルさを安定性の源泉とする。状態は SQLite（WALモード）に永続化し、プロセス再起動時に Alpaca 側との状態突合を行う。

戦略・リスク管理・学習ロジックは純粋関数として `broker/` 層から分離し、テストの容易性と将来のブローカー差し替え可能性を担保する。本番（Live）への切り替えは `.env` の `ALPACA_BASE_URL` と確認フラグの変更で完結するが、**fractional shares / PDT rule など Live 固有の制約**は別途コードで吸収する。

「人間が手動で介入できる余地」を意図的に最小化する。手動売買UIは作らない。緊急停止コマンドのみ提供する。これは「大負けしない」を裏切る最大の敵が人間の感情であるという設計思想に基づく。

**外部死活監視**：launchdが死亡した場合に bot 自体は警告できない（停止しているため）ので、healthchecks.io（無料）への heartbeat ping を各 runner の正常終了時に送信し、外部から死活を監視する。

## Components

新規ディレクトリ `equity_trading/` を `fx_trading/` と並列で作成する。

```
equity_trading/
├── .env.example
├── requirements.txt                  # ライブラリ・バージョン制約を本仕様書 Configuration セクションに記載
├── pyproject.toml
├── README_LIVE.md                    # 本番移行手順・緊急停止手順・税務/PDT/wash sale リスクを冒頭に
├── src/
│   ├── config.py                     # 環境変数・設定値の一元管理＋起動時バリデーション
│   ├── broker/
│   │   └── alpaca_client.py          # Alpaca SDKラッパー（薄い層）。Paper/Live差分を吸収
│   ├── data/
│   │   ├── price_fetcher.py          # 価格取得・キャッシュ（Free planのIEX feed制約を考慮）
│   │   ├── feature_builder.py        # RSI/BB/VWAP/出来高比/200d MA計算（純粋関数）
│   │   └── market_calendar.py        # 米国祝日・前場短縮日判定（pandas-market-calendars）
│   ├── strategy/
│   │   ├── intraday_reversion.py     # マルチシグナル戦略本体（純粋関数）
│   │   └── signal_weights.py         # シグナル重みのDB読み書きと正規化
│   ├── learning/
│   │   ├── parameter_optimizer.py    # 月次WFA最適化（縮小版グリッド）
│   │   ├── signal_tracker.py         # シグナル別の勝率・期待値を記録（寄与度按分）
│   │   ├── weight_updater.py         # 直近成績でシグナル重みを日次更新（信頼区間考慮）
│   │   └── promotion_gate.py         # Paper→Live移行可否を信頼区間ベースで判定
│   ├── risk/
│   │   ├── circuit_breaker.py        # 5階層のサーキットブレーカー（v1.0で月次/週次追加）
│   │   ├── position_sizer.py         # 1取引リスク0.7%でサイズ計算
│   │   └── flash_crash_guard.py      # 急変時のセーフティ二段ストップ
│   ├── execution/
│   │   ├── intraday_loop.py          # 5分間隔のシグナル評価＆発注（オープン後30分待機）
│   │   ├── exit_manager.py           # 利確・損切り・大引け強制決済
│   │   └── partial_fill_handler.py   # 部分約定の追跡と完了処理
│   ├── state/
│   │   ├── store.py                  # SQLite永続化（WALモード、busy_timeout、PIDファイル排他）
│   │   ├── migrations.py             # スキーマ管理（手書き、alembic不使用）
│   │   ├── backup.py                 # 日次dump、30日保持
│   │   └── reconciler.py             # Alpaca/SQLite状態突合、entry_price復元
│   ├── monitor/
│   │   ├── logger.py                 # 構造化ログ（UTC統一）
│   │   ├── dashboard.py              # 日次レポート生成
│   │   ├── notifier.py               # Slack/メール通知（任意）
│   │   └── heartbeat.py              # healthchecks.io ping送信
│   └── runner/
│       ├── intraday_runner.py        # 5分ごと：シグナル評価・発注
│       ├── eod_runner.py             # 大引け後：日次集計・重み更新
│       ├── monthly_runner.py         # 月初：WFA最適化・移行ゲート評価
│       └── emergency_stop.py         # 緊急停止
├── scripts/
│   ├── bootstrap_data.py             # 初期データ取得（過去1年分）
│   ├── backtest.py                   # バックテストCLI（コスト込み）
│   ├── paper_summary.py              # Paper運用累積レポート
│   ├── parameter_history.py          # パラメータ変更履歴
│   ├── promotion_check.py            # 本番移行可否チェック
│   ├── migrate_db_to_macmini.py      # MacBook→Mac Mini DB移行
│   ├── export_for_tax.py             # 確定申告用CSV出力
│   └── emergency_stop_cli.py         # 緊急停止CLI
├── deploy/
│   ├── com.user.equity-bot-intraday.plist   # 米国市場時間中5分間隔
│   ├── com.user.equity-bot-eod.plist        # 大引け30分後日次
│   ├── com.user.equity-bot-monthly.plist    # 月初日本時間7:00
│   └── README_DEPLOY.md                     # plist インストール手順
├── tests/
│   ├── test_intraday_reversion.py
│   ├── test_circuit_breaker.py
│   ├── test_parameter_optimizer.py
│   ├── test_signal_tracker.py
│   ├── test_weight_updater.py
│   ├── test_promotion_gate.py
│   ├── test_position_sizer.py
│   ├── test_market_calendar.py
│   ├── test_partial_fill_handler.py
│   ├── test_reconciler.py
│   └── test_integration_flow.py
└── data/
    ├── prices/                       # 価格キャッシュ（gitignore）
    ├── trades.sqlite                 # 取引・パラメータ履歴（gitignore）
    └── backups/                      # 日次dump（gitignore）
```

### モジュールの責任分担

| モジュール | 責任 | 依存 | テスト方針 |
|---|---|---|---|
| `config.py` | 環境変数読込・型変換・**起動時バリデーション**（risk_per_trade > 0.05でエラー等） | なし | 値テスト |
| `broker/alpaca_client.py` | Alpaca APIの薄いラッパー、Paper/Live差分吸収 | alpaca-py | モック化 |
| `data/price_fetcher.py` | 価格取得・キャッシュ、IEX feed前提 | alpaca-py | 既知期間テスト |
| `data/feature_builder.py` | 指標計算（純粋関数） | pandas | 既知データで決定論的 |
| `data/market_calendar.py` | 米国祝日・前場短縮日判定 | pandas-market-calendars | 既知日テスト |
| `strategy/intraday_reversion.py` | シグナル評価・統合スコア（純粋関数） | pandas | 既知データで決定論的 |
| `learning/*.py` | 学習ロジック（信頼区間考慮） | scipy.stats | 単体・統合テスト |
| `risk/*.py` | リスク管理（純粋関数） | なし | パラメータテスト |
| `execution/*.py` | 注文発注、部分約定処理 | broker | モック化 |
| `state/store.py` | SQLite永続化（WALモード） | sqlite3 | 一時DB |
| `state/reconciler.py` | Alpaca/SQLite突合、entry_price復元 | broker, store | 統合テスト |
| `monitor/heartbeat.py` | healthchecks.io ping | requests | モック化 |
| `runner/*.py` | スケジューラ・統合 | 全部 | 統合テスト |

設計原則：
- `strategy/` `risk/` `learning/` は純粋関数。副作用なし、テスト容易。
- ブローカーAPIを叩くのは `broker/` のみ。他層からは隠蔽。
- `runner/` だけが各層を統合する責任を持つ。
- **タイムスタンプは全てUTC**。表示時のみ ET/JST に変換。

### 主要モジュールの公開API（実装計画フェーズで詳細化）

```python
# strategy/intraday_reversion.py
@dataclass(frozen=True)
class SignalResult:
    signal_name: str
    score: float          # 0.0〜1.0
    raw_value: float      # デバッグ用の生値（RSI実数値等）

@dataclass(frozen=True)
class EntryDecision:
    should_enter: bool
    combined_score: float
    contributing_signals: tuple[SignalResult, ...]
    reason: str           # "trend_filter_blocked" | "score_below_threshold" | "entry_signal"

def evaluate_entry(
    prices: pd.DataFrame,    # 5分足、直近N本必要
    daily: pd.DataFrame,     # 日足、200日MA計算用
    weights: dict[str, float],
    params: StrategyParams,
) -> EntryDecision: ...

# risk/circuit_breaker.py
@dataclass(frozen=True)
class CircuitBreakerState:
    is_halted: bool
    halted_at: datetime | None
    reason: str | None
    resume_after: datetime | None

def evaluate(state: TradingState, config: RiskConfig) -> CircuitBreakerState: ...
```

詳細なAPIシグネチャは writing-plans フェーズで決定する。

## Strategy Logic

### 入力
- SPY/QQQ の 1分足・5分足・日足（直近1年分は常時キャッシュ）
- 現在保有ポジション・口座残高
- 現在のシグナル重み（DB から取得、合計1.0）
- 現在のパラメータ（DB から取得、月次最適化で更新）

### Alpaca Free plan の制約と対応

Alpaca Market Data API の Free plan は **IEXフィードのみ**で、SIPフィード（米国全市場統合）は別途 $99/月 が必要。

**影響：**
- 出来高シグナルの精度が低下（IEX出来高はSIP全体の数%程度）
- リアルタイム気配のスプレッドが広めに見える
- 直近15分のSIPデータはブロックされる

**対応：**
- 開発・Paper期間：**Free planで運用**、出来高シグナルの重みを下げる（初期重み 0.15 → 0.10）
- Live移行時：成績次第で SIP feed への課金を検討（Configuration の `DATA_PLAN` で切替）
- requirements.txt にデータプラン依存を明記

### エントリー判定（5分間隔、ただしオープン後30分は待機）

**0. 市場オープン直後の待機（v1.0で追加）**
- 米国市場オープン（9:30 ET）後 **30分は新規エントリー停止**
- オープン直後は流動性とボラがバグる時間帯、リバージョン戦略は最も危険
- 既ポジのエグジット判定は通常通り継続

**1. トレンドフィルター（必須）**
- SPY 日足終値 > 200日移動平均 → 取引可能
- SPY 日足終値 < 200日移動平均 → その日は買いを完全停止（現金待機）
- 暴落相場で逆張りして殺されるリスクを構造的に除去する

**2. シグナル評価（各シグナルが0〜1のスコアを出す）**

| シグナル | スコア計算式 | 初期重み |
|---|---|---|
| RSI過売り | 5分足RSI(14)が30以下 → score = (30 - RSI) / 30 | 0.30 |
| ボリンジャー下抜け | BB(20本, 2σ)下限を下抜け → score = 下抜け幅 / σ_20 | 0.25 |
| VWAP乖離 | 当日VWAPからの下方乖離率 / σ_60min | 0.25 |
| 出来高急増 | 直近20本平均の1.5倍以上 → score = min(出来高比 / 2, 1) | 0.10 |
| 短期勢い反転 | 直近3本の終値線形回帰の傾きが負→正に反転 | 0.10 |

詳細：
- VWAP起点：米東部時間 9:30（プレマーケットは含めない）
- σ_20 = BB計算用の20本ローリング標準偏差
- σ_60min = 60分ローリングのVWAP乖離率の標準偏差
- 短期勢い反転：3本の終値で `np.polyfit(degree=1)` の傾きを計算、前回 < 0 かつ今回 > 0 で発火

**統合スコア = Σ(各シグナルのスコア × 重み)**
- 統合スコア ≥ 0.6 ならエントリー（保守側）
- エントリー後は **5分間のクールダウン**（同方向への即再エントリー禁止）

**3. ポジションサイズ**
- 1取引のリスク = 口座残高の **0.7%**
- 損切り幅から逆算してドル数量を決定
- 最大でも口座残高の **50%** まで
- **fractional shares**：Paperは可、Liveは銘柄により制限あり → `broker/alpaca_client.py` で吸収

### エグジット判定（既ポジション保有時、毎分）

| 発動条件 | アクション | 優先順位 |
|---|---|---|
| 1日累計損失 ≤ -2% | 全ポジション即時決済＆当日全停止 | 0（最最優先） |
| 連続3敗 | 既ポジは通常エグジット、当日新規停止 | 0 |
| エントリー価格 -0.5% 到達 | 即時損切り（指値ストップ＋セーフティ成行） | 1 |
| エントリー価格 +0.8% 到達 | 利確（指値、約定見込み高い時は成行） | 2 |
| 大引け15分前 | 強制決済（オーバーナイト持ち越し禁止） | 3 |
| `flash_crash_guard.py` が発動 | エントリー停止＆既ポジ即時決済（条件は flash_crash_guard.py に一元定義） | 1 |

**ペイオフ比は損切り0.5%・利確0.8% で 1.6:1。コスト0.10%込みの損益分岐勝率は 46.15%。** 年6-10%リターンを得るには勝率47-49%で十分だが、Paper運用での運要素を排除するため promotion_gate では勝率57%を要求する（安全マージン+10pt）。

### フラッシュクラッシュガード（v1.0で追加、v1.0.1で master 化）

`risk/flash_crash_guard.py` が**全ATR判定の唯一の master**。エグジット表・サーキットブレーカー階層1の関連項目はすべてここを参照する：

- **発動条件**：ATR(14, 5min) が直近20本平均の3倍を超えた場合
- **アクション**：即時全ポジション決済＆当日エントリー停止
- **セーフティストップ**：指値ストップが滑った場合に備え、エントリー時に -0.7%（損切りラインの1.4倍）にバックストップ成行注文を別途配置
- 2010年5月、2015年8月のSPYフラッシュクラッシュ事例を念頭に設計

**運用ルール：30日間で5回超発動した場合**
- 直接的な「停止」はしない（誤発動リスクを認識しているため）
- 月次レポートに警告フラグを立て、`monthly_runner` で人間に通知
- 人間が原因調査の上、ATR閾値の見直しまたはトレンドフィルターの強化を判断

## Learning System (Level 1.5)

### A. シグナル重みの動的更新（日次）

`eod_runner` が大引け30分後に実行：
1. 当日のすべての取引について、エントリー判断に寄与したシグナルを記録
   - 寄与度按分：`(signal.score × signal.weight) / combined_score` で各シグナルにP&Lを按分
2. 過去90日分のデータから各シグナルの期待値を計算
   - 期待値 = 勝率 × 平均利益 - 負率 × 平均損失
   - **取引数 ≥ 30件のシグナルのみ更新対象**
3. 期待値を 0〜1 に正規化して新しい重みを生成
4. 指数移動平均で滑らかに更新：`new = 0.9 × old + 0.1 × normalized`（v0.9の0.8/0.2から保守側に）
5. 合計が1.0になるよう再正規化

**安全装置（v1.0で強化）：**
- **日次変動 ≤ ±2%**（v0.9の月次±20%は実効性が低かった）
- **任意のシグナル重みは [0.05, 0.50] の範囲内**（極端な集中・除外を防ぐ）
- 取引数30件未満のシグナルは重み変更しない（統計的有意性）
- 全重み合計は常に1.0

**初期半年の挙動（v1.0.1で説明明確化）：**
- 重みが初期半年動かない理由は **学習率（0.9/0.1）ではなく、30件閾値**にある
- 5シグナル × 月15-50取引 = 月間で各シグナル3-10件しかカウントされない
- 30件閾値クリアは累積ベース、つまり最初の3-6ヶ月は重みが「動かないように設計されている」
- これは「Paper初期はノイズが多い→重みを動かさない」という意図的な保守姿勢
- 学習率 0.9/0.1 自体は半減期約6.6日と十分高速、30件閾値クリア後は数日で実勢に追従する

### B. パラメータ最適化（月次）

`monthly_runner` が毎月1日 日本時間 7:00 に実行：
1. 過去6ヶ月の価格データ＋取引履歴を取得
2. 以下のパラメータをグリッドサーチ（**v1.0で縮小**：3パラメータ×各3-4値）：
   - RSI閾値: [28, 30, 32]
   - 損切り幅: [0.4%, 0.5%, 0.6%]
   - 利確幅: [0.7%, 0.8%, 1.0%, 1.2%]
   - 統合スコア閾値: [0.55, 0.60, 0.65]
   - 合計 3×3×4×3 = **108通り**（v0.9の540通りから縮小）
3. 各組み合わせをバックテスト（コスト 0.10% 込み）
   - 評価指標 = **Calmar比（CAGR / MaxDD）** 単独で評価（v0.9の合成指標は重複情報が多かった）
4. ベスト10%を Walk-Forward Analysis で検証
   - **6ヶ月を 4:2 に分割**（v0.9の5:1から変更、test期間2ヶ月確保）
   - 4ヶ月で最適化、2ヶ月で検証
   - 各分割で Calmar > 1.0 を要求
5. 全分割で安定上位の組み合わせを採用
6. 新パラメータを DB に保存（旧値は履歴として残す）
7. **計算予算**：MacBook Air M1 で 30-60分以内（numpy ベクトル化必須）

### C. Paper→Live 昇格ゲート（v1.0で統計的厳格化）

`promotion_gate` が以下の全条件を AND で判定：
- **Paper運用が累積6ヶ月以上**（v0.9の3ヶ月から延長）
- **累積取引回数 ≥ 120件**（v0.9の60件から倍増）
- 勝率 ≥ 57%（v0.9の55%から強化）
- プロフィットファクター ≥ 1.4（v0.9の1.3から強化）
- **Rolling 90日 MaxDD の悪い側95%分位 が -15% より浅い** — 計算: 各営業日について「直近90日間のエクイティカーブから算出した最大ドローダウン率」を時系列化し、その時系列の **95パーセンタイル（=より悪い側上位5%の閾値）** が -15% を上回ること（例：-12% なら合格、-17% なら不合格）。Paper運用6ヶ月で有効サンプルは約120営業日、95%分位の信頼性は限定的だが「最悪期でも -15% 内に収まったか」を見る安全弁として機能
- シャープレシオ ≥ 1.0（90日換算）
- **直近2ヶ月で月次パラメータが大きく変動していない**（変動許容：各パラメータ±10%以内）
- システムエラー比率 < 5%
- ログにフラッシュクラッシュガード誤発動が含まれていない

**全条件クリア時のみ「本番移行可能」と判定。自動では切り替えない。** 必ず人間が `promotion_check.py` を実行 → レポート確認 → `.env` を手動切り替え。

## Data Flow

### 米国市場時間と日本時間の対応（DST対応）

**v1.0方針：DBは全てUTC統一、表示時のみ変換**

```python
# market_calendar.py で常に正しいクローズ時刻を取得
import pandas_market_calendars as mcal
nyse = mcal.get_calendar("NYSE")
schedule = nyse.schedule(start_date="2026-05-01", end_date="2026-05-31")
# schedule.market_close は UTC で正しい時刻（DST含む、前場短縮日含む）
```

**DST境界例：**
- 冬時間（11月〜3月）：米東部 9:30〜16:00 = 日本 23:30〜翌6:00 = UTC 14:30〜21:00
- 夏時間（3月〜11月）：米東部 9:30〜16:00 = 日本 22:30〜翌5:00 = UTC 13:30〜20:00
- 前場短縮日（年8日程度）：米東部 9:30〜13:00 = JST/UTC は通常時間 - 3時間

### Runner スケジュール

**`intraday_runner`：5分間隔（米国市場時間中のみ）**

```
[起動]
  ↓ 1. heartbeat 送信（healthchecks.io）
  ↓ 2. PIDファイル取得（既に動いていれば即終了）
  ↓ 3. SQLite WALモード接続、busy_timeout=5000ms
  ↓ 4. 市場オープン状態確認（market_calendar.py で当日のクローズ時刻取得）
  ↓    - クローズ中なら即終了
  ↓    - オープン後30分以内なら新規エントリー停止フラグON
  ↓ 5. サーキットブレーカー状態確認（停止中は即終了）
  ↓ 6. Alpaca/SQLite 状態突合（reconciler）
  ↓ 7. 現保有ポジション確認
  ↓ 8. ポジションあり？
       YES → エグジット判定
       NO  → エントリー判定（オープン後30分なら不可）
  ↓ 9. ログ・状態保存
[終了 → heartbeat 完了通知]
```

1回の実行は10〜30秒程度（API呼び出し3〜5回）。

**`eod_runner`：1日1回（米国大引け30分後、UTC指定）**
```
当日取引履歴集計 → シグナル寄与度記録 → 重み再計算（信頼区間考慮）
→ 翌日用重みを保存 → 日次レポート生成
→ サーキットブレーカー日次リセット
→ DB日次バックアップ（30日保持）
→ heartbeat 送信
```

**`monthly_runner`：月初1回（毎月1日 日本時間 7:00 = UTC 22:00 前日）**
```
過去6ヶ月データ取得 → グリッドサーチ（108通り）→ WFA 4:2検証
→ 新パラメータ保存 → promotion_gate判定（信頼区間ベース）
→ 月次レポート生成
→ heartbeat 送信
```

### launchd plist サンプル

**`deploy/com.user.equity-bot-intraday.plist`**：
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.equity-bot-intraday</string>

    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/python3</string>
        <string>/Users/USERNAME/equity_trading/src/runner/intraday_runner.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/Users/USERNAME/equity_trading</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin</string>
        <key>PYTHONUNBUFFERED</key>
        <string>1</string>
    </dict>

    <!-- 5分間隔だが、JST 22:00〜07:00 のみ起動（夏時間のオープン1時間前〜クローズ2時間後カバー） -->
    <!-- 市場時間外は intraday_runner 内で即終了する -->
    <key>StartCalendarInterval</key>
    <array>
        <!-- 22時台 0,5,10,...,55分 -->
        <dict><key>Hour</key><integer>22</integer><key>Minute</key><integer>0</integer></dict>
        <dict><key>Hour</key><integer>22</integer><key>Minute</key><integer>5</integer></dict>
        <!-- ...省略、全60エントリ × 9時間 = 約108エントリ。実装時にスクリプトで生成 ... -->
    </array>

    <key>StandardOutPath</key>
    <string>/Users/USERNAME/equity_trading/data/logs/intraday-stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/USERNAME/equity_trading/data/logs/intraday-stderr.log</string>

    <key>ThrottleInterval</key>
    <integer>10</integer>

    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
```

**plist インストール手順は `deploy/README_DEPLOY.md` に記載：**
```bash
# シンボリックリンクで管理
ln -s ~/equity_trading/deploy/com.user.equity-bot-intraday.plist \
      ~/Library/LaunchAgents/com.user.equity-bot-intraday.plist
launchctl load ~/Library/LaunchAgents/com.user.equity-bot-intraday.plist

# アンインストール
launchctl unload ~/Library/LaunchAgents/com.user.equity-bot-intraday.plist
rm ~/Library/LaunchAgents/com.user.equity-bot-intraday.plist
```

### SQLite スキーマ（主要テーブル）

```sql
-- WALモード設定（接続時に必ず実行）
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;
PRAGMA synchronous = NORMAL;

-- 設定値・パラメータ（学習で更新）
CREATE TABLE parameters (
  key TEXT PRIMARY KEY,
  value_json TEXT NOT NULL,
  updated_at_utc TIMESTAMP NOT NULL,    -- 全てUTC
  source TEXT NOT NULL                  -- 'manual' | 'monthly_optimizer' | 'initial'
);

CREATE TABLE parameter_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  key TEXT NOT NULL,
  old_value TEXT,
  new_value TEXT,
  changed_at_utc TIMESTAMP NOT NULL
);

-- シグナル重み（日次更新）
CREATE TABLE signal_weights (
  signal_name TEXT PRIMARY KEY,
  weight REAL NOT NULL,
  updated_at_utc TIMESTAMP NOT NULL
);

-- 取引履歴
CREATE TABLE trades (
  id TEXT PRIMARY KEY,                  -- alpaca order id (UUID)
  symbol TEXT NOT NULL,
  side TEXT NOT NULL,
  quantity REAL,
  entry_price REAL,
  exit_price REAL,
  entry_time_utc TIMESTAMP,
  exit_time_utc TIMESTAMP,
  pnl REAL,
  signals_used_json TEXT,               -- どのシグナルで入ったか（寄与度按分用）
  exit_reason TEXT,                     -- 'take_profit' | 'stop_loss' | 'eod' | 'circuit_breaker' | 'flash_crash'
  partial_fills_json TEXT,              -- 部分約定の履歴
  is_dividend BOOLEAN DEFAULT FALSE     -- 配当はP&L集計から分離
);
CREATE INDEX idx_trades_entry_time ON trades(entry_time_utc);

-- 日次サマリー
CREATE TABLE daily_summary (
  date_et TEXT PRIMARY KEY,             -- 米東部日付
  trade_count INTEGER,
  win_count INTEGER,
  total_pnl REAL,
  rolling_90d_dd_pct REAL,              -- 信頼区間判定用
  circuit_breaker_triggered BOOLEAN
);

-- サーキットブレーカー状態
CREATE TABLE circuit_breaker_state (
  id INTEGER PRIMARY KEY,               -- 常に1
  is_halted BOOLEAN,
  halted_at_utc TIMESTAMP,
  reason TEXT,
  resume_after_utc TIMESTAMP
);

-- ハートビート（外部監視と整合確認用）
CREATE TABLE heartbeats (
  runner TEXT NOT NULL,                 -- 'intraday' | 'eod' | 'monthly'
  last_heartbeat_utc TIMESTAMP NOT NULL,
  PRIMARY KEY (runner)
);

-- 配当・分配金（P&Lから分離）
CREATE TABLE dividends (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT,
  amount_usd REAL,
  ex_date_et TEXT,
  pay_date_et TEXT
);
```

## Error Handling

### エラー分類と対応

| カテゴリ | 例 | 対応 | 通知 |
|---|---|---|---|
| API一時エラー | タイムアウト、502/503 | 指数バックオフでリトライ最大3回 | エラーログ |
| APIレート制限 | 429（Free planは200req/min） | 60秒待機後リトライ | 警告ログ |
| API恒久エラー | 401/403 | 即時停止 | 緊急通知 |
| 資金不足 | margin insufficient | 当該注文スキップ | 警告通知 |
| 重複注文 | already filled | 状態同期して冪等処理 | ログのみ |
| データ欠損 | feed古い（IEX feed制約） | 取引スキップ | 警告ログ |
| 部分約定 | partial fill | partial_fill_handler が追跡完了処理 | ログのみ |
| 市場異常 | halt、ハイ・ボラ | flash_crash_guard 発動 | 緊急通知 |
| DB障害 | ロック・破損 | リトライ後復旧不能なら全停止 | 緊急通知 |
| Botクラッシュ | OOM、未処理例外 | launchd自動再起動、起動時状態整合チェック | 警告通知 |
| 戦略バグ | 暴走（大量注文） | 注文レート制限で阻止、即停止 | 緊急通知 |
| Heartbeat欠落 | 12時間以上 ping なし | healthchecks.io から外部通知 | 緊急通知 |

### サーキットブレーカー（5階層、v1.0で月次/週次追加）

**階層1：取引単位（即時）**
- 1取引の損失が想定の2倍超 → 緊急成行決済
- 注文10秒以内に約定確認できず → キャンセル
- フラッシュクラッシュ → `flash_crash_guard.py` の判定に従う（条件は当該モジュールに一元定義）

**階層2：日次（翌営業日リセット）**
- 当日累計損失 ≤ -2% → 既ポジ即時決済＆当日全停止
- 連続3敗 → 既ポジ通常エグジット、当日新規停止
- 当日取引数 ≥ 20件 → 過剰取引と判定、当日停止
- API失敗率 > 10%（直近1時間） → 当日停止

**階層3：週次（翌週月曜リセット）**
- 週次累計損失 ≤ -5% → 翌週月曜まで全停止

**階層4：月次（翌月初リセット）**
- 月次累計損失 ≤ -8% → 翌月初まで全停止

**階層5：累計（手動リセットのみ）**
- 累計DD ≥ -20% → 全停止、再開不可
  - リセットは `emergency_stop_cli.py --reset` のみ
  - 1営業日経過 + 手動承認が必須

**システム階層（即時かつ永続）**
- API認証エラー → 即停止、`.env` 確認後手動再開
- DB破損 → 即停止、バックアップから復元
- Alpaca側で口座制限 → 即停止
- フラッシュクラッシュガードの誤発動疑いは `flash_crash_guard.py` の運用ルール参照（自動停止はしない、月次レポート警告で人間判断）

### 状態整合性

`intraday_runner` 起動毎に以下を実行：
1. SQLite「現在保有」と Alpaca「実保有」を突合
   - 不一致 → Alpaca側を信頼してSQLite修正、警告ログ
   - **entry_priceが SQLite に無い場合**：Alpaca orders API から該当注文を検索して entry 価格を復元、それも失敗時は緊急停止＆通知
2. 未約定注文の状態確認、30秒以上 pending はキャンセル
3. サーキットブレーカー状態確認、停止中は即終了
4. 最終正常実行から12時間以上経過なら警告（外部 healthchecks.io が独立通知）

「孤立ポジション」検出：
- Alpacaに保有あり、SQLiteなし → 緊急停止＆通知
- SQLiteに保有あり、Alpacaなし → SQLite側修正＆ログ

### 「人間が壊さない」ガード
1. 手動売買UIを作らない
2. `.env` の主要パラメータを起動時にバリデーション（例：`risk_per_trade > 0.05` ならエラー）
3. Liveでは `CONFIRM_LIVE=true` 明示しないと起動しない
4. 緊急停止後は「1営業日経過 + 手動承認」で再開
5. パラメータ自動更新の最大変動率を制限
6. `.env` ファイルは `chmod 600`（README_LIVE.mdに記載）
7. 累計DD-20%停止後の再開は2人称確認プロンプト（`emergency_stop_cli.py --reset` がパスフレーズを要求）

## Testing Strategy

### Layer 1：ユニットテスト（純粋関数モジュール）
- 戦略ロジック：トレンドフィルター・各シグナル・統合スコア計算
- リスク管理：5階層サーキットブレーカー・ポジションサイザー・flash_crash_guard
- 学習：重み更新の滑らかさ・合計1.0保持・統計的有意性・信頼区間
- カレンダー：祝日・前場短縮日の正確判定
- 目標カバレッジ：純粋関数モジュール 95%以上

### Layer 2：統合テスト（Alpaca モック）
- エントリー → 約定 → 利確 → 状態更新の一連フロー
- サーキットブレーカー全階層の発動シナリオ
- 部分約定の追跡完了
- 孤立ポジション検出
- DB と Alpaca の状態整合（entry_price復元含む）
- フラッシュクラッシュガードの発動と回復

### Layer 3：バックテスト（過去5〜10年、コスト込み）

**データ：** Alpaca から SPY/QQQ の1分足・5分足・日足を取得、2018〜2024年

**取引コストモデル：**
- スリッページ：成行 0.05%（往復0.10%）、指値は0
- スプレッド：1bp（0.01%）
- SEC fee：売却額の 0.00229%
- TAF fee：株数 × $0.000166

**合格基準（v1.0で厳格化）：**
- 年率CAGR > **+6%**（v0.9の50%/7年=年6%同等だが、明示）
- Calmar比 > 1.0（CAGR/MaxDD）
- シャープレシオ > **1.2**（v0.9の0.8から強化）
- 最大ドローダウン > -20%
- 勝率 > **57%**（v0.9の55%から強化）
- プロフィットファクター > **1.4**（v0.9の1.3から強化）
- 連続マイナス月 < 4
- 月次取引回数 15〜50

**WFA で頑健性検証**：
- 過去6年を 1年ずつスライドさせ 6 windows
- 各 window で 4ヶ月最適化 / 2ヶ月検証（4:2分割）
- 全 window で Calmar > 1.0 を要求

**バックテスト罠への対策：**
- 未来データ使用の検出（feature計算で `shift(-N)` 禁止のlinter）
- 約定価格の現実的再現（成行は次足始値、指値は実約定可能性）
- 取引コスト全種類を考慮
- 米国祝日・週末・前場短縮日の正確スキップ

### Layer 4：Paper運用（最低6ヶ月、120取引以上）

**v1.0で延長：** 3ヶ月→6ヶ月、60取引→120取引

**監視指標：**
- 累積損益、バックテストとの乖離
- 取引数、API失敗率、クラッシュ
- フラッシュクラッシュガード発動回数
- パラメータ・重みの変動

**チェックリスト：**
- 200日MA下では取引していない
- オープン後30分は新規エントリー停止
- サーキットブレーカー全階層が想定通り発動した（テスト発動含む）
- オーバーナイト持ち越しが起きていない
- シグナル重みが日次で滑らかに更新されている
- 月次最適化が実行されている
- DB と Alpaca の状態が常に一致
- entry_price 復元ロジックが動く（テストシナリオで確認）
- 緊急停止コマンドが動く
- Mac再起動後に launchd で自動復帰する
- DB日次バックアップが取れている
- healthchecks.io ping が継続している

### Layer 5：本番監視
- 自動レポート：日次・週次・月次
- 自動アラート：想定外挙動、累計DD段階警告、3ヶ月連続マイナス
- 運用ルール：
  - 最初の3ヶ月は資金の20-30%のみ投入
  - 月次レポート必読
  - パラメータ大幅変動は人間が承認
  - 戦略変更は Paper に戻して再検証
  - **PDT rule 監視**：5営業日中4回デイトレで $25k 必須、Live残高がこれを下回る局面では取引数制限
  - **wash sale 監視**：30日以内同銘柄ロスは税務上注意（年末に集計レポート）

## Configuration

### 主要パラメータ（初期値、月次最適化で更新）
- 通貨：USD（Alpaca米国口座）
- 対象：SPY, QQQ
- 1取引リスク：0.7%
- 最大ポジションサイズ：口座残高の50%
- **損切り幅：0.5%**（v0.9の0.4%から修正）
- **利確幅：0.8%**（v0.9の0.5%から修正、ペイオフ比1.6:1）
- 統合スコア閾値：0.6
- 日次損失上限：2%
- 連敗停止：3回
- 週次損失上限：5%
- 月次損失上限：8%
- 累計DD停止：20%
- トレンドフィルター：SPY 日足 vs 200日移動平均
- オープン後待機時間：30分
- ATR急増判定：直近20本×3倍

### requirements.txt（v1.0で明示）
```
alpaca-py>=0.40.0,<0.50.0
pandas>=2.0.0,<3.0.0
numpy>=1.24.0,<2.0.0
pandas-market-calendars>=4.4.0
scipy>=1.11.0
python-dotenv>=1.0.0
requests>=2.31.0
pytest>=7.4.0
pytest-cov>=4.1.0
freezegun>=1.4.0           # 時刻モックテスト用
```

### 環境変数（`.env`）
```
ALPACA_API_KEY=
ALPACA_SECRET_KEY=
ALPACA_BASE_URL=https://paper-api.alpaca.markets
DATA_PLAN=free                       # 'free' (IEX) | 'paid' (SIP)

CONFIRM_LIVE=false                   # Live起動時のみ true 明示

INITIAL_CAPITAL_USD=100000
RISK_PER_TRADE=0.007
MAX_POSITION_PCT=0.50
DAILY_LOSS_LIMIT=0.02
WEEKLY_LOSS_LIMIT=0.05
MONTHLY_LOSS_LIMIT=0.08
CUMULATIVE_DD_LIMIT=0.20

# 外部死活監視
HEALTHCHECKS_INTRADAY_URL=
HEALTHCHECKS_EOD_URL=
HEALTHCHECKS_MONTHLY_URL=

# 通知（任意）
SLACK_WEBHOOK_URL=
NOTIFICATION_EMAIL=
```

`.env` 自体は `chmod 600` 必須（README_LIVE.md に記載）。

### MacBook→Mac Mini 移行運用ルール

**v1.0で具体化：DB と Paper運用の連続性をどう扱うか**

オプションA（推奨）：DB含めて移管
1. MacBook で `scripts/migrate_db_to_macmini.py --export ./migration_bundle.tar.gz`
2. Mac Mini に bundle をコピー
3. Mac Mini で `scripts/migrate_db_to_macmini.py --import ./migration_bundle.tar.gz`
4. Paper運用の累積3ヶ月（例）が引き継がれる
5. Mac Mini で launchd 設定 → そのまま継続Paper運用

オプションB：Mac Mini で再Paperから始める（promotion_gate がリセット、6ヶ月延長）
- DBを移行せず、Mac Mini で新規開始
- 開発機の動作確認が済んだら、本番機で再度6ヶ月Paper運用

### Live移行運用ルール

1. promotion_gate の全条件をクリア（`promotion_check.py` で確認）
2. 最終レポートを人間がレビュー
3. `.env` の `ALPACA_BASE_URL` を Live 用に変更
4. `CONFIRM_LIVE=true` を明示
5. **資金は当初20-30%のみ投入**（残りは手元）
6. 1ヶ月正常稼働を確認後、段階的に増資
7. **PDT rule（$25k）を割らないよう資金管理**
8. **W-8BEN フォーム提出**（Alpaca Live開設時、米国源泉徴収軽減）
9. 日本での確定申告：年末に `scripts/export_for_tax.py` で取引履歴CSV出力

## Risks Communicated to User（README_LIVE.md 冒頭に記載）

運用前にユーザーが認識すべきリスク：

1. **数学的期待値の前提**：本仕様は往復コスト0.10%、ペイオフ比1.6:1。損益分岐勝率は46.15%、年6-10%目標に必要な勝率は47-49%。実測コストが0.15%超に膨らむと損益分岐勝率は50.0%に上昇し、運用難易度が上がる
2. **戦略劣化リスク**：5分足リバージョンの優位性はHFT進化で年々減少。3年後に同戦略が機能している保証はない
3. **Alpaca仕様変更リスク**：Free planのレート制限・data feed・APIは変更される
4. **税務リスク（日本）**：
   - 米国ETF Live取引は雑所得 or 申告分離（要税理士相談）
   - 米国源泉徴収（10〜30%、租税条約適用で軽減）
   - W-8BEN フォーム提出必須
5. **wash sale ルール**：30日以内同銘柄売買で損失計上制限（米国税務）
6. **PDT rule**：5営業日4回デイトレで$25k必須。割れば取引制限
7. **Paper vs Live のP&L乖離**：Paperは Last trade price ベースで甘い。Liveでは日次0.05%程度乖離する想定
8. **MacBook sleep**：開発機での3-6ヶ月Paper期間中、sleep入ると launchd 停止。`pmset noidle` 設定 or 充電器接続必須
9. **フラッシュクラッシュ**：成行スリッページが想定の数倍になる事例あり。flash_crash_guardで限定的に対応
10. **戦略変更時の再Paper**：Live運用中に戦略を大きく変えたら、Paperから再検証

## Out of Scope

以下は本設計には含めない：
- 個別株の取引（ETFのみ）
- 暗号資産の取引（将来拡張可能性は残す）
- レバレッジETF（TQQQ等）の取引
  - **重要：レバETFを入れた瞬間 DD-20% 制約は破綻する**
- 米国スマートβETF（SCHD等）・債券ETF（TLT等）の組み入れ
- ショート・空売り
- オプション取引
- ML予測モデル（Random Forest, NN等。Level 3 は採用しない）
- 手動売買UI
- 既存 `fx_trading/` のコード変更
- マルチユーザー対応
- W-8BEN以外の税務書類自動生成
- リアルタイムでのwash sale計算（年末バッチ集計のみ）
