# Plan 1.5: Multi-Strategy Phase 0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Plan 1 で実装した Phase 0 を拡張し、**5つの異なる戦略** を同じ過去データで並行検証して、データに基づき最良戦略を選定できる比較レポートを出力する。

**Architecture:** 戦略を共通インターフェース（Protocol/ABC）に統一し、シミュレータは戦略を「差し替え可能」にする。1回の Phase 0 実行で5戦略すべてを評価し、ETF × 戦略 × パラメータの3次元比較表を出力。

**Tech Stack:** Python 3.12、pandas、scipy、pytest（既存スタックの上に追加なし）

**前提：** Plan 1 完了済み（commit `46982c0`）。`equity_trading/src/` に基盤コード、`phase0/` に Phase 0 モジュール群が存在。

**仕様書参照：** `docs/superpowers/specs/2026-05-02-equity-intraday-reversion-bot-design.md` v2.0.1

---

## 5つの戦略仕様

| # | 戦略名 | 考え方 | エントリー条件 |
|---|--------|--------|----------------|
| A | **MeanReversion**（既存） | 「下がりすぎたら戻る」 | RSI/BB/VWAP/出来高/勢い反転 5 シグナル合致スコア ≥ 閾値 + 200d MA 上 |
| B | **TrendFollow** | 「上がってる方向に乗る」 | SPY 200d MA 上 + 直近 20 日高値更新 + RSI > 50 |
| C | **MomentumBreakout** | 「ボラ突破は流れの始まり」 | 直近 N 本（例 78本=6.5h）高値ブレイク + 出来高 1.5 倍以上 + 200d MA 上 |
| D | **EnvDependentReversion** | 「平均回帰 + 状況フィルター」 | 戦略 A の条件 + 「オープン後30分以上、クローズ前30分以上、当日下落 < 1%」 |
| E | **MultiTimeframe** | 「複数時間軸合致」 | 5min RSI < 30 **かつ** 15min RSI < 35 **かつ** 1h RSI < 40 + 200d MA 上 |

各戦略は同じインターフェース `compute_entry_signal(bars_5min, daily, params) -> pd.Series[bool]` を実装する。

---

### Task 1: 戦略の共通インターフェース（StrategyBase）

**Files:**
- Create: `equity_trading/src/strategy/base.py`
- Test: `equity_trading/tests/test_strategy_base.py`

- [ ] **Step 1: 失敗するテストを書く**

ファイル `equity_trading/tests/test_strategy_base.py`：

```python
import pandas as pd
import pytest

from equity_trading.src.strategy.base import TradingStrategy, StrategyResult


def test_strategy_base_is_abstract():
    with pytest.raises(TypeError):
        TradingStrategy()


def test_strategy_subclass_must_implement_compute_entry_signal():
    class IncompleteStrategy(TradingStrategy):
        name = "incomplete"

    with pytest.raises(TypeError):
        IncompleteStrategy()


def test_strategy_subclass_with_implementation_works():
    class DummyStrategy(TradingStrategy):
        name = "dummy"

        def compute_entry_signal(self, bars_5min, daily, atr_pct, params):
            return pd.Series([False] * len(bars_5min), index=bars_5min.index)

    s = DummyStrategy()
    assert s.name == "dummy"
    bars = pd.DataFrame(
        {"close": [100.0, 101.0]},
        index=pd.date_range("2024-01-01", periods=2, freq="5min", tz="UTC"),
    )
    daily = pd.DataFrame(
        {"close": [100.0]},
        index=pd.date_range("2024-01-01", periods=1, freq="1D", tz="UTC"),
    )
    signal = s.compute_entry_signal(bars, daily, atr_pct=0.10, params={})
    assert len(signal) == 2


def test_strategy_result_dataclass():
    r = StrategyResult(
        strategy_name="test",
        symbol="SPY",
        threshold=0.6,
        trade_count=10,
        win_count=6,
        win_rate=0.6,
        avg_pnl_pct=0.05,
    )
    assert r.expected_value == pytest.approx(10 * 0.05)
```

- [ ] **Step 2: テスト失敗確認**

```bash
cd "/Users/hideakimacbookair/自動トレード"
python3 -m pytest equity_trading/tests/test_strategy_base.py -v 2>&1 | tail -10
```

期待：`ImportError`

- [ ] **Step 3: 実装**

ファイル `equity_trading/src/strategy/base.py`：

```python
"""戦略の共通インターフェース."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import pandas as pd


class TradingStrategy(ABC):
    """全戦略が実装する共通インターフェース.

    Subclass attributes:
        name: 戦略の一意な識別子（例 'mean_reversion', 'trend_follow'）

    Subclass methods:
        compute_entry_signal: エントリーシグナル時系列を返す（True=エントリー）
    """

    name: str = ""

    @abstractmethod
    def compute_entry_signal(
        self,
        bars_5min: pd.DataFrame,
        daily: pd.DataFrame,
        atr_pct: float,
        params: dict,
    ) -> pd.Series:
        """エントリーシグナルを計算.

        Args:
            bars_5min: 5分足 OHLCV
            daily: 日足 OHLCV（200d MA トレンドフィルター用）
            atr_pct: ETFのATR中央値（%）。利用するかは戦略次第
            params: 戦略固有のパラメータ辞書

        Returns:
            bool型のSeries（True=エントリー、False=何もしない）
        """
        ...


@dataclass(frozen=True)
class StrategyResult:
    """1戦略 × 1ETF × 1閾値の検証結果."""

    strategy_name: str
    symbol: str
    threshold: float          # 戦略によっては意味なし（その場合 0.0）
    trade_count: int
    win_count: int
    win_rate: float
    avg_pnl_pct: float

    @property
    def expected_value(self) -> float:
        """期待値 = 取引数 × 平均損益."""
        return self.trade_count * self.avg_pnl_pct
```

- [ ] **Step 4: テストパス**

```bash
cd "/Users/hideakimacbookair/自動トレード"
python3 -m pytest equity_trading/tests/test_strategy_base.py -v 2>&1 | tail -10
```

期待：`4 passed`

- [ ] **Step 5: コミット**

```bash
cd "/Users/hideakimacbookair/自動トレード"
git add equity_trading/src/strategy/base.py equity_trading/tests/test_strategy_base.py
git commit -m "feat(strategy): add TradingStrategy abstract base and StrategyResult"
```

---

### Task 2: 戦略A（MeanReversion）を新インターフェースで実装

**Files:**
- Create: `equity_trading/src/strategy/strategies/__init__.py`
- Create: `equity_trading/src/strategy/strategies/mean_reversion.py`
- Test: `equity_trading/tests/test_strategy_mean_reversion.py`

- [ ] **Step 1: __init__.py 作成**

```bash
mkdir -p equity_trading/src/strategy/strategies
touch equity_trading/src/strategy/strategies/__init__.py
```

- [ ] **Step 2: 失敗するテストを書く**

ファイル `equity_trading/tests/test_strategy_mean_reversion.py`：

```python
import numpy as np
import pandas as pd

from equity_trading.src.strategy.strategies.mean_reversion import MeanReversionStrategy


def _make_bars(n: int) -> pd.DataFrame:
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
        index=pd.date_range("2024-01-01", periods=n, freq="5min", tz="UTC"),
    )


def _make_daily_above_ma(n: int = 250) -> pd.DataFrame:
    """200d MAより上にある日足."""
    closes = pd.Series(100.0 + np.linspace(0, 20, n))
    return pd.DataFrame(
        {"close": closes.values},
        index=pd.date_range("2023-01-01", periods=n, freq="1D", tz="UTC"),
    )


def test_mean_reversion_has_correct_name():
    s = MeanReversionStrategy()
    assert s.name == "mean_reversion"


def test_mean_reversion_returns_bool_series():
    s = MeanReversionStrategy()
    bars = _make_bars(100)
    daily = _make_daily_above_ma()
    signal = s.compute_entry_signal(bars, daily, atr_pct=0.10, params={"threshold": 0.5})
    assert len(signal) == len(bars)
    assert signal.dtype == bool or signal.dtype == "bool"


def test_mean_reversion_blocks_when_below_200ma():
    """SPY が 200d MA 下では取引せず."""
    s = MeanReversionStrategy()
    bars = _make_bars(100)
    daily_below = pd.DataFrame(
        {"close": [50.0] * 250},  # 200d MA より下
        index=pd.date_range("2023-01-01", periods=250, freq="1D", tz="UTC"),
    )
    signal = s.compute_entry_signal(bars, daily_below, atr_pct=0.10, params={"threshold": 0.5})
    assert not signal.any()
```

- [ ] **Step 3: テスト失敗確認**

```bash
cd "/Users/hideakimacbookair/自動トレード"
python3 -m pytest equity_trading/tests/test_strategy_mean_reversion.py -v 2>&1 | tail -10
```

期待：`ImportError`

- [ ] **Step 4: 実装**

ファイル `equity_trading/src/strategy/strategies/mean_reversion.py`：

```python
"""平均回帰戦略（マルチシグナル合致）."""
from __future__ import annotations

import pandas as pd

from equity_trading.src.data.feature_builder import (
    compute_bollinger_bands,
    compute_momentum_reversal,
    compute_rsi,
    compute_sma,
    compute_volume_ratio,
    compute_vwap,
)
from equity_trading.src.strategy.base import TradingStrategy


DEFAULT_WEIGHTS = {
    "rsi": 0.30,
    "bb": 0.25,
    "vwap": 0.25,
    "volume": 0.10,
    "momentum": 0.10,
}


class MeanReversionStrategy(TradingStrategy):
    """RSI/BB/VWAP/出来高/勢い反転 の合致スコアでエントリー判定."""

    name = "mean_reversion"

    def compute_entry_signal(
        self,
        bars_5min: pd.DataFrame,
        daily: pd.DataFrame,
        atr_pct: float,
        params: dict,
    ) -> pd.Series:
        threshold = float(params.get("threshold", 0.6))
        weights = params.get("weights", DEFAULT_WEIGHTS)

        score = self._compute_combined_score(bars_5min, weights)

        # トレンドフィルター
        sma200 = compute_sma(daily["close"], period=200)
        daily_above_ma = (daily["close"] > sma200).reindex(
            bars_5min.index, method="pad"
        ).fillna(False)

        signal = (score >= threshold) & daily_above_ma
        return signal.astype(bool)

    def _compute_combined_score(self, bars: pd.DataFrame, weights: dict) -> pd.Series:
        rsi = compute_rsi(bars["close"], period=14)
        rsi_score = ((30.0 - rsi) / 30.0).clip(lower=0.0, upper=1.0)

        upper, middle, lower = compute_bollinger_bands(bars["close"], period=20, num_std=2.0)
        sigma = (upper - middle) / 2.0
        bb_score = ((lower - bars["close"]) / sigma).clip(lower=0.0, upper=1.0).fillna(0)

        vwap = compute_vwap(bars)
        vwap_dev = ((vwap - bars["close"]) / bars["close"]).clip(lower=0.0, upper=1.0).fillna(0)

        vol_ratio = compute_volume_ratio(bars["volume"], period=20)
        vol_score = (vol_ratio / 2.0).clip(lower=0.0, upper=1.0).fillna(0)
        vol_score = vol_score.where(vol_ratio >= 1.5, 0.0)

        mom_rev = compute_momentum_reversal(bars["close"], lookback=3)
        mom_score = mom_rev.astype(float).fillna(0.0)

        return (
            weights["rsi"] * rsi_score.fillna(0)
            + weights["bb"] * bb_score
            + weights["vwap"] * vwap_dev
            + weights["volume"] * vol_score
            + weights["momentum"] * mom_score
        )
```

- [ ] **Step 5: テストパス**

```bash
cd "/Users/hideakimacbookair/自動トレード"
python3 -m pytest equity_trading/tests/test_strategy_mean_reversion.py -v 2>&1 | tail -10
```

期待：`3 passed`

- [ ] **Step 6: コミット**

```bash
cd "/Users/hideakimacbookair/自動トレード"
git add equity_trading/src/strategy/strategies/__init__.py equity_trading/src/strategy/strategies/mean_reversion.py equity_trading/tests/test_strategy_mean_reversion.py
git commit -m "feat(strategy): add MeanReversion strategy implementing TradingStrategy"
```

---

### Task 3: 戦略B（TrendFollow）

**Files:**
- Create: `equity_trading/src/strategy/strategies/trend_follow.py`
- Test: `equity_trading/tests/test_strategy_trend_follow.py`

- [ ] **Step 1: 失敗するテストを書く**

ファイル `equity_trading/tests/test_strategy_trend_follow.py`：

```python
import numpy as np
import pandas as pd

from equity_trading.src.strategy.strategies.trend_follow import TrendFollowStrategy


def test_trend_follow_has_correct_name():
    assert TrendFollowStrategy().name == "trend_follow"


def test_trend_follow_returns_bool_series():
    s = TrendFollowStrategy()
    np.random.seed(42)
    n = 100
    closes = 100.0 + np.cumsum(np.random.randn(n) * 0.1)
    bars = pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes, "volume": [10000] * n},
        index=pd.date_range("2024-01-01", periods=n, freq="5min", tz="UTC"),
    )
    daily = pd.DataFrame(
        {"close": list(np.linspace(80, 120, 250))},
        index=pd.date_range("2023-01-01", periods=250, freq="1D", tz="UTC"),
    )
    signal = s.compute_entry_signal(bars, daily, atr_pct=0.10, params={})
    assert len(signal) == len(bars)


def test_trend_follow_no_signal_when_below_200ma():
    s = TrendFollowStrategy()
    n = 100
    closes = np.full(n, 50.0)
    bars = pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes, "volume": [10000] * n},
        index=pd.date_range("2024-01-01", periods=n, freq="5min", tz="UTC"),
    )
    daily = pd.DataFrame(
        {"close": [100.0] * 250},
        index=pd.date_range("2023-01-01", periods=250, freq="1D", tz="UTC"),
    )
    signal = s.compute_entry_signal(bars, daily, atr_pct=0.10, params={})
    assert not signal.any()


def test_trend_follow_signals_on_breakout():
    """直近20本高値を上抜けた瞬間にシグナル."""
    s = TrendFollowStrategy()
    # 100本中80本目までは100、その後120まで上昇
    closes = np.array([100.0] * 80 + list(np.linspace(100.0, 120.0, 20)))
    bars = pd.DataFrame(
        {"open": closes, "high": closes + 0.5, "low": closes - 0.05, "close": closes, "volume": [10000] * 100},
        index=pd.date_range("2024-01-01 09:30", periods=100, freq="5min", tz="UTC"),
    )
    daily = pd.DataFrame(
        {"close": list(np.linspace(80, 120, 250))},
        index=pd.date_range("2023-01-01", periods=250, freq="1D", tz="UTC"),
    )
    signal = s.compute_entry_signal(bars, daily, atr_pct=0.10, params={"breakout_period": 20})
    # 後半でブレイクアウトが発生
    assert signal.iloc[80:].any()
```

- [ ] **Step 2: 失敗確認**

```bash
cd "/Users/hideakimacbookair/自動トレード"
python3 -m pytest equity_trading/tests/test_strategy_trend_follow.py -v 2>&1 | tail -10
```

期待：`ImportError`

- [ ] **Step 3: 実装**

ファイル `equity_trading/src/strategy/strategies/trend_follow.py`：

```python
"""トレンドフォロー戦略（200d MA + 直近高値ブレイク + RSI>50）."""
from __future__ import annotations

import pandas as pd

from equity_trading.src.data.feature_builder import compute_rsi, compute_sma
from equity_trading.src.strategy.base import TradingStrategy


class TrendFollowStrategy(TradingStrategy):
    """200d MA 上 + 直近 N 本高値更新 + RSI > 50 で買い."""

    name = "trend_follow"

    def compute_entry_signal(
        self,
        bars_5min: pd.DataFrame,
        daily: pd.DataFrame,
        atr_pct: float,
        params: dict,
    ) -> pd.Series:
        breakout_period = int(params.get("breakout_period", 20))
        rsi_threshold = float(params.get("rsi_threshold", 50.0))

        # 200d MA トレンドフィルター
        sma200 = compute_sma(daily["close"], period=200)
        daily_above_ma = (daily["close"] > sma200).reindex(
            bars_5min.index, method="pad"
        ).fillna(False)

        # 直近 N 本高値ブレイクアウト（当該本の高値が直近 N 本中で最大）
        rolling_max = bars_5min["high"].rolling(window=breakout_period).max()
        breakout = bars_5min["high"] >= rolling_max

        # RSI > 50（勢いがある）
        rsi = compute_rsi(bars_5min["close"], period=14)
        rsi_strong = rsi > rsi_threshold

        signal = daily_above_ma & breakout & rsi_strong.fillna(False)
        return signal.astype(bool)
```

- [ ] **Step 4: テストパス**

```bash
cd "/Users/hideakimacbookair/自動トレード"
python3 -m pytest equity_trading/tests/test_strategy_trend_follow.py -v 2>&1 | tail -10
```

期待：`3 passed`

- [ ] **Step 5: コミット**

```bash
cd "/Users/hideakimacbookair/自動トレード"
git add equity_trading/src/strategy/strategies/trend_follow.py equity_trading/tests/test_strategy_trend_follow.py
git commit -m "feat(strategy): add TrendFollow strategy (200d MA + breakout + RSI)"
```

---

### Task 4: 戦略C（MomentumBreakout）

**Files:**
- Create: `equity_trading/src/strategy/strategies/momentum_breakout.py`
- Test: `equity_trading/tests/test_strategy_momentum_breakout.py`

- [ ] **Step 1: 失敗するテストを書く**

ファイル `equity_trading/tests/test_strategy_momentum_breakout.py`：

```python
import numpy as np
import pandas as pd

from equity_trading.src.strategy.strategies.momentum_breakout import MomentumBreakoutStrategy


def test_momentum_breakout_has_correct_name():
    assert MomentumBreakoutStrategy().name == "momentum_breakout"


def test_momentum_breakout_signals_with_volume():
    s = MomentumBreakoutStrategy()
    n = 200
    # 最後の 5 本だけ価格急騰、出来高も急増
    closes = np.array([100.0] * (n - 5) + [100.5, 101.0, 101.5, 102.0, 102.5])
    volumes = [10000] * (n - 5) + [20000, 22000, 25000, 28000, 30000]
    bars = pd.DataFrame(
        {"open": closes, "high": closes + 0.1, "low": closes - 0.05, "close": closes, "volume": volumes},
        index=pd.date_range("2024-01-01 09:30", periods=n, freq="5min", tz="UTC"),
    )
    daily = pd.DataFrame(
        {"close": list(np.linspace(80, 120, 250))},
        index=pd.date_range("2023-01-01", periods=250, freq="1D", tz="UTC"),
    )
    signal = s.compute_entry_signal(bars, daily, atr_pct=0.10, params={"breakout_period": 78})
    # 後半でシグナル発生
    assert signal.iloc[-5:].any()


def test_momentum_breakout_no_signal_without_volume():
    s = MomentumBreakoutStrategy()
    n = 200
    closes = np.array([100.0] * (n - 5) + [100.5, 101.0, 101.5, 102.0, 102.5])
    volumes = [10000] * n  # 出来高変化なし
    bars = pd.DataFrame(
        {"open": closes, "high": closes + 0.1, "low": closes - 0.05, "close": closes, "volume": volumes},
        index=pd.date_range("2024-01-01 09:30", periods=n, freq="5min", tz="UTC"),
    )
    daily = pd.DataFrame(
        {"close": list(np.linspace(80, 120, 250))},
        index=pd.date_range("2023-01-01", periods=250, freq="1D", tz="UTC"),
    )
    signal = s.compute_entry_signal(bars, daily, atr_pct=0.10, params={"breakout_period": 78})
    # 出来高条件を満たさないのでシグナルなし
    assert not signal.iloc[-5:].any()
```

- [ ] **Step 2: 失敗確認**

```bash
cd "/Users/hideakimacbookair/自動トレード"
python3 -m pytest equity_trading/tests/test_strategy_momentum_breakout.py -v 2>&1 | tail -10
```

- [ ] **Step 3: 実装**

ファイル `equity_trading/src/strategy/strategies/momentum_breakout.py`：

```python
"""モメンタム・ブレイクアウト戦略（直近高値抜け + 出来高急増）."""
from __future__ import annotations

import pandas as pd

from equity_trading.src.data.feature_builder import compute_sma, compute_volume_ratio
from equity_trading.src.strategy.base import TradingStrategy


class MomentumBreakoutStrategy(TradingStrategy):
    """直近 N 本の高値ブレイクと出来高 1.5 倍以上で買い."""

    name = "momentum_breakout"

    def compute_entry_signal(
        self,
        bars_5min: pd.DataFrame,
        daily: pd.DataFrame,
        atr_pct: float,
        params: dict,
    ) -> pd.Series:
        breakout_period = int(params.get("breakout_period", 78))  # 6.5h
        volume_multiplier = float(params.get("volume_multiplier", 1.5))

        # 200d MA トレンドフィルター
        sma200 = compute_sma(daily["close"], period=200)
        daily_above_ma = (daily["close"] > sma200).reindex(
            bars_5min.index, method="pad"
        ).fillna(False)

        # 直近 N-1 本（自分を含めない）の高値を超える瞬間
        prev_max = bars_5min["high"].shift(1).rolling(window=breakout_period - 1).max()
        breakout = bars_5min["high"] > prev_max

        # 出来高急増
        vol_ratio = compute_volume_ratio(bars_5min["volume"], period=20)
        vol_strong = (vol_ratio >= volume_multiplier).fillna(False)

        signal = daily_above_ma & breakout & vol_strong
        return signal.astype(bool)
```

- [ ] **Step 4: テストパス**

```bash
cd "/Users/hideakimacbookair/自動トレード"
python3 -m pytest equity_trading/tests/test_strategy_momentum_breakout.py -v 2>&1 | tail -10
```

期待：`3 passed`

- [ ] **Step 5: コミット**

```bash
cd "/Users/hideakimacbookair/自動トレード"
git add equity_trading/src/strategy/strategies/momentum_breakout.py equity_trading/tests/test_strategy_momentum_breakout.py
git commit -m "feat(strategy): add MomentumBreakout strategy (high break + volume surge)"
```

---

### Task 5: 戦略D（EnvDependentReversion）

**Files:**
- Create: `equity_trading/src/strategy/strategies/env_dependent.py`
- Test: `equity_trading/tests/test_strategy_env_dependent.py`

戦略 A（MeanReversion）に環境フィルター（時間帯・当日下落率）を追加。

- [ ] **Step 1: 失敗するテストを書く**

ファイル `equity_trading/tests/test_strategy_env_dependent.py`：

```python
import numpy as np
import pandas as pd

from equity_trading.src.strategy.strategies.env_dependent import EnvDependentReversionStrategy


def test_env_dependent_has_correct_name():
    assert EnvDependentReversionStrategy().name == "env_dependent_reversion"


def test_env_dependent_blocks_first_30_min_after_open():
    """市場オープン後30分以内はシグナルなし."""
    s = EnvDependentReversionStrategy()
    # 9:30 ET = 14:30 UTC（冬時間想定）
    n = 50
    np.random.seed(42)
    closes = 100.0 + np.cumsum(np.random.randn(n) * 0.1)
    bars = pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes, "volume": [10000] * n},
        # 14:30 UTC スタート、5分間隔
        index=pd.date_range("2024-01-15 14:30", periods=n, freq="5min", tz="UTC"),
    )
    daily = pd.DataFrame(
        {"close": list(np.linspace(80, 120, 250))},
        index=pd.date_range("2023-01-01", periods=250, freq="1D", tz="UTC"),
    )
    signal = s.compute_entry_signal(bars, daily, atr_pct=0.10, params={"threshold": 0.3})
    # 最初の 6 本（30分）は False
    assert not signal.iloc[:6].any()
```

- [ ] **Step 2: 失敗確認**

```bash
cd "/Users/hideakimacbookair/自動トレード"
python3 -m pytest equity_trading/tests/test_strategy_env_dependent.py -v 2>&1 | tail -10
```

- [ ] **Step 3: 実装**

ファイル `equity_trading/src/strategy/strategies/env_dependent.py`：

```python
"""環境依存リバージョン戦略（MeanReversion + 時間帯/当日下落率フィルター）."""
from __future__ import annotations

import pandas as pd

from equity_trading.src.strategy.base import TradingStrategy
from equity_trading.src.strategy.strategies.mean_reversion import MeanReversionStrategy


class EnvDependentReversionStrategy(TradingStrategy):
    """MeanReversion に以下のフィルターを追加：
    - 米国市場オープン後30分以内は禁止
    - 米国市場クローズ前30分以内は禁止
    - 当日累計下落率 > 1% なら禁止（パニック相場除外）
    """

    name = "env_dependent_reversion"

    def __init__(self) -> None:
        self._base = MeanReversionStrategy()

    def compute_entry_signal(
        self,
        bars_5min: pd.DataFrame,
        daily: pd.DataFrame,
        atr_pct: float,
        params: dict,
    ) -> pd.Series:
        # ベースとなるリバージョンシグナル
        base_signal = self._base.compute_entry_signal(bars_5min, daily, atr_pct, params)

        # 環境フィルター
        ok_env = self._compute_env_filter(bars_5min)

        return (base_signal & ok_env).astype(bool)

    @staticmethod
    def _compute_env_filter(bars: pd.DataFrame) -> pd.Series:
        """各バーで環境条件を満たすか判定."""
        idx = bars.index

        # 1. 当該日の最初の30分を除外
        # 当該日の最初のバー時刻からの経過時間
        date_only = idx.tz_convert("America/New_York").date
        date_series = pd.Series(date_only, index=idx)
        first_bar_time = date_series.groupby(date_series).transform(
            lambda g: g.index.min()
        )
        elapsed_minutes = (idx - pd.DatetimeIndex(first_bar_time)).total_seconds() / 60.0
        ok_after_open = elapsed_minutes >= 30

        # 2. 当該日の最後の30分を除外
        last_bar_time = date_series.groupby(date_series).transform(
            lambda g: g.index.max()
        )
        until_close = (pd.DatetimeIndex(last_bar_time) - idx).total_seconds() / 60.0
        ok_before_close = until_close >= 30

        # 3. 当日下落率 > 1% を除外（始値からの下落率）
        date_only_str = pd.Series(date_only.astype(str), index=idx)
        first_open = bars.groupby(date_only_str)["open"].transform("first")
        intraday_change = (bars["close"] - first_open) / first_open
        ok_no_panic = intraday_change > -0.01

        return ok_after_open & ok_before_close & ok_no_panic
```

- [ ] **Step 4: テストパス**

```bash
cd "/Users/hideakimacbookair/自動トレード"
python3 -m pytest equity_trading/tests/test_strategy_env_dependent.py -v 2>&1 | tail -10
```

- [ ] **Step 5: コミット**

```bash
cd "/Users/hideakimacbookair/自動トレード"
git add equity_trading/src/strategy/strategies/env_dependent.py equity_trading/tests/test_strategy_env_dependent.py
git commit -m "feat(strategy): add EnvDependentReversion (MR + open/close/panic filters)"
```

---

### Task 6: 戦略E（MultiTimeframe）

**Files:**
- Create: `equity_trading/src/strategy/strategies/multi_timeframe.py`
- Test: `equity_trading/tests/test_strategy_multi_timeframe.py`

5分足・15分足・1時間足の RSI が**全部** 過売りで合致した時のみエントリー。

- [ ] **Step 1: 失敗するテストを書く**

ファイル `equity_trading/tests/test_strategy_multi_timeframe.py`：

```python
import numpy as np
import pandas as pd

from equity_trading.src.strategy.strategies.multi_timeframe import MultiTimeframeStrategy


def test_multi_timeframe_has_correct_name():
    assert MultiTimeframeStrategy().name == "multi_timeframe"


def test_multi_timeframe_returns_bool_series():
    s = MultiTimeframeStrategy()
    np.random.seed(42)
    n = 500  # 1h RSI 計算には十分なバー数が必要
    closes = 100.0 + np.cumsum(np.random.randn(n) * 0.1)
    bars = pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes, "volume": [10000] * n},
        index=pd.date_range("2024-01-01 14:30", periods=n, freq="5min", tz="UTC"),
    )
    daily = pd.DataFrame(
        {"close": list(np.linspace(80, 120, 250))},
        index=pd.date_range("2023-01-01", periods=250, freq="1D", tz="UTC"),
    )
    signal = s.compute_entry_signal(bars, daily, atr_pct=0.10, params={})
    assert len(signal) == n


def test_multi_timeframe_no_signal_when_below_200ma():
    s = MultiTimeframeStrategy()
    n = 500
    closes = np.full(n, 50.0)
    bars = pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes, "volume": [10000] * n},
        index=pd.date_range("2024-01-01 14:30", periods=n, freq="5min", tz="UTC"),
    )
    daily = pd.DataFrame(
        {"close": [100.0] * 250},  # 価格は MA より下
        index=pd.date_range("2023-01-01", periods=250, freq="1D", tz="UTC"),
    )
    signal = s.compute_entry_signal(bars, daily, atr_pct=0.10, params={})
    assert not signal.any()
```

- [ ] **Step 2: 失敗確認**

```bash
cd "/Users/hideakimacbookair/自動トレード"
python3 -m pytest equity_trading/tests/test_strategy_multi_timeframe.py -v 2>&1 | tail -10
```

- [ ] **Step 3: 実装**

ファイル `equity_trading/src/strategy/strategies/multi_timeframe.py`：

```python
"""マルチタイムフレーム合致戦略（5min + 15min + 1h RSI 過売り合致）."""
from __future__ import annotations

import pandas as pd

from equity_trading.src.data.feature_builder import compute_rsi, compute_sma
from equity_trading.src.strategy.base import TradingStrategy


class MultiTimeframeStrategy(TradingStrategy):
    """5min RSI<30 かつ 15min RSI<35 かつ 1h RSI<40 の合致でエントリー."""

    name = "multi_timeframe"

    def compute_entry_signal(
        self,
        bars_5min: pd.DataFrame,
        daily: pd.DataFrame,
        atr_pct: float,
        params: dict,
    ) -> pd.Series:
        rsi_5_th = float(params.get("rsi_5min_threshold", 30.0))
        rsi_15_th = float(params.get("rsi_15min_threshold", 35.0))
        rsi_60_th = float(params.get("rsi_60min_threshold", 40.0))

        # トレンドフィルター
        sma200 = compute_sma(daily["close"], period=200)
        daily_above_ma = (daily["close"] > sma200).reindex(
            bars_5min.index, method="pad"
        ).fillna(False)

        # 5min RSI
        rsi_5 = compute_rsi(bars_5min["close"], period=14)
        cond_5 = (rsi_5 < rsi_5_th).fillna(False)

        # 15min RSI（5min を 3本ずつまとめる）
        bars_15 = bars_5min["close"].resample("15min").last().dropna()
        rsi_15 = compute_rsi(bars_15, period=14)
        # 5分足インデックスへ前方フィル
        cond_15_5min = (rsi_15 < rsi_15_th).reindex(bars_5min.index, method="pad").fillna(False)

        # 1h RSI
        bars_60 = bars_5min["close"].resample("60min").last().dropna()
        rsi_60 = compute_rsi(bars_60, period=14)
        cond_60_5min = (rsi_60 < rsi_60_th).reindex(bars_5min.index, method="pad").fillna(False)

        signal = daily_above_ma & cond_5 & cond_15_5min & cond_60_5min
        return signal.astype(bool)
```

- [ ] **Step 4: テストパス**

```bash
cd "/Users/hideakimacbookair/自動トレード"
python3 -m pytest equity_trading/tests/test_strategy_multi_timeframe.py -v 2>&1 | tail -10
```

- [ ] **Step 5: コミット**

```bash
cd "/Users/hideakimacbookair/自動トレード"
git add equity_trading/src/strategy/strategies/multi_timeframe.py equity_trading/tests/test_strategy_multi_timeframe.py
git commit -m "feat(strategy): add MultiTimeframe (5/15/60 min RSI confluence)"
```

---

### Task 7: シミュレータを戦略インターフェース対応にリファクタ

**Files:**
- Modify: `equity_trading/src/phase0/signal_simulator.py`
- Create: `equity_trading/src/phase0/strategy_simulator.py`
- Test: `equity_trading/tests/test_strategy_simulator.py`

既存の `signal_simulator.py` は MeanReversion 専用。新しい `strategy_simulator.py` は任意の戦略を受け取って同じ「stop/target ループ」でシミュレートする。

- [ ] **Step 1: 失敗するテストを書く**

ファイル `equity_trading/tests/test_strategy_simulator.py`：

```python
import numpy as np
import pandas as pd

from equity_trading.src.phase0.strategy_simulator import simulate_strategy
from equity_trading.src.strategy.strategies.mean_reversion import MeanReversionStrategy


def _make_bars(n: int = 200) -> pd.DataFrame:
    np.random.seed(42)
    closes = 100.0 + np.cumsum(np.random.randn(n) * 0.1)
    return pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes, "volume": [10000] * n},
        index=pd.date_range("2024-01-01 14:30", periods=n, freq="5min", tz="UTC"),
    )


def _make_daily(n: int = 250) -> pd.DataFrame:
    return pd.DataFrame(
        {"close": list(np.linspace(80, 120, n))},
        index=pd.date_range("2023-01-01", periods=n, freq="1D", tz="UTC"),
    )


def test_simulate_strategy_returns_dict():
    s = MeanReversionStrategy()
    bars = _make_bars()
    daily = _make_daily()
    result = simulate_strategy(
        strategy=s,
        bars_5min=bars,
        daily=daily,
        atr_pct=0.10,
        params={"threshold": 0.5},
    )
    assert "trade_count" in result
    assert "win_count" in result
    assert "win_rate" in result
    assert "avg_pnl_pct" in result


def test_simulate_strategy_zero_signal_returns_zero_trades():
    """全シグナルが False の戦略は trade_count=0."""
    class ZeroStrategy(MeanReversionStrategy):
        name = "zero"

        def compute_entry_signal(self, bars_5min, daily, atr_pct, params):
            return pd.Series([False] * len(bars_5min), index=bars_5min.index, dtype=bool)

    s = ZeroStrategy()
    result = simulate_strategy(
        strategy=s,
        bars_5min=_make_bars(),
        daily=_make_daily(),
        atr_pct=0.10,
        params={},
    )
    assert result["trade_count"] == 0
```

- [ ] **Step 2: 失敗確認**

```bash
cd "/Users/hideakimacbookair/自動トレード"
python3 -m pytest equity_trading/tests/test_strategy_simulator.py -v 2>&1 | tail -10
```

- [ ] **Step 3: 実装**

ファイル `equity_trading/src/phase0/strategy_simulator.py`：

```python
"""任意の戦略を受け取り、同じ stop/target ロジックでバックテストする."""
from __future__ import annotations

import numpy as np
import pandas as pd

from equity_trading.src.strategy.base import TradingStrategy


def simulate_strategy(
    strategy: TradingStrategy,
    bars_5min: pd.DataFrame,
    daily: pd.DataFrame,
    atr_pct: float,
    params: dict | None = None,
    stop_multiplier: float = 1.5,
    target_multiplier: float = 2.4,
    cost_pct: float = 0.10,
    max_hold_bars: int = 78,
) -> dict[str, float]:
    """1戦略 × 1ETF でバックテストし、結果を辞書で返す.

    Args:
        strategy: TradingStrategy インスタンス
        bars_5min: 5分足 OHLCV
        daily: 日足 OHLCV
        atr_pct: ETF の ATR 中央値（%）
        params: 戦略固有のパラメータ辞書
        stop_multiplier: 損切り幅 = atr_pct * stop_multiplier （価格対比%）
        target_multiplier: 利確幅 = atr_pct * target_multiplier
        cost_pct: 往復コスト %
        max_hold_bars: 最大保持バー数（時間切れ強制決済）

    Returns:
        {'trade_count', 'win_count', 'win_rate', 'avg_pnl_pct'}
    """
    if params is None:
        params = {}

    entry_signal = strategy.compute_entry_signal(bars_5min, daily, atr_pct, params)

    stop_pct = atr_pct * stop_multiplier / 100.0
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
            entry_idx = i + 1
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
            elif i - entry_idx > max_hold_bars:
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
```

- [ ] **Step 4: テストパス**

```bash
cd "/Users/hideakimacbookair/自動トレード"
python3 -m pytest equity_trading/tests/test_strategy_simulator.py -v 2>&1 | tail -10
```

期待：`2 passed`

- [ ] **Step 5: コミット**

```bash
cd "/Users/hideakimacbookair/自動トレード"
git add equity_trading/src/phase0/strategy_simulator.py equity_trading/tests/test_strategy_simulator.py
git commit -m "feat(phase0): add strategy-agnostic simulator"
```

---

### Task 8: マルチ戦略ランナー

**Files:**
- Create: `equity_trading/src/phase0/multi_strategy_runner.py`
- Test: `equity_trading/tests/test_multi_strategy_runner.py`

5戦略すべて × 5ETF × 関連パラメータの全組み合わせをまとめて実行。

- [ ] **Step 1: 失敗するテストを書く**

ファイル `equity_trading/tests/test_multi_strategy_runner.py`：

```python
import numpy as np
import pandas as pd

from equity_trading.src.phase0.multi_strategy_runner import (
    run_all_strategies,
)
from equity_trading.src.strategy.strategies.mean_reversion import MeanReversionStrategy
from equity_trading.src.strategy.strategies.trend_follow import TrendFollowStrategy


def _make_bars(n: int = 300) -> pd.DataFrame:
    np.random.seed(42)
    closes = 100.0 + np.cumsum(np.random.randn(n) * 0.1)
    return pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes, "volume": [10000] * n},
        index=pd.date_range("2024-01-01 14:30", periods=n, freq="5min", tz="UTC"),
    )


def _make_daily(n: int = 250) -> pd.DataFrame:
    return pd.DataFrame(
        {"close": list(np.linspace(80, 120, n))},
        index=pd.date_range("2023-01-01", periods=n, freq="1D", tz="UTC"),
    )


def test_run_all_strategies_returns_dataframe_per_strategy():
    data_map = {
        ("SPY", 5): _make_bars(),
        ("SPY", 1440): _make_daily(),
        ("QQQ", 5): _make_bars(),
        ("QQQ", 1440): _make_daily(),
    }
    atr_map = {"SPY": 0.10, "QQQ": 0.13}

    strategies = [MeanReversionStrategy(), TrendFollowStrategy()]
    results = run_all_strategies(
        strategies=strategies,
        symbols=["SPY", "QQQ"],
        data_map=data_map,
        atr_map=atr_map,
        param_grid={
            "mean_reversion": [{"threshold": 0.5}, {"threshold": 0.6}],
            "trend_follow": [{}],
        },
    )

    assert "mean_reversion" in results
    assert "trend_follow" in results
    assert isinstance(results["mean_reversion"], pd.DataFrame)
    # mean_reversion: 2 ETF × 2 thresholds = 4 行
    assert len(results["mean_reversion"]) == 4
    # trend_follow: 2 ETF × 1 param = 2 行
    assert len(results["trend_follow"]) == 2
    cols = {"strategy", "symbol", "params", "trade_count", "win_count", "win_rate", "avg_pnl_pct"}
    assert cols.issubset(results["mean_reversion"].columns)
```

- [ ] **Step 2: 失敗確認**

```bash
cd "/Users/hideakimacbookair/自動トレード"
python3 -m pytest equity_trading/tests/test_multi_strategy_runner.py -v 2>&1 | tail -10
```

- [ ] **Step 3: 実装**

ファイル `equity_trading/src/phase0/multi_strategy_runner.py`：

```python
"""5戦略 × 5ETF × パラメータグリッドのマルチ戦略ランナー."""
from __future__ import annotations

import json
from typing import Sequence

import pandas as pd

from equity_trading.src.phase0.strategy_simulator import simulate_strategy
from equity_trading.src.strategy.base import TradingStrategy


def run_all_strategies(
    strategies: Sequence[TradingStrategy],
    symbols: Sequence[str],
    data_map: dict[tuple[str, int], pd.DataFrame],
    atr_map: dict[str, float],
    param_grid: dict[str, list[dict]],
) -> dict[str, pd.DataFrame]:
    """全戦略 × 全ETF × パラメータでシミュレーションを実行.

    Args:
        strategies: TradingStrategy インスタンスのリスト
        symbols: 検証対象のETFティッカー
        data_map: collect_phase0_data の戻り値（{(symbol, timeframe): DataFrame}）
        atr_map: {symbol: atr_median_pct}
        param_grid: {strategy_name: [params_dict, ...]}

    Returns:
        {strategy_name: DataFrame} の辞書。
        各 DataFrame の列：strategy, symbol, params, trade_count, win_count, win_rate, avg_pnl_pct
    """
    results: dict[str, list[dict]] = {s.name: [] for s in strategies}

    for strategy in strategies:
        param_list = param_grid.get(strategy.name, [{}])
        for symbol in symbols:
            bars_5 = data_map[(symbol, 5)]
            daily = data_map[(symbol, 1440)]
            atr_pct = atr_map[symbol]
            for params in param_list:
                summary = simulate_strategy(
                    strategy=strategy,
                    bars_5min=bars_5,
                    daily=daily,
                    atr_pct=atr_pct,
                    params=params,
                )
                summary["strategy"] = strategy.name
                summary["symbol"] = symbol
                summary["params"] = json.dumps(params, sort_keys=True)
                results[strategy.name].append(summary)

    return {
        name: pd.DataFrame(rows)[
            ["strategy", "symbol", "params", "trade_count", "win_count", "win_rate", "avg_pnl_pct"]
        ]
        for name, rows in results.items()
    }
```

- [ ] **Step 4: テストパス**

```bash
cd "/Users/hideakimacbookair/自動トレード"
python3 -m pytest equity_trading/tests/test_multi_strategy_runner.py -v 2>&1 | tail -10
```

期待：`1 passed`

- [ ] **Step 5: コミット**

```bash
cd "/Users/hideakimacbookair/自動トレード"
git add equity_trading/src/phase0/multi_strategy_runner.py equity_trading/tests/test_multi_strategy_runner.py
git commit -m "feat(phase0): add multi-strategy runner over symbols and param grids"
```

---

### Task 9: 比較レポート生成器

**Files:**
- Create: `equity_trading/src/phase0/comparison_report.py`
- Test: `equity_trading/tests/test_comparison_report.py`

5戦略の結果を横並びで Markdown に整形。最良戦略を推奨。

- [ ] **Step 1: 失敗するテストを書く**

ファイル `equity_trading/tests/test_comparison_report.py`：

```python
from pathlib import Path

import pandas as pd

from equity_trading.src.phase0.comparison_report import generate_comparison_report


def _make_results() -> dict[str, pd.DataFrame]:
    return {
        "mean_reversion": pd.DataFrame([
            {"strategy": "mean_reversion", "symbol": "SPY", "params": "{}",
             "trade_count": 30, "win_count": 14, "win_rate": 0.467, "avg_pnl_pct": -0.05},
            {"strategy": "mean_reversion", "symbol": "XLK", "params": "{}",
             "trade_count": 36, "win_count": 23, "win_rate": 0.639, "avg_pnl_pct": 0.028},
        ]),
        "trend_follow": pd.DataFrame([
            {"strategy": "trend_follow", "symbol": "SPY", "params": "{}",
             "trade_count": 80, "win_count": 46, "win_rate": 0.575, "avg_pnl_pct": 0.10},
        ]),
    }


def test_report_contains_all_strategies(tmp_path):
    out = tmp_path / "comparison.md"
    generate_comparison_report(
        results=_make_results(),
        atr_results={"SPY": {"median_pct": 0.10}, "XLK": {"median_pct": 0.13}},
        output_path=out,
        period_start="2024-05-01",
        period_end="2026-05-01",
    )
    content = out.read_text()
    assert "mean_reversion" in content
    assert "trend_follow" in content
    assert "Comparison" in content or "比較" in content


def test_report_recommends_best_overall_strategy(tmp_path):
    out = tmp_path / "comparison.md"
    generate_comparison_report(
        results=_make_results(),
        atr_results={"SPY": {"median_pct": 0.10}, "XLK": {"median_pct": 0.13}},
        output_path=out,
        period_start="2024-05-01",
        period_end="2026-05-01",
    )
    content = out.read_text()
    # trend_follow は SPY で 80 trades * 0.10% = 8.0 expected
    # mean_reversion XLK は 36 * 0.028 = 1.008
    # → trend_follow が推奨
    assert "trend_follow" in content
    # 期待値が表示される
    assert "8" in content
```

- [ ] **Step 2: 失敗確認**

```bash
cd "/Users/hideakimacbookair/自動トレード"
python3 -m pytest equity_trading/tests/test_comparison_report.py -v 2>&1 | tail -10
```

- [ ] **Step 3: 実装**

ファイル `equity_trading/src/phase0/comparison_report.py`：

```python
"""5戦略の比較レポート（Markdown）."""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def generate_comparison_report(
    results: dict[str, pd.DataFrame],
    atr_results: dict[str, dict[str, float]],
    output_path: Path | str,
    period_start: str,
    period_end: str,
) -> None:
    """5戦略の検証結果を比較レポートに整形.

    Args:
        results: {strategy_name: DataFrame(strategy, symbol, params, trade_count, win_rate, avg_pnl_pct)}
        atr_results: {symbol: {'median_pct', ...}}
        output_path: 出力ファイルパス
        period_start, period_end: データ期間
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append("# Phase 0 Multi-Strategy Comparison Report")
    lines.append("")
    lines.append(f"**Period:** {period_start} 〜 {period_end}")
    lines.append("")

    # ATR 表
    lines.append("## ETF別 ATR(14, 5min) 中央値（価格対比 %）")
    lines.append("")
    lines.append("| ETF | Median |")
    lines.append("|-----|--------|")
    for sym, atr in atr_results.items():
        lines.append(f"| {sym} | {atr['median_pct']:.3f}% |")
    lines.append("")

    # 各戦略の詳細テーブル + 戦略毎ベスト
    best_per_strategy: list[dict] = []
    for strategy_name, df in results.items():
        lines.append(f"## 戦略: {strategy_name}")
        lines.append("")
        lines.append("| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |")
        lines.append("|--------|--------|--------|------|----------|---------|----------------------|")

        df_copy = df.copy()
        df_copy["expected"] = df_copy["avg_pnl_pct"] * df_copy["trade_count"]

        for _, row in df_copy.iterrows():
            wr = row["win_rate"]
            wr_str = f"{wr:.3f}" if pd.notna(wr) else "nan"
            pnl = row["avg_pnl_pct"]
            pnl_str = f"{pnl:.3f}%" if pd.notna(pnl) else "nan%"
            ev = row["expected"]
            ev_str = f"{ev:.2f}" if pd.notna(ev) else "nan"
            lines.append(
                f"| {row['symbol']} | `{row['params']}` | "
                f"{int(row['trade_count'])} | {int(row['win_count'])} | "
                f"{wr_str} | {pnl_str} | {ev_str} |"
            )

        # この戦略のベスト
        df_valid = df_copy[df_copy["trade_count"] > 0].copy()
        if len(df_valid) > 0:
            best = df_valid.loc[df_valid["expected"].idxmax()]
            lines.append("")
            lines.append(
                f"**Best for {strategy_name}:** {best['symbol']} / `{best['params']}` "
                f"→ EV {best['expected']:.2f} (WR {best['win_rate']:.3f}, Trades {int(best['trade_count'])})"
            )
            best_per_strategy.append({
                "strategy": strategy_name,
                "symbol": best["symbol"],
                "params": best["params"],
                "expected": best["expected"],
                "win_rate": best["win_rate"],
                "trade_count": int(best["trade_count"]),
            })
        lines.append("")

    # 全戦略横断ベスト
    lines.append("## 横断比較：戦略別ベスト")
    lines.append("")
    lines.append("| Rank | Strategy | Symbol | Params | EV | Win Rate | Trades |")
    lines.append("|------|----------|--------|--------|-----|----------|--------|")
    sorted_best = sorted(best_per_strategy, key=lambda d: d["expected"], reverse=True)
    for rank, b in enumerate(sorted_best, start=1):
        lines.append(
            f"| {rank} | {b['strategy']} | {b['symbol']} | `{b['params']}` | "
            f"{b['expected']:.2f} | {b['win_rate']:.3f} | {b['trade_count']} |"
        )
    lines.append("")

    if sorted_best:
        winner = sorted_best[0]
        lines.append(f"## 推奨：**{winner['strategy']}** （{winner['symbol']}、EV {winner['expected']:.2f}）")
        lines.append("")

    lines.append("## 次のステップ")
    lines.append("")
    lines.append("1. このレポートを人間がレビュー、最良戦略を確認")
    lines.append("2. 推奨戦略を Plan 2 の本実装の対象とする")
    lines.append("3. 必要に応じて、上位2戦略をアンサンブル運用も検討")

    output_path.write_text("\n".join(lines), encoding="utf-8")
```

- [ ] **Step 4: テストパス**

```bash
cd "/Users/hideakimacbookair/自動トレード"
python3 -m pytest equity_trading/tests/test_comparison_report.py -v 2>&1 | tail -10
```

期待：`2 passed`

- [ ] **Step 5: コミット**

```bash
cd "/Users/hideakimacbookair/自動トレード"
git add equity_trading/src/phase0/comparison_report.py equity_trading/tests/test_comparison_report.py
git commit -m "feat(phase0): add multi-strategy comparison report"
```

---

### Task 10: マルチ戦略 Phase 0 CLI

**Files:**
- Create: `equity_trading/scripts/run_phase0_multi.py`
- Test: `equity_trading/tests/test_run_phase0_multi.py`

既存 `run_phase0.py` は MeanReversion 単独。新 CLI は5戦略すべてを実行。

- [ ] **Step 1: 失敗するテストを書く**

ファイル `equity_trading/tests/test_run_phase0_multi.py`：

```python
"""マルチ戦略 Phase 0 CLI の E2E テスト（モック）."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd


def _make_bars(n: int, freq: str = "5min") -> pd.DataFrame:
    np.random.seed(42)
    closes = 100.0 + np.cumsum(np.random.randn(n) * 0.1)
    return pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes, "volume": [10000] * n},
        index=pd.date_range("2024-01-01", periods=n, freq=freq, tz="UTC"),
    )


def test_run_phase0_multi_e2e_creates_report(tmp_path, monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "PKTEST")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "secret")
    monkeypatch.setenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

    project_root = tmp_path / "project"
    (project_root / "data" / "prices").mkdir(parents=True)
    (project_root / "phase0").mkdir(parents=True)

    bars_5min = _make_bars(500, freq="5min")
    bars_daily = _make_bars(500, freq="1D")

    with patch(
        "equity_trading.src.broker.alpaca_client.StockHistoricalDataClient"
    ) as mock_data, patch(
        "equity_trading.src.broker.alpaca_client.TradingClient"
    ):
        def fake_get_bars(req):
            if hasattr(req, "timeframe") and "Day" in str(req.timeframe):
                return type("X", (), {"df": bars_daily})()
            return type("X", (), {"df": bars_5min})()
        mock_data.return_value.get_stock_bars.side_effect = fake_get_bars

        from equity_trading.scripts.run_phase0_multi import main

        report_path = project_root / "phase0" / "comparison_report.md"
        cache_dir = project_root / "data" / "prices"

        main(
            symbols=["SPY"],
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2024, 1, 31, tzinfo=timezone.utc),
            cache_dir=cache_dir,
            report_path=report_path,
        )

    assert report_path.exists()
    content = report_path.read_text()
    assert "mean_reversion" in content
    assert "trend_follow" in content
    assert "momentum_breakout" in content
    assert "env_dependent_reversion" in content
    assert "multi_timeframe" in content
```

- [ ] **Step 2: 失敗確認**

```bash
cd "/Users/hideakimacbookair/自動トレード"
python3 -m pytest equity_trading/tests/test_run_phase0_multi.py -v 2>&1 | tail -10
```

- [ ] **Step 3: 実装**

ファイル `equity_trading/scripts/run_phase0_multi.py`：

```python
"""マルチ戦略 Phase 0 統合スクリプト.

5戦略すべてを過去データで検証して比較レポートを出す.

実行：
    cd /Users/hideakimacbookair/自動トレード
    python3 equity_trading/scripts/run_phase0_multi.py --days 730
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from equity_trading.src.broker.alpaca_client import AlpacaClient
from equity_trading.src.config import load_config
from equity_trading.src.data.price_fetcher import PriceFetcher
from equity_trading.src.monitor.logger import setup_logger
from equity_trading.src.phase0.atr_analyzer import analyze_atr_distribution
from equity_trading.src.phase0.comparison_report import generate_comparison_report
from equity_trading.src.phase0.data_collector import collect_phase0_data
from equity_trading.src.phase0.multi_strategy_runner import run_all_strategies
from equity_trading.src.strategy.strategies.env_dependent import EnvDependentReversionStrategy
from equity_trading.src.strategy.strategies.mean_reversion import MeanReversionStrategy
from equity_trading.src.strategy.strategies.momentum_breakout import MomentumBreakoutStrategy
from equity_trading.src.strategy.strategies.multi_timeframe import MultiTimeframeStrategy
from equity_trading.src.strategy.strategies.trend_follow import TrendFollowStrategy


DEFAULT_SYMBOLS = ["SPY", "QQQ", "IWM", "DIA", "XLK"]


# 各戦略のパラメータグリッド
PARAM_GRID = {
    "mean_reversion": [
        {"threshold": 0.40},
        {"threshold": 0.50},
        {"threshold": 0.60},
    ],
    "trend_follow": [
        {"breakout_period": 20, "rsi_threshold": 50.0},
        {"breakout_period": 50, "rsi_threshold": 55.0},
    ],
    "momentum_breakout": [
        {"breakout_period": 78, "volume_multiplier": 1.5},
        {"breakout_period": 78, "volume_multiplier": 2.0},
    ],
    "env_dependent_reversion": [
        {"threshold": 0.40},
        {"threshold": 0.50},
    ],
    "multi_timeframe": [
        {"rsi_5min_threshold": 30.0, "rsi_15min_threshold": 35.0, "rsi_60min_threshold": 40.0},
        {"rsi_5min_threshold": 25.0, "rsi_15min_threshold": 30.0, "rsi_60min_threshold": 35.0},
    ],
}


def main(
    symbols: Sequence[str] = DEFAULT_SYMBOLS,
    start: datetime | None = None,
    end: datetime | None = None,
    cache_dir: Path | None = None,
    report_path: Path | None = None,
) -> int:
    log = setup_logger("equity_trading.phase0_multi")

    if end is None:
        end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    if start is None:
        start = end - timedelta(days=730)

    project_root = Path(__file__).resolve().parents[1]
    if cache_dir is None:
        cache_dir = project_root / "data" / "prices"
    if report_path is None:
        report_path = project_root / "phase0" / "comparison_report.md"

    log.info("phase0_multi_start", extra={"symbols": list(symbols)})

    env_path = project_root / ".env"
    cfg = load_config(env_path=env_path if env_path.exists() else None)
    broker = AlpacaClient(
        api_key=cfg.alpaca_api_key,
        secret_key=cfg.alpaca_secret_key,
        base_url=cfg.alpaca_base_url,
    )
    fetcher = PriceFetcher(broker=broker, cache_dir=cache_dir)

    log.info("phase0_multi_collecting_data")
    data_map = collect_phase0_data(
        fetcher=fetcher,
        symbols=symbols,
        start=start,
        end=end,
        timeframes=[5, 1440],
    )

    log.info("phase0_multi_analyzing_atr")
    atr_results: dict[str, dict[str, float]] = {}
    atr_map: dict[str, float] = {}
    for sym in symbols:
        atr_results[sym] = analyze_atr_distribution(data_map[(sym, 5)], period=14)
        atr_map[sym] = atr_results[sym]["median_pct"]

    log.info("phase0_multi_running_strategies")
    strategies = [
        MeanReversionStrategy(),
        TrendFollowStrategy(),
        MomentumBreakoutStrategy(),
        EnvDependentReversionStrategy(),
        MultiTimeframeStrategy(),
    ]
    results = run_all_strategies(
        strategies=strategies,
        symbols=list(symbols),
        data_map=data_map,
        atr_map=atr_map,
        param_grid=PARAM_GRID,
    )

    log.info("phase0_multi_generating_report", extra={"output": str(report_path)})
    generate_comparison_report(
        results=results,
        atr_results=atr_results,
        output_path=report_path,
        period_start=start.date().isoformat(),
        period_end=end.date().isoformat(),
    )

    log.info("phase0_multi_done", extra={"report_path": str(report_path)})
    print(f"\n✅ Phase 0 Multi-Strategy 完了。レポート：{report_path}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-strategy Phase 0")
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    parser.add_argument("--days", type=int, default=730)
    args = parser.parse_args()

    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=args.days)
    sys.exit(main(symbols=args.symbols, start=start, end=end))
```

- [ ] **Step 4: テストパス**

```bash
cd "/Users/hideakimacbookair/自動トレード"
python3 -m pytest equity_trading/tests/test_run_phase0_multi.py -v 2>&1 | tail -15
```

期待：`1 passed`

- [ ] **Step 5: コミット**

```bash
cd "/Users/hideakimacbookair/自動トレード"
git add equity_trading/scripts/run_phase0_multi.py equity_trading/tests/test_run_phase0_multi.py
git commit -m "feat(phase0): add multi-strategy CLI integrating all 5 strategies"
```

---

### Task 11: 全テスト + 実機マルチ戦略 Phase 0 実行

- [ ] **Step 1: 全テスト**

```bash
cd "/Users/hideakimacbookair/自動トレード"
python3 -m pytest equity_trading/tests/ -v 2>&1 | tail -15
```

期待：すべて pass。

- [ ] **Step 2: 過去データキャッシュをクリア（クリーン状態で実機実行）**

```bash
cd "/Users/hideakimacbookair/自動トレード"
rm -rf equity_trading/data/prices/*
```

- [ ] **Step 3: マルチ戦略 Phase 0 を実機実行（2年分）**

```bash
cd "/Users/hideakimacbookair/自動トレード"
python3 equity_trading/scripts/run_phase0_multi.py --days 730 2>&1 | tail -20
```

期待：3〜5分で完了。`✅ Phase 0 Multi-Strategy 完了` の表示。

- [ ] **Step 4: 比較レポートを確認**

```bash
cat "/Users/hideakimacbookair/自動トレード/equity_trading/phase0/comparison_report.md"
```

確認項目：
- 5戦略すべての結果テーブルが表示されている
- 各戦略の Best が選定されている
- 戦略横断比較で順位がついている
- 推奨戦略が明記されている

- [ ] **Step 5: 結果コミット**

```bash
cd "/Users/hideakimacbookair/自動トレード"
echo "Multi-strategy Phase 0 completed: $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> equity_trading/phase0/run_log.txt
git add equity_trading/phase0/comparison_report.md equity_trading/phase0/run_log.txt
git commit -m "feat(phase0): generate multi-strategy comparison report from real 2-year data"
```

---

## Plan 1.5 完了条件

- [ ] 全 11 タスク完了
- [ ] `pytest equity_trading/tests/` で全テスト pass
- [ ] `equity_trading/phase0/comparison_report.md` に5戦略の比較結果が記載され、推奨戦略が明示されている
- [ ] ユーザーが結果を確認し、Plan 2 で本実装する戦略を決定する

## Plan 2 への引き渡し情報

Plan 1.5 で確定した値（Plan 2 で使う）：

1. **採用戦略**：比較レポートの推奨戦略（または上位 2 戦略のアンサンブル）
2. **採用パラメータ**：その戦略で最良EVを出した params
3. **対象ETF**：その戦略 × ETF の組み合わせ
4. **Paper運用合格基準**：実測勝率の -3pt、実測取引数の -20% を最低ラインに

これらが `phase0/comparison_report.md` に記載され、Plan 2 着手時に `recommended_config.json` に書き出す。

---

## Self-Review チェック

- [x] **仕様カバー**：v2.0.1 仕様の Phase 0 セクションを5戦略対応に拡張、戦略インターフェース・マルチランナー・比較レポートをすべてカバー
- [x] **プレースホルダー無し**：全タスクに完全なコード・コマンド・期待出力
- [x] **型一貫性**：`TradingStrategy`、`StrategyResult`、`run_all_strategies` のシグネチャがタスク間で統一
- [x] **コミット境界**：各タスクで独立コミット
- [x] **TDD**：全タスクが「テスト → fail → 実装 → pass → commit」
