# FX自動売買拡張（Slack通知+複数戦略） Design

## Goal

既存のFX自動売買システムにSlack通知機能と3つの新規テクニカル戦略（移動平均線クロス、ダウ理論、ストキャスティクス）を追加し、複数戦略の同時評価・選定・通知を自動化する。

## Architecture

既存フレームワークにSlack Webhook通知システムと戦略ファクトリーを統合する。通知はLoggerとCircuitBreakerのイベントをフックして非同期送信。戦略は共通基底クラスを継承し、ファクトリーで動的に生成。Runnerが複数戦略のシグナルを集約して最適なアクションを決定する。

## Components

### 通知システム
- `src/notifications/slack_notifier.py`: Slack Webhookへのメッセージ送信。取引・エラー・サーキットブレーカーイベントを整形して投稿
- `src/notifications/__init__.py`: パッケージ初期化

### 戦略システム
- `src/strategies/factory.py`: 戦略名（文字列）からインスタンスを生成するファクトリー
- `src/strategies/ma_cross.py`: シンプル移動平均線クロス戦略（SMA短期/長期のゴールデン/デッドクロス）
- `src/strategies/dow_theory.py`: ダウ理論ベース戦略（高値更新で買い、安値更新で売い）
- `src/strategies/stochastic.py`: ストキャスティクス戦略（%K/%Dクロス＋オーバーブラウト/ソールド判定）

### 統合
- `src/monitoring/logger.py`（拡張）: ファイルログに加え、設定されていればSlackにも通知
- `src/safety/circuit_breaker.py`（拡張）: 作動時にSlack通知を送信
- `src/runner/polling_runner.py`（拡張）: 複数戦略のシグナルを生成・比較し、最も強いシグナルで注文
- `src/config/settings.py`（拡張）: `SLACK_WEBHOOK_URL` を追加

## Data Flow（通知）

```
[取引/エラー/サーキットブレーカーイベント発生]
    ↓
[Logger / CircuitBreaker が SlackNotifier を呼び出し]
    ↓
[SlackNotifier がメッセージを整形]
    ↓
[Slack Webhook URL へ POST 送信]
```

## Data Flow（戦略）

```
[市場データ取得]
    ↓
[StrategyFactory で複数戦略を生成]
    ↓
[各戦略でシグナル生成] → [シグナル強度を比較・集約]
    ↓
[最も強い/多数派のシグナルで注文判定]
    ↓
[注文実行 + 通知送信]
```

## Error Handling

| 失敗モード | 対応 |
|-----------|------|
| Slack Webhook無効/URL間違い | 通知送信失敗をログに記録。取引自体は継続。URLが未設定なら通知をスキップ |
| Slackレート制限 | 429応答を検知。1秒待機後リトライ。それでも失敗なら諦める |
| 戦略ファクトリーに存在しない名前 | `ValueError` を送出。`available_strategies()` で確認可能なリストを提供 |
| 戦略シグナルが全て0（ノーシグナル） | 注文せず、次回の定期実行に委ねる |
| 戦略間でシグナルが衝突（買いと売いが同時） | 優先順位（強度スコア）または「両方スキップ」で解決。設定可能にする |
| 新戦略でゼロ除算/欠損データ | ガード節で回避。異常時はシグナル0（ノーアクション）を返す |

## Testing Strategy

- **通知テスト**: `responses` ライブラリでWebhook POSTをモックし、正しいJSONペイロードが送信されるか検証
- **SlackNotifierテスト**: 各イベントタイプ（取引/エラー/サーキットブレーカー）で適切なメッセージが生成されるか
- **戦略ファクトリーテスト**: 各戦略名から正しいクラスが生成されるか。存在しない名前で例外が出るか
- **MAクロステスト**: 上昇トレンドデータで買いシグナル、下降で売いシグナルが出るか
- **ダウ理論テスト**: 高値更新時に買い、安値更新時に売いシグナルが出るか
- **ストキャスティクステスト**: %Kが%Dを上抜けかつオーバーソールド時に買い、下抜けかつオーバーブラウト時に売い
- **統合テスト**: `polling_runner` で複数戦略のシグナルが正しく集約されるか
- **設定テスト**: `SLACK_WEBHOOK_URL` が未設定でもシステムがクラッシュしないか
