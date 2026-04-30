# FX自動売買 実データ検証・ダッシュボード強化・ML精度向上 Design

## Goal

OANDA APIから複数通貨ペアの実データを取得してバックテストを検証し、ダッシュボードを5秒間隔ポーリングでリアルタイム更新し、MLモデルの特徴量とハイパーパラメーターを強化する。

## Architecture

実データ取得専用モジュールを追加してOANDAから過去データをフェッチ・CSV保存。ダッシュボードのJavaScriptを5秒間隔ポーリングに拡張し、差分検出で自動更新。MLの特徴量エンジニアにMACDヒストグラム・ボリンジャーバンド・ATR等を追加し、GridSearchCVでハイパーパラメーターを最適化する。

## Components

- `src/data/oanda_fetcher.py`: OANDA APIから過去ローソク足データを取得し、CSVに保存
- `dashboard/app.js`（拡張）: 5秒間隔でJSONポーリング、差分検出でDOM更新
- `src/ml/feature_engineer.py`（拡張）: MACDヒストグラム、ボリンジャーバンド（±1σ, ±2σ）、ATR、価格パターン等を特徴量に追加
- `src/ml/trainer.py`（拡張）: scikit-learnのGridSearchCVでLogisticRegression/RandomForestのハイパーパラメーターを最適化
- `src/main.py`（拡張）: 全通貨ペア・全戦略の一括バックテストCLIコマンド

## Data Flow

```
[OANDA API] → [oanda_fetcher.py] → [CSV保存] → [バックテスト実行]
                                    ↓
                            [結果をJSONエクスポート]
                                    ↓
                            [ダッシュボードが5秒ごとにポーリング]
                                    ↓
                            [差分があればDOM自動更新]
```

```
[価格データ] → [FeatureEngineer拡張] → [豊富な特徴量]
                                    ↓
                            [GridSearchCVで最適パラメーター探索]
                                    ↓
                            [MLStrategyが高精度予測]
```

## Error Handling

| 失敗モード | 対応 |
|-----------|------|
| OANDA APIからデータ取得失敗 | リトライ3回、それでも失敗ならスキップして次のペアへ |
| レート制限（429） | 指数バックオフで待機 |
| ダッシュボードJSON読み込み失敗 | 前回データを維持、次回ポーリングで再試行 |
| ML特徴量でNaN/Inf発生 | ガード節で0に置換または行を削除 |
| GridSearchCVで学習失敗 | デフォルトパラメーターにフォールバック |
| 複数ペアでメモリ不足 | 逐次処理（1ペアずつバックテスト） |

## Testing Strategy

- **データ取得テスト**: OANDA APIのモック応答でCSV出力を検証
- **ダッシュボードテスト**: JSONファイルを手動作成し、ブラウザでDOM更新を目視確認
- **ML特徴量テスト**: 各新特徴量が正しく計算されるか（MACDヒストグラム、ボリンジャーバンド等）
- **MLハイパーパラメーターテスト**: GridSearchCVがエラーなく完了し、最適パラメーターが返るか
- **統合テスト**: 全ペア・全戦略の一括バックテストが正常終了するか
