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
| SPY | `{"threshold": 0.4}` | 114 | 49 | 0.430 | -0.089% | -10.17 |
| SPY | `{"threshold": 0.5}` | 21 | 14 | 0.667 | -0.033% | -0.68 |
| SPY | `{"threshold": 0.6}` | 3 | 1 | 0.333 | -0.112% | -0.34 |
| QQQ | `{"threshold": 0.4}` | 128 | 50 | 0.391 | -0.102% | -13.03 |
| QQQ | `{"threshold": 0.5}` | 28 | 15 | 0.536 | -0.051% | -1.42 |
| QQQ | `{"threshold": 0.6}` | 2 | 0 | 0.000 | -0.225% | -0.45 |
| IWM | `{"threshold": 0.4}` | 75 | 37 | 0.493 | -0.055% | -4.09 |
| IWM | `{"threshold": 0.5}` | 17 | 8 | 0.471 | -0.068% | -1.15 |
| IWM | `{"threshold": 0.6}` | 0 | 0 | nan | nan% | nan |
| DIA | `{"threshold": 0.4}` | 42 | 20 | 0.476 | -0.072% | -3.04 |
| DIA | `{"threshold": 0.5}` | 3 | 0 | 0.000 | -0.209% | -0.63 |
| DIA | `{"threshold": 0.6}` | 0 | 0 | nan | nan% | nan |
| XLK | `{"threshold": 0.4}` | 36 | 22 | 0.611 | 0.019% | 0.69 |
| XLK | `{"threshold": 0.5}` | 2 | 0 | 0.000 | -0.294% | -0.59 |
| XLK | `{"threshold": 0.6}` | 0 | 0 | nan | nan% | nan |

**Best for mean_reversion:** XLK / `{"threshold": 0.4}` → EV 0.69 (WR 0.611, Trades 36)

## 戦略: trend_follow

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"breakout_period": 20, "rsi_threshold": 50.0}` | 1516 | 529 | 0.349 | -0.111% | -168.73 |
| SPY | `{"breakout_period": 50, "rsi_threshold": 55.0}` | 989 | 343 | 0.347 | -0.113% | -111.53 |
| QQQ | `{"breakout_period": 20, "rsi_threshold": 50.0}` | 1441 | 513 | 0.356 | -0.109% | -156.72 |
| QQQ | `{"breakout_period": 50, "rsi_threshold": 55.0}` | 915 | 333 | 0.364 | -0.108% | -99.18 |
| IWM | `{"breakout_period": 20, "rsi_threshold": 50.0}` | 1287 | 452 | 0.351 | -0.119% | -152.94 |
| IWM | `{"breakout_period": 50, "rsi_threshold": 55.0}` | 842 | 291 | 0.346 | -0.118% | -99.00 |
| DIA | `{"breakout_period": 20, "rsi_threshold": 50.0}` | 1148 | 443 | 0.386 | -0.104% | -119.49 |
| DIA | `{"breakout_period": 50, "rsi_threshold": 55.0}` | 757 | 291 | 0.384 | -0.103% | -78.34 |
| XLK | `{"breakout_period": 20, "rsi_threshold": 50.0}` | 590 | 244 | 0.414 | -0.151% | -89.13 |
| XLK | `{"breakout_period": 50, "rsi_threshold": 55.0}` | 399 | 163 | 0.409 | -0.083% | -33.15 |

**Best for trend_follow:** XLK / `{"breakout_period": 50, "rsi_threshold": 55.0}` → EV -33.15 (WR 0.409, Trades 399)

## 戦略: momentum_breakout

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"breakout_period": 78, "volume_multiplier": 1.5}` | 617 | 211 | 0.342 | -0.110% | -67.99 |
| SPY | `{"breakout_period": 78, "volume_multiplier": 2.0}` | 510 | 161 | 0.316 | -0.117% | -59.64 |
| QQQ | `{"breakout_period": 78, "volume_multiplier": 1.5}` | 594 | 198 | 0.333 | -0.118% | -69.83 |
| QQQ | `{"breakout_period": 78, "volume_multiplier": 2.0}` | 506 | 163 | 0.322 | -0.124% | -62.49 |
| IWM | `{"breakout_period": 78, "volume_multiplier": 1.5}` | 520 | 154 | 0.296 | -0.137% | -71.47 |
| IWM | `{"breakout_period": 78, "volume_multiplier": 2.0}` | 439 | 125 | 0.285 | -0.143% | -62.88 |
| DIA | `{"breakout_period": 78, "volume_multiplier": 1.5}` | 405 | 173 | 0.427 | -0.090% | -36.47 |
| DIA | `{"breakout_period": 78, "volume_multiplier": 2.0}` | 340 | 148 | 0.435 | -0.088% | -29.94 |
| XLK | `{"breakout_period": 78, "volume_multiplier": 1.5}` | 191 | 77 | 0.403 | -0.090% | -17.19 |
| XLK | `{"breakout_period": 78, "volume_multiplier": 2.0}` | 165 | 72 | 0.436 | -0.076% | -12.52 |

**Best for momentum_breakout:** XLK / `{"breakout_period": 78, "volume_multiplier": 2.0}` → EV -12.52 (WR 0.436, Trades 165)

## 戦略: env_dependent_reversion

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"threshold": 0.4}` | 67 | 24 | 0.358 | -0.106% | -7.12 |
| SPY | `{"threshold": 0.5}` | 3 | 3 | 1.000 | 0.047% | 0.14 |
| QQQ | `{"threshold": 0.4}` | 74 | 24 | 0.324 | -0.126% | -9.33 |
| QQQ | `{"threshold": 0.5}` | 6 | 3 | 0.500 | -0.062% | -0.37 |
| IWM | `{"threshold": 0.4}` | 36 | 15 | 0.417 | -0.084% | -3.01 |
| IWM | `{"threshold": 0.5}` | 2 | 1 | 0.500 | -0.057% | -0.11 |
| DIA | `{"threshold": 0.4}` | 31 | 17 | 0.548 | -0.052% | -1.61 |
| DIA | `{"threshold": 0.5}` | 2 | 0 | 0.000 | -0.209% | -0.42 |
| XLK | `{"threshold": 0.4}` | 21 | 12 | 0.571 | -0.005% | -0.11 |
| XLK | `{"threshold": 0.5}` | 1 | 0 | 0.000 | -0.294% | -0.29 |

**Best for env_dependent_reversion:** SPY / `{"threshold": 0.5}` → EV 0.14 (WR 1.000, Trades 3)

## 戦略: multi_timeframe

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"rsi_15min_threshold": 35.0, "rsi_5min_threshold": 30.0, "rsi_60min_threshold": 40.0}` | 227 | 91 | 0.401 | -0.094% | -21.35 |
| SPY | `{"rsi_15min_threshold": 30.0, "rsi_5min_threshold": 25.0, "rsi_60min_threshold": 35.0}` | 80 | 29 | 0.362 | -0.104% | -8.32 |
| QQQ | `{"rsi_15min_threshold": 35.0, "rsi_5min_threshold": 30.0, "rsi_60min_threshold": 40.0}` | 235 | 83 | 0.353 | -0.103% | -24.10 |
| QQQ | `{"rsi_15min_threshold": 30.0, "rsi_5min_threshold": 25.0, "rsi_60min_threshold": 35.0}` | 80 | 33 | 0.412 | -0.091% | -7.27 |
| IWM | `{"rsi_15min_threshold": 35.0, "rsi_5min_threshold": 30.0, "rsi_60min_threshold": 40.0}` | 180 | 83 | 0.461 | -0.069% | -12.34 |
| IWM | `{"rsi_15min_threshold": 30.0, "rsi_5min_threshold": 25.0, "rsi_60min_threshold": 35.0}` | 54 | 26 | 0.481 | -0.060% | -3.22 |
| DIA | `{"rsi_15min_threshold": 35.0, "rsi_5min_threshold": 30.0, "rsi_60min_threshold": 40.0}` | 178 | 78 | 0.438 | -0.083% | -14.83 |
| DIA | `{"rsi_15min_threshold": 30.0, "rsi_5min_threshold": 25.0, "rsi_60min_threshold": 35.0}` | 51 | 18 | 0.353 | -0.104% | -5.30 |
| XLK | `{"rsi_15min_threshold": 35.0, "rsi_5min_threshold": 30.0, "rsi_60min_threshold": 40.0}` | 99 | 41 | 0.414 | -0.080% | -7.93 |
| XLK | `{"rsi_15min_threshold": 30.0, "rsi_5min_threshold": 25.0, "rsi_60min_threshold": 35.0}` | 37 | 13 | 0.351 | -0.100% | -3.69 |

**Best for multi_timeframe:** IWM / `{"rsi_15min_threshold": 30.0, "rsi_5min_threshold": 25.0, "rsi_60min_threshold": 35.0}` → EV -3.22 (WR 0.481, Trades 54)

## 戦略: analysis_driven_reversion

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.3}` | 96 | 41 | 0.427 | -0.096% | -9.23 |
| SPY | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.25}` | 135 | 50 | 0.370 | -0.106% | -14.33 |
| SPY | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.2}` | 712 | 230 | 0.323 | -0.116% | -82.70 |
| QQQ | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.3}` | 108 | 43 | 0.398 | -0.090% | -9.77 |
| QQQ | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.25}` | 152 | 58 | 0.382 | -0.107% | -16.25 |
| QQQ | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.2}` | 660 | 226 | 0.342 | -0.116% | -76.67 |
| IWM | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.3}` | 96 | 40 | 0.417 | -0.091% | -8.69 |
| IWM | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.25}` | 134 | 52 | 0.388 | -0.108% | -14.41 |
| IWM | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.2}` | 617 | 198 | 0.321 | -0.134% | -82.78 |
| DIA | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.3}` | 43 | 18 | 0.419 | -0.100% | -4.32 |
| DIA | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.25}` | 79 | 33 | 0.418 | -0.090% | -7.09 |
| DIA | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.2}` | 473 | 187 | 0.395 | -0.102% | -48.07 |
| XLK | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.3}` | 31 | 11 | 0.355 | -0.096% | -2.98 |
| XLK | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.25}` | 47 | 20 | 0.426 | -0.058% | -2.73 |
| XLK | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.2}` | 243 | 96 | 0.395 | -0.249% | -60.55 |

**Best for analysis_driven_reversion:** XLK / `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.25}` → EV -2.73 (WR 0.426, Trades 47)

## 戦略: vwap_scalp

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"k_entry": 1.0}` | 2 | 1 | 0.500 | -0.072% | -0.14 |
| SPY | `{"k_entry": 1.5}` | 2 | 2 | 1.000 | 0.047% | 0.09 |
| SPY | `{"k_entry": 2.0}` | 1 | 1 | 1.000 | 0.047% | 0.05 |
| QQQ | `{"k_entry": 1.0}` | 0 | 0 | nan | nan% | nan |
| QQQ | `{"k_entry": 1.5}` | 0 | 0 | nan | nan% | nan |
| QQQ | `{"k_entry": 2.0}` | 0 | 0 | nan | nan% | nan |
| IWM | `{"k_entry": 1.0}` | 0 | 0 | nan | nan% | nan |
| IWM | `{"k_entry": 1.5}` | 0 | 0 | nan | nan% | nan |
| IWM | `{"k_entry": 2.0}` | 0 | 0 | nan | nan% | nan |
| DIA | `{"k_entry": 1.0}` | 13 | 4 | 0.308 | -0.144% | -1.87 |
| DIA | `{"k_entry": 1.5}` | 11 | 3 | 0.273 | -0.158% | -1.74 |
| DIA | `{"k_entry": 2.0}` | 10 | 2 | 0.200 | -0.184% | -1.84 |
| XLK | `{"k_entry": 1.0}` | 0 | 0 | nan | nan% | nan |
| XLK | `{"k_entry": 1.5}` | 0 | 0 | nan | nan% | nan |
| XLK | `{"k_entry": 2.0}` | 0 | 0 | nan | nan% | nan |

**Best for vwap_scalp:** SPY / `{"k_entry": 1.5}` → EV 0.09 (WR 1.000, Trades 2)

## 戦略: opening_range_breakout

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"or_window_bars": 6}` | 239 | 43 | 0.180 | -0.135% | -32.32 |
| SPY | `{"or_window_bars": 12}` | 237 | 49 | 0.207 | -0.157% | -37.13 |
| QQQ | `{"or_window_bars": 6}` | 231 | 45 | 0.195 | -0.174% | -40.13 |
| QQQ | `{"or_window_bars": 12}` | 232 | 49 | 0.211 | -0.196% | -45.58 |
| IWM | `{"or_window_bars": 6}` | 207 | 50 | 0.242 | -0.128% | -26.50 |
| IWM | `{"or_window_bars": 12}` | 204 | 58 | 0.284 | -0.161% | -32.76 |
| DIA | `{"or_window_bars": 6}` | 220 | 40 | 0.182 | -0.117% | -25.72 |
| DIA | `{"or_window_bars": 12}` | 213 | 59 | 0.277 | -0.111% | -23.72 |
| XLK | `{"or_window_bars": 6}` | 136 | 53 | 0.390 | -0.068% | -9.19 |
| XLK | `{"or_window_bars": 12}` | 132 | 55 | 0.417 | -0.076% | -10.09 |

**Best for opening_range_breakout:** XLK / `{"or_window_bars": 6}` → EV -9.19 (WR 0.390, Trades 136)

## 戦略: gap_fill

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"gap_threshold": 0.003, "stop_extension": 0.005}` | 39 | 26 | 0.667 | 0.116% | 4.53 |
| SPY | `{"gap_threshold": 0.005, "stop_extension": 0.005}` | 19 | 12 | 0.632 | 0.138% | 2.62 |
| SPY | `{"gap_threshold": 0.01, "stop_extension": 0.01}` | 6 | 5 | 0.833 | 0.295% | 1.77 |
| QQQ | `{"gap_threshold": 0.003, "stop_extension": 0.005}` | 45 | 29 | 0.644 | 0.174% | 7.84 |
| QQQ | `{"gap_threshold": 0.005, "stop_extension": 0.005}` | 24 | 16 | 0.667 | 0.282% | 6.76 |
| QQQ | `{"gap_threshold": 0.01, "stop_extension": 0.01}` | 10 | 8 | 0.800 | 0.599% | 5.99 |
| IWM | `{"gap_threshold": 0.003, "stop_extension": 0.005}` | 42 | 15 | 0.357 | -0.135% | -5.69 |
| IWM | `{"gap_threshold": 0.005, "stop_extension": 0.005}` | 30 | 11 | 0.367 | -0.090% | -2.69 |
| IWM | `{"gap_threshold": 0.01, "stop_extension": 0.01}` | 13 | 9 | 0.692 | 0.465% | 6.04 |
| DIA | `{"gap_threshold": 0.003, "stop_extension": 0.005}` | 34 | 19 | 0.559 | 0.028% | 0.95 |
| DIA | `{"gap_threshold": 0.005, "stop_extension": 0.005}` | 25 | 13 | 0.520 | 0.017% | 0.43 |
| DIA | `{"gap_threshold": 0.01, "stop_extension": 0.01}` | 5 | 2 | 0.400 | -0.349% | -1.75 |
| XLK | `{"gap_threshold": 0.003, "stop_extension": 0.005}` | 31 | 14 | 0.452 | -0.046% | -1.41 |
| XLK | `{"gap_threshold": 0.005, "stop_extension": 0.005}` | 17 | 11 | 0.647 | 0.193% | 3.29 |
| XLK | `{"gap_threshold": 0.01, "stop_extension": 0.01}` | 6 | 3 | 0.500 | 0.389% | 2.34 |

**Best for gap_fill:** QQQ / `{"gap_threshold": 0.003, "stop_extension": 0.005}` → EV 7.84 (WR 0.644, Trades 45)

## 横断比較：戦略別ベスト

| Rank | Strategy | Symbol | Params | EV | Win Rate | Trades |
|------|----------|--------|--------|-----|----------|--------|
| 1 | gap_fill | QQQ | `{"gap_threshold": 0.003, "stop_extension": 0.005}` | 7.84 | 0.644 | 45 |
| 2 | mean_reversion | XLK | `{"threshold": 0.4}` | 0.69 | 0.611 | 36 |
| 3 | env_dependent_reversion | SPY | `{"threshold": 0.5}` | 0.14 | 1.000 | 3 |
| 4 | vwap_scalp | SPY | `{"k_entry": 1.5}` | 0.09 | 1.000 | 2 |
| 5 | analysis_driven_reversion | XLK | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.25}` | -2.73 | 0.426 | 47 |
| 6 | multi_timeframe | IWM | `{"rsi_15min_threshold": 30.0, "rsi_5min_threshold": 25.0, "rsi_60min_threshold": 35.0}` | -3.22 | 0.481 | 54 |
| 7 | opening_range_breakout | XLK | `{"or_window_bars": 6}` | -9.19 | 0.390 | 136 |
| 8 | momentum_breakout | XLK | `{"breakout_period": 78, "volume_multiplier": 2.0}` | -12.52 | 0.436 | 165 |
| 9 | trend_follow | XLK | `{"breakout_period": 50, "rsi_threshold": 55.0}` | -33.15 | 0.409 | 399 |

## 推奨：**gap_fill** （QQQ、EV 7.84）

## 次のステップ

1. このレポートを人間がレビュー、最良戦略を確認
2. 推奨戦略を Plan 2 の本実装の対象とする
3. 必要に応じて、上位2戦略をアンサンブル運用も検討