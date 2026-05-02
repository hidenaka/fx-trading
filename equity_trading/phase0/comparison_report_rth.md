# Phase 0 Multi-Strategy Comparison Report

**Period:** 2019-05-01 〜 2026-05-01

## ETF別 ATR(14, 5min) 中央値（価格対比 %）

| ETF | Median |
|-----|--------|
| SPY | 0.107% |
| QQQ | 0.146% |
| IWM | 0.168% |
| DIA | 0.099% |
| XLK | 0.155% |

## 戦略: mean_reversion

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"threshold": 0.4}` | 189 | 67 | 0.354 | -0.117% | -22.05 |
| SPY | `{"threshold": 0.5}` | 27 | 8 | 0.296 | -0.137% | -3.70 |
| SPY | `{"threshold": 0.6}` | 0 | 0 | nan | nan% | nan |
| QQQ | `{"threshold": 0.4}` | 215 | 77 | 0.358 | -0.108% | -23.21 |
| QQQ | `{"threshold": 0.5}` | 41 | 16 | 0.390 | -0.097% | -3.97 |
| QQQ | `{"threshold": 0.6}` | 0 | 0 | nan | nan% | nan |
| IWM | `{"threshold": 0.4}` | 167 | 69 | 0.413 | -0.080% | -13.34 |
| IWM | `{"threshold": 0.5}` | 28 | 9 | 0.321 | -0.141% | -3.94 |
| IWM | `{"threshold": 0.6}` | 0 | 0 | nan | nan% | nan |
| DIA | `{"threshold": 0.4}` | 196 | 76 | 0.388 | -0.092% | -18.02 |
| DIA | `{"threshold": 0.5}` | 35 | 7 | 0.200 | -0.171% | -6.00 |
| DIA | `{"threshold": 0.6}` | 0 | 0 | nan | nan% | nan |
| XLK | `{"threshold": 0.4}` | 193 | 72 | 0.373 | -0.096% | -18.51 |
| XLK | `{"threshold": 0.5}` | 38 | 14 | 0.368 | -0.110% | -4.17 |
| XLK | `{"threshold": 0.6}` | 1 | 1 | 1.000 | 0.272% | 0.27 |

**Best for mean_reversion:** XLK / `{"threshold": 0.6}` → EV 0.27 (WR 1.000, Trades 1)

## 戦略: trend_follow

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"breakout_period": 20, "rsi_threshold": 50.0}` | 2971 | 1242 | 0.418 | -0.091% | -271.03 |
| SPY | `{"breakout_period": 50, "rsi_threshold": 55.0}` | 2006 | 834 | 0.416 | -0.092% | -184.36 |
| QQQ | `{"breakout_period": 20, "rsi_threshold": 50.0}` | 3098 | 1262 | 0.407 | -0.091% | -283.45 |
| QQQ | `{"breakout_period": 50, "rsi_threshold": 55.0}` | 2088 | 865 | 0.414 | -0.090% | -187.21 |
| IWM | `{"breakout_period": 20, "rsi_threshold": 50.0}` | 2443 | 954 | 0.391 | -0.100% | -243.95 |
| IWM | `{"breakout_period": 50, "rsi_threshold": 55.0}` | 1641 | 670 | 0.408 | -0.081% | -133.29 |
| DIA | `{"breakout_period": 20, "rsi_threshold": 50.0}` | 2984 | 1276 | 0.428 | -0.083% | -246.81 |
| DIA | `{"breakout_period": 50, "rsi_threshold": 55.0}` | 1995 | 820 | 0.411 | -0.092% | -183.05 |
| XLK | `{"breakout_period": 20, "rsi_threshold": 50.0}` | 2956 | 1223 | 0.414 | -0.083% | -244.51 |
| XLK | `{"breakout_period": 50, "rsi_threshold": 55.0}` | 2003 | 853 | 0.426 | -0.073% | -145.98 |

**Best for trend_follow:** IWM / `{"breakout_period": 50, "rsi_threshold": 55.0}` → EV -133.29 (WR 0.408, Trades 1641)

## 戦略: momentum_breakout

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"breakout_period": 78, "volume_multiplier": 1.5}` | 904 | 385 | 0.426 | -0.084% | -76.13 |
| SPY | `{"breakout_period": 78, "volume_multiplier": 2.0}` | 614 | 274 | 0.446 | -0.075% | -45.92 |
| QQQ | `{"breakout_period": 78, "volume_multiplier": 1.5}` | 991 | 421 | 0.425 | -0.081% | -80.23 |
| QQQ | `{"breakout_period": 78, "volume_multiplier": 2.0}` | 735 | 311 | 0.423 | -0.076% | -56.18 |
| IWM | `{"breakout_period": 78, "volume_multiplier": 1.5}` | 747 | 312 | 0.418 | -0.069% | -51.61 |
| IWM | `{"breakout_period": 78, "volume_multiplier": 2.0}` | 554 | 232 | 0.419 | -0.066% | -36.79 |
| DIA | `{"breakout_period": 78, "volume_multiplier": 1.5}` | 1025 | 415 | 0.405 | -0.090% | -92.67 |
| DIA | `{"breakout_period": 78, "volume_multiplier": 2.0}` | 808 | 329 | 0.407 | -0.089% | -71.88 |
| XLK | `{"breakout_period": 78, "volume_multiplier": 1.5}` | 860 | 365 | 0.424 | -0.067% | -57.25 |
| XLK | `{"breakout_period": 78, "volume_multiplier": 2.0}` | 632 | 279 | 0.441 | -0.059% | -37.45 |

**Best for momentum_breakout:** IWM / `{"breakout_period": 78, "volume_multiplier": 2.0}` → EV -36.79 (WR 0.419, Trades 554)

## 戦略: env_dependent_reversion

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"threshold": 0.4}` | 59 | 24 | 0.407 | -0.098% | -5.78 |
| SPY | `{"threshold": 0.5}` | 4 | 2 | 0.500 | -0.052% | -0.21 |
| QQQ | `{"threshold": 0.4}` | 41 | 14 | 0.341 | -0.123% | -5.05 |
| QQQ | `{"threshold": 0.5}` | 0 | 0 | nan | nan% | nan |
| IWM | `{"threshold": 0.4}` | 13 | 4 | 0.308 | -0.172% | -2.23 |
| IWM | `{"threshold": 0.5}` | 1 | 1 | 1.000 | 0.302% | 0.30 |
| DIA | `{"threshold": 0.4}` | 46 | 21 | 0.457 | -0.066% | -3.05 |
| DIA | `{"threshold": 0.5}` | 3 | 1 | 0.333 | -0.120% | -0.36 |
| XLK | `{"threshold": 0.4}` | 28 | 13 | 0.464 | -0.045% | -1.25 |
| XLK | `{"threshold": 0.5}` | 0 | 0 | nan | nan% | nan |

**Best for env_dependent_reversion:** IWM / `{"threshold": 0.5}` → EV 0.30 (WR 1.000, Trades 1)

## 戦略: multi_timeframe

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"rsi_15min_threshold": 35.0, "rsi_5min_threshold": 30.0, "rsi_60min_threshold": 40.0}` | 430 | 165 | 0.384 | -0.100% | -43.19 |
| SPY | `{"rsi_15min_threshold": 30.0, "rsi_5min_threshold": 25.0, "rsi_60min_threshold": 35.0}` | 139 | 51 | 0.367 | -0.106% | -14.69 |
| QQQ | `{"rsi_15min_threshold": 35.0, "rsi_5min_threshold": 30.0, "rsi_60min_threshold": 40.0}` | 453 | 151 | 0.333 | -0.144% | -65.10 |
| QQQ | `{"rsi_15min_threshold": 30.0, "rsi_5min_threshold": 25.0, "rsi_60min_threshold": 35.0}` | 163 | 59 | 0.362 | -0.126% | -20.48 |
| IWM | `{"rsi_15min_threshold": 35.0, "rsi_5min_threshold": 30.0, "rsi_60min_threshold": 40.0}` | 319 | 129 | 0.404 | -0.102% | -32.38 |
| IWM | `{"rsi_15min_threshold": 30.0, "rsi_5min_threshold": 25.0, "rsi_60min_threshold": 35.0}` | 89 | 40 | 0.449 | -0.050% | -4.48 |
| DIA | `{"rsi_15min_threshold": 35.0, "rsi_5min_threshold": 30.0, "rsi_60min_threshold": 40.0}` | 428 | 174 | 0.407 | -0.099% | -42.25 |
| DIA | `{"rsi_15min_threshold": 30.0, "rsi_5min_threshold": 25.0, "rsi_60min_threshold": 35.0}` | 151 | 54 | 0.358 | -0.109% | -16.46 |
| XLK | `{"rsi_15min_threshold": 35.0, "rsi_5min_threshold": 30.0, "rsi_60min_threshold": 40.0}` | 457 | 170 | 0.372 | -0.121% | -55.29 |
| XLK | `{"rsi_15min_threshold": 30.0, "rsi_5min_threshold": 25.0, "rsi_60min_threshold": 35.0}` | 156 | 60 | 0.385 | -0.097% | -15.16 |

**Best for multi_timeframe:** IWM / `{"rsi_15min_threshold": 30.0, "rsi_5min_threshold": 25.0, "rsi_60min_threshold": 35.0}` → EV -4.48 (WR 0.449, Trades 89)

## 戦略: analysis_driven_reversion

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.3}` | 200 | 72 | 0.360 | -0.120% | -24.04 |
| SPY | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.25}` | 262 | 97 | 0.370 | -0.113% | -29.52 |
| SPY | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.2}` | 860 | 363 | 0.422 | -0.077% | -65.87 |
| QQQ | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.3}` | 204 | 84 | 0.412 | -0.079% | -16.12 |
| QQQ | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.25}` | 274 | 112 | 0.409 | -0.084% | -23.15 |
| QQQ | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.2}` | 923 | 373 | 0.404 | -0.089% | -82.20 |
| IWM | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.3}` | 189 | 64 | 0.339 | -0.130% | -24.62 |
| IWM | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.25}` | 244 | 85 | 0.348 | -0.127% | -30.87 |
| IWM | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.2}` | 820 | 321 | 0.391 | -0.091% | -74.27 |
| DIA | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.3}` | 196 | 70 | 0.357 | -0.110% | -21.47 |
| DIA | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.25}` | 266 | 100 | 0.376 | -0.105% | -27.88 |
| DIA | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.2}` | 1081 | 457 | 0.423 | -0.089% | -96.57 |
| XLK | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.3}` | 176 | 67 | 0.381 | -0.108% | -19.02 |
| XLK | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.25}` | 254 | 94 | 0.370 | -0.132% | -33.52 |
| XLK | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.2}` | 900 | 378 | 0.420 | -0.076% | -68.83 |

**Best for analysis_driven_reversion:** QQQ / `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.3}` → EV -16.12 (WR 0.412, Trades 204)

## 戦略: vwap_scalp

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"k_entry": 1.0}` | 14 | 10 | 0.714 | 0.038% | 0.53 |
| SPY | `{"k_entry": 1.5}` | 13 | 9 | 0.692 | 0.028% | 0.37 |
| SPY | `{"k_entry": 2.0}` | 13 | 8 | 0.615 | -0.004% | -0.05 |
| QQQ | `{"k_entry": 1.0}` | 21 | 10 | 0.476 | -0.048% | -1.01 |
| QQQ | `{"k_entry": 1.5}` | 21 | 9 | 0.429 | -0.075% | -1.58 |
| QQQ | `{"k_entry": 2.0}` | 21 | 9 | 0.429 | -0.075% | -1.58 |
| IWM | `{"k_entry": 1.0}` | 7 | 6 | 0.857 | 0.209% | 1.46 |
| IWM | `{"k_entry": 1.5}` | 6 | 5 | 0.833 | 0.193% | 1.16 |
| IWM | `{"k_entry": 2.0}` | 6 | 5 | 0.833 | 0.193% | 1.16 |
| DIA | `{"k_entry": 1.0}` | 0 | 0 | nan | nan% | nan |
| DIA | `{"k_entry": 1.5}` | 0 | 0 | nan | nan% | nan |
| DIA | `{"k_entry": 2.0}` | 0 | 0 | nan | nan% | nan |
| XLK | `{"k_entry": 1.0}` | 2 | 1 | 0.500 | -0.030% | -0.06 |
| XLK | `{"k_entry": 1.5}` | 2 | 1 | 0.500 | -0.030% | -0.06 |
| XLK | `{"k_entry": 2.0}` | 2 | 1 | 0.500 | -0.030% | -0.06 |

**Best for vwap_scalp:** IWM / `{"k_entry": 1.0}` → EV 1.46 (WR 0.857, Trades 7)

## 戦略: opening_range_breakout

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"or_window_bars": 6}` | 882 | 400 | 0.454 | -0.090% | -79.52 |
| SPY | `{"or_window_bars": 12}` | 732 | 370 | 0.505 | -0.060% | -43.88 |
| QQQ | `{"or_window_bars": 6}` | 828 | 437 | 0.528 | -0.040% | -33.15 |
| QQQ | `{"or_window_bars": 12}` | 712 | 394 | 0.553 | 0.011% | 7.78 |
| IWM | `{"or_window_bars": 6}` | 589 | 313 | 0.531 | -0.029% | -16.86 |
| IWM | `{"or_window_bars": 12}` | 477 | 254 | 0.532 | 0.005% | 2.58 |
| DIA | `{"or_window_bars": 6}` | 742 | 384 | 0.518 | -0.048% | -35.73 |
| DIA | `{"or_window_bars": 12}` | 653 | 325 | 0.498 | -0.070% | -45.65 |
| XLK | `{"or_window_bars": 6}` | 732 | 396 | 0.541 | -0.074% | -54.07 |
| XLK | `{"or_window_bars": 12}` | 624 | 341 | 0.546 | -0.023% | -14.56 |

**Best for opening_range_breakout:** QQQ / `{"or_window_bars": 12}` → EV 7.78 (WR 0.553, Trades 712)

## 戦略: gap_fill

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"gap_threshold": 0.003, "stop_extension": 0.005}` | 229 | 97 | 0.424 | -0.120% | -27.50 |
| SPY | `{"gap_threshold": 0.005, "stop_extension": 0.005}` | 139 | 52 | 0.374 | -0.141% | -19.64 |
| SPY | `{"gap_threshold": 0.01, "stop_extension": 0.01}` | 50 | 26 | 0.520 | -0.056% | -2.79 |
| QQQ | `{"gap_threshold": 0.003, "stop_extension": 0.005}` | 291 | 112 | 0.385 | -0.114% | -33.23 |
| QQQ | `{"gap_threshold": 0.005, "stop_extension": 0.005}` | 195 | 72 | 0.369 | -0.120% | -23.39 |
| QQQ | `{"gap_threshold": 0.01, "stop_extension": 0.01}` | 79 | 38 | 0.481 | -0.091% | -7.21 |
| IWM | `{"gap_threshold": 0.003, "stop_extension": 0.005}` | 265 | 93 | 0.351 | -0.104% | -27.47 |
| IWM | `{"gap_threshold": 0.005, "stop_extension": 0.005}` | 186 | 67 | 0.360 | -0.096% | -17.78 |
| IWM | `{"gap_threshold": 0.01, "stop_extension": 0.01}` | 73 | 42 | 0.575 | 0.010% | 0.75 |
| DIA | `{"gap_threshold": 0.003, "stop_extension": 0.005}` | 220 | 88 | 0.400 | -0.138% | -30.33 |
| DIA | `{"gap_threshold": 0.005, "stop_extension": 0.005}` | 122 | 40 | 0.328 | -0.176% | -21.46 |
| DIA | `{"gap_threshold": 0.01, "stop_extension": 0.01}` | 37 | 19 | 0.514 | -0.078% | -2.90 |
| XLK | `{"gap_threshold": 0.003, "stop_extension": 0.005}` | 296 | 115 | 0.389 | -0.067% | -19.90 |
| XLK | `{"gap_threshold": 0.005, "stop_extension": 0.005}` | 214 | 84 | 0.393 | -0.049% | -10.44 |
| XLK | `{"gap_threshold": 0.01, "stop_extension": 0.01}` | 94 | 41 | 0.436 | -0.056% | -5.22 |

**Best for gap_fill:** IWM / `{"gap_threshold": 0.01, "stop_extension": 0.01}` → EV 0.75 (WR 0.575, Trades 73)

## 戦略: intraday_momentum

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"_max_hold_bars": 5, "entry_bar_pos": 71, "threshold": 0.001}` | 644 | 169 | 0.262 | -0.120% | -77.30 |
| SPY | `{"_max_hold_bars": 5, "entry_bar_pos": 71, "threshold": 0.003}` | 230 | 70 | 0.304 | -0.122% | -27.98 |
| SPY | `{"_max_hold_bars": 11, "entry_bar_pos": 65, "threshold": 0.001}` | 644 | 198 | 0.307 | -0.122% | -78.77 |
| SPY | `{"_max_hold_bars": 11, "entry_bar_pos": 65, "threshold": 0.003}` | 230 | 81 | 0.352 | -0.104% | -23.88 |
| QQQ | `{"_max_hold_bars": 5, "entry_bar_pos": 71, "threshold": 0.001}` | 749 | 223 | 0.298 | -0.098% | -73.42 |
| QQQ | `{"_max_hold_bars": 5, "entry_bar_pos": 71, "threshold": 0.003}` | 428 | 124 | 0.290 | -0.103% | -44.01 |
| QQQ | `{"_max_hold_bars": 11, "entry_bar_pos": 65, "threshold": 0.001}` | 749 | 272 | 0.363 | -0.103% | -77.51 |
| QQQ | `{"_max_hold_bars": 11, "entry_bar_pos": 65, "threshold": 0.003}` | 428 | 154 | 0.360 | -0.092% | -39.42 |
| IWM | `{"_max_hold_bars": 5, "entry_bar_pos": 71, "threshold": 0.001}` | 734 | 216 | 0.294 | -0.113% | -82.68 |
| IWM | `{"_max_hold_bars": 5, "entry_bar_pos": 71, "threshold": 0.003}` | 484 | 147 | 0.304 | -0.114% | -54.95 |
| IWM | `{"_max_hold_bars": 11, "entry_bar_pos": 65, "threshold": 0.001}` | 735 | 260 | 0.354 | -0.113% | -82.79 |
| IWM | `{"_max_hold_bars": 11, "entry_bar_pos": 65, "threshold": 0.003}` | 485 | 178 | 0.367 | -0.116% | -56.04 |
| DIA | `{"_max_hold_bars": 5, "entry_bar_pos": 71, "threshold": 0.001}` | 643 | 160 | 0.249 | -0.109% | -70.08 |
| DIA | `{"_max_hold_bars": 5, "entry_bar_pos": 71, "threshold": 0.003}` | 283 | 70 | 0.247 | -0.121% | -34.37 |
| DIA | `{"_max_hold_bars": 11, "entry_bar_pos": 65, "threshold": 0.001}` | 643 | 184 | 0.286 | -0.115% | -73.86 |
| DIA | `{"_max_hold_bars": 11, "entry_bar_pos": 65, "threshold": 0.003}` | 283 | 83 | 0.293 | -0.126% | -35.64 |
| XLK | `{"_max_hold_bars": 5, "entry_bar_pos": 71, "threshold": 0.001}` | 777 | 269 | 0.346 | -0.090% | -70.13 |
| XLK | `{"_max_hold_bars": 5, "entry_bar_pos": 71, "threshold": 0.003}` | 489 | 168 | 0.344 | -0.092% | -45.21 |
| XLK | `{"_max_hold_bars": 11, "entry_bar_pos": 65, "threshold": 0.001}` | 777 | 305 | 0.393 | -0.090% | -70.11 |
| XLK | `{"_max_hold_bars": 11, "entry_bar_pos": 65, "threshold": 0.003}` | 489 | 194 | 0.397 | -0.094% | -46.10 |

**Best for intraday_momentum:** SPY / `{"_max_hold_bars": 11, "entry_bar_pos": 65, "threshold": 0.003}` → EV -23.88 (WR 0.352, Trades 230)

## 戦略: pre_fomc_drift

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"_max_hold_bars": 130, "entry_bar_pos": 0}` | 57 | 30 | 0.526 | 0.288% | 16.42 |
| SPY | `{"_max_hold_bars": 94, "entry_bar_pos": 36}` | 57 | 30 | 0.526 | 0.065% | 3.72 |
| SPY | `{"_max_hold_bars": 41, "entry_bar_pos": 36}` | 57 | 26 | 0.456 | 0.038% | 2.18 |
| QQQ | `{"_max_hold_bars": 130, "entry_bar_pos": 0}` | 57 | 32 | 0.561 | 0.411% | 23.43 |
| QQQ | `{"_max_hold_bars": 94, "entry_bar_pos": 36}` | 57 | 33 | 0.579 | 0.214% | 12.21 |
| QQQ | `{"_max_hold_bars": 41, "entry_bar_pos": 36}` | 57 | 30 | 0.526 | 0.156% | 8.89 |
| IWM | `{"_max_hold_bars": 130, "entry_bar_pos": 0}` | 57 | 33 | 0.579 | 0.407% | 23.21 |
| IWM | `{"_max_hold_bars": 94, "entry_bar_pos": 36}` | 57 | 28 | 0.491 | 0.227% | 12.95 |
| IWM | `{"_max_hold_bars": 41, "entry_bar_pos": 36}` | 57 | 33 | 0.579 | 0.102% | 5.83 |
| DIA | `{"_max_hold_bars": 130, "entry_bar_pos": 0}` | 57 | 29 | 0.509 | 0.190% | 10.82 |
| DIA | `{"_max_hold_bars": 94, "entry_bar_pos": 36}` | 57 | 30 | 0.526 | -0.041% | -2.33 |
| DIA | `{"_max_hold_bars": 41, "entry_bar_pos": 36}` | 57 | 27 | 0.474 | -0.022% | -1.28 |
| XLK | `{"_max_hold_bars": 130, "entry_bar_pos": 0}` | 57 | 34 | 0.596 | 0.511% | 29.14 |
| XLK | `{"_max_hold_bars": 94, "entry_bar_pos": 36}` | 57 | 34 | 0.596 | 0.301% | 17.16 |
| XLK | `{"_max_hold_bars": 41, "entry_bar_pos": 36}` | 57 | 35 | 0.614 | 0.181% | 10.33 |

**Best for pre_fomc_drift:** XLK / `{"_max_hold_bars": 130, "entry_bar_pos": 0}` → EV 29.14 (WR 0.596, Trades 57)

## 戦略: turn_of_month

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"_max_hold_bars": 70, "entry_bar_pos": 0}` | 332 | 168 | 0.506 | -0.044% | -14.61 |
| SPY | `{"_max_hold_bars": 60, "entry_bar_pos": 12}` | 332 | 161 | 0.485 | -0.052% | -17.14 |
| QQQ | `{"_max_hold_bars": 70, "entry_bar_pos": 0}` | 331 | 179 | 0.541 | -0.047% | -15.49 |
| QQQ | `{"_max_hold_bars": 60, "entry_bar_pos": 12}` | 332 | 162 | 0.488 | -0.056% | -18.64 |
| IWM | `{"_max_hold_bars": 70, "entry_bar_pos": 0}` | 330 | 163 | 0.494 | -0.052% | -17.19 |
| IWM | `{"_max_hold_bars": 60, "entry_bar_pos": 12}` | 331 | 156 | 0.471 | -0.058% | -19.32 |
| DIA | `{"_max_hold_bars": 70, "entry_bar_pos": 0}` | 328 | 163 | 0.497 | -0.043% | -14.07 |
| DIA | `{"_max_hold_bars": 60, "entry_bar_pos": 12}` | 328 | 158 | 0.482 | -0.048% | -15.85 |
| XLK | `{"_max_hold_bars": 70, "entry_bar_pos": 0}` | 328 | 172 | 0.524 | -0.050% | -16.29 |
| XLK | `{"_max_hold_bars": 60, "entry_bar_pos": 12}` | 329 | 161 | 0.489 | -0.069% | -22.85 |

**Best for turn_of_month:** DIA / `{"_max_hold_bars": 70, "entry_bar_pos": 0}` → EV -14.07 (WR 0.497, Trades 328)

## 横断比較：戦略別ベスト

| Rank | Strategy | Symbol | Params | EV | Win Rate | Trades |
|------|----------|--------|--------|-----|----------|--------|
| 1 | pre_fomc_drift | XLK | `{"_max_hold_bars": 130, "entry_bar_pos": 0}` | 29.14 | 0.596 | 57 |
| 2 | opening_range_breakout | QQQ | `{"or_window_bars": 12}` | 7.78 | 0.553 | 712 |
| 3 | vwap_scalp | IWM | `{"k_entry": 1.0}` | 1.46 | 0.857 | 7 |
| 4 | gap_fill | IWM | `{"gap_threshold": 0.01, "stop_extension": 0.01}` | 0.75 | 0.575 | 73 |
| 5 | env_dependent_reversion | IWM | `{"threshold": 0.5}` | 0.30 | 1.000 | 1 |
| 6 | mean_reversion | XLK | `{"threshold": 0.6}` | 0.27 | 1.000 | 1 |
| 7 | multi_timeframe | IWM | `{"rsi_15min_threshold": 30.0, "rsi_5min_threshold": 25.0, "rsi_60min_threshold": 35.0}` | -4.48 | 0.449 | 89 |
| 8 | turn_of_month | DIA | `{"_max_hold_bars": 70, "entry_bar_pos": 0}` | -14.07 | 0.497 | 328 |
| 9 | analysis_driven_reversion | QQQ | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.3}` | -16.12 | 0.412 | 204 |
| 10 | intraday_momentum | SPY | `{"_max_hold_bars": 11, "entry_bar_pos": 65, "threshold": 0.003}` | -23.88 | 0.352 | 230 |
| 11 | momentum_breakout | IWM | `{"breakout_period": 78, "volume_multiplier": 2.0}` | -36.79 | 0.419 | 554 |
| 12 | trend_follow | IWM | `{"breakout_period": 50, "rsi_threshold": 55.0}` | -133.29 | 0.408 | 1641 |

## 推奨：**pre_fomc_drift** （XLK、EV 29.14）

## 次のステップ

1. このレポートを人間がレビュー、最良戦略を確認
2. 推奨戦略を Plan 2 の本実装の対象とする
3. 必要に応じて、上位2戦略をアンサンブル運用も検討