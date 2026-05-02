# Phase 0 Multi-Strategy Comparison Report

**Period:** 2024-05-02 〜 2026-05-02

## ETF別 ATR(14, 5min) 中央値（価格対比 %）

| ETF | Median |
|-----|--------|
| SPY | 0.061% |
| QQQ | 0.083% |
| IWM | 0.096% |
| DIA | 0.073% |
| XLK | 0.129% |

## 戦略: mean_reversion

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"threshold": 0.4}` | 113 | 55 | 0.487 | -0.076% | -8.54 |
| SPY | `{"threshold": 0.5}` | 21 | 10 | 0.476 | -0.078% | -1.64 |
| SPY | `{"threshold": 0.6}` | 3 | 1 | 0.333 | -0.112% | -0.34 |
| QQQ | `{"threshold": 0.4}` | 127 | 62 | 0.488 | -0.065% | -8.30 |
| QQQ | `{"threshold": 0.5}` | 28 | 15 | 0.536 | -0.051% | -1.42 |
| QQQ | `{"threshold": 0.6}` | 2 | 1 | 0.500 | -0.062% | -0.12 |
| IWM | `{"threshold": 0.4}` | 74 | 36 | 0.486 | -0.059% | -4.37 |
| IWM | `{"threshold": 0.5}` | 17 | 10 | 0.588 | -0.024% | -0.40 |
| IWM | `{"threshold": 0.6}` | 0 | 0 | nan | nan% | nan |
| DIA | `{"threshold": 0.4}` | 42 | 22 | 0.524 | -0.061% | -2.54 |
| DIA | `{"threshold": 0.5}` | 3 | 1 | 0.333 | -0.115% | -0.34 |
| DIA | `{"threshold": 0.6}` | 0 | 0 | nan | nan% | nan |
| XLK | `{"threshold": 0.4}` | 36 | 23 | 0.639 | 0.028% | 1.01 |
| XLK | `{"threshold": 0.5}` | 2 | 0 | 0.000 | -0.294% | -0.59 |
| XLK | `{"threshold": 0.6}` | 0 | 0 | nan | nan% | nan |

**Best for mean_reversion:** XLK / `{"threshold": 0.4}` → EV 1.01 (WR 0.639, Trades 36)

## 戦略: trend_follow

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"breakout_period": 20, "rsi_threshold": 50.0}` | 1293 | 541 | 0.418 | -0.091% | -117.57 |
| SPY | `{"breakout_period": 50, "rsi_threshold": 55.0}` | 851 | 348 | 0.409 | -0.093% | -79.09 |
| QQQ | `{"breakout_period": 20, "rsi_threshold": 50.0}` | 1223 | 513 | 0.419 | -0.087% | -106.54 |
| QQQ | `{"breakout_period": 50, "rsi_threshold": 55.0}` | 783 | 326 | 0.416 | -0.087% | -68.10 |
| IWM | `{"breakout_period": 20, "rsi_threshold": 50.0}` | 1123 | 473 | 0.421 | -0.085% | -95.61 |
| IWM | `{"breakout_period": 50, "rsi_threshold": 55.0}` | 745 | 311 | 0.417 | -0.085% | -63.52 |
| DIA | `{"breakout_period": 20, "rsi_threshold": 50.0}` | 1039 | 418 | 0.402 | -0.094% | -98.07 |
| DIA | `{"breakout_period": 50, "rsi_threshold": 55.0}` | 682 | 284 | 0.416 | -0.090% | -61.69 |
| XLK | `{"breakout_period": 20, "rsi_threshold": 50.0}` | 520 | 230 | 0.442 | -0.071% | -36.97 |
| XLK | `{"breakout_period": 50, "rsi_threshold": 55.0}` | 356 | 158 | 0.444 | -0.071% | -25.26 |

**Best for trend_follow:** XLK / `{"breakout_period": 50, "rsi_threshold": 55.0}` → EV -25.26 (WR 0.444, Trades 356)

## 戦略: momentum_breakout

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"breakout_period": 78, "volume_multiplier": 1.5}` | 548 | 229 | 0.418 | -0.091% | -49.80 |
| SPY | `{"breakout_period": 78, "volume_multiplier": 2.0}` | 468 | 185 | 0.395 | -0.096% | -44.89 |
| QQQ | `{"breakout_period": 78, "volume_multiplier": 1.5}` | 522 | 217 | 0.416 | -0.087% | -45.46 |
| QQQ | `{"breakout_period": 78, "volume_multiplier": 2.0}` | 454 | 189 | 0.416 | -0.087% | -39.50 |
| IWM | `{"breakout_period": 78, "volume_multiplier": 1.5}` | 472 | 182 | 0.386 | -0.098% | -46.36 |
| IWM | `{"breakout_period": 78, "volume_multiplier": 2.0}` | 395 | 150 | 0.380 | -0.101% | -39.97 |
| DIA | `{"breakout_period": 78, "volume_multiplier": 1.5}` | 378 | 165 | 0.437 | -0.085% | -32.10 |
| DIA | `{"breakout_period": 78, "volume_multiplier": 2.0}` | 320 | 142 | 0.444 | -0.083% | -26.49 |
| XLK | `{"breakout_period": 78, "volume_multiplier": 1.5}` | 184 | 79 | 0.429 | -0.075% | -13.78 |
| XLK | `{"breakout_period": 78, "volume_multiplier": 2.0}` | 158 | 74 | 0.468 | -0.057% | -8.94 |

**Best for momentum_breakout:** XLK / `{"breakout_period": 78, "volume_multiplier": 2.0}` → EV -8.94 (WR 0.468, Trades 158)

## 戦略: env_dependent_reversion

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"threshold": 0.4}` | 67 | 32 | 0.478 | -0.078% | -5.21 |
| SPY | `{"threshold": 0.5}` | 3 | 2 | 0.667 | -0.033% | -0.10 |
| QQQ | `{"threshold": 0.4}` | 74 | 34 | 0.459 | -0.074% | -5.47 |
| QQQ | `{"threshold": 0.5}` | 6 | 3 | 0.500 | -0.062% | -0.37 |
| IWM | `{"threshold": 0.4}` | 35 | 12 | 0.343 | -0.110% | -3.84 |
| IWM | `{"threshold": 0.5}` | 2 | 1 | 0.500 | -0.057% | -0.11 |
| DIA | `{"threshold": 0.4}` | 31 | 18 | 0.581 | -0.044% | -1.38 |
| DIA | `{"threshold": 0.5}` | 2 | 1 | 0.500 | -0.067% | -0.13 |
| XLK | `{"threshold": 0.4}` | 21 | 13 | 0.619 | 0.018% | 0.38 |
| XLK | `{"threshold": 0.5}` | 1 | 0 | 0.000 | -0.294% | -0.29 |

**Best for env_dependent_reversion:** XLK / `{"threshold": 0.4}` → EV 0.38 (WR 0.619, Trades 21)

## 戦略: multi_timeframe

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"rsi_15min_threshold": 35.0, "rsi_5min_threshold": 30.0, "rsi_60min_threshold": 40.0}` | 191 | 88 | 0.461 | -0.082% | -15.62 |
| SPY | `{"rsi_15min_threshold": 30.0, "rsi_5min_threshold": 25.0, "rsi_60min_threshold": 35.0}` | 67 | 30 | 0.448 | -0.085% | -5.69 |
| QQQ | `{"rsi_15min_threshold": 35.0, "rsi_5min_threshold": 30.0, "rsi_60min_threshold": 40.0}` | 201 | 89 | 0.443 | -0.081% | -16.30 |
| QQQ | `{"rsi_15min_threshold": 30.0, "rsi_5min_threshold": 25.0, "rsi_60min_threshold": 35.0}` | 68 | 34 | 0.500 | -0.062% | -4.25 |
| IWM | `{"rsi_15min_threshold": 35.0, "rsi_5min_threshold": 30.0, "rsi_60min_threshold": 40.0}` | 164 | 71 | 0.433 | -0.081% | -13.29 |
| IWM | `{"rsi_15min_threshold": 30.0, "rsi_5min_threshold": 25.0, "rsi_60min_threshold": 35.0}` | 49 | 21 | 0.429 | -0.084% | -4.09 |
| DIA | `{"rsi_15min_threshold": 35.0, "rsi_5min_threshold": 30.0, "rsi_60min_threshold": 40.0}` | 161 | 74 | 0.460 | -0.079% | -12.68 |
| DIA | `{"rsi_15min_threshold": 30.0, "rsi_5min_threshold": 25.0, "rsi_60min_threshold": 35.0}` | 47 | 17 | 0.362 | -0.106% | -5.00 |
| XLK | `{"rsi_15min_threshold": 35.0, "rsi_5min_threshold": 30.0, "rsi_60min_threshold": 40.0}` | 92 | 41 | 0.446 | -0.069% | -6.37 |
| XLK | `{"rsi_15min_threshold": 30.0, "rsi_5min_threshold": 25.0, "rsi_60min_threshold": 35.0}` | 33 | 17 | 0.515 | -0.034% | -1.13 |

**Best for multi_timeframe:** XLK / `{"rsi_15min_threshold": 30.0, "rsi_5min_threshold": 25.0, "rsi_60min_threshold": 35.0}` → EV -1.13 (WR 0.515, Trades 33)

## 戦略: analysis_driven_reversion

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.3}` | 95 | 43 | 0.453 | -0.083% | -7.84 |
| SPY | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.25}` | 134 | 57 | 0.425 | -0.089% | -11.98 |
| SPY | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.2}` | 623 | 257 | 0.413 | -0.092% | -57.16 |
| QQQ | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.3}` | 107 | 48 | 0.449 | -0.077% | -8.28 |
| QQQ | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.25}` | 144 | 59 | 0.410 | -0.090% | -12.95 |
| QQQ | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.2}` | 579 | 237 | 0.409 | -0.090% | -52.16 |
| IWM | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.3}` | 93 | 45 | 0.484 | -0.063% | -5.84 |
| IWM | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.25}` | 127 | 54 | 0.425 | -0.085% | -10.77 |
| IWM | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.2}` | 547 | 227 | 0.415 | -0.088% | -48.35 |
| DIA | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.3}` | 43 | 19 | 0.442 | -0.084% | -3.60 |
| DIA | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.25}` | 78 | 35 | 0.449 | -0.082% | -6.38 |
| DIA | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.2}` | 446 | 186 | 0.417 | -0.091% | -40.37 |
| XLK | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.3}` | 31 | 11 | 0.355 | -0.115% | -3.56 |
| XLK | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.25}` | 45 | 20 | 0.444 | -0.070% | -3.14 |
| XLK | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.2}` | 227 | 97 | 0.427 | -0.078% | -17.80 |

**Best for analysis_driven_reversion:** XLK / `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.25}` → EV -3.14 (WR 0.444, Trades 45)

## 横断比較：戦略別ベスト

| Rank | Strategy | Symbol | Params | EV | Win Rate | Trades |
|------|----------|--------|--------|-----|----------|--------|
| 1 | mean_reversion | XLK | `{"threshold": 0.4}` | 1.01 | 0.639 | 36 |
| 2 | env_dependent_reversion | XLK | `{"threshold": 0.4}` | 0.38 | 0.619 | 21 |
| 3 | multi_timeframe | XLK | `{"rsi_15min_threshold": 30.0, "rsi_5min_threshold": 25.0, "rsi_60min_threshold": 35.0}` | -1.13 | 0.515 | 33 |
| 4 | analysis_driven_reversion | XLK | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.25}` | -3.14 | 0.444 | 45 |
| 5 | momentum_breakout | XLK | `{"breakout_period": 78, "volume_multiplier": 2.0}` | -8.94 | 0.468 | 158 |
| 6 | trend_follow | XLK | `{"breakout_period": 50, "rsi_threshold": 55.0}` | -25.26 | 0.444 | 356 |

## 推奨：**mean_reversion** （XLK、EV 1.01）

## 次のステップ

1. このレポートを人間がレビュー、最良戦略を確認
2. 推奨戦略を Plan 2 の本実装の対象とする
3. 必要に応じて、上位2戦略をアンサンブル運用も検討