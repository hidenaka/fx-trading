# 米国ETFデイトレードBot（マルチシグナル × 短期リバージョン × トレンドフィルター）Design v2.0

**改訂履歴：**
- v0.9-draft 〜 v1.1 (2026-05-02): 段階的改訂を経たが、v1.1のレビューで「設定値の整合性破綻・セクター集中の形骸化・取引頻度の根拠不在」という根本問題が指摘された
- **v2.0 (2026-05-02)**: v1.x を全面書き直し。実装の最初に行う実測キャリブレーション（Phase 0）を必須化、ETF別ATR比例パラメータ、加重テック露出ベースの真のセクター中立、強シグナル例外、N依存の期待値表を導入。「楽観的な机上の空論」を排除する設計

## Goal

米国主要ETF **5本（SPY/QQQ/IWM/DIA/XLK）** を対象に、複数のテクニカルシグナルを組み合わせた短期リバージョン戦略をローカルMacで自動運用し、**スリッページ・スプレッドを正直に織り込んだ上で年6〜10%リターン・最大ドローダウン-20%以内**で長期複利成長を狙う、感情を排した自動売買Botを構築する。

実装の最初に **Phase 0: Empirical Calibration** を必須実施し、過去2年分の実データで「シグナル発火頻度・各ETFのボラ特性・現実的な勝率」を実測してから、Paper運用の合格基準とパラメータを確定する。Paper Trading環境で**最低6ヶ月・累積200取引以上**（Phase 0結果次第で調整）の検証を経た上で、信頼区間ベースの合格基準を満たした場合のみLive Tradingへ手動承認で移行する。

### 期待値の数学（N依存の透明な表）

ペイオフ比 1.6:1（利確0.8倍 / 損切り0.5倍 ※ETFごとのATR比例で実値変動）、往復コスト 0.10% 想定。

**損益分岐勝率 = 46.15%** （計算: `(損切+コスト)/(利確+損切) = (0.5+0.1)/(0.8+0.5) = 0.4615`）

**年率期待リターン（口座対比、単利近似、コスト0.10%込み）：**

| 年取引数 | 勝率48% | 勝率50% | 勝率55% | 勝率60% |
|---|---|---|---|---|
| 200 | +0.4% | +2.0% | +6.0% | +10.0% |
| 600 | +1.3% | +6.0% | +18% | +30% |
| 1200 | +2.6% | +12% | +36% | +60% |
| 2400 | +5.2% | +24% | +72% | +120% |

**含意：**
- 「年6-10%リターン」は **勝率と取引頻度の組み合わせ問題**であり、単一の数値で語れない
- N=200（月17取引、控えめ）なら勝率55%必要
- N=1200（月100取引、5ETFで日5回相当）なら勝率49%で目標達成
- Phase 0 で実測される頻度に応じて、必要勝率が変わる
- **コストが0.15%に膨らむと損益分岐勝率は50.0%に上昇** → 警戒ライン

### 設計上の絶対制約

| 制約 | 値 | 意図 |
|---|---|---|
| 最大ドローダウン許容 | -20% | ユーザーの心理的限界、再開可能ライン |
| 最大1取引リスク | 口座残高の0.5% | 5ETF × 3同時保有の総リスク管理 |
| 最大同時保有 | 3ポジション | 監視可能性とリスク分散のバランス |
| 1銘柄あたり最大ポジション | 口座残高の25% | 3 × 25% = 総エクスポージャ75%上限 |
| 加重テック露出上限 | 40% | 真のセクター中立 |
| オーバーナイト持ち越し | 禁止 | 夜間ギャップリスク完全排除 |
| Paper期間 | 6ヶ月以上、200取引以上 | Phase 0結果次第で調整 |
| Live移行 | 手動承認必須 | 自動移行は許さない |

## Architecture

シングルプロセス・ステートフルなBotを launchd で常駐させ、Alpaca Paper/Live API と通信する。MacBook（開発）→ Mac Mini（本番）への移管は launchd plist と `.env` のコピー＋DB移行手順（後述）で完結する。

戦略・リスク管理・学習ロジックは**純粋関数**として `broker/` 層から分離する。これによりテスト容易性、ブローカー差し替え可能性、デバッグ容易性を担保する。

「人間が手動で介入できる余地」を意図的に最小化する。手動売買UIは作らない。緊急停止コマンドのみ提供する。

**外部死活監視**：healthchecks.io への heartbeat ping を各 runner の正常終了時に送信。Bot 自体が死んだ場合に外部から検知できる。

## Phase 0: Empirical Calibration（実装フェーズ最初の必須作業）

仕様を「机上で決める」のではなく、**実データで決める**ためのキャリブレーション。これは実装計画の最初のマイルストーンとして必ず通過する。

### Phase 0 の手順

1. **データ収集**
   - Alpaca から SPY/QQQ/IWM/DIA/XLK の過去 **2年分** の 1分足・5分足・日足を取得
   - キャッシュは `data/historical/` に保存

2. **ETF別ボラ特性の測定**
   - 各ETFについて 5分足 ATR(14) の中央値と分布を計測
   - 各ETFの平均スプレッド・典型的な約定スリッページを推定
   - 出力：`data/calibration/atr_per_symbol.json`
   - これが ATR比例パラメータの基準値になる

3. **シグナル発火頻度の実測**
   - 統合スコア閾値を 0.40〜0.75 で 0.05刻み変動させ、各設定での：
     - 1日あたり何回シグナルが発火するか
     - 翌5分・15分・60分・大引けまでの実現リターン分布
     - 仮の損切0.5×ATR・利確0.8×ATR で運用した場合の勝率
   - 出力：`data/calibration/signal_frequency.csv`、`signal_frequency.png`

4. **現実的な目標頻度・勝率の決定**
   - Phase 0 結果から、**「目標頻度を満たし、かつ勝率55%以上の見込み」となる統合スコア閾値**を決定
   - 例：閾値0.6 で日3〜5回・勝率53%、閾値0.55 で日5〜8回・勝率50% → 後者を選択
   - 結果次第で「5-10/日 は無理、3-5/日 が現実」と判明したら**目標を下方修正**

5. **Paper運用合格基準の確定**
   - Phase 0 で見えた実測勝率の **-3pt** を Paper 合格基準に設定
   - 取引数の最低基準は実測頻度から逆算
   - 例：実測 月60取引・勝率53% → Paper合格基準 月50取引・勝率50%

### Phase 0 の成果物（writing-plans に渡す）

- `phase0/calibration_report.md`：実測値・推奨パラメータ・推奨合格基準
- `phase0/recommended_config.json`：本番運用で使うパラメータ初期値
- これらが揃わない限り Paper運用に進まない

### Phase 0 で「目標達成不可能」が判明した場合

実測の結果、現実的な閾値で 5ETF合計 1日 3-5回しか出ない、勝率も実測50%が限界、ということが判明する可能性がある。**この場合の対応：**

- 取引頻度目標を下方修正（5-10/日 → 3-5/日）
- 年間期待リターンも再計算（N=600-1200で勝率50% → 年率6-12%）
- Promotion基準も連動修正
- ユーザーに必ず通知し、進めるか停止するか判断を仰ぐ

**「楽観的な仕様で実装→Paper運用→失敗」のサイクルを Phase 0 で防ぐ。**

## Strategy Logic

### 対象ETF（5本）

| ティッカー | 名称 | 主要構成 | 流動性 | テック比率 | セクター分類 |
|---|---|---|---|---|---|
| **SPY** | SPDR S&P 500 ETF | 大型株500社 | 最高（出来高8000万株/日） | 約30% | broad |
| **QQQ** | Invesco QQQ Trust | NASDAQ100 | 最高（出来高5000万株/日） | 約50% | tech-heavy |
| **IWM** | iShares Russell 2000 | 小型株2000社 | 高（出来高3000万株/日） | 約5% | small-cap |
| **DIA** | SPDR Dow Jones 30 | NYダウ30社 | 中（出来高300万株/日） | 約20% | broad-defensive |
| **XLK** | Technology Select Sector | テクノロジーセクター | 中-高（出来高800万株/日） | 約95% | tech-pure |

### 入力
- 各ETFの 1分足・5分足・日足（Phase 0で2年分、運用中は直近1年分常時キャッシュ）
- 現在保有ポジション・口座残高
- 現在のシグナル重み（DB から取得、合計1.0）
- 現在のパラメータ（DB から取得、月次最適化で更新、ETF別）
- 各ETFのキャリブレーション値（Phase 0 由来、ATR等）

### エントリー判定（5分間隔、ただしオープン後30分は待機）

#### 0. 市場オープン直後の待機
- 米国市場オープン（9:30 ET）後 **30分は新規エントリー停止**
- オープン直後は流動性とボラがバグる時間帯
- 既ポジのエグジット判定は通常通り継続

#### 1. トレンドフィルター（ETF別判定 + マクロ防御）

**ETF別トレンドフィルター：**
- 各ETFについて：当該ETFの日足終値 > 200日移動平均 → そのETFは取引可能
- 各ETFについて：当該ETFの日足終値 < 200日移動平均 → そのETFは当日買い停止

**マクロ防御フィルター：**
- SPY 日足終値 < 200日移動平均（市場全体が弱気）→ QQQ・XLK・DIA・**IWM全て**取引不可
- ※ v1.1 で曖昧だった IWM の扱いを v2.0 で明確化：マクロ防御発動時は IWM も停止する（小型株は弱気相場で先行下落しがち）

#### 2. シグナル評価（5シグナル、各ETFごとに独立）

| シグナル | スコア計算式（ETF別ATR/σを使用） | 初期重み |
|---|---|---|
| RSI過売り | 5分足RSI(14)が30以下 → score = (30 - RSI) / 30 | 0.30 |
| ボリンジャー下抜け | BB(20本, 2σ_etf)下限を下抜け → score = 下抜け幅 / σ_etf | 0.25 |
| VWAP乖離 | 当日VWAPからの下方乖離率 / σ_60min,etf | 0.25 |
| 出来高急増 | 直近20本平均の1.5倍以上 → score = min(出来高比 / 2, 1) | 0.10 |
| 短期勢い反転 | 直近3本の終値線形回帰の傾きが負→正に反転 | 0.10 |

**詳細：**
- VWAP起点：米東部時間 9:30（プレマーケットは含めない）
- σ_etf = ETF別の20本ローリング標準偏差
- σ_60min,etf = ETF別の60分ローリングVWAP乖離率の標準偏差

**統合スコア = Σ(各シグナルのスコア × 重み)** （ETFごとに独立計算）

エントリー候補条件：
- 統合スコア ≥ **PHASE_0_THRESHOLD**（Phase 0 で確定、想定 0.55〜0.65）
- 同一ETFのエントリー後 5分間はクールダウン

#### 3. ETF別パラメータ（v2.0で導入）

固定パラメータの代わりに、各ETFの ATR(14, 5min) 中央値（Phase 0 実測値）に比例：

```
損切り幅_etf = ATR_5min_etf × 1.5
利確幅_etf  = ATR_5min_etf × 2.4
```

**Phase 0 を待たずに想定する初期値（参考）：**

| ETF | ATR_5min（推定） | 損切り | 利確 | ペイオフ比 |
|---|---|---|---|---|
| SPY | 0.10% | 0.15% | 0.24% | 1.6:1 |
| QQQ | 0.13% | 0.20% | 0.32% | 1.6:1 |
| IWM | 0.18% | 0.27% | 0.43% | 1.6:1 |
| DIA | 0.09% | 0.14% | 0.22% | 1.6:1 |
| XLK | 0.12% | 0.18% | 0.29% | 1.6:1 |

**なぜATR比例にするか：** SPY と IWM では同じ「0.5%損切り」でもストップ刈り頻度が3倍違う。ETF別にスケーリングすることで、5ETFを横並びで運用しても各ETFのストップ刈り頻度が揃う。

#### 4. ポジション管理ルール

エントリー候補が出ても、以下の **全チェック** を通過しないとエントリーしない：

| ルール | 内容 | 目的 |
|---|---|---|
| **同時保有上限** | 最大3ポジション同時保有 | 過度なリスク集中防止 |
| **同銘柄重複禁止** | 既保有のETFには再エントリーしない | サイズ拡大による無自覚なリスク増加防止 |
| **加重テック露出上限** | 既保有+新規の3ポジ加重平均テック比率 ≤ 40% | 真のセクター中立 |
| **総エクスポージャ上限** | 全ポジション合計で口座残高の75%まで | 3 × 25% = 75% |
| **新規エントリー優先順位** | スコア降順、同点時は流動性順 SPY > QQQ > XLK > IWM > DIA | 流動性実測ベースに修正（v1.1 の DIA > XLK は誤り） |

**加重テック露出の計算例：**
```
保有候補：SPY (tech 30%) + QQQ (50%) + IWM (5%) → 平均 28.3% （OK、40%以下）
保有候補：SPY (30%) + QQQ (50%) + XLK (95%) → 平均 58.3% （NG、却下）
保有候補：QQQ (50%) + XLK (95%) → 平均 72.5%（NG）
```

つまりv1.1の「{QQQ, XLK} 最大1」は、**この加重ルールから自然に派生する**特殊ケース。明示的に40%上限を計算することでより安全に。

#### 5. 強シグナル例外ルール（v2.0で追加）

3ポジ既保有時に新シグナルが出ても通常は無視するが、**例外条件：**

- 新シグナルの統合スコアが、既保有3ポジの最下位スコア + 0.15 を超える
- かつ、新シグナルがエントリーするETFのトレンドフィルターを通過している
- かつ、加重テック露出が40%以下に収まる組み合わせ

**この場合：** 既保有最下位ポジションを成行で即時決済し、新シグナルでエントリー

例：
- 既保有：SPY (entry score 0.62), QQQ (0.68), DIA (0.71)
- 新シグナル：IWM score 0.85
- 0.85 - 0.62 = 0.23（≥ 0.15）→ 例外発動、SPY決済→IWMエントリー

これにより「3ポジ満了の取りこぼし」を回避。

#### 6. ポジションサイズ
- 1取引のリスク = 口座残高の **0.5%**
- 損切り幅（ETF別）から逆算してドル数量を決定
- **1銘柄あたり最大25%** まで
- fractional shares：Paperは可、Liveは銘柄により制限あり → `broker/alpaca_client.py` で吸収

### エグジット判定（既ポジション保有時、毎分）

| 発動条件 | アクション | 優先順位 |
|---|---|---|
| 1日累計損失 ≤ -2% | 全ポジション即時決済＆当日全停止 | 0（最最優先） |
| 連続3敗 | 既ポジは通常エグジット、当日新規停止 | 0 |
| エントリー価格 -損切り幅_etf 到達 | 即時損切り（指値ストップ＋セーフティ成行） | 1 |
| エントリー価格 +利確幅_etf 到達 | 利確（指値、約定見込み高い時は成行） | 2 |
| 大引け15分前 | 強制決済（オーバーナイト持ち越し禁止） | 3 |
| `flash_crash_guard` 発動 | エントリー停止＆既ポジ即時決済 | 1 |
| 強シグナル例外発動 | 既ポジ最下位を成行決済 | 2 |

### フラッシュクラッシュガード

`risk/flash_crash_guard.py` が **全ATR判定の唯一の master**：
- **発動条件**：あるETFの 5分足 ATR(14) が直近20本平均の3倍を超えた
- **アクション**：そのETFの即時全ポジション決済＆当日エントリー停止
- **セーフティストップ**：エントリー時に -損切り幅×1.4 にバックストップ成行注文を別途配置（指値ストップが滑った場合に備える）
- **誤発動疑い**：30日で5回超なら月次レポート警告（自動停止はしない、人間判断）

## Components

新規ディレクトリ `equity_trading/` を `fx_trading/` と並列で作成する。

```
equity_trading/
├── .env.example                      # ※v2.0 整合性チェック済み
├── requirements.txt
├── pyproject.toml
├── README_LIVE.md                    # 本番移行手順・緊急停止・税務リスク・Phase 0結果サマリ
├── src/
│   ├── config.py                     # 環境変数・設定値・ETF別パラメータの一元管理＋起動時バリデーション
│   ├── broker/
│   │   └── alpaca_client.py          # Alpaca SDKラッパー、Paper/Live差分吸収
│   ├── data/
│   │   ├── price_fetcher.py          # 5ETF並列の価格取得・キャッシュ
│   │   ├── feature_builder.py        # RSI/BB/VWAP/出来高比/200d MA計算（ETF別）
│   │   └── market_calendar.py        # 米国祝日・前場短縮日判定（pandas-market-calendars）
│   ├── strategy/
│   │   ├── intraday_reversion.py     # マルチシグナル戦略本体（純粋関数、ETF別評価）
│   │   ├── signal_weights.py         # シグナル重みのDB読み書きと正規化
│   │   └── universe.py               # 5ETFのメタデータ・テック比率・流動性順位
│   ├── learning/
│   │   ├── parameter_optimizer.py    # 月次WFA最適化（ETF別 + 共通シグナル重み）
│   │   ├── signal_tracker.py         # シグナル別の勝率・期待値を記録（寄与度按分）
│   │   ├── weight_updater.py         # 直近成績でシグナル重みを日次更新
│   │   └── promotion_gate.py         # Paper→Live移行可否を信頼区間ベースで判定
│   ├── risk/
│   │   ├── circuit_breaker.py        # 5階層のサーキットブレーカー
│   │   ├── position_sizer.py         # ETF別ATRベースのサイズ計算
│   │   ├── sector_exposure.py        # 加重テック露出計算
│   │   ├── flash_crash_guard.py      # ATR3倍判定、セーフティストップ
│   │   └── cost_monitor.py           # 実測コスト追跡、警戒ライン判定
│   ├── execution/
│   │   ├── intraday_loop.py          # 5分間隔のシグナル評価＆発注
│   │   ├── position_manager.py       # 同時保有・セクター中立・優先順位・強シグナル例外
│   │   ├── exit_manager.py           # 利確・損切り・大引け強制決済
│   │   └── partial_fill_handler.py   # 部分約定の追跡と完了処理
│   ├── state/
│   │   ├── store.py                  # SQLite永続化（WAL + busy_timeout + PIDファイル排他）
│   │   ├── migrations.py             # スキーマ管理（手書き）
│   │   ├── backup.py                 # 日次dump、30日保持
│   │   └── reconciler.py             # Alpaca/SQLite状態突合、entry_price復元
│   ├── monitor/
│   │   ├── logger.py                 # 構造化ログ（UTC統一）
│   │   ├── dashboard.py              # 日次レポート生成
│   │   ├── notifier.py               # Slack/メール通知（任意）
│   │   └── heartbeat.py              # healthchecks.io ping送信
│   ├── phase0/                        # ★ NEW：実測キャリブレーション
│   │   ├── data_collector.py         # 過去2年データ取得
│   │   ├── atr_analyzer.py           # ETF別ATR・スプレッド・スリッページ測定
│   │   ├── signal_simulator.py       # 統合スコア閾値別の発火頻度・勝率推定
│   │   └── report_generator.py       # calibration_report.md 出力
│   └── runner/
│       ├── intraday_runner.py        # 5分ごと：シグナル評価・発注
│       ├── eod_runner.py             # 大引け後：日次集計・重み更新
│       ├── monthly_runner.py         # 月初：WFA最適化・移行ゲート評価
│       ├── phase0_runner.py          # Phase 0 一括実行（手動or実装最初の1回）
│       └── emergency_stop.py         # 緊急停止
├── scripts/
│   ├── bootstrap_data.py             # 初期データ取得
│   ├── run_phase0.py                 # Phase 0 キャリブレーション一発実行
│   ├── backtest.py                   # バックテストCLI（コスト込み、ETF別パラメータ）
│   ├── paper_summary.py              # Paper運用累積レポート
│   ├── parameter_history.py          # パラメータ変更履歴
│   ├── promotion_check.py            # 本番移行可否チェック
│   ├── migrate_db_to_macmini.py      # MacBook→Mac Mini DB移行
│   ├── export_for_tax.py             # 確定申告用CSV出力
│   ├── generate_launchd_intervals.py # launchd plist の StartCalendarInterval 生成
│   └── emergency_stop_cli.py         # 緊急停止CLI
├── deploy/
│   ├── com.user.equity-bot-intraday.plist
│   ├── com.user.equity-bot-eod.plist
│   ├── com.user.equity-bot-monthly.plist
│   └── README_DEPLOY.md
├── tests/
│   ├── test_intraday_reversion.py
│   ├── test_circuit_breaker.py
│   ├── test_sector_exposure.py        # 加重テック露出計算テスト
│   ├── test_position_manager.py       # 強シグナル例外含む
│   ├── test_atr_parameters.py         # ETF別ATR比例パラメータ
│   ├── test_parameter_optimizer.py
│   ├── test_signal_tracker.py
│   ├── test_weight_updater.py
│   ├── test_promotion_gate.py
│   ├── test_position_sizer.py
│   ├── test_market_calendar.py
│   ├── test_partial_fill_handler.py
│   ├── test_reconciler.py
│   ├── test_cost_monitor.py
│   ├── test_phase0.py                 # Phase 0 全段階のテスト
│   └── test_integration_flow.py
├── data/
│   ├── prices/                       # 価格キャッシュ（gitignore）
│   ├── historical/                   # Phase 0用2年データ（gitignore）
│   ├── calibration/                  # Phase 0結果（gitignore）
│   ├── trades.sqlite                 # 取引・パラメータ履歴（gitignore）
│   └── backups/                      # 日次dump（gitignore）
└── phase0/                           # Phase 0成果物
    ├── calibration_report.md         # 実測値・推奨パラメータ・推奨基準
    └── recommended_config.json       # 採用された初期値
```

### モジュール責任分担

| モジュール | 責任 | 純粋性 |
|---|---|---|
| `config.py` | 環境変数・ETF別パラメータの一元管理、起動時バリデーション | データ |
| `broker/alpaca_client.py` | Alpaca APIの薄いラッパー | 副作用層 |
| `data/feature_builder.py` | 指標計算（ETF別） | 純粋関数 |
| `data/market_calendar.py` | 米国祝日・前場短縮判定 | 純粋関数 |
| `strategy/intraday_reversion.py` | シグナル評価（ETF別、純粋関数） | 純粋関数 |
| `strategy/universe.py` | 5ETFのメタデータ提供 | データ |
| `risk/sector_exposure.py` | 加重テック露出計算 | 純粋関数 |
| `risk/flash_crash_guard.py` | ATR3倍判定（**全ATR判定のmaster**） | 純粋関数 |
| `risk/cost_monitor.py` | 実測コスト追跡、警戒ライン判定 | 純粋関数 |
| `risk/circuit_breaker.py` | 5階層判定 | 純粋関数 |
| `execution/position_manager.py` | エントリー可否判定（強シグナル例外含む） | ロジック層 |
| `learning/*.py` | 学習ロジック（信頼区間考慮） | 純粋関数 |
| `state/store.py` | SQLite永続化（WALモード） | 副作用層 |
| `state/reconciler.py` | Alpaca/SQLite突合、entry_price復元 | ロジック層 |
| `monitor/heartbeat.py` | healthchecks.io ping | 副作用層 |
| `phase0/*.py` | Phase 0 各段階 | 副作用層（データ収集）+ 純粋関数（解析） |
| `runner/*.py` | スケジューラ・統合 | 統合層 |

設計原則：
- 純粋関数モジュールはAPIを叩かない、副作用なし
- ブローカーAPIを叩くのは `broker/` のみ
- タイムスタンプは全てUTC、表示時のみ ET/JST に変換
- 全ETFパラメータはETF別、共通パラメータはシグナル重みのみ

## Learning System (Level 1.5)

### A. シグナル重みの動的更新（日次）

`eod_runner` が大引け30分後に実行：
1. 当日のすべての取引について、エントリー判断に寄与したシグナルを記録
   - 寄与度按分：`(signal.score × signal.weight) / combined_score`
2. 過去90日分のデータから各シグナルの期待値を計算
   - 期待値 = 勝率 × 平均利益 - 負率 × 平均損失
   - **取引数 ≥ 30件のシグナルのみ更新対象**
3. 期待値を 0〜1 に正規化して新しい重みを生成
4. 指数移動平均で滑らかに更新：`new = 0.9 × old + 0.1 × normalized`
5. 合計が1.0になるよう再正規化

**安全装置：**
- 日次変動 ≤ ±2%
- 任意のシグナル重みは [0.05, 0.50] の範囲内
- 取引数30件未満のシグナルは重み変更しない

**重みは全ETF共通**（シグナル設計が同じため）。ただしETF別の損切/利確幅はシグナル重みとは独立にETF別最適化される。

### B. パラメータ最適化（月次）

`monthly_runner` が毎月1日 日本時間 7:00 に実行：

**ETF別最適化（5ETFをそれぞれ独立に）：**
- 各ETFについて以下のパラメータをグリッドサーチ：
  - ATR乗数（損切り）: [1.2, 1.5, 1.8]
  - ATR乗数（利確）: [2.0, 2.4, 2.8]
- 1ETFあたり 3×3 = 9 通り
- 5ETF × 9 = 45 通り

**共通パラメータ最適化：**
- 統合スコア閾値: [0.55, 0.60, 0.65]
- RSI閾値: [28, 30, 32]
- 共通 3×3 = 9 通り

**合計： 45 + 9 = 54通り**（v1.1 の108通りから半減）

**Walk-Forward Analysis：**
- 過去6ヶ月を 4ヶ月最適化 / 2ヶ月検証で 4:2 分割
- 6 windows（年単位スライド）
- 1 window あたり 54 通り × 5ETFバックテスト = 270 シナリオ
- 計算予算：MacBook Air M1 で**最大 90分以内**を目標（numpy ベクトル化必須）
- 90分超えなら Phase 0 で実測してから writing-plans で再見積もり

**評価指標：**
- Calmar比 (CAGR/MaxDD) を主指標
- 全 windows で Calmar > 1.0 を要求

新パラメータを DB に保存。旧値は履歴として残す。

### C. Paper→Live 昇格ゲート

`promotion_gate` が以下の **全条件をAND** で判定：

- Paper運用が累積6ヶ月以上
- 累積取引回数 ≥ Phase 0 で確定する目標値（想定 200件）
- 全体勝率 ≥ Phase 0 実測勝率 - 3pt（想定 50-55%）
- プロフィットファクター ≥ 1.3
- **Rolling 90日 MaxDD の悪い側95%分位** が -15% より浅い
  - 計算：各営業日について「直近90日エクイティカーブから算出した最大DD率」を時系列化、その時系列の **95パーセンタイル（より悪い側上位5%閾値）** が -15% を上回る
- シャープレシオ ≥ 1.0（90日換算）
- **5ETF個別の勝率も全て信頼区間下限45%以上**（90% CI下限ベース、運の偏り防止）
- 直近2ヶ月で月次パラメータが大きく変動していない（各パラメータ ±10% 以内）
- システムエラー比率 < 5%
- 実測往復コスト < 0.13%（コストが想定通り）
- フラッシュクラッシュガード誤発動が直近30日で5回未満

**全条件クリア時のみ「本番移行可能」と判定。自動では切り替えない。** `promotion_check.py` を手動実行 → レポート確認 → `.env` を手動切り替え。

## Data Flow

### 米国市場時間と日本時間の対応（DST対応）

**方針：DBは全てUTC統一、表示時のみ変換**

```python
import pandas_market_calendars as mcal
nyse = mcal.get_calendar("NYSE")
schedule = nyse.schedule(start_date="2026-05-01", end_date="2026-05-31")
# schedule.market_close は UTC で正しい時刻（DST含む、前場短縮日含む）
```

**境界例：**
- 冬時間：米東部 9:30〜16:00 = JST 23:30〜翌6:00 = UTC 14:30〜21:00
- 夏時間：米東部 9:30〜16:00 = JST 22:30〜翌5:00 = UTC 13:30〜20:00
- 前場短縮日（年8日程度）：米東部 9:30〜13:00 = 通常時間 - 3時間

### Runner スケジュール

#### `intraday_runner`：5分間隔（米国市場時間中のみ、5ETF並列）

```
[起動]
  1. heartbeat 送信（healthchecks.io）
  2. PIDファイル取得（既に動いていれば即終了）
  3. SQLite WALモード接続、busy_timeout=5000ms
  4. 市場オープン状態確認（market_calendar）
     - クローズ中なら即終了
     - オープン後30分以内なら新規エントリー停止フラグON
  5. サーキットブレーカー状態確認（停止中は即終了）
  6. Alpaca/SQLite 状態突合（reconciler）
  7. 現保有ポジション確認
  8. 各ETF（SPY/QQQ/IWM/DIA/XLK）について：
     a. 既保有？ YES → 当該ETFのエグジット判定
     b. 既保有でなく、新規エントリー可能？ → エントリー候補スコア計算
  9. エントリー候補をスコア降順でソート
 10. position_manager.py がエントリー可否判定
     - 既保有数 < 3
     - 同銘柄重複なし
     - 加重テック露出 ≤ 40%（既保有+新規で計算）
     - マクロ防御フィルター
     - クールダウン中でない
 11. 強シグナル例外チェック
     - 3ポジ既保有時、最下位 + 0.15 を超える新シグナルがあれば最下位を成行決済
 12. 通過したものを発注（同サイクル内最大2件まで）
 13. ログ・状態保存
[終了 → heartbeat 完了通知]
```

1回の実行は20〜60秒程度（API呼び出し10〜15回、Free planの200req/min から見て余裕）。

#### `eod_runner`：1日1回（米国大引け30分後）

```
当日取引履歴集計（ETF別と全体）→ シグナル寄与度記録 → 重み再計算
→ 翌日用重みを保存 → 日次レポート生成
→ サーキットブレーカー日次リセット
→ DB日次バックアップ（30日保持）
→ 実測コスト追跡（cost_monitor）
→ heartbeat 送信
```

#### `monthly_runner`：月初1回（毎月1日 日本時間 7:00）

```
過去6ヶ月データ取得 → グリッドサーチ（54通り、ETF別+共通）→ WFA 4:2検証
→ 新パラメータ保存 → promotion_gate判定（信頼区間ベース）
→ 月次レポート生成
→ heartbeat 送信
```

#### `phase0_runner`：実装フェーズ最初の1回

```
データ収集（2年分5ETF）→ ATR分析 → シグナル発火頻度測定
→ 推奨パラメータ・推奨合格基準を生成
→ calibration_report.md と recommended_config.json を出力
→ ユーザーがレポートをレビュー → 採用判断
```

### launchd plist サンプル

`deploy/com.user.equity-bot-intraday.plist`：
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
        <key>PATH</key><string>/usr/local/bin:/usr/bin:/bin</string>
        <key>PYTHONUNBUFFERED</key><string>1</string>
    </dict>
    <!-- StartCalendarInterval は generate_launchd_intervals.py で生成 -->
    <key>StartCalendarInterval</key>
    <array>
        <!-- ここに JST 22:00〜07:00 の 5分間隔 108 エントリが生成される -->
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

`scripts/generate_launchd_intervals.py` が `StartCalendarInterval` の108エントリを生成して plist 内にインジェクトする。

### SQLite スキーマ

```sql
-- 起動時設定
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;
PRAGMA synchronous = NORMAL;

-- 設定値・パラメータ（学習で更新、ETF別 or 共通）
CREATE TABLE parameters (
  scope TEXT NOT NULL,                  -- 'common' | 'SPY' | 'QQQ' | 'IWM' | 'DIA' | 'XLK'
  key TEXT NOT NULL,
  value_json TEXT NOT NULL,
  updated_at_utc TIMESTAMP NOT NULL,
  source TEXT NOT NULL,                 -- 'phase0' | 'manual' | 'monthly_optimizer'
  PRIMARY KEY (scope, key)
);

CREATE TABLE parameter_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  scope TEXT NOT NULL,
  key TEXT NOT NULL,
  old_value TEXT,
  new_value TEXT,
  changed_at_utc TIMESTAMP NOT NULL
);

-- シグナル重み（日次更新、共通）
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
  signals_used_json TEXT,               -- JSON: [{name, score, weight, contribution}, ...]
  exit_reason TEXT,                     -- 'take_profit' | 'stop_loss' | 'eod' | 'circuit_breaker' | 'flash_crash' | 'strong_signal_replacement'
  partial_fills_json TEXT,
  is_dividend BOOLEAN DEFAULT FALSE
);
CREATE INDEX idx_trades_entry_time ON trades(entry_time_utc);
CREATE INDEX idx_trades_symbol ON trades(symbol);

-- 日次サマリー（全体）
CREATE TABLE daily_summary (
  date_et TEXT PRIMARY KEY,
  trade_count INTEGER,
  win_count INTEGER,
  total_pnl REAL,
  rolling_90d_dd_pct REAL,
  circuit_breaker_triggered BOOLEAN
);

-- ETF別の日次パフォーマンス
CREATE TABLE daily_summary_per_symbol (
  date_et TEXT NOT NULL,
  symbol TEXT NOT NULL,
  trade_count INTEGER,
  win_count INTEGER,
  pnl REAL,
  PRIMARY KEY (date_et, symbol)
);

-- サーキットブレーカー状態
CREATE TABLE circuit_breaker_state (
  id INTEGER PRIMARY KEY,               -- 常に1
  is_halted BOOLEAN,
  halted_at_utc TIMESTAMP,
  reason TEXT,
  resume_after_utc TIMESTAMP
);

-- ハートビート
CREATE TABLE heartbeats (
  runner TEXT NOT NULL,
  last_heartbeat_utc TIMESTAMP NOT NULL,
  PRIMARY KEY (runner)
);

-- 配当・分配金
CREATE TABLE dividends (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT,
  amount_usd REAL,
  ex_date_et TEXT,
  pay_date_et TEXT
);

-- コスト実測（v2.0で追加）
CREATE TABLE cost_observations (
  trade_id TEXT NOT NULL,
  observed_cost_pct REAL NOT NULL,      -- スリッページ + スプレッド + 手数料
  expected_cost_pct REAL NOT NULL,      -- 想定 0.10%
  PRIMARY KEY (trade_id),
  FOREIGN KEY (trade_id) REFERENCES trades(id)
);
```

## Error Handling

### エラー分類と対応

| カテゴリ | 例 | 対応 | 通知 |
|---|---|---|---|
| API一時エラー | タイムアウト、502/503 | 指数バックオフ最大3回 | エラーログ |
| APIレート制限 | 429（200req/min） | 60秒待機後リトライ | 警告ログ |
| API恒久エラー | 401/403 | 即時停止 | 緊急通知 |
| 資金不足 | margin insufficient | 当該注文スキップ | 警告通知 |
| 重複注文 | already filled | 状態同期して冪等処理 | ログ |
| データ欠損 | feed古い | 取引スキップ | 警告ログ |
| 部分約定 | partial fill | partial_fill_handler が追跡完了処理 | ログ |
| 市場異常 | halt、ハイ・ボラ | flash_crash_guard 発動 | 緊急通知 |
| DB障害 | ロック・破損 | リトライ後復旧不能なら全停止 | 緊急通知 |
| Botクラッシュ | OOM、未処理例外 | launchd自動再起動、起動時状態整合チェック | 警告通知 |
| 戦略バグ | 暴走（大量注文） | 注文レート制限で阻止、即停止 | 緊急通知 |
| Heartbeat欠落 | 12時間以上 ping なし | healthchecks.io から外部通知 | 緊急通知 |
| 実測コスト超過 | 0.13%警告/0.15%停止/0.18%緊急 | cost_monitor が判定 | 警告/緊急 |

### サーキットブレーカー（5階層）

| 階層 | 条件 | アクション | リセット |
|---|---|---|---|
| **1：取引単位** | 1取引損失が想定の2倍超 | 緊急成行決済 | 自動なし |
| **1：取引単位** | フラッシュクラッシュ判定 | flash_crash_guard.py の決定に従う | 自動なし |
| **2：日次** | 当日累計損失 ≤ -2% | 既ポジ即時決済＆当日全停止 | 翌営業日 |
| **2：日次** | 連続3敗 | 既ポジ通常エグジット、当日新規停止 | 翌営業日 |
| **2：日次** | 当日取引数 ≥ 20件 | 過剰取引と判定、当日停止 | 翌営業日 |
| **2：日次** | API失敗率 > 10%（直近1時間） | 当日停止 | 翌営業日 |
| **3：週次** | 週次累計損失 ≤ -5% | 翌週月曜まで全停止 | 翌週月曜 |
| **4：月次** | 月次累計損失 ≤ -8% | 翌月初まで全停止 | 翌月初 |
| **5：累計** | 累計DD ≥ -20% | 全停止、再開不可 | 手動承認のみ |
| システム | API認証エラー | 即停止 | 手動再開 |
| システム | DB破損 | 即停止 | バックアップ復元 |
| システム | 実測コスト > 0.18% | 取引停止、人間判断 | 手動再開 |

### 状態整合性

`intraday_runner` 起動毎：
1. SQLite「現在保有」と Alpaca「実保有」突合、Alpaca側信頼で SQLite修正
2. **entry_price が SQLite に無い場合**：Alpaca orders API から該当注文を検索して entry 価格を復元、失敗時は緊急停止＆通知
3. 未約定注文 30秒以上 pending はキャンセル
4. サーキットブレーカー状態確認、停止中は即終了
5. 12時間以上の長時間停止検知（healthchecks.ioで外部通知）

### 「人間が壊さない」ガード
1. 手動売買UIを作らない
2. `.env` 起動時バリデーション（risk_per_trade > 0.05 でエラー等）
3. Liveでは `CONFIRM_LIVE=true` 明示しないと起動しない
4. 緊急停止後は「1営業日経過 + 手動承認」で再開
5. パラメータ自動更新の最大変動率制限
6. `.env` ファイルは `chmod 600` 必須
7. 累計DD-20%停止後の再開はパスフレーズ確認

## Testing Strategy

### Layer 0: Phase 0 キャリブレーション（実装最初の必須段階）
- 過去2年データで実測：ETF別ATR、シグナル発火頻度、勝率推定、コスト推定
- `phase0/calibration_report.md` を生成し、ユーザー確認後に Paper運用パラメータ確定

### Layer 1: ユニットテスト（純粋関数）
- 戦略ロジック：トレンドフィルター・各シグナル・統合スコア計算（ETF別）
- リスク管理：5階層サーキットブレーカー、ポジションサイザー、加重テック露出計算、flash_crash_guard、cost_monitor
- 学習：重み更新の滑らかさ、合計1.0保持、信頼区間
- カレンダー：祝日・前場短縮日の正確判定
- 強シグナル例外：score差0.15判定の境界
- 目標カバレッジ：純粋関数モジュール 95%以上

### Layer 2: 統合テスト（Alpaca モック）
- エントリー→約定→利確→状態更新の一連フロー（5ETF独立）
- サーキットブレーカー全階層の発動シナリオ
- 部分約定の追跡完了
- 孤立ポジション検出
- DB と Alpaca の状態整合（entry_price復元含む）
- フラッシュクラッシュガード発動と回復
- 強シグナル例外による既ポジ入替
- 加重テック露出による新規エントリー却下

### Layer 3: バックテスト（過去5〜10年、コスト込み、ETF別パラメータ）

データ：5ETF の1分足・5分足・日足を 2018〜2024 で取得。

**取引コストモデル：**
- スリッページ：成行 0.05%（往復0.10%）、指値は0
- スプレッド：1bp（0.01%）
- SEC fee：売却額の 0.00229%
- TAF fee：株数 × $0.000166

**合格基準（Phase 0結果次第で再調整可、初期想定）：**
- 年率CAGR > +6%
- Calmar比 > 1.0
- シャープレシオ > 1.2
- 最大ドローダウン > -20%
- 全体勝率 > 50%
- プロフィットファクター > 1.3
- 連続マイナス月 < 4
- 月次取引回数 = Phase 0 想定範囲（例：60〜200）
- 各ETF個別の勝率 > 信頼区間下限45%

**WFA：** 6 windows（年単位スライド）、各 4:2分割、全 windows で Calmar > 1.0 要求

**バックテスト罠への対策：** 未来データ使用検出、約定価格の現実的再現、取引コスト全種類考慮、休場日正確スキップ

### Layer 4: Paper運用（最低6ヶ月、Phase 0確定の最低取引数以上）

**監視指標：** 累積損益、バックテストとの乖離、取引数、API失敗率、クラッシュ、フラッシュクラッシュガード発動回数、実測コスト

**チェックリスト：**
- 200日MA下では取引していない（マクロ防御含む）
- オープン後30分は新規エントリー停止
- サーキットブレーカー全階層が想定通り発動した
- オーバーナイト持ち越しが起きていない
- シグナル重みが日次で滑らかに更新されている
- 月次最適化が実行されている
- DB と Alpaca の状態が常に一致
- entry_price 復元ロジックが動く
- 緊急停止コマンドが動く
- Mac再起動後に launchd で自動復帰する
- DB日次バックアップが取れている
- healthchecks.io ping が継続している
- 強シグナル例外が想定通り発動した（Paper期間中に最低1回）
- 加重テック露出ガードが想定通り発動した（同上）
- 実測コストが想定（0.10%）の±50%以内に収まっている

### Layer 5: 本番監視
- 自動レポート：日次・週次・月次
- 自動アラート：想定外挙動、累計DD段階警告、3ヶ月連続マイナス、コスト警戒
- 運用ルール：
  - 最初の3ヶ月は資金の20-30%のみ投入
  - 月次レポート必読
  - パラメータ大幅変動は人間が承認
  - 戦略変更は Paper に戻して再検証
  - PDT rule 監視（$25k）
  - wash sale 監視（年末集計）

## Configuration

### 主要パラメータ初期値

**v2.0 重要：以下は Phase 0 完了前の暫定値。Phase 0 で実測してから confirmed config に置き換える。**

#### 共通パラメータ
- 通貨：USD
- 対象ETF：SPY, QQQ, IWM, DIA, XLK（5本）
- 1取引リスク：**0.5%**
- 最大ポジションサイズ：口座残高の **25%/銘柄**
- 同時保有上限：**3ポジション**
- 総エクスポージャ上限：**75%**
- 加重テック露出上限：**40%**
- 統合スコア閾値（暫定）：**0.6**
- 強シグナル例外閾値：**0.15**
- 日次損失上限：**2%**
- 連敗停止：**3回**
- 週次損失上限：**5%**
- 月次損失上限：**8%**
- 累計DD停止：**20%**
- オープン後待機：**30分**
- ATR急増判定：直近20本×3倍
- 流動性順位：SPY > QQQ > XLK > IWM > DIA（v1.1の誤りを訂正）
- コスト警戒：0.13%、停止：0.18%

#### ETF別パラメータ（Phase 0で実測値に置き換え、初期想定値）

| ETF | ATR_5min | 損切り（×1.5） | 利確（×2.4） |
|---|---|---|---|
| SPY | 0.10% | 0.15% | 0.24% |
| QQQ | 0.13% | 0.20% | 0.32% |
| IWM | 0.18% | 0.27% | 0.43% |
| DIA | 0.09% | 0.14% | 0.22% |
| XLK | 0.12% | 0.18% | 0.29% |

### requirements.txt
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
freezegun>=1.4.0
matplotlib>=3.7.0
```

### .env テンプレート（v2.0で整合性チェック済み）

```
ALPACA_API_KEY=
ALPACA_SECRET_KEY=
ALPACA_BASE_URL=https://paper-api.alpaca.markets
DATA_PLAN=free                       # 'free' (IEX) | 'paid' (SIP)

CONFIRM_LIVE=false                   # Live起動時のみ true 明示

INITIAL_CAPITAL_USD=100000
RISK_PER_TRADE=0.005                 # 0.5%（v2.0で0.7→0.5に変更済み）
MAX_POSITION_PCT=0.25                # 25%（v2.0で0.5→0.25に変更済み）
MAX_CONCURRENT_POSITIONS=3
MAX_TECH_EXPOSURE=0.40
DAILY_LOSS_LIMIT=0.02
WEEKLY_LOSS_LIMIT=0.05
MONTHLY_LOSS_LIMIT=0.08
CUMULATIVE_DD_LIMIT=0.20
COST_WARN_THRESHOLD=0.0013           # 0.13%
COST_HALT_THRESHOLD=0.0018           # 0.18%

# 外部死活監視
HEALTHCHECKS_INTRADAY_URL=
HEALTHCHECKS_EOD_URL=
HEALTHCHECKS_MONTHLY_URL=

# 通知（任意）
SLACK_WEBHOOK_URL=
NOTIFICATION_EMAIL=
```

`.env` 自体は `chmod 600` 必須（README_LIVE.mdに記載）。

### MacBook→Mac Mini 移行運用ルール

**オプションA（推奨）：DB含めて移管**
1. MacBook で `scripts/migrate_db_to_macmini.py --export ./migration_bundle.tar.gz`
2. Mac Mini に bundle をコピー
3. Mac Mini で `scripts/migrate_db_to_macmini.py --import ./migration_bundle.tar.gz`
4. Paper運用の累積期間が引き継がれる
5. Mac Mini で launchd 設定 → 継続Paper運用

**オプションB：Mac Mini で再Paperから始める**（promotion_gate がリセット）

### Live移行運用ルール

1. promotion_gate の全条件をクリア
2. 最終レポートを人間がレビュー
3. `.env` の `ALPACA_BASE_URL` を Live 用に変更
4. `CONFIRM_LIVE=true` を明示
5. **資金は当初20-30%のみ投入**
6. 1ヶ月正常稼働を確認後、段階的に増資
7. PDT rule（$25k）を割らないよう資金管理
8. W-8BEN フォーム提出（Alpaca Live開設時）
9. 年末に `scripts/export_for_tax.py` で取引履歴CSV出力

## Risks Communicated to User（README_LIVE.md 冒頭に記載）

1. **数学的期待値の前提**：往復コスト0.10%、ペイオフ比1.6:1。損益分岐勝率46.15%。年6-10%目標は取引数Nに依存（N=1200で勝率49%以上、N=600で勝率55%以上）。実測コストが0.15%超に膨らむと損益分岐50.0%、目標達成困難
2. **Phase 0 で目標下方修正の可能性**：実測の結果、想定した取引頻度・勝率が出ない場合がある。その時は目標を実測ベースに下方修正する
3. **戦略劣化リスク**：5分足リバージョンの優位性はHFT進化で年々減少。3年後に同戦略が機能している保証はない
4. **Alpaca仕様変更リスク**：Free planのレート制限・data feed・APIは変更される
5. **税務リスク（日本）**：米国ETF Live取引は雑所得 or 申告分離（要税理士相談）、米国源泉徴収（10〜30%）、W-8BEN必須
6. **wash sale ルール**：30日以内同銘柄売買で損失計上制限
7. **PDT rule**：5営業日4回デイトレで$25k必須
8. **Paper vs Live のP&L乖離**：Paperは Last trade price ベースで甘い、Live日次0.05%程度乖離想定
9. **MacBook sleep**：開発機での Paper期間中、sleep入ると launchd 停止、`pmset noidle` 設定 or 充電器接続必須
10. **フラッシュクラッシュ**：成行スリッページが想定の数倍になる事例あり
11. **戦略変更時の再Paper**：Live運用中に戦略を大きく変えたら、Paperから再検証

## Out of Scope

- 個別株の取引（ETFのみ）
- 対象5ETF以外の株式ETF（VTI, VOO等は将来拡張余地）
- 暗号資産の取引
- レバレッジETF（TQQQ等）—**重要：DD-20%制約破綻**
- 米国スマートβETF（SCHD等）・債券ETF（TLT等）
- セクターETF（XLK以外のXLF, XLE等）の追加
- ショート・空売り
- オプション取引
- ML予測モデル（Random Forest, NN等。Level 3 は採用しない）
- 手動売買UI
- 既存 `fx_trading/` のコード変更
- マルチユーザー対応
- W-8BEN以外の税務書類自動生成
- リアルタイムwash sale計算（年末バッチのみ）
- ペアトレード・ロング/ショート同時保有

## Writing-Plans Queue（実装計画フェーズで詳細化する項目）

以下は本仕様書ではあえて方向性のみ記述し、`writing-plans` フェーズで具体実装を決定する：

1. **モジュール公開API（dataclass、関数シグネチャ）の網羅的詳細化**
2. **部分約定処理の3ケース定義**：(a) entry時の部分約定後 entry_price は加重平均、(b) 部分約定中に逆シグナル発生時の挙動、(c) exit時の部分約定追跡
3. **entry_price 復元の Alpaca orders API 詳細**：参照フィールド、複数orderマッチング、エッジケース
4. **scripts/bootstrap_data.py の取得範囲・フォーマット・キャッシュ構造**
5. **DBバックアップ方式**：`.dump` vs `VACUUM INTO`、発火時刻、保持期間
6. **signals_used_json の JSON スキーマ定義**
7. **scripts/generate_launchd_intervals.py の StartCalendarInterval 生成ロジック**
8. **月次グリッドサーチのベクトル化方針**：pandas vs numpy、メモリ vs ディスク、想定実時間
9. **promotion_gate の各信頼区間計算の具体実装**：90% CI下限、95%分位の計算方法
10. **強シグナル例外の境界ケース処理**：同時に複数の強シグナル発生時の優先処理
11. **Phase 0 シグナルシミュレータの実装方針**：閾値スイープのベクトル化、メモリ使用量上限
