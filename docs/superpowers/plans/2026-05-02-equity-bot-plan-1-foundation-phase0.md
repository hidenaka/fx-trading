# Plan 1: Equity Bot Foundation + Phase 0 Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 米国ETFデイトレードBotの基盤プロジェクトを立ち上げ、過去2年分の実データから ETF別ATR・シグナル発火頻度・推定勝率を実測する Phase 0 キャリブレーション機構を完成させる。実行すると `phase0/calibration_report.md` が出力される。

**Architecture:** `/Users/hideakimacbookair/自動トレード/equity_trading/` に新規プロジェクトを作成。既存 `fx_trading/` には触れない。Alpaca Paper API のキーを使って過去データを取得し、ローカル SQLite と CSV/JSON にキャッシュ。Phase 0 の解析は純粋関数 + pandas ベクトル化で実行。

**Tech Stack:** Python 3.12、alpaca-py 0.43+、pandas 2.x、pandas-market-calendars 4.4+、scipy、pytest、python-dotenv

**前提：**
- alpaca_test/ ディレクトリで Alpaca Paper Trading のキー（PK..., Secret）が動作確認済み
- そのキーを `equity_trading/.env` にコピーして使う（同じキーで両方動く）
- Python 3.12 と pip3 がシステムにインストール済み

**仕様書参照：** `docs/superpowers/specs/2026-05-02-equity-intraday-reversion-bot-design.md`

---

### Task 1: プロジェクト初期化と .gitignore

**Files:**
- Create: `equity_trading/.gitignore`
- Create: `equity_trading/__init__.py`
- Create: `equity_trading/src/__init__.py`
- Create: `equity_trading/tests/__init__.py`
- Create: `equity_trading/data/.gitkeep`
- Create: `equity_trading/phase0/.gitkeep`

- [ ] **Step 1: ディレクトリ構造を作成**

```bash
cd "/Users/hideakimacbookair/自動トレード"
mkdir -p equity_trading/src/{broker,data,strategy,state,monitor,phase0}
mkdir -p equity_trading/tests
mkdir -p equity_trading/scripts
mkdir -p equity_trading/data/{prices,historical,calibration,backups,logs}
mkdir -p equity_trading/phase0
```

- [ ] **Step 2: 各 Python パッケージに __init__.py を作る**

```bash
cd "/Users/hideakimacbookair/自動トレード/equity_trading"
touch __init__.py
touch src/__init__.py
touch src/broker/__init__.py
touch src/data/__init__.py
touch src/strategy/__init__.py
touch src/state/__init__.py
touch src/monitor/__init__.py
touch src/phase0/__init__.py
touch tests/__init__.py
touch data/.gitkeep
touch phase0/.gitkeep
```

- [ ] **Step 3: .gitignore を作成**

ファイル `equity_trading/.gitignore`：

```
# Environment
.env
.env.local
*.env

# Python
__pycache__/
*.py[cod]
*.so
*.egg-info/
.pytest_cache/
.coverage
htmlcov/
venv/
.venv/

# Data (local only, gitignored)
data/prices/*
data/historical/*
data/calibration/*
data/backups/*
data/logs/*
!data/prices/.gitkeep
!data/historical/.gitkeep
!data/calibration/.gitkeep
!data/backups/.gitkeep
!data/logs/.gitkeep

# SQLite databases
*.sqlite
*.sqlite-shm
*.sqlite-wal
*.db

# OS
.DS_Store

# IDE
.vscode/
.idea/
*.swp
```

- [ ] **Step 4: .gitkeep をデータディレクトリに置く**

```bash
cd "/Users/hideakimacbookair/自動トレード/equity_trading"
touch data/prices/.gitkeep
touch data/historical/.gitkeep
touch data/calibration/.gitkeep
touch data/backups/.gitkeep
touch data/logs/.gitkeep
```

- [ ] **Step 5: コミット**

```bash
cd "/Users/hideakimacbookair/自動トレード"
git add equity_trading/.gitignore equity_trading/__init__.py equity_trading/src equity_trading/tests equity_trading/data equity_trading/phase0
git commit -m "chore: initialize equity_trading project structure"
```

---

### Task 2: requirements.txt と .env.example

**Files:**
- Create: `equity_trading/requirements.txt`
- Create: `equity_trading/.env.example`

- [ ] **Step 1: requirements.txt を作成**

ファイル `equity_trading/requirements.txt`：

```
alpaca-py>=0.40.0,<0.50.0
pandas>=2.0.0,<3.0.0
numpy>=1.24.0,<2.0.0
pandas-market-calendars>=4.4.0
scipy>=1.11.0
python-dotenv>=1.0.0
requests>=2.31.0
matplotlib>=3.7.0
pytest>=7.4.0
pytest-cov>=4.1.0
freezegun>=1.4.0
```

- [ ] **Step 2: .env.example を作成（仕様書 Configuration セクション準拠）**

ファイル `equity_trading/.env.example`：

```
# === Alpaca API ===
ALPACA_API_KEY=PK...your-paper-key-here
ALPACA_SECRET_KEY=your-paper-secret-here
ALPACA_BASE_URL=https://paper-api.alpaca.markets
DATA_PLAN=free

# === Live Trading Confirmation ===
CONFIRM_LIVE=false

# === Capital and Risk ===
INITIAL_CAPITAL_USD=100000
RISK_PER_TRADE=0.005
MAX_POSITION_PCT=0.25
MAX_CONCURRENT_POSITIONS=3
MAX_TECH_EXPOSURE=0.40
DAILY_LOSS_LIMIT=0.02
WEEKLY_LOSS_LIMIT=0.05
MONTHLY_LOSS_LIMIT=0.08
CUMULATIVE_DD_LIMIT=0.20
COST_WARN_THRESHOLD=0.0013
COST_HALT_THRESHOLD=0.0018

# === External Heartbeat (optional, leave blank for now) ===
HEALTHCHECKS_INTRADAY_URL=
HEALTHCHECKS_EOD_URL=
HEALTHCHECKS_MONTHLY_URL=

# === Notifications (optional) ===
SLACK_WEBHOOK_URL=
NOTIFICATION_EMAIL=
```

- [ ] **Step 3: 依存関係をインストール**

```bash
cd "/Users/hideakimacbookair/自動トレード/equity_trading"
pip3 install -r requirements.txt
```

期待出力：`Successfully installed ...` （多くは alpaca_test/ で既にインストール済みのはず）

- [ ] **Step 4: pytest 動作確認**

```bash
cd "/Users/hideakimacbookair/自動トレード/equity_trading"
pytest --version
```

期待出力：`pytest 7.x.x` または `pytest 8.x.x`

- [ ] **Step 5: コミット**

```bash
cd "/Users/hideakimacbookair/自動トレード"
git add equity_trading/requirements.txt equity_trading/.env.example
git commit -m "chore: add requirements.txt and .env.example for equity_trading"
```

---

### Task 3: ロガーモジュール

**Files:**
- Create: `equity_trading/src/monitor/logger.py`
- Test: `equity_trading/tests/test_logger.py`

仕様書の「構造化ログ（UTC統一）」を実装。シンプルな JSON 行形式。

- [ ] **Step 1: 失敗するテストを書く**

ファイル `equity_trading/tests/test_logger.py`：

```python
import json
import logging
from io import StringIO

from equity_trading.src.monitor.logger import setup_logger, JsonFormatter


def test_logger_outputs_json_with_utc_timestamp():
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("test_logger_utc")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    logger.info("hello", extra={"foo": "bar"})

    line = stream.getvalue().strip()
    parsed = json.loads(line)
    assert parsed["level"] == "INFO"
    assert parsed["message"] == "hello"
    assert parsed["foo"] == "bar"
    assert parsed["timestamp"].endswith("Z") or "+00:00" in parsed["timestamp"]


def test_setup_logger_creates_named_logger():
    logger = setup_logger("equity_trading.test")
    assert logger.name == "equity_trading.test"
    assert logger.level == logging.INFO
```

- [ ] **Step 2: テスト実行（失敗確認）**

```bash
cd "/Users/hideakimacbookair/自動トレード"
pytest equity_trading/tests/test_logger.py -v
```

期待：`ImportError` または `ModuleNotFoundError`

- [ ] **Step 3: 実装を書く**

ファイル `equity_trading/src/monitor/logger.py`：

```python
"""構造化ログ（JSON行形式、UTC統一）."""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """LogRecord を JSON 1行で出力."""

    BUILTIN_KEYS = {
        "name", "msg", "args", "levelname", "levelno", "pathname",
        "filename", "module", "exc_info", "exc_text", "stack_info",
        "lineno", "funcName", "created", "msecs", "relativeCreated",
        "thread", "threadName", "processName", "process", "message",
        "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # 追加フィールド（extra=で渡されたもの）を含める
        for key, value in record.__dict__.items():
            if key not in self.BUILTIN_KEYS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """指定名のロガーを構築。stdoutへ JSON で出力."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.propagate = False
    return logger
```

- [ ] **Step 4: テスト実行（成功確認）**

```bash
cd "/Users/hideakimacbookair/自動トレード"
pytest equity_trading/tests/test_logger.py -v
```

期待：`2 passed`

- [ ] **Step 5: コミット**

```bash
cd "/Users/hideakimacbookair/自動トレード"
git add equity_trading/src/monitor/logger.py equity_trading/tests/test_logger.py
git commit -m "feat(monitor): add JSON-formatted UTC structured logger"
```

---

### Task 4: ETF Universe 定義

**Files:**
- Create: `equity_trading/src/strategy/universe.py`
- Test: `equity_trading/tests/test_universe.py`

仕様書 Strategy Logic セクションの 5ETF メタデータ。

- [ ] **Step 1: 失敗するテストを書く**

ファイル `equity_trading/tests/test_universe.py`：

```python
from equity_trading.src.strategy.universe import (
    UNIVERSE,
    EtfMeta,
    get_etf_meta,
    liquidity_priority,
    macro_defense_followers,
)


def test_universe_contains_5_etfs():
    assert {e.symbol for e in UNIVERSE} == {"SPY", "QQQ", "IWM", "DIA", "XLK"}


def test_get_etf_meta_returns_correct_metadata():
    spy = get_etf_meta("SPY")
    assert spy.symbol == "SPY"
    assert spy.tech_pct == 0.30
    assert spy.sector_class == "broad"


def test_liquidity_priority_order():
    assert liquidity_priority() == ["SPY", "QQQ", "XLK", "IWM", "DIA"]


def test_macro_defense_followers_excludes_spy_and_iwm_specially():
    # SPY 200日下なら QQQ/XLK/DIA 取引不可、さらに IWM も停止（v2.0方針）
    followers = macro_defense_followers()
    assert set(followers) == {"QQQ", "XLK", "DIA", "IWM"}


def test_get_etf_meta_unknown_raises():
    import pytest
    with pytest.raises(KeyError):
        get_etf_meta("AAPL")


def test_etf_meta_is_immutable():
    spy = get_etf_meta("SPY")
    import dataclasses
    assert dataclasses.is_dataclass(spy)
    # frozen dataclass のため属性変更で例外
    import pytest
    with pytest.raises(dataclasses.FrozenInstanceError):
        spy.tech_pct = 0.50  # type: ignore[misc]
```

- [ ] **Step 2: テスト実行（失敗確認）**

```bash
cd "/Users/hideakimacbookair/自動トレード"
pytest equity_trading/tests/test_universe.py -v
```

期待：`ImportError`

- [ ] **Step 3: 実装を書く**

ファイル `equity_trading/src/strategy/universe.py`：

```python
"""5ETFのメタデータ・セクター分類・流動性順位."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EtfMeta:
    """ETF1本のメタデータ."""

    symbol: str
    name: str
    sector_class: str        # 'broad' | 'tech-heavy' | 'tech-pure' | 'small-cap' | 'broad-defensive'
    tech_pct: float          # 構成銘柄のテクノロジー比率（加重テック露出計算用）


UNIVERSE: tuple[EtfMeta, ...] = (
    EtfMeta("SPY", "SPDR S&P 500 ETF", "broad", 0.30),
    EtfMeta("QQQ", "Invesco QQQ Trust", "tech-heavy", 0.50),
    EtfMeta("IWM", "iShares Russell 2000", "small-cap", 0.05),
    EtfMeta("DIA", "SPDR Dow Jones 30", "broad-defensive", 0.20),
    EtfMeta("XLK", "Technology Select Sector SPDR", "tech-pure", 0.95),
)

_BY_SYMBOL: dict[str, EtfMeta] = {e.symbol: e for e in UNIVERSE}


def get_etf_meta(symbol: str) -> EtfMeta:
    """ETFメタデータを返す。未知の銘柄は KeyError."""
    return _BY_SYMBOL[symbol]


def liquidity_priority() -> list[str]:
    """流動性の高い順に並べた銘柄リスト（同点エントリー時の優先順位）.

    実測出来高ベース：SPY > QQQ > XLK > IWM > DIA
    （v1.1 で誤って DIA > XLK と書いていたものを v2.0 で訂正）
    """
    return ["SPY", "QQQ", "XLK", "IWM", "DIA"]


def macro_defense_followers() -> list[str]:
    """SPYが200日MA下のとき取引停止すべき銘柄リスト.

    v2.0方針：QQQ/XLK/DIA に加え、IWM も停止（小型株は弱気相場で先行下落）.
    """
    return ["QQQ", "XLK", "DIA", "IWM"]
```

- [ ] **Step 4: テスト実行（成功確認）**

```bash
cd "/Users/hideakimacbookair/自動トレード"
pytest equity_trading/tests/test_universe.py -v
```

期待：`6 passed`

- [ ] **Step 5: コミット**

```bash
cd "/Users/hideakimacbookair/自動トレード"
git add equity_trading/src/strategy/universe.py equity_trading/tests/test_universe.py
git commit -m "feat(strategy): add ETF universe with metadata and priority orders"
```

---

### Task 5: Market Calendar（米国祝日・前場短縮判定）

**Files:**
- Create: `equity_trading/src/data/market_calendar.py`
- Test: `equity_trading/tests/test_market_calendar.py`

`pandas-market-calendars` ライブラリを薄くラップする。

- [ ] **Step 1: 失敗するテストを書く**

ファイル `equity_trading/tests/test_market_calendar.py`：

```python
from datetime import date, datetime, timezone

import pytest

from equity_trading.src.data.market_calendar import (
    is_trading_day,
    market_close_utc,
    market_open_utc,
    is_early_close_day,
)


def test_is_trading_day_for_typical_weekday():
    # 2026-05-04 は月曜（祝日でない）
    assert is_trading_day(date(2026, 5, 4)) is True


def test_is_not_trading_day_for_saturday():
    assert is_trading_day(date(2026, 5, 9)) is False  # Saturday


def test_is_not_trading_day_for_us_holiday():
    # 2026年の独立記念日（7/3 金曜が振替休日）
    # 2026-07-03 は祝日扱い
    # ただし pandas_market_calendars の実データ依存なので
    # 7/4（土曜）・週末を含めてチェック
    assert is_trading_day(date(2026, 7, 4)) is False  # Saturday


def test_market_open_utc_for_winter_day():
    # 冬時間（11月-3月）の通常日：9:30 ET = 14:30 UTC
    open_utc = market_open_utc(date(2026, 1, 5))  # 月曜
    assert open_utc.hour == 14
    assert open_utc.minute == 30


def test_market_open_utc_for_summer_day():
    # 夏時間（3月-11月）の通常日：9:30 ET = 13:30 UTC
    open_utc = market_open_utc(date(2026, 6, 1))  # 月曜
    assert open_utc.hour == 13
    assert open_utc.minute == 30


def test_market_close_utc_for_normal_day():
    # 通常16:00 ET
    close_utc = market_close_utc(date(2026, 6, 1))  # 月曜・夏時間
    assert close_utc.hour == 20
    assert close_utc.minute == 0


def test_is_early_close_day_for_thanksgiving_friday():
    # サンクスギビング翌日（金曜）は前場短縮（13:00 ET クローズ）
    # 2026年は 11/27 (Fri)
    assert is_early_close_day(date(2026, 11, 27)) is True


def test_is_early_close_day_for_normal_day():
    assert is_early_close_day(date(2026, 6, 1)) is False
```

- [ ] **Step 2: テスト実行（失敗確認）**

```bash
cd "/Users/hideakimacbookair/自動トレード"
pytest equity_trading/tests/test_market_calendar.py -v
```

期待：`ImportError`

- [ ] **Step 3: 実装を書く**

ファイル `equity_trading/src/data/market_calendar.py`：

```python
"""米国市場（NYSE）の祝日・取引日・前場短縮判定."""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from functools import lru_cache

import pandas as pd
import pandas_market_calendars as mcal


_NYSE = mcal.get_calendar("NYSE")


@lru_cache(maxsize=1024)
def _schedule_for_date(d: date) -> pd.Series | None:
    """指定日のNYSE schedule（market_open, market_close）を返す。非取引日は None."""
    schedule = _NYSE.schedule(start_date=d.isoformat(), end_date=d.isoformat())
    if len(schedule) == 0:
        return None
    return schedule.iloc[0]


def is_trading_day(d: date) -> bool:
    """米国市場の取引日か（週末・祝日でない）."""
    return _schedule_for_date(d) is not None


def market_open_utc(d: date) -> datetime:
    """指定日の市場オープン時刻（UTC）. 非取引日は ValueError."""
    s = _schedule_for_date(d)
    if s is None:
        raise ValueError(f"{d} is not a trading day")
    open_ts: pd.Timestamp = s["market_open"]
    return open_ts.to_pydatetime().astimezone(timezone.utc)


def market_close_utc(d: date) -> datetime:
    """指定日の市場クローズ時刻（UTC）. 非取引日は ValueError."""
    s = _schedule_for_date(d)
    if s is None:
        raise ValueError(f"{d} is not a trading day")
    close_ts: pd.Timestamp = s["market_close"]
    return close_ts.to_pydatetime().astimezone(timezone.utc)


def is_early_close_day(d: date) -> bool:
    """前場短縮日（13:00 ET クローズ）か.

    通常16:00 ETクローズに対して、年8日程度ある13:00 ETクローズ日を判定.
    """
    s = _schedule_for_date(d)
    if s is None:
        return False
    close_ts: pd.Timestamp = s["market_close"]
    close_et = close_ts.tz_convert("America/New_York")
    # 通常クローズは 16:00 ET。13:00 ET ならearly close
    return close_et.time() < time(15, 0)
```

- [ ] **Step 4: テスト実行（成功確認）**

```bash
cd "/Users/hideakimacbookair/自動トレード"
pytest equity_trading/tests/test_market_calendar.py -v
```

期待：`8 passed`

注：`is_early_close_day` のテストはサンクスギビング翌日が前場短縮として記録されているか pandas-market-calendars の実装に依存。失敗した場合は実日付を確認して調整。

- [ ] **Step 5: コミット**

```bash
cd "/Users/hideakimacbookair/自動トレード"
git add equity_trading/src/data/market_calendar.py equity_trading/tests/test_market_calendar.py
git commit -m "feat(data): add NYSE market calendar helper for trading day / early close"
```

---

### Task 6: Feature Builder - RSI

**Files:**
- Create: `equity_trading/src/data/feature_builder.py`
- Test: `equity_trading/tests/test_feature_builder.py`

仕様書のシグナル群（RSI, BB, VWAP, 出来高比, 勢い反転, 200日MA）を計算する純粋関数群。Task 6-11 で1つずつ追加していく。

- [ ] **Step 1: 失敗するテストを書く（RSI）**

ファイル `equity_trading/tests/test_feature_builder.py`：

```python
import numpy as np
import pandas as pd
import pytest

from equity_trading.src.data.feature_builder import compute_rsi


def test_rsi_constant_prices_returns_neutral():
    # 価格が変わらない場合、RSI は計算不能（NaN）か50近辺
    prices = pd.Series([100.0] * 30)
    rsi = compute_rsi(prices, period=14)
    # 最初の14本は NaN、その後は値変化ゼロで NaN または 50
    last = rsi.iloc[-1]
    assert pd.isna(last) or abs(last - 50.0) < 0.01


def test_rsi_strictly_rising_approaches_100():
    prices = pd.Series([100.0 + i for i in range(30)])
    rsi = compute_rsi(prices, period=14)
    assert rsi.iloc[-1] > 99.0


def test_rsi_strictly_falling_approaches_0():
    prices = pd.Series([100.0 - i for i in range(30)])
    rsi = compute_rsi(prices, period=14)
    assert rsi.iloc[-1] < 1.0


def test_rsi_mixed_movement_in_valid_range():
    np.random.seed(42)
    prices = pd.Series(100.0 + np.cumsum(np.random.randn(50)))
    rsi = compute_rsi(prices, period=14)
    valid = rsi.dropna()
    assert (valid >= 0).all() and (valid <= 100).all()


def test_rsi_first_period_values_are_nan():
    prices = pd.Series([100.0 + i for i in range(20)])
    rsi = compute_rsi(prices, period=14)
    # period 個目までは NaN
    assert rsi.iloc[:13].isna().all()
```

- [ ] **Step 2: テスト実行（失敗確認）**

```bash
cd "/Users/hideakimacbookair/自動トレード"
pytest equity_trading/tests/test_feature_builder.py -v
```

期待：`ImportError`

- [ ] **Step 3: 実装を書く**

ファイル `equity_trading/src/data/feature_builder.py`：

```python
"""テクニカル指標の純粋関数群（pandas ベース）."""
from __future__ import annotations

import pandas as pd


def compute_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index を計算.

    Args:
        prices: 終値の時系列
        period: 計算期間（典型値 14）

    Returns:
        RSI 値（0〜100）の時系列。最初の period-1 本は NaN。
    """
    delta = prices.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    # Wilder's smoothing（指数移動平均、α = 1/period）
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()

    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    # avg_loss が 0 のとき rs = inf → rsi = 100
    rsi = rsi.where(avg_loss != 0, 100.0)
    # avg_gain が 0 かつ avg_loss が 0 のとき NaN（変化なし）
    rsi = rsi.where(~((avg_gain == 0) & (avg_loss == 0)), pd.NA)
    return rsi
```

- [ ] **Step 4: テスト実行（成功確認）**

```bash
cd "/Users/hideakimacbookair/自動トレード"
pytest equity_trading/tests/test_feature_builder.py -v
```

期待：`5 passed`

- [ ] **Step 5: コミット**

```bash
cd "/Users/hideakimacbookair/自動トレード"
git add equity_trading/src/data/feature_builder.py equity_trading/tests/test_feature_builder.py
git commit -m "feat(data): add RSI computation in feature_builder"
```

---

### Task 7: Feature Builder - Bollinger Bands

**Files:**
- Modify: `equity_trading/src/data/feature_builder.py`
- Modify: `equity_trading/tests/test_feature_builder.py`

- [ ] **Step 1: テストを追加**

ファイル `equity_trading/tests/test_feature_builder.py` の末尾に追加：

```python


from equity_trading.src.data.feature_builder import compute_bollinger_bands


def test_bollinger_bands_constant_prices_yields_zero_width():
    prices = pd.Series([100.0] * 30)
    upper, middle, lower = compute_bollinger_bands(prices, period=20, num_std=2.0)
    # 最後の値は middle = 100、upper = lower = 100 (std=0)
    assert middle.iloc[-1] == 100.0
    assert upper.iloc[-1] == 100.0
    assert lower.iloc[-1] == 100.0


def test_bollinger_middle_equals_simple_moving_average():
    np.random.seed(42)
    prices = pd.Series(100.0 + np.cumsum(np.random.randn(30)))
    _, middle, _ = compute_bollinger_bands(prices, period=20, num_std=2.0)
    sma = prices.rolling(20).mean()
    pd.testing.assert_series_equal(middle.dropna(), sma.dropna())


def test_bollinger_upper_above_lower():
    np.random.seed(42)
    prices = pd.Series(100.0 + np.cumsum(np.random.randn(30)))
    upper, _, lower = compute_bollinger_bands(prices, period=20, num_std=2.0)
    valid = upper.notna() & lower.notna()
    assert (upper[valid] >= lower[valid]).all()


def test_bollinger_first_period_values_are_nan():
    prices = pd.Series(np.arange(30, dtype=float))
    upper, middle, lower = compute_bollinger_bands(prices, period=20, num_std=2.0)
    assert upper.iloc[:19].isna().all()
```

- [ ] **Step 2: テスト実行（失敗確認）**

```bash
cd "/Users/hideakimacbookair/自動トレード"
pytest equity_trading/tests/test_feature_builder.py::test_bollinger_bands_constant_prices_yields_zero_width -v
```

期待：`ImportError: cannot import compute_bollinger_bands`

- [ ] **Step 3: 実装を追加**

`equity_trading/src/data/feature_builder.py` の末尾に追加：

```python


def compute_bollinger_bands(
    prices: pd.Series,
    period: int = 20,
    num_std: float = 2.0,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """ボリンジャーバンドを計算.

    Args:
        prices: 終値の時系列
        period: 移動平均期間
        num_std: バンド幅の標準偏差倍数

    Returns:
        (upper_band, middle_band, lower_band) のタプル
    """
    middle = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std(ddof=0)
    upper = middle + num_std * std
    lower = middle - num_std * std
    return upper, middle, lower
```

- [ ] **Step 4: テスト実行（成功確認）**

```bash
cd "/Users/hideakimacbookair/自動トレード"
pytest equity_trading/tests/test_feature_builder.py -v
```

期待：`9 passed`

- [ ] **Step 5: コミット**

```bash
cd "/Users/hideakimacbookair/自動トレード"
git add equity_trading/src/data/feature_builder.py equity_trading/tests/test_feature_builder.py
git commit -m "feat(data): add Bollinger Bands computation"
```

---

### Task 8: Feature Builder - VWAP

**Files:**
- Modify: `equity_trading/src/data/feature_builder.py`
- Modify: `equity_trading/tests/test_feature_builder.py`

VWAP（出来高加重平均価格）を当日の累積で計算。米東部 9:30 ET から累積開始。

- [ ] **Step 1: テストを追加**

ファイル `equity_trading/tests/test_feature_builder.py` の末尾に追加：

```python


from equity_trading.src.data.feature_builder import compute_vwap


def test_vwap_constant_price_equals_price():
    df = pd.DataFrame({
        "high": [100.0] * 5,
        "low": [100.0] * 5,
        "close": [100.0] * 5,
        "volume": [1000, 2000, 1500, 3000, 2500],
    })
    vwap = compute_vwap(df)
    assert (vwap == 100.0).all()


def test_vwap_weighted_correctly():
    df = pd.DataFrame({
        "high": [100.0, 110.0, 90.0],
        "low":  [100.0, 110.0, 90.0],
        "close":[100.0, 110.0, 90.0],
        "volume": [100, 200, 100],
    })
    # typical price = close、cumulative VWAP after each row:
    # row0: 100*100 / 100 = 100
    # row1: (100*100 + 200*110) / (100+200) = 32000/300 ≈ 106.67
    # row2: (100*100 + 200*110 + 100*90) / 400 = 41000/400 = 102.5
    vwap = compute_vwap(df)
    assert vwap.iloc[0] == pytest.approx(100.0)
    assert vwap.iloc[1] == pytest.approx(32000.0 / 300.0)
    assert vwap.iloc[2] == pytest.approx(41000.0 / 400.0)


def test_vwap_zero_volume_returns_nan():
    df = pd.DataFrame({
        "high": [100.0, 110.0],
        "low":  [100.0, 110.0],
        "close":[100.0, 110.0],
        "volume": [0, 0],
    })
    vwap = compute_vwap(df)
    assert vwap.isna().all()
```

- [ ] **Step 2: テスト実行（失敗確認）**

```bash
cd "/Users/hideakimacbookair/自動トレード"
pytest equity_trading/tests/test_feature_builder.py::test_vwap_constant_price_equals_price -v
```

期待：`ImportError: cannot import compute_vwap`

- [ ] **Step 3: 実装を追加**

`equity_trading/src/data/feature_builder.py` の末尾に追加：

```python


def compute_vwap(df: pd.DataFrame) -> pd.Series:
    """累積VWAPを計算.

    入力DataFrameは high/low/close/volume カラムを持つこと。
    典型価格（high+low+close）/3 を出来高で重み付けして累積平均。
    呼び出し側で「当日分のみ」を渡すことで「当日VWAP」になる。

    Args:
        df: ['high', 'low', 'close', 'volume'] カラムを持つ DataFrame

    Returns:
        累積VWAP の時系列。volume が 0 のときは NaN。
    """
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    pv = typical * df["volume"]
    cum_pv = pv.cumsum()
    cum_v = df["volume"].cumsum()
    vwap = cum_pv / cum_v
    return vwap.where(cum_v > 0, pd.NA)
```

- [ ] **Step 4: テスト実行（成功確認）**

```bash
cd "/Users/hideakimacbookair/自動トレード"
pytest equity_trading/tests/test_feature_builder.py -v
```

期待：`12 passed`

- [ ] **Step 5: コミット**

```bash
cd "/Users/hideakimacbookair/自動トレード"
git add equity_trading/src/data/feature_builder.py equity_trading/tests/test_feature_builder.py
git commit -m "feat(data): add cumulative VWAP computation"
```

---

### Task 9: Feature Builder - 出来高比・勢い反転・200日MA

**Files:**
- Modify: `equity_trading/src/data/feature_builder.py`
- Modify: `equity_trading/tests/test_feature_builder.py`

残りの3指標を追加。

- [ ] **Step 1: テストを追加**

ファイル `equity_trading/tests/test_feature_builder.py` の末尾に追加：

```python


from equity_trading.src.data.feature_builder import (
    compute_volume_ratio,
    compute_momentum_reversal,
    compute_sma,
)


def test_volume_ratio_against_recent_average():
    volume = pd.Series([100] * 20 + [150])
    ratio = compute_volume_ratio(volume, period=20)
    # 最後の値：150 / mean(直近20本=100) = 1.5
    assert ratio.iloc[-1] == pytest.approx(1.5)


def test_volume_ratio_first_period_is_nan():
    volume = pd.Series([100] * 25)
    ratio = compute_volume_ratio(volume, period=20)
    assert ratio.iloc[:19].isna().all()


def test_momentum_reversal_detects_negative_to_positive():
    # 直近3本で「下げ→上げ反転」の流れ
    prices = pd.Series([100.0, 99.5, 99.0, 98.5, 99.0, 99.5, 100.0])
    flag = compute_momentum_reversal(prices, lookback=3)
    # 後半で反転検出
    assert flag.iloc[-1] is True or flag.iloc[-1] == 1


def test_momentum_reversal_constant_prices_no_reversal():
    prices = pd.Series([100.0] * 10)
    flag = compute_momentum_reversal(prices, lookback=3)
    # 反転していない
    assert flag.iloc[-1] is False or flag.iloc[-1] == 0


def test_sma_basic():
    prices = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    sma = compute_sma(prices, period=3)
    assert sma.iloc[2] == pytest.approx(2.0)
    assert sma.iloc[4] == pytest.approx(4.0)
    assert sma.iloc[:2].isna().all()
```

- [ ] **Step 2: テスト実行（失敗確認）**

```bash
cd "/Users/hideakimacbookair/自動トレード"
pytest equity_trading/tests/test_feature_builder.py::test_sma_basic -v
```

期待：`ImportError`

- [ ] **Step 3: 実装を追加**

`equity_trading/src/data/feature_builder.py` の末尾に追加：

```python


def compute_volume_ratio(volume: pd.Series, period: int = 20) -> pd.Series:
    """直近period本平均に対する出来高比を計算.

    Args:
        volume: 出来高の時系列
        period: 平均を取る期間

    Returns:
        出来高 / 直近平均 の時系列。最初の period-1 本は NaN。
    """
    avg = volume.rolling(window=period).mean()
    return volume / avg


def compute_momentum_reversal(prices: pd.Series, lookback: int = 3) -> pd.Series:
    """短期勢い反転（負→正）を検出.

    直近lookback本の終値で線形回帰し、
    1本前の傾きが負、当該本の傾きが正なら True を返す。

    Args:
        prices: 終値の時系列
        lookback: 線形回帰のウィンドウ

    Returns:
        反転フラグ（bool）の時系列。
    """
    import numpy as np

    def _slope(y: np.ndarray) -> float:
        if len(y) < 2:
            return float("nan")
        x = np.arange(len(y), dtype=float)
        # 平均ベースの一次回帰係数
        x_mean = x.mean()
        y_mean = y.mean()
        denom = ((x - x_mean) ** 2).sum()
        if denom == 0:
            return 0.0
        return float(((x - x_mean) * (y - y_mean)).sum() / denom)

    slopes = prices.rolling(window=lookback).apply(_slope, raw=True)
    prev = slopes.shift(1)
    reversal = (prev < 0) & (slopes > 0)
    return reversal


def compute_sma(prices: pd.Series, period: int) -> pd.Series:
    """単純移動平均を計算（200日MAなどに使用）.

    Args:
        prices: 価格の時系列
        period: 期間

    Returns:
        SMA の時系列。最初の period-1 本は NaN。
    """
    return prices.rolling(window=period).mean()
```

- [ ] **Step 4: テスト実行（成功確認）**

```bash
cd "/Users/hideakimacbookair/自動トレード"
pytest equity_trading/tests/test_feature_builder.py -v
```

期待：`17 passed`

- [ ] **Step 5: コミット**

```bash
cd "/Users/hideakimacbookair/自動トレード"
git add equity_trading/src/data/feature_builder.py equity_trading/tests/test_feature_builder.py
git commit -m "feat(data): add volume ratio, momentum reversal, and SMA computations"
```

---

### Task 10: Config モジュール

**Files:**
- Create: `equity_trading/src/config.py`
- Test: `equity_trading/tests/test_config.py`

`.env` から環境変数を読み込み、型変換・バリデーションする。

- [ ] **Step 1: 失敗するテストを書く**

ファイル `equity_trading/tests/test_config.py`：

```python
import os

import pytest

from equity_trading.src.config import Config, load_config, ConfigError


def test_load_config_from_env(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ALPACA_API_KEY=PKABCDEF\n"
        "ALPACA_SECRET_KEY=secret123\n"
        "ALPACA_BASE_URL=https://paper-api.alpaca.markets\n"
        "DATA_PLAN=free\n"
        "CONFIRM_LIVE=false\n"
        "INITIAL_CAPITAL_USD=100000\n"
        "RISK_PER_TRADE=0.005\n"
        "MAX_POSITION_PCT=0.25\n"
        "MAX_CONCURRENT_POSITIONS=3\n"
        "MAX_TECH_EXPOSURE=0.40\n"
        "DAILY_LOSS_LIMIT=0.02\n"
        "WEEKLY_LOSS_LIMIT=0.05\n"
        "MONTHLY_LOSS_LIMIT=0.08\n"
        "CUMULATIVE_DD_LIMIT=0.20\n"
        "COST_WARN_THRESHOLD=0.0013\n"
        "COST_HALT_THRESHOLD=0.0018\n"
    )
    cfg = load_config(env_path=env_file)
    assert cfg.alpaca_api_key == "PKABCDEF"
    assert cfg.alpaca_base_url == "https://paper-api.alpaca.markets"
    assert cfg.data_plan == "free"
    assert cfg.confirm_live is False
    assert cfg.initial_capital_usd == 100000.0
    assert cfg.risk_per_trade == 0.005
    assert cfg.max_position_pct == 0.25


def test_load_config_validates_risk_per_trade_too_high(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ALPACA_API_KEY=PKABCDEF\n"
        "ALPACA_SECRET_KEY=secret123\n"
        "ALPACA_BASE_URL=https://paper-api.alpaca.markets\n"
        "RISK_PER_TRADE=0.10\n"  # 10% は許容上限超え
    )
    with pytest.raises(ConfigError, match="RISK_PER_TRADE"):
        load_config(env_path=env_file)


def test_load_config_rejects_live_url_without_confirm(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ALPACA_API_KEY=PKABCDEF\n"
        "ALPACA_SECRET_KEY=secret123\n"
        "ALPACA_BASE_URL=https://api.alpaca.markets\n"  # Live URL
        "CONFIRM_LIVE=false\n"
    )
    with pytest.raises(ConfigError, match="CONFIRM_LIVE"):
        load_config(env_path=env_file)


def test_load_config_missing_api_key(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("")
    with pytest.raises(ConfigError, match="ALPACA_API_KEY"):
        load_config(env_path=env_file)
```

- [ ] **Step 2: テスト実行（失敗確認）**

```bash
cd "/Users/hideakimacbookair/自動トレード"
pytest equity_trading/tests/test_config.py -v
```

期待：`ImportError`

- [ ] **Step 3: 実装を書く**

ファイル `equity_trading/src/config.py`：

```python
"""環境変数から設定値を読み込み・型変換・バリデーション."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(ValueError):
    """設定不備の例外."""


@dataclass(frozen=True)
class Config:
    """全設定値の集約."""

    alpaca_api_key: str
    alpaca_secret_key: str
    alpaca_base_url: str
    data_plan: str                       # 'free' | 'paid'
    confirm_live: bool
    initial_capital_usd: float
    risk_per_trade: float                # 例 0.005 = 0.5%
    max_position_pct: float
    max_concurrent_positions: int
    max_tech_exposure: float
    daily_loss_limit: float
    weekly_loss_limit: float
    monthly_loss_limit: float
    cumulative_dd_limit: float
    cost_warn_threshold: float
    cost_halt_threshold: float
    healthchecks_intraday_url: str
    healthchecks_eod_url: str
    healthchecks_monthly_url: str
    slack_webhook_url: str
    notification_email: str


def _get_required(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise ConfigError(f"{key} is required but not set")
    return val


def _get_float(key: str, default: float | None = None) -> float:
    val = os.environ.get(key)
    if val is None or val == "":
        if default is not None:
            return default
        raise ConfigError(f"{key} is required but not set")
    try:
        return float(val)
    except ValueError as e:
        raise ConfigError(f"{key} must be float: {val}") from e


def _get_int(key: str, default: int | None = None) -> int:
    val = os.environ.get(key)
    if val is None or val == "":
        if default is not None:
            return default
        raise ConfigError(f"{key} is required but not set")
    try:
        return int(val)
    except ValueError as e:
        raise ConfigError(f"{key} must be int: {val}") from e


def _get_bool(key: str, default: bool = False) -> bool:
    val = os.environ.get(key, "").lower()
    if val in ("true", "yes", "1"):
        return True
    if val in ("false", "no", "0", ""):
        return default
    raise ConfigError(f"{key} must be true/false: {val}")


def load_config(env_path: Path | str | None = None) -> Config:
    """`.env` を読み込み、Config を返す。バリデーション失敗時は ConfigError."""
    if env_path is not None:
        load_dotenv(env_path, override=True)

    cfg = Config(
        alpaca_api_key=_get_required("ALPACA_API_KEY"),
        alpaca_secret_key=_get_required("ALPACA_SECRET_KEY"),
        alpaca_base_url=_get_required("ALPACA_BASE_URL"),
        data_plan=os.environ.get("DATA_PLAN", "free"),
        confirm_live=_get_bool("CONFIRM_LIVE", default=False),
        initial_capital_usd=_get_float("INITIAL_CAPITAL_USD", default=100000.0),
        risk_per_trade=_get_float("RISK_PER_TRADE", default=0.005),
        max_position_pct=_get_float("MAX_POSITION_PCT", default=0.25),
        max_concurrent_positions=_get_int("MAX_CONCURRENT_POSITIONS", default=3),
        max_tech_exposure=_get_float("MAX_TECH_EXPOSURE", default=0.40),
        daily_loss_limit=_get_float("DAILY_LOSS_LIMIT", default=0.02),
        weekly_loss_limit=_get_float("WEEKLY_LOSS_LIMIT", default=0.05),
        monthly_loss_limit=_get_float("MONTHLY_LOSS_LIMIT", default=0.08),
        cumulative_dd_limit=_get_float("CUMULATIVE_DD_LIMIT", default=0.20),
        cost_warn_threshold=_get_float("COST_WARN_THRESHOLD", default=0.0013),
        cost_halt_threshold=_get_float("COST_HALT_THRESHOLD", default=0.0018),
        healthchecks_intraday_url=os.environ.get("HEALTHCHECKS_INTRADAY_URL", ""),
        healthchecks_eod_url=os.environ.get("HEALTHCHECKS_EOD_URL", ""),
        healthchecks_monthly_url=os.environ.get("HEALTHCHECKS_MONTHLY_URL", ""),
        slack_webhook_url=os.environ.get("SLACK_WEBHOOK_URL", ""),
        notification_email=os.environ.get("NOTIFICATION_EMAIL", ""),
    )

    _validate(cfg)
    return cfg


def _validate(cfg: Config) -> None:
    if cfg.risk_per_trade > 0.05:
        raise ConfigError(
            f"RISK_PER_TRADE too high ({cfg.risk_per_trade}); max 0.05 to prevent runaway risk"
        )
    if cfg.max_position_pct > 1.0 or cfg.max_position_pct <= 0:
        raise ConfigError(f"MAX_POSITION_PCT must be in (0, 1.0]: {cfg.max_position_pct}")
    if cfg.max_concurrent_positions < 1 or cfg.max_concurrent_positions > 10:
        raise ConfigError(
            f"MAX_CONCURRENT_POSITIONS must be 1..10: {cfg.max_concurrent_positions}"
        )
    if cfg.max_tech_exposure <= 0 or cfg.max_tech_exposure > 1.0:
        raise ConfigError(f"MAX_TECH_EXPOSURE must be in (0, 1.0]: {cfg.max_tech_exposure}")
    if cfg.cumulative_dd_limit > 0.50:
        raise ConfigError(f"CUMULATIVE_DD_LIMIT too lax: {cfg.cumulative_dd_limit}")

    is_live_url = "paper-api" not in cfg.alpaca_base_url
    if is_live_url and not cfg.confirm_live:
        raise ConfigError(
            "Live URL detected but CONFIRM_LIVE=false. Set CONFIRM_LIVE=true to confirm Live trading"
        )
```

- [ ] **Step 4: テスト実行（成功確認）**

```bash
cd "/Users/hideakimacbookair/自動トレード"
pytest equity_trading/tests/test_config.py -v
```

期待：`4 passed`

注：テストでは `monkeypatch` で環境変数をクリアする必要がある場合は適宜調整。`load_dotenv(override=True)` を使っているので各テストで env_path 経由のみ反映される。

- [ ] **Step 5: コミット**

```bash
cd "/Users/hideakimacbookair/自動トレード"
git add equity_trading/src/config.py equity_trading/tests/test_config.py
git commit -m "feat(config): add config loader with validation"
```

---

### Task 11: Alpaca Broker Client（薄いラッパー）

**Files:**
- Create: `equity_trading/src/broker/alpaca_client.py`
- Test: `equity_trading/tests/test_alpaca_client.py`

Alpaca SDK を薄くラップ。Phase 0 では「過去データ取得」だけ使う。

- [ ] **Step 1: 失敗するテストを書く**

ファイル `equity_trading/tests/test_alpaca_client.py`：

```python
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from equity_trading.src.broker.alpaca_client import AlpacaClient


def test_get_historical_bars_returns_dataframe():
    fake_bars = MagicMock()
    fake_bars.df = pd.DataFrame({
        "open": [100.0, 101.0],
        "high": [101.0, 102.0],
        "low": [99.0, 100.0],
        "close": [100.5, 101.5],
        "volume": [10000, 12000],
    })

    with patch("equity_trading.src.broker.alpaca_client.StockHistoricalDataClient") as mock_data:
        mock_data.return_value.get_stock_bars.return_value = fake_bars

        client = AlpacaClient(api_key="K", secret_key="S")
        df = client.get_historical_bars(
            symbol="SPY",
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2024, 1, 2, tzinfo=timezone.utc),
            timeframe_minutes=5,
        )

    assert len(df) == 2
    assert "close" in df.columns
    assert df["close"].iloc[0] == 100.5


def test_get_account_returns_account_dict():
    fake_account = MagicMock()
    fake_account.account_number = "PA123"
    fake_account.cash = "100000"
    fake_account.equity = "100000"
    fake_account.buying_power = "200000"

    with patch("equity_trading.src.broker.alpaca_client.TradingClient") as mock_trading:
        mock_trading.return_value.get_account.return_value = fake_account

        client = AlpacaClient(api_key="K", secret_key="S")
        acct = client.get_account()

    assert acct["account_number"] == "PA123"
    assert acct["cash"] == 100000.0
    assert acct["equity"] == 100000.0


def test_paper_url_uses_paper_flag():
    with patch("equity_trading.src.broker.alpaca_client.TradingClient") as mock_trading, \
         patch("equity_trading.src.broker.alpaca_client.StockHistoricalDataClient"):
        AlpacaClient(api_key="K", secret_key="S", base_url="https://paper-api.alpaca.markets")

    args, kwargs = mock_trading.call_args
    assert kwargs.get("paper") is True


def test_live_url_disables_paper_flag():
    with patch("equity_trading.src.broker.alpaca_client.TradingClient") as mock_trading, \
         patch("equity_trading.src.broker.alpaca_client.StockHistoricalDataClient"):
        AlpacaClient(api_key="K", secret_key="S", base_url="https://api.alpaca.markets")

    args, kwargs = mock_trading.call_args
    assert kwargs.get("paper") is False
```

- [ ] **Step 2: テスト実行（失敗確認）**

```bash
cd "/Users/hideakimacbookair/自動トレード"
pytest equity_trading/tests/test_alpaca_client.py -v
```

期待：`ImportError`

- [ ] **Step 3: 実装を書く**

ファイル `equity_trading/src/broker/alpaca_client.py`：

```python
"""Alpaca SDK の薄いラッパー."""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.trading.client import TradingClient


class AlpacaClient:
    """Trading API と Market Data API のシン薄ラッパー.

    本ラッパーは Paper / Live の差分を base_url で吸収する。
    """

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        base_url: str = "https://paper-api.alpaca.markets",
    ) -> None:
        is_paper = "paper-api" in base_url
        self._trading = TradingClient(api_key, secret_key, paper=is_paper)
        self._data = StockHistoricalDataClient(api_key, secret_key)

    def get_account(self) -> dict[str, Any]:
        """口座情報を辞書で返す."""
        a = self._trading.get_account()
        return {
            "account_number": a.account_number,
            "status": str(a.status),
            "currency": a.currency,
            "cash": float(a.cash),
            "equity": float(a.equity),
            "buying_power": float(a.buying_power),
            "pattern_day_trader": bool(a.pattern_day_trader),
        }

    def get_historical_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe_minutes: int,
    ) -> pd.DataFrame:
        """過去のバー（OHLCV）を pandas DataFrame で返す.

        Args:
            symbol: ティッカー（例 "SPY"）
            start: 開始時刻（UTC tz aware）
            end: 終了時刻（UTC tz aware）
            timeframe_minutes: 1, 5, 15, 60, または 1440 (=日足)
        """
        if timeframe_minutes == 1:
            tf = TimeFrame(1, TimeFrameUnit.Minute)
        elif timeframe_minutes == 5:
            tf = TimeFrame(5, TimeFrameUnit.Minute)
        elif timeframe_minutes == 15:
            tf = TimeFrame(15, TimeFrameUnit.Minute)
        elif timeframe_minutes == 60:
            tf = TimeFrame(1, TimeFrameUnit.Hour)
        elif timeframe_minutes == 1440:
            tf = TimeFrame(1, TimeFrameUnit.Day)
        else:
            raise ValueError(f"Unsupported timeframe: {timeframe_minutes} minutes")

        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=tf,
            start=start,
            end=end,
        )
        bars = self._data.get_stock_bars(request)
        df = bars.df
        # MultiIndex (symbol, timestamp) を timestamp だけに reduce
        if isinstance(df.index, pd.MultiIndex):
            df = df.reset_index(level=0, drop=True)
        return df
```

- [ ] **Step 4: テスト実行（成功確認）**

```bash
cd "/Users/hideakimacbookair/自動トレード"
pytest equity_trading/tests/test_alpaca_client.py -v
```

期待：`4 passed`

- [ ] **Step 5: コミット**

```bash
cd "/Users/hideakimacbookair/自動トレード"
git add equity_trading/src/broker/alpaca_client.py equity_trading/tests/test_alpaca_client.py
git commit -m "feat(broker): add thin Alpaca SDK wrapper for account and historical bars"
```

---

### Task 12: Price Fetcher（5ETF並列取得＆ローカルキャッシュ）

**Files:**
- Create: `equity_trading/src/data/price_fetcher.py`
- Test: `equity_trading/tests/test_price_fetcher.py`

Alpaca から取得した価格データをローカルファイル（Parquet 形式）にキャッシュ。

- [ ] **Step 1: 失敗するテストを書く**

ファイル `equity_trading/tests/test_price_fetcher.py`：

```python
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from equity_trading.src.data.price_fetcher import PriceFetcher


def _make_bars(n: int = 3) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": [100.0 + i for i in range(n)],
            "high": [101.0 + i for i in range(n)],
            "low": [99.0 + i for i in range(n)],
            "close": [100.5 + i for i in range(n)],
            "volume": [10000 + 1000 * i for i in range(n)],
        },
        index=pd.date_range("2024-01-01", periods=n, freq="5min", tz="UTC"),
    )


def test_fetcher_loads_from_cache_when_exists(tmp_path):
    cache_dir = tmp_path / "prices"
    cache_dir.mkdir()
    df = _make_bars()
    df.to_parquet(cache_dir / "SPY_5min_2024-01.parquet")

    broker = MagicMock()
    fetcher = PriceFetcher(broker=broker, cache_dir=cache_dir)
    out = fetcher.fetch(
        symbol="SPY",
        start=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
        end=datetime(2024, 1, 1, 0, 15, tzinfo=timezone.utc),
        timeframe_minutes=5,
    )

    pd.testing.assert_frame_equal(out, df)
    broker.get_historical_bars.assert_not_called()


def test_fetcher_calls_broker_when_cache_missing(tmp_path):
    cache_dir = tmp_path / "prices"
    cache_dir.mkdir()
    bars = _make_bars()

    broker = MagicMock()
    broker.get_historical_bars.return_value = bars

    fetcher = PriceFetcher(broker=broker, cache_dir=cache_dir)
    out = fetcher.fetch(
        symbol="SPY",
        start=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
        end=datetime(2024, 1, 1, 0, 15, tzinfo=timezone.utc),
        timeframe_minutes=5,
    )

    pd.testing.assert_frame_equal(out, bars)
    broker.get_historical_bars.assert_called_once()
    # キャッシュに保存されたか
    cache_files = list(cache_dir.glob("SPY_5min_*.parquet"))
    assert len(cache_files) == 1


def test_fetcher_keys_by_symbol_and_timeframe(tmp_path):
    cache_dir = tmp_path / "prices"
    cache_dir.mkdir()
    bars = _make_bars()

    broker = MagicMock()
    broker.get_historical_bars.return_value = bars

    fetcher = PriceFetcher(broker=broker, cache_dir=cache_dir)
    fetcher.fetch(
        symbol="QQQ",
        start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end=datetime(2024, 1, 1, 0, 15, tzinfo=timezone.utc),
        timeframe_minutes=1,
    )
    cache_files = sorted(p.name for p in cache_dir.glob("*.parquet"))
    assert any("QQQ_1min" in name for name in cache_files)
```

- [ ] **Step 2: テスト実行（失敗確認）**

```bash
cd "/Users/hideakimacbookair/自動トレード"
pytest equity_trading/tests/test_price_fetcher.py -v
```

期待：`ImportError`

- [ ] **Step 3: 実装を書く**

ファイル `equity_trading/src/data/price_fetcher.py`：

```python
"""価格データの取得とローカルキャッシュ（Parquet形式）."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from equity_trading.src.broker.alpaca_client import AlpacaClient


class PriceFetcher:
    """ブローカーから過去価格を取得し、Parquet にキャッシュ."""

    def __init__(self, broker: AlpacaClient, cache_dir: Path | str) -> None:
        self.broker = broker
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def fetch(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe_minutes: int,
    ) -> pd.DataFrame:
        """過去バーを取得.

        ローカルキャッシュ（Parquet）に同条件のファイルがあれば優先利用、
        なければブローカー API を叩いて取得＆保存。
        """
        cache_path = self._cache_key(symbol, start, end, timeframe_minutes)
        if cache_path.exists():
            return pd.read_parquet(cache_path)

        df = self.broker.get_historical_bars(
            symbol=symbol,
            start=start,
            end=end,
            timeframe_minutes=timeframe_minutes,
        )
        df.to_parquet(cache_path)
        return df

    def _cache_key(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe_minutes: int,
    ) -> Path:
        tf_label = f"{timeframe_minutes}min" if timeframe_minutes < 1440 else "1day"
        start_label = start.strftime("%Y-%m-%dT%H%M")
        end_label = end.strftime("%Y-%m-%dT%H%M")
        return self.cache_dir / f"{symbol}_{tf_label}_{start_label}_{end_label}.parquet"
```

- [ ] **Step 4: テスト実行（成功確認）**

```bash
cd "/Users/hideakimacbookair/自動トレード"
pytest equity_trading/tests/test_price_fetcher.py -v
```

期待：`3 passed`

注：1つ目のテスト `test_fetcher_loads_from_cache_when_exists` のキャッシュ命名規則が `_cache_key` と整合するように調整必要。テストの cache ファイル名 `SPY_5min_2024-01.parquet` は実装の命名規則と異なるので、テスト側を修正：

ファイル `equity_trading/tests/test_price_fetcher.py` の `test_fetcher_loads_from_cache_when_exists` を修正：

```python
def test_fetcher_loads_from_cache_when_exists(tmp_path):
    cache_dir = tmp_path / "prices"
    cache_dir.mkdir()
    df = _make_bars()
    # 実装の cache_key 命名規則に合わせる
    cache_name = "SPY_5min_2024-01-01T0000_2024-01-01T0015.parquet"
    df.to_parquet(cache_dir / cache_name)

    broker = MagicMock()
    fetcher = PriceFetcher(broker=broker, cache_dir=cache_dir)
    out = fetcher.fetch(
        symbol="SPY",
        start=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
        end=datetime(2024, 1, 1, 0, 15, tzinfo=timezone.utc),
        timeframe_minutes=5,
    )

    pd.testing.assert_frame_equal(out, df)
    broker.get_historical_bars.assert_not_called()
```

修正後再実行：

```bash
pytest equity_trading/tests/test_price_fetcher.py -v
```

期待：`3 passed`

- [ ] **Step 5: コミット**

```bash
cd "/Users/hideakimacbookair/自動トレード"
git add equity_trading/src/data/price_fetcher.py equity_trading/tests/test_price_fetcher.py
git commit -m "feat(data): add PriceFetcher with Parquet caching"
```

---

### Task 13: SQLite 初期化（Phase 0 用最小スキーマ）

**Files:**
- Create: `equity_trading/src/state/migrations.py`
- Test: `equity_trading/tests/test_migrations.py`

Phase 0 で使うのは parameter テーブルのみ。仕様書 SQLite スキーマの parameters と parameter_history を実装。

- [ ] **Step 1: 失敗するテストを書く**

ファイル `equity_trading/tests/test_migrations.py`：

```python
import sqlite3
from pathlib import Path

import pytest

from equity_trading.src.state.migrations import init_database


def test_init_database_creates_parameters_table(tmp_path):
    db_path = tmp_path / "test.sqlite"
    init_database(db_path)

    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='parameters'"
        )
        rows = cur.fetchall()
    assert len(rows) == 1


def test_init_database_creates_parameter_history_table(tmp_path):
    db_path = tmp_path / "test.sqlite"
    init_database(db_path)

    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='parameter_history'"
        )
        rows = cur.fetchall()
    assert len(rows) == 1


def test_init_database_enables_wal_mode(tmp_path):
    db_path = tmp_path / "test.sqlite"
    init_database(db_path)

    with sqlite3.connect(db_path) as conn:
        cur = conn.execute("PRAGMA journal_mode")
        mode = cur.fetchone()[0]
    assert mode.lower() == "wal"


def test_init_database_idempotent(tmp_path):
    db_path = tmp_path / "test.sqlite"
    init_database(db_path)
    init_database(db_path)  # 2回目もエラーなし

    with sqlite3.connect(db_path) as conn:
        cur = conn.execute("SELECT count(*) FROM parameters")
        count = cur.fetchone()[0]
    assert count == 0  # 重複作成はない
```

- [ ] **Step 2: テスト実行（失敗確認）**

```bash
cd "/Users/hideakimacbookair/自動トレード"
pytest equity_trading/tests/test_migrations.py -v
```

期待：`ImportError`

- [ ] **Step 3: 実装を書く**

ファイル `equity_trading/src/state/migrations.py`：

```python
"""SQLite スキーマ管理（手書きマイグレーション）.

Phase 0 では parameters と parameter_history のみ作成する。
Plan 2/3 で他テーブル（trades, signal_weights など）を追加する。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_PHASE0 = [
    """
    CREATE TABLE IF NOT EXISTS parameters (
        scope TEXT NOT NULL,
        key TEXT NOT NULL,
        value_json TEXT NOT NULL,
        updated_at_utc TIMESTAMP NOT NULL,
        source TEXT NOT NULL,
        PRIMARY KEY (scope, key)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS parameter_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scope TEXT NOT NULL,
        key TEXT NOT NULL,
        old_value TEXT,
        new_value TEXT,
        changed_at_utc TIMESTAMP NOT NULL
    );
    """,
]


def init_database(db_path: Path | str) -> None:
    """SQLite を初期化する。WALモード有効化＆Phase 0スキーマ作成."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA synchronous=NORMAL")
        for ddl in SCHEMA_PHASE0:
            conn.execute(ddl)
        conn.commit()
```

- [ ] **Step 4: テスト実行（成功確認）**

```bash
cd "/Users/hideakimacbookair/自動トレード"
pytest equity_trading/tests/test_migrations.py -v
```

期待：`4 passed`

- [ ] **Step 5: コミット**

```bash
cd "/Users/hideakimacbookair/自動トレード"
git add equity_trading/src/state/migrations.py equity_trading/tests/test_migrations.py
git commit -m "feat(state): add SQLite schema initialization for Phase 0"
```

---

### Task 14: Phase 0 - データコレクター

**Files:**
- Create: `equity_trading/src/phase0/data_collector.py`
- Test: `equity_trading/tests/test_data_collector.py`

5ETF × 過去2年分のデータを集める。

- [ ] **Step 1: 失敗するテストを書く**

ファイル `equity_trading/tests/test_data_collector.py`：

```python
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

from equity_trading.src.phase0.data_collector import collect_phase0_data


def _make_bars(n: int = 3) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": [100.0] * n,
            "high": [101.0] * n,
            "low": [99.0] * n,
            "close": [100.5] * n,
            "volume": [10000] * n,
        },
        index=pd.date_range("2024-01-01", periods=n, freq="5min", tz="UTC"),
    )


def test_collect_calls_fetcher_for_each_etf_and_timeframe(tmp_path):
    fetcher = MagicMock()
    fetcher.fetch.return_value = _make_bars()

    result = collect_phase0_data(
        fetcher=fetcher,
        symbols=["SPY", "QQQ"],
        start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end=datetime(2024, 1, 31, tzinfo=timezone.utc),
        timeframes=[5, 1440],
    )

    # 2 ETF × 2 timeframes = 4 calls
    assert fetcher.fetch.call_count == 4
    assert ("SPY", 5) in result
    assert ("SPY", 1440) in result
    assert ("QQQ", 5) in result
    assert ("QQQ", 1440) in result


def test_collect_returns_dataframes_keyed_by_symbol_timeframe():
    fetcher = MagicMock()
    fetcher.fetch.return_value = _make_bars()

    result = collect_phase0_data(
        fetcher=fetcher,
        symbols=["SPY"],
        start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end=datetime(2024, 1, 2, tzinfo=timezone.utc),
        timeframes=[5],
    )
    assert isinstance(result[("SPY", 5)], pd.DataFrame)
    assert len(result[("SPY", 5)]) == 3
```

- [ ] **Step 2: テスト実行（失敗確認）**

```bash
cd "/Users/hideakimacbookair/自動トレード"
pytest equity_trading/tests/test_data_collector.py -v
```

期待：`ImportError`

- [ ] **Step 3: 実装を書く**

ファイル `equity_trading/src/phase0/data_collector.py`：

```python
"""Phase 0：過去データ収集（5ETF × 複数時間足）."""
from __future__ import annotations

from datetime import datetime
from typing import Sequence

import pandas as pd

from equity_trading.src.data.price_fetcher import PriceFetcher


def collect_phase0_data(
    fetcher: PriceFetcher,
    symbols: Sequence[str],
    start: datetime,
    end: datetime,
    timeframes: Sequence[int],
) -> dict[tuple[str, int], pd.DataFrame]:
    """各 ETF × 各時間足で過去データを取得し、辞書で返す.

    Args:
        fetcher: PriceFetcher インスタンス（キャッシュ機能あり）
        symbols: ETF ティッカーリスト
        start: 開始時刻（UTC tz aware）
        end: 終了時刻（UTC tz aware）
        timeframes: タイムフレーム（分単位）リスト。例 [1, 5, 1440]

    Returns:
        {(symbol, timeframe_minutes): DataFrame} の辞書
    """
    result: dict[tuple[str, int], pd.DataFrame] = {}
    for symbol in symbols:
        for tf in timeframes:
            df = fetcher.fetch(
                symbol=symbol,
                start=start,
                end=end,
                timeframe_minutes=tf,
            )
            result[(symbol, tf)] = df
    return result
```

- [ ] **Step 4: テスト実行（成功確認）**

```bash
cd "/Users/hideakimacbookair/自動トレード"
pytest equity_trading/tests/test_data_collector.py -v
```

期待：`2 passed`

- [ ] **Step 5: コミット**

```bash
cd "/Users/hideakimacbookair/自動トレード"
git add equity_trading/src/phase0/data_collector.py equity_trading/tests/test_data_collector.py
git commit -m "feat(phase0): add data collector for 5-ETF x multi-timeframe historical data"
```

---

### Task 15: Phase 0 - ATR Analyzer

**Files:**
- Create: `equity_trading/src/phase0/atr_analyzer.py`
- Test: `equity_trading/tests/test_atr_analyzer.py`

各ETFのATR(14, 5min)分布を測定し、中央値を「推奨損切り計算」のベースとする。

- [ ] **Step 1: 失敗するテストを書く**

ファイル `equity_trading/tests/test_atr_analyzer.py`：

```python
import numpy as np
import pandas as pd

from equity_trading.src.phase0.atr_analyzer import (
    compute_atr,
    analyze_atr_distribution,
)


def _make_5min_bars(n: int) -> pd.DataFrame:
    np.random.seed(42)
    base = 100.0
    closes = base + np.cumsum(np.random.randn(n) * 0.1)
    highs = closes + np.abs(np.random.randn(n) * 0.05)
    lows = closes - np.abs(np.random.randn(n) * 0.05)
    return pd.DataFrame(
        {
            "open": closes,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": [10000] * n,
        },
        index=pd.date_range("2024-01-01", periods=n, freq="5min", tz="UTC"),
    )


def test_compute_atr_returns_positive_values():
    df = _make_5min_bars(50)
    atr = compute_atr(df, period=14)
    valid = atr.dropna()
    assert (valid > 0).all()


def test_compute_atr_first_period_is_nan():
    df = _make_5min_bars(50)
    atr = compute_atr(df, period=14)
    assert atr.iloc[:13].isna().all()


def test_analyze_atr_distribution_returns_summary():
    df = _make_5min_bars(100)
    summary = analyze_atr_distribution(df, period=14)
    assert "median_pct" in summary
    assert "mean_pct" in summary
    assert "p25_pct" in summary
    assert "p75_pct" in summary
    assert summary["median_pct"] > 0
```

- [ ] **Step 2: テスト実行（失敗確認）**

```bash
cd "/Users/hideakimacbookair/自動トレード"
pytest equity_trading/tests/test_atr_analyzer.py -v
```

期待：`ImportError`

- [ ] **Step 3: 実装を書く**

ファイル `equity_trading/src/phase0/atr_analyzer.py`：

```python
"""Phase 0：ETF別 ATR(14, 5min) の中央値・分布を測定."""
from __future__ import annotations

import pandas as pd


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """ATR (Average True Range) を計算.

    True Range = max(high-low, |high-prev_close|, |low-prev_close|)
    ATR = TRのWilder's smoothing（指数移動平均、α=1/period）

    Args:
        df: high/low/close カラムを持つ DataFrame
        period: 平滑化期間

    Returns:
        ATR の絶対値時系列。最初の period-1 本は NaN。
    """
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    return atr


def analyze_atr_distribution(df: pd.DataFrame, period: int = 14) -> dict[str, float]:
    """ATR分布の要約統計（価格対比%）を返す.

    Returns:
        {
            'median_pct': float,  # ATR中央値 / 平均価格 * 100
            'mean_pct': float,
            'p25_pct': float,
            'p75_pct': float,
        }
    """
    atr = compute_atr(df, period=period).dropna()
    avg_price = df["close"].mean()
    pct = (atr / avg_price) * 100.0

    return {
        "median_pct": float(pct.median()),
        "mean_pct": float(pct.mean()),
        "p25_pct": float(pct.quantile(0.25)),
        "p75_pct": float(pct.quantile(0.75)),
    }
```

- [ ] **Step 4: テスト実行（成功確認）**

```bash
cd "/Users/hideakimacbookair/自動トレード"
pytest equity_trading/tests/test_atr_analyzer.py -v
```

期待：`3 passed`

- [ ] **Step 5: コミット**

```bash
cd "/Users/hideakimacbookair/自動トレード"
git add equity_trading/src/phase0/atr_analyzer.py equity_trading/tests/test_atr_analyzer.py
git commit -m "feat(phase0): add ATR distribution analyzer per ETF"
```

---

### Task 16: Phase 0 - Signal Simulator（閾値スイープ）

**Files:**
- Create: `equity_trading/src/phase0/signal_simulator.py`
- Test: `equity_trading/tests/test_signal_simulator.py`

統合スコア閾値を 0.40〜0.75 で振り、各ETFごとに「シグナル発火回数」「ATR比例損切後の勝率」を簡易バックテストで計測。

- [ ] **Step 1: 失敗するテストを書く**

ファイル `equity_trading/tests/test_signal_simulator.py`：

```python
import numpy as np
import pandas as pd

from equity_trading.src.phase0.signal_simulator import (
    sweep_thresholds,
    simulate_one_threshold,
)


def _make_bars_with_clear_dip(n: int = 200) -> pd.DataFrame:
    """中盤に明確な「過売り→反発」がある合成データ."""
    np.random.seed(42)
    closes = []
    base = 100.0
    for i in range(n):
        if 80 <= i < 100:
            base -= 0.05  # ディップ
        elif 100 <= i < 120:
            base += 0.05  # リバウンド
        closes.append(base + np.random.randn() * 0.02)
    closes = np.array(closes)
    return pd.DataFrame(
        {
            "open": closes,
            "high": closes + 0.02,
            "low": closes - 0.02,
            "close": closes,
            "volume": [10000] * n,
        },
        index=pd.date_range("2024-01-01", periods=n, freq="5min", tz="UTC"),
    )


def test_simulate_one_threshold_returns_summary():
    bars = _make_bars_with_clear_dip(200)
    daily = bars.resample("1D").last().ffill()
    summary = simulate_one_threshold(
        bars_5min=bars,
        daily=daily,
        threshold=0.5,
        atr_pct=0.10,
        stop_multiplier=1.5,
        target_multiplier=2.4,
    )
    assert "trade_count" in summary
    assert "win_count" in summary
    assert "win_rate" in summary
    # 0 取引のときは win_rate = NaN
    if summary["trade_count"] > 0:
        assert 0.0 <= summary["win_rate"] <= 1.0


def test_sweep_thresholds_returns_dataframe():
    bars = _make_bars_with_clear_dip(200)
    daily = bars.resample("1D").last().ffill()
    df_results = sweep_thresholds(
        bars_5min=bars,
        daily=daily,
        thresholds=[0.40, 0.50, 0.60, 0.70],
        atr_pct=0.10,
    )
    assert isinstance(df_results, pd.DataFrame)
    assert "threshold" in df_results.columns
    assert "trade_count" in df_results.columns
    assert "win_rate" in df_results.columns
    assert len(df_results) == 4
```

- [ ] **Step 2: テスト実行（失敗確認）**

```bash
cd "/Users/hideakimacbookair/自動トレード"
pytest equity_trading/tests/test_signal_simulator.py -v
```

期待：`ImportError`

- [ ] **Step 3: 実装を書く**

ファイル `equity_trading/src/phase0/signal_simulator.py`：

```python
"""Phase 0：シグナル発火頻度・勝率を簡易シミュレートする閾値スイープ."""
from __future__ import annotations

import math
from typing import Sequence

import numpy as np
import pandas as pd

from equity_trading.src.data.feature_builder import (
    compute_rsi,
    compute_bollinger_bands,
    compute_vwap,
    compute_volume_ratio,
    compute_momentum_reversal,
    compute_sma,
)


# 仕様書 Strategy Logic セクション準拠の初期重み
DEFAULT_WEIGHTS = {
    "rsi": 0.30,
    "bb": 0.25,
    "vwap": 0.25,
    "volume": 0.10,
    "momentum": 0.10,
}


def _compute_combined_score(bars: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    """5シグナルの統合スコアを各バーで計算."""
    rsi = compute_rsi(bars["close"], period=14)
    rsi_score = ((30.0 - rsi) / 30.0).clip(lower=0.0, upper=1.0)

    upper, middle, lower = compute_bollinger_bands(bars["close"], period=20, num_std=2.0)
    sigma = (upper - middle) / 2.0
    bb_score = ((lower - bars["close"]) / sigma).clip(lower=0.0, upper=1.0).fillna(0)

    # VWAP の起点：日付ベース。ここでは簡易で全体累積を使う（Phase 0シミュレータ簡略化）
    vwap = compute_vwap(bars)
    vwap_dev = ((vwap - bars["close"]) / bars["close"]).clip(lower=0.0, upper=1.0).fillna(0)

    vol_ratio = compute_volume_ratio(bars["volume"], period=20)
    vol_score = ((vol_ratio / 2.0).clip(lower=0.0, upper=1.0)).fillna(0)
    vol_score = vol_score.where(vol_ratio >= 1.5, 0.0)

    mom_rev = compute_momentum_reversal(bars["close"], lookback=3)
    mom_score = mom_rev.astype(float).fillna(0.0)

    combined = (
        weights["rsi"] * rsi_score.fillna(0)
        + weights["bb"] * bb_score
        + weights["vwap"] * vwap_dev
        + weights["volume"] * vol_score
        + weights["momentum"] * mom_score
    )
    return combined


def simulate_one_threshold(
    bars_5min: pd.DataFrame,
    daily: pd.DataFrame,
    threshold: float,
    atr_pct: float,
    stop_multiplier: float = 1.5,
    target_multiplier: float = 2.4,
    weights: dict[str, float] | None = None,
    cost_pct: float = 0.10,
) -> dict[str, float]:
    """1 つの閾値で簡易バックテスト.

    Args:
        bars_5min: 5分足 OHLCV
        daily: 日足（200日MAトレンドフィルター用）
        threshold: 統合スコア閾値
        atr_pct: ETFのATR中央値（%、価格対比）
        stop_multiplier: ATR乗数（損切り幅 = atr_pct × stop_multiplier）
        target_multiplier: ATR乗数（利確幅 = atr_pct × target_multiplier）
        weights: シグナル重み（None で DEFAULT_WEIGHTS 使用）
        cost_pct: 往復コスト % （価格対比、利確/損切から差し引かれる）

    Returns:
        {
          'trade_count': int,
          'win_count': int,
          'win_rate': float,
          'avg_pnl_pct': float,  # 取引あたり平均損益（%）
        }
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS

    # 1. 200日MAトレンドフィルター
    sma200 = compute_sma(daily["close"], period=200)
    daily_above_ma = (daily["close"] > sma200).reindex(
        bars_5min.index, method="pad"
    ).fillna(False)

    # 2. 統合スコア
    score = _compute_combined_score(bars_5min, weights)

    # 3. エントリー判定（トレンドフィルター + score閾値）
    entry_signal = (score >= threshold) & daily_above_ma

    # 4. 各エントリーシグナルで「次バー始値（=close）でエントリー、利確/損切まで保持」
    stop_pct = atr_pct * stop_multiplier / 100.0  # 例 0.10 × 1.5 = 0.15% → 0.0015
    target_pct = atr_pct * target_multiplier / 100.0

    closes = bars_5min["close"].values
    n = len(closes)
    trades: list[float] = []
    in_position = False
    entry_idx = -1
    entry_price = 0.0

    for i in range(n - 1):
        if not in_position and bool(entry_signal.iloc[i]):
            in_position = True
            entry_idx = i + 1  # 次バーでエントリー
            if entry_idx >= n:
                break
            entry_price = closes[entry_idx]
        elif in_position:
            current = closes[i]
            stop_price = entry_price * (1 - stop_pct)
            target_price = entry_price * (1 + target_pct)
            if current <= stop_price:
                trades.append(-stop_pct - cost_pct / 100.0)
                in_position = False
            elif current >= target_price:
                trades.append(target_pct - cost_pct / 100.0)
                in_position = False
            elif i - entry_idx > 78:  # 6時間 (78 × 5分) で時間切れ強制決済
                pnl_pct = (current - entry_price) / entry_price - cost_pct / 100.0
                trades.append(pnl_pct)
                in_position = False

    trade_count = len(trades)
    if trade_count == 0:
        return {
            "trade_count": 0,
            "win_count": 0,
            "win_rate": float("nan"),
            "avg_pnl_pct": float("nan"),
        }

    wins = sum(1 for t in trades if t > 0)
    return {
        "trade_count": trade_count,
        "win_count": wins,
        "win_rate": wins / trade_count,
        "avg_pnl_pct": float(np.mean(trades) * 100.0),
    }


def sweep_thresholds(
    bars_5min: pd.DataFrame,
    daily: pd.DataFrame,
    thresholds: Sequence[float],
    atr_pct: float,
    stop_multiplier: float = 1.5,
    target_multiplier: float = 2.4,
    weights: dict[str, float] | None = None,
    cost_pct: float = 0.10,
) -> pd.DataFrame:
    """複数の閾値をスイープして結果を DataFrame で返す."""
    rows: list[dict] = []
    for th in thresholds:
        s = simulate_one_threshold(
            bars_5min=bars_5min,
            daily=daily,
            threshold=th,
            atr_pct=atr_pct,
            stop_multiplier=stop_multiplier,
            target_multiplier=target_multiplier,
            weights=weights,
            cost_pct=cost_pct,
        )
        s["threshold"] = th
        rows.append(s)
    return pd.DataFrame(rows)[
        ["threshold", "trade_count", "win_count", "win_rate", "avg_pnl_pct"]
    ]
```

- [ ] **Step 4: テスト実行（成功確認）**

```bash
cd "/Users/hideakimacbookair/自動トレード"
pytest equity_trading/tests/test_signal_simulator.py -v
```

期待：`2 passed`

注：合成データなので「明確な過売り→反発」が含まれていてもシグナル条件が複合的なので発火回数が0になるケースもある。テスト基準は「形が正しいか」のみで、具体的な勝率値は問わない。

- [ ] **Step 5: コミット**

```bash
cd "/Users/hideakimacbookair/自動トレード"
git add equity_trading/src/phase0/signal_simulator.py equity_trading/tests/test_signal_simulator.py
git commit -m "feat(phase0): add signal simulator with threshold sweep"
```

---

### Task 17: Phase 0 - Report Generator

**Files:**
- Create: `equity_trading/src/phase0/report_generator.py`
- Test: `equity_trading/tests/test_report_generator.py`

ATR分布結果と閾値スイープ結果を Markdown レポートに整形。

- [ ] **Step 1: 失敗するテストを書く**

ファイル `equity_trading/tests/test_report_generator.py`：

```python
from pathlib import Path

import pandas as pd

from equity_trading.src.phase0.report_generator import generate_calibration_report


def test_report_contains_atr_table_and_threshold_results(tmp_path):
    atr_results = {
        "SPY": {"median_pct": 0.10, "mean_pct": 0.12, "p25_pct": 0.08, "p75_pct": 0.14},
        "QQQ": {"median_pct": 0.13, "mean_pct": 0.15, "p25_pct": 0.10, "p75_pct": 0.18},
    }
    sweep_results = {
        "SPY": pd.DataFrame({
            "threshold": [0.5, 0.6],
            "trade_count": [120, 50],
            "win_count": [70, 30],
            "win_rate": [0.583, 0.6],
            "avg_pnl_pct": [0.05, 0.08],
        }),
        "QQQ": pd.DataFrame({
            "threshold": [0.5, 0.6],
            "trade_count": [100, 40],
            "win_count": [55, 22],
            "win_rate": [0.55, 0.55],
            "avg_pnl_pct": [0.04, 0.06],
        }),
    }
    out_path = tmp_path / "calibration_report.md"
    generate_calibration_report(
        atr_results=atr_results,
        sweep_results=sweep_results,
        output_path=out_path,
        period_start="2024-01-01",
        period_end="2024-12-31",
    )
    content = out_path.read_text()
    assert "Phase 0" in content
    assert "ATR" in content
    assert "SPY" in content
    assert "QQQ" in content
    assert "0.10" in content  # SPY median_pct
    assert "Threshold" in content or "閾値" in content


def test_report_recommends_threshold_with_highest_expected_value(tmp_path):
    atr_results = {"SPY": {"median_pct": 0.10, "mean_pct": 0.10, "p25_pct": 0.08, "p75_pct": 0.12}}
    sweep_results = {
        "SPY": pd.DataFrame({
            "threshold": [0.5, 0.6, 0.7],
            "trade_count": [200, 100, 30],
            "win_count": [105, 55, 18],
            "win_rate": [0.525, 0.55, 0.60],
            "avg_pnl_pct": [0.02, 0.05, 0.10],
        }),
    }
    out_path = tmp_path / "report.md"
    generate_calibration_report(
        atr_results=atr_results,
        sweep_results=sweep_results,
        output_path=out_path,
        period_start="2024-01-01",
        period_end="2024-12-31",
    )
    content = out_path.read_text()
    # 期待値（avg_pnl_pct × trade_count）が最大の閾値が推奨
    # 0.5: 0.02*200=4.0、0.6: 0.05*100=5.0、0.7: 0.10*30=3.0 → 0.6 が推奨
    assert "0.6" in content
```

- [ ] **Step 2: テスト実行（失敗確認）**

```bash
cd "/Users/hideakimacbookair/自動トレード"
pytest equity_trading/tests/test_report_generator.py -v
```

期待：`ImportError`

- [ ] **Step 3: 実装を書く**

ファイル `equity_trading/src/phase0/report_generator.py`：

```python
"""Phase 0：キャリブレーション結果の Markdown レポート生成."""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def generate_calibration_report(
    atr_results: dict[str, dict[str, float]],
    sweep_results: dict[str, pd.DataFrame],
    output_path: Path | str,
    period_start: str,
    period_end: str,
) -> None:
    """ATR と閾値スイープの結果を Markdown レポートに書き出す.

    Args:
        atr_results: {symbol: {'median_pct', 'mean_pct', 'p25_pct', 'p75_pct'}}
        sweep_results: {symbol: DataFrame(threshold, trade_count, win_rate, avg_pnl_pct, ...)}
        output_path: 出力ファイルパス
        period_start, period_end: データ期間（表示用）
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append("# Phase 0 Calibration Report")
    lines.append("")
    lines.append(f"**Period:** {period_start} 〜 {period_end}")
    lines.append("")
    lines.append("## ETF別 ATR(14, 5min) 分布（価格対比 %）")
    lines.append("")
    lines.append("| ETF | Median | Mean | P25 | P75 | 推奨損切(×1.5) | 推奨利確(×2.4) |")
    lines.append("|-----|--------|------|-----|-----|---------------|----------------|")
    for sym, atr in atr_results.items():
        med = atr["median_pct"]
        lines.append(
            f"| {sym} | {med:.3f}% | {atr['mean_pct']:.3f}% | "
            f"{atr['p25_pct']:.3f}% | {atr['p75_pct']:.3f}% | "
            f"{med*1.5:.3f}% | {med*2.4:.3f}% |"
        )
    lines.append("")

    lines.append("## ETF別 統合スコア閾値スイープ結果")
    for sym, df in sweep_results.items():
        lines.append("")
        lines.append(f"### {sym}")
        lines.append("")
        lines.append("| Threshold | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |")
        lines.append("|-----------|--------|------|----------|---------|----------------------|")
        for _, row in df.iterrows():
            ev = row["avg_pnl_pct"] * row["trade_count"]
            lines.append(
                f"| {row['threshold']:.2f} | {int(row['trade_count'])} | "
                f"{int(row['win_count'])} | {row['win_rate']:.3f} | "
                f"{row['avg_pnl_pct']:.3f}% | {ev:.2f} |"
            )
        # 推奨閾値：期待値（avg_pnl_pct × trade_count）最大
        df_valid = df[df["trade_count"] > 0].copy()
        if len(df_valid) > 0:
            df_valid["expected"] = df_valid["avg_pnl_pct"] * df_valid["trade_count"]
            best = df_valid.loc[df_valid["expected"].idxmax()]
            lines.append("")
            lines.append(
                f"**推奨閾値（期待値最大）:** {best['threshold']:.2f}"
                f" — Win Rate {best['win_rate']:.3f}, Trades {int(best['trade_count'])}"
            )

    lines.append("")
    lines.append("## 次のステップ")
    lines.append("")
    lines.append("1. このレポートを人間がレビュー")
    lines.append("2. 推奨閾値・推奨ATR乗数を `phase0/recommended_config.json` に書き出す")
    lines.append("3. その値を `equity_trading/data/trades.sqlite` の `parameters` テーブルに投入")
    lines.append("4. Plan 2 の実装に進む")

    output_path.write_text("\n".join(lines), encoding="utf-8")
```

- [ ] **Step 4: テスト実行（成功確認）**

```bash
cd "/Users/hideakimacbookair/自動トレード"
pytest equity_trading/tests/test_report_generator.py -v
```

期待：`2 passed`

- [ ] **Step 5: コミット**

```bash
cd "/Users/hideakimacbookair/自動トレード"
git add equity_trading/src/phase0/report_generator.py equity_trading/tests/test_report_generator.py
git commit -m "feat(phase0): add Markdown calibration report generator"
```

---

### Task 18: Phase 0 統合スクリプト（CLI）

**Files:**
- Create: `equity_trading/scripts/run_phase0.py`
- Test: `equity_trading/tests/test_run_phase0.py`

すべてを統合する CLI。実行すると `phase0/calibration_report.md` が生成される。

- [ ] **Step 1: 失敗するテストを書く**

ファイル `equity_trading/tests/test_run_phase0.py`：

```python
"""Phase 0 統合スクリプトの E2E テスト（モック使用）."""
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest


def _make_synthetic_bars(n: int, freq: str = "5min") -> pd.DataFrame:
    np.random.seed(42)
    closes = 100.0 + np.cumsum(np.random.randn(n) * 0.1)
    return pd.DataFrame(
        {
            "open": closes,
            "high": closes + 0.05,
            "low": closes - 0.05,
            "close": closes,
            "volume": [10000] * n,
        },
        index=pd.date_range("2024-01-01", periods=n, freq=freq, tz="UTC"),
    )


def test_run_phase0_e2e_creates_report(tmp_path, monkeypatch):
    # 環境変数モック
    monkeypatch.setenv("ALPACA_API_KEY", "PKTEST")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "secret")
    monkeypatch.setenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "data" / "prices").mkdir(parents=True)
    (project_root / "phase0").mkdir()

    # AlpacaClient をモック
    bars_5min = _make_synthetic_bars(500, freq="5min")
    bars_daily = _make_synthetic_bars(500, freq="1D")

    with patch(
        "equity_trading.src.broker.alpaca_client.StockHistoricalDataClient"
    ) as mock_data, patch(
        "equity_trading.src.broker.alpaca_client.TradingClient"
    ):
        # broker.get_historical_bars が呼ばれた時の戻り値
        def fake_bars(*args, **kwargs):
            res = MagicMock()
            res.df = bars_5min if kwargs.get("timeframe", "").__class__.__name__ != "TimeFrame" else bars_5min
            return res

        mock_data.return_value.get_stock_bars.side_effect = lambda req: type(
            "X", (), {"df": bars_5min if str(req.timeframe).startswith("5") else bars_daily}
        )()

        from equity_trading.scripts.run_phase0 import main

        report_path = project_root / "phase0" / "calibration_report.md"
        cache_dir = project_root / "data" / "prices"

        # 短い期間でテスト
        main(
            symbols=["SPY"],
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2024, 1, 31, tzinfo=timezone.utc),
            thresholds=[0.5, 0.6],
            cache_dir=cache_dir,
            report_path=report_path,
        )

    assert report_path.exists()
    content = report_path.read_text()
    assert "SPY" in content
    assert "Phase 0" in content
```

- [ ] **Step 2: テスト実行（失敗確認）**

```bash
cd "/Users/hideakimacbookair/自動トレード"
pytest equity_trading/tests/test_run_phase0.py -v
```

期待：`ImportError`

- [ ] **Step 3: 実装を書く**

ファイル `equity_trading/scripts/run_phase0.py`：

```python
"""Phase 0 キャリブレーション統合スクリプト.

実行：
    cd /Users/hideakimacbookair/自動トレード/equity_trading
    python -m scripts.run_phase0

または引数を渡したい場合：
    python scripts/run_phase0.py
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Sequence

# プロジェクトルートを sys.path に追加
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from equity_trading.src.broker.alpaca_client import AlpacaClient
from equity_trading.src.config import load_config
from equity_trading.src.data.price_fetcher import PriceFetcher
from equity_trading.src.monitor.logger import setup_logger
from equity_trading.src.phase0.atr_analyzer import analyze_atr_distribution
from equity_trading.src.phase0.data_collector import collect_phase0_data
from equity_trading.src.phase0.report_generator import generate_calibration_report
from equity_trading.src.phase0.signal_simulator import sweep_thresholds


DEFAULT_SYMBOLS = ["SPY", "QQQ", "IWM", "DIA", "XLK"]
DEFAULT_THRESHOLDS = [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75]


def main(
    symbols: Sequence[str] = DEFAULT_SYMBOLS,
    start: datetime | None = None,
    end: datetime | None = None,
    thresholds: Sequence[float] = DEFAULT_THRESHOLDS,
    cache_dir: Path | None = None,
    report_path: Path | None = None,
) -> int:
    log = setup_logger("equity_trading.phase0")

    # デフォルト：過去2年
    if end is None:
        end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    if start is None:
        start = end - timedelta(days=730)

    project_root = Path(__file__).resolve().parents[1]
    if cache_dir is None:
        cache_dir = project_root / "data" / "prices"
    if report_path is None:
        report_path = project_root / "phase0" / "calibration_report.md"

    log.info("phase0_start", extra={"symbols": list(symbols), "start": start.isoformat(), "end": end.isoformat()})

    # 設定（ALPACA_API_KEY 等を取得）
    cfg = load_config()
    broker = AlpacaClient(
        api_key=cfg.alpaca_api_key,
        secret_key=cfg.alpaca_secret_key,
        base_url=cfg.alpaca_base_url,
    )
    fetcher = PriceFetcher(broker=broker, cache_dir=cache_dir)

    # 1. データ収集（5分足 + 日足）
    log.info("phase0_collecting_data")
    data_map = collect_phase0_data(
        fetcher=fetcher,
        symbols=symbols,
        start=start,
        end=end,
        timeframes=[5, 1440],
    )

    # 2. ETF別 ATR 分析
    log.info("phase0_analyzing_atr")
    atr_results: dict[str, dict[str, float]] = {}
    for sym in symbols:
        bars_5 = data_map[(sym, 5)]
        atr_results[sym] = analyze_atr_distribution(bars_5, period=14)

    # 3. ETF別 閾値スイープ
    log.info("phase0_sweeping_thresholds")
    sweep_results: dict[str, "pd.DataFrame"] = {}  # type: ignore[name-defined]
    for sym in symbols:
        bars_5 = data_map[(sym, 5)]
        daily = data_map[(sym, 1440)]
        atr_pct = atr_results[sym]["median_pct"]
        sweep = sweep_thresholds(
            bars_5min=bars_5,
            daily=daily,
            thresholds=thresholds,
            atr_pct=atr_pct,
        )
        sweep_results[sym] = sweep

    # 4. レポート生成
    log.info("phase0_generating_report", extra={"output": str(report_path)})
    generate_calibration_report(
        atr_results=atr_results,
        sweep_results=sweep_results,
        output_path=report_path,
        period_start=start.date().isoformat(),
        period_end=end.date().isoformat(),
    )

    log.info("phase0_done", extra={"report_path": str(report_path)})
    print(f"\n✅ Phase 0 完了。レポート：{report_path}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 0 キャリブレーション実行")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=DEFAULT_SYMBOLS,
        help="対象ETFティッカー（デフォルト: 5本）",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=730,
        help="過去何日分のデータを取るか（デフォルト730=2年）",
    )
    args = parser.parse_args()

    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=args.days)
    sys.exit(main(symbols=args.symbols, start=start, end=end))
```

- [ ] **Step 4: テスト実行（成功確認）**

```bash
cd "/Users/hideakimacbookair/自動トレード"
pytest equity_trading/tests/test_run_phase0.py -v
```

期待：`1 passed`

注：このE2Eテストはモックが複雑なので、本物の Alpaca を叩く統合テストは Task 19 で別途行う。

- [ ] **Step 5: コミット**

```bash
cd "/Users/hideakimacbookair/自動トレード"
git add equity_trading/scripts/run_phase0.py equity_trading/tests/test_run_phase0.py
git commit -m "feat(phase0): add main CLI integrating data collection, ATR, sweep, report"
```

---

### Task 19: 全テスト実行と Phase 0 実機実行確認

**Files:** なし（実機で動作確認のみ）

これまで作った全コードを統合し、実際に Alpaca Paper の鍵を使って Phase 0 を走らせ、レポートが生成されることを確認する。

- [ ] **Step 1: 全テストを実行**

```bash
cd "/Users/hideakimacbookair/自動トレード"
pytest equity_trading/tests/ -v
```

期待：すべて pass。失敗があれば修正。

- [ ] **Step 2: `.env` を作る**

```bash
cd "/Users/hideakimacbookair/自動トレード/equity_trading"
cp .env.example .env
```

`.env` を編集して Alpaca のキーを設定（alpaca_test/.env からコピーしてOK）。

確認：
```bash
grep -E "^ALPACA_(API|SECRET)" "/Users/hideakimacbookair/自動トレード/equity_trading/.env" | head -2
```

期待：実際の鍵がプレースホルダーでなく入っている。

- [ ] **Step 3: 短期間（30日）で Phase 0 を実行**

最初は2年ではなく30日でテスト：

```bash
cd "/Users/hideakimacbookair/自動トレード/equity_trading"
python scripts/run_phase0.py --days 30
```

期待：
- API 呼び出しに数秒〜1分
- `phase0/calibration_report.md` が生成される
- ターミナルに `✅ Phase 0 完了。レポート：...` と表示

- [ ] **Step 4: レポートを確認**

```bash
cat "/Users/hideakimacbookair/自動トレード/equity_trading/phase0/calibration_report.md"
```

確認項目：
- 5ETF（SPY/QQQ/IWM/DIA/XLK）すべての ATR が表示されている
- 各ETFの閾値スイープ結果が表示されている
- 推奨閾値が選ばれている

- [ ] **Step 5: 本番（2年分）で Phase 0 を実行**

```bash
cd "/Users/hideakimacbookair/自動トレード/equity_trading"
python scripts/run_phase0.py
```

期待：データ取得に数分〜数十分。Alpaca Free plan のレート制限（200 req/min）に注意。

レポート確認：
```bash
ls -la "/Users/hideakimacbookair/自動トレード/equity_trading/phase0/"
open "/Users/hideakimacbookair/自動トレード/equity_trading/phase0/calibration_report.md"
```

- [ ] **Step 6: 結果のサマリーを Plan 1 完了報告として残す**

```bash
cd "/Users/hideakimacbookair/自動トレード/equity_trading"
echo "Phase 0 first run completed: $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> phase0/run_log.txt
git add phase0/calibration_report.md phase0/run_log.txt
git commit -m "feat(phase0): generate first calibration report from 2 years of data"
```

注：`calibration_report.md` 自体は機微情報を含まないので gitに入れて良い。`data/historical/`、`data/prices/` は .gitignore で除外済み。

---

## Plan 1 完了条件

- [ ] 全 19 タスク完了
- [ ] `pytest equity_trading/tests/` で全テスト pass
- [ ] `equity_trading/phase0/calibration_report.md` が生成され、5ETF分のATR・閾値結果・推奨が記載されている
- [ ] レポートをユーザーがレビューし、Plan 2 への進行可否を判断する

## Plan 2 への引き渡し情報

Plan 1 で確定した値（Plan 2 で使う）：
1. ETF別 ATR(14, 5min) 中央値 → 各ETFの初期損切り/利確幅
2. 推奨統合スコア閾値 → エントリー判定の初期値
3. 各閾値での想定勝率・取引頻度 → Paper運用の合格基準
4. 想定年率リターン分布 → promotion_gate の基準

これらが `phase0/calibration_report.md` に記載され、Plan 2 着手時に `phase0/recommended_config.json` に書き出して `parameters` テーブルへ投入する。

---

## Self-Review チェック

- [x] **仕様カバー**: 仕様書 `Phase 0: Empirical Calibration` セクションのすべての要素（データ収集、ATR分析、シグナルシミュレータ、レポート生成）を Task 14-18 でカバー
- [x] **プレースホルダー無し**: TBD/TODO/「TBD」「実装は後」の類なし
- [x] **型一貫性**: `EtfMeta`、`PriceFetcher`、`AlpacaClient` の API がタスク間で一致
- [x] **コミット境界**: 各タスク終わりに必ずコミット
- [x] **TDD**: 各タスクは「テスト → fail → 実装 → pass → commit」
