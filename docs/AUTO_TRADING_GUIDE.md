# FX自動取引 段階的移行ガイド

## 現在の状況

- **コード:** 実際の注文送信ロジック実装済み
- **テスト:** 137テストPASS
- **ダッシュボード:** GitHub Pagesで公開中（15分間隔自動更新）
- **安全装置:** opus4.7による強化済み（cost model, exposure manager, circuit breaker, mandatory SL）

---

## Phase 1: ドライラン（即座に開始可能）

```bash
cd fx_trading
PYTHONPATH=src python3 src/main.py --portfolio --dry-run
```

**確認ポイント:**
- シグナル生成が正しく動作するか
- ポジションサイズが適切か
- ログにエラーが出ていないか

---

## Phase 2: OANDA Globalデモ口座（次のステップ）

### 必要な準備
1. **OANDA Global口座開設**
   - https://www.oanda.com/ にアクセス
   - デモ口座を開設
   - APIトークンを取得

2. **環境変数設定**
   ```bash
   cp fx_trading/.env.example fx_trading/.env
   # .envファイルを編集
   OANDA_API_TOKEN=your-demo-token
   OANDA_ACCOUNT_ID=your-demo-account
   OANDA_ENVIRONMENT=practice
   ```

3. **接続テスト**
   ```bash
   cd fx_trading
   PYTHONPATH=src python3 -c "
   from src.broker.oanda_client import OandaClient
   from src.config.settings import Settings
   settings = Settings()
   client = OandaClient(
       api_token=settings.api_token,
       account_id=settings.account_id,
       environment=settings.environment,
   )
   price = client.get_current_price('USD_JPY')
   print(f'Connection OK: {price}')
   "
   ```

---

## Phase 3: デモ取引（1〜2週間）

```bash
cd fx_trading
PYTHONPATH=src python3 src/main.py --portfolio --live
```

**注意:** `--live` はデモ環境でも「実際の注文」を送信します

**監視項目:**
- 日次損失が `MAX_DAILY_LOSS_PCT`（5%）を超えていないか
- 連続損失が `MAX_CONSECUTIVE_LOSSES`（5回）を超えていないか
- ドローダウンが `MAX_DRAWDOWN_PCT`（15%）を超えていないか
- ダッシュボードでP&L推移を確認

---

## Phase 4: 本番移行（判断基準を満たした後）

### 移行条件
- デモ取引で1〜2週間、安定した動作
- プロフィットファクターが1.2以上
- 最大ドローダウンが15%以内

### 本番設定変更
```bash
# .envファイルを編集
OANDA_ENVIRONMENT=live
RISK_PER_TRADE=0.005  # 本番ではより保守的に
```

### 初回実行
```bash
cd fx_trading
PYTHONPATH=src python3 src/main.py --portfolio --live
```

---

## 安全装置チェックリスト

| 機能 | 設定値 | 確認方法 |
|------|--------|----------|
| サーキットブレーカー（日次損失） | 5% | `MAX_DAILY_LOSS_PCT` |
| サーキットブレーカー（ドローダウン） | 15% | `MAX_DRAWDOWN_PCT` |
| サーキットブレーカー（連続損失） | 5回 | `MAX_CONSECUTIVE_LOSSES` |
| 必須ストップロス | 有効 | opus4.7実装済み |
| エクスポージャーリミット | 通貨ペアあたり2ポジション | `MAX_POSITIONS_PER_CURRENCY` |
| トレーディング時間 | 7:00〜6:00 | `TRADING_START_HOUR`/`TRADING_END_HOUR` |
| コストモデル | スプレッド/スリッページ/スワップ | opus4.7実装済み |

---

## ダッシュボード監視

- **URL:** https://hidenaka.github.io/fx-trading/dashboard/
- **更新間隔:** 15分
- **確認項目:**
  - Total Capitalの推移
  - Daily P&Lの変動
  - Equity Curveの形状
  - Open Positionsの状態

---

## 緊急時の対応

### 取引を即座に停止したい場合
1. プロセスを停止（Ctrl+C）
2. OANDAダッシュボードから手動でポジションをクローズ

### サーキットブレーカーが発動した場合
- Slack通知（`SLACK_WEBHOOK_URL`設定時）
- ログファイル（`fx_trading/logs/trades.log`）で確認
- 自動的に取引停止（翌日リセット）

---

## 次のアクション

1. **即座にできる:** ドライラン実行 `--dry-run`
2. **次のステップ:** OANDA Globalデモ口座開設
3. **確認後:** デモ取引開始 `--live`（practice環境）
4. **判断後:** 本番移行 `.env`で`live`設定

## opus4.7のfollow-up tasks（将来対応）

- [ ] ML StandardScalerパイプラインの本番適用
- [ ] トランザクション照合（transactions/sinceid）の定期実行
- [ ] WFAサマリーCLIの拡張
- [ ] ダッシュボードへのリスクメトリクス追加（Sharpe, Sortino, MaxDD）
