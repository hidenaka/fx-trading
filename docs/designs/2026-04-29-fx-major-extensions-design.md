# FX自動売買 大規模拡張 Design

## Goal

既存のFX自動売買システムに、複数通貨ペア対応、Webダッシュボード可視化、機械学習予測モデルの3つの拡張を同時に追加する。

## Architecture

1. **複数通貨ペア対応**: `DataLoader`と`OandaClient`を拡張し、USD/JPY, EUR/USD, GBP/JPYを同時に監視・バックテスト。`PollingRunner`が各ペアで独立にシグナルを生成。
2. **Webダッシュボード**: `dashboard/`ディレクトリにHTML/JS/Chart.jsを配置。Pythonの簡易HTTPサーバーでJSONデータを提供し、ブラウザでエクイティカーブ、戦略ランキング、ポートフォリオ状況を可視化。
3. **機械学習予測モデル**: `src/ml/`にscikit-learnベースのモデルを配置。過去の価格データとテクニカル指標から翌時間足の方向を予測し、戦略のシグナルと組み合わせる。

## Components

### 複数通貨ペア対応
- `src/config/settings.py`（拡張）: `CURRENCY_PAIRS`設定を追加（カンマ区切り複数ペア対応）
- `src/data/loader.py`（拡張）: 複数ペアのデータを一括取得・管理
- `src/broker/oanda_client.py`（拡張）: 複数ペアの価格を一括取得
- `src/runner/polling_runner.py`（拡張）: 複数ペアをループして独立にシグナル生成・注文

### Webダッシュボード
- `dashboard/index.html`: メインダッシュボード画面
- `dashboard/app.js`: データ取得・Chart.js描画・リアルタイム更新
- `dashboard/styles.css`: Tailwind CDN + カスタムスタイル
- `src/api/server.py`: 簡易HTTPサーバー。バックテスト結果・取引履歴・ポートフォリオ状況をJSONで提供
- `src/api/data_exporter.py`: バックテスト/ライブ取引の結果をJSONファイルにエクスポート

### 機械学習予測モデル
- `src/ml/__init__.py`
- `src/ml/feature_engineer.py`: テクニカル指標をML特徴量に変換
- `src/ml/predictor.py`: scikit-learnのロジスティック回帰/ランダムフォレストで方向予測
- `src/ml/trainer.py`: モデルの学習・保存・評価
- `src/ml/strategy.py`: ML予測をStrategyインターフェースでラップ

## Data Flow

```
[複数通貨ペアデータ取得]
    ↓
[各ペアでテクニカル戦略 + ML予測モデルでシグナル生成]
    ↓
[シグナル集約 → 注文判定]
    ↓
[取引実行 → ログ出力 → JSONエクスポート]
    ↓
[ダッシュボードがJSONを読み込み → Chart.jsで可視化]
```

## Error Handling

| 失敗モード | 対応 |
|-----------|------|
| 特定通貨ペアのAPI取得失敗 | そのペアのみスキップ。他のペアは継続 |
| MLモデル未学習 | フォールバックしてテクニカル戦略のみ使用 |
| ダッシュボードJSON読み込み失敗 | 空の状態を表示。「データ未取得」を表示 |
| 複数ペアで同時にシグナル | 各ペア独立に処理。資金は各ペアに均等配分 |

## Testing Strategy

- **マルチペアテスト**: 複数ペアのデータ取得と独立シグナル生成を検証
- **ダッシュボードテスト**: JSONエクスポートが正しい形式で出力されるか
- **MLテスト**: 特徴量エンジニアリング、モデル学習・予測の動作を検証
- **統合テスト**: バックテスト → JSONエクスポート → ダッシュボード表示の一連フロー

## Tech Stack

- **Backend**: Python 3.11+, pandas, numpy, pytest, requests, scikit-learn
- **Frontend**: HTML5, Vanilla JS, Tailwind CSS CDN, Chart.js CDN
- **ML**: scikit-learn (LogisticRegression, RandomForestClassifier)
- **Server**: Python `http.server` + カスタムハンドラー
