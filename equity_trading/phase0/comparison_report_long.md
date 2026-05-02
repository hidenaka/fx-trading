# Phase 0 Multi-Strategy Comparison Report

**Period:** 2019-05-01 〜 2026-05-01

## ETF別 ATR(14, 5min) 中央値（価格対比 %）

| ETF | Median |
|-----|--------|
| SPY | 0.069% |
| QQQ | 0.090% |
| IWM | 0.108% |
| DIA | 0.079% |
| XLK | 0.138% |

## 戦略: mean_reversion

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"threshold": 0.4}` | 461 | 190 | 0.412 | -0.094% | -43.15 |
| SPY | `{"threshold": 0.5}` | 77 | 30 | 0.390 | -0.107% | -8.21 |
| SPY | `{"threshold": 0.6}` | 6 | 1 | 0.167 | -0.159% | -0.95 |
| QQQ | `{"threshold": 0.4}` | 543 | 215 | 0.396 | -0.089% | -48.57 |
| QQQ | `{"threshold": 0.5}` | 104 | 49 | 0.471 | -0.066% | -6.86 |
| QQQ | `{"threshold": 0.6}` | 5 | 0 | 0.000 | -0.235% | -1.18 |
| IWM | `{"threshold": 0.4}` | 322 | 128 | 0.398 | -0.101% | -32.59 |
| IWM | `{"threshold": 0.5}` | 58 | 22 | 0.379 | -0.104% | -6.05 |
| IWM | `{"threshold": 0.6}` | 1 | 0 | 0.000 | -0.262% | -0.26 |
| DIA | `{"threshold": 0.4}` | 189 | 77 | 0.407 | -0.093% | -17.49 |
| DIA | `{"threshold": 0.5}` | 13 | 1 | 0.077 | -0.191% | -2.49 |
| DIA | `{"threshold": 0.6}` | 0 | 0 | nan | nan% | nan |
| XLK | `{"threshold": 0.4}` | 136 | 51 | 0.375 | -0.102% | -13.81 |
| XLK | `{"threshold": 0.5}` | 7 | 2 | 0.286 | -0.153% | -1.07 |
| XLK | `{"threshold": 0.6}` | 0 | 0 | nan | nan% | nan |

**Best for mean_reversion:** IWM / `{"threshold": 0.6}` → EV -0.26 (WR 0.000, Trades 1)

## 戦略: trend_follow

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"breakout_period": 20, "rsi_threshold": 50.0}` | 7307 | 2720 | 0.372 | -0.105% | -768.80 |
| SPY | `{"breakout_period": 50, "rsi_threshold": 55.0}` | 4723 | 1764 | 0.373 | -0.105% | -494.84 |
| QQQ | `{"breakout_period": 20, "rsi_threshold": 50.0}` | 7542 | 2763 | 0.366 | -0.107% | -804.26 |
| QQQ | `{"breakout_period": 50, "rsi_threshold": 55.0}` | 4896 | 1780 | 0.364 | -0.111% | -544.69 |
| IWM | `{"breakout_period": 20, "rsi_threshold": 50.0}` | 5726 | 2085 | 0.364 | -0.115% | -655.69 |
| IWM | `{"breakout_period": 50, "rsi_threshold": 55.0}` | 3782 | 1358 | 0.359 | -0.116% | -439.44 |
| DIA | `{"breakout_period": 20, "rsi_threshold": 50.0}` | 5289 | 2102 | 0.397 | -0.101% | -535.17 |
| DIA | `{"breakout_period": 50, "rsi_threshold": 55.0}` | 3455 | 1339 | 0.388 | -0.103% | -357.41 |
| XLK | `{"breakout_period": 20, "rsi_threshold": 50.0}` | 4511 | 1793 | 0.397 | -0.110% | -498.37 |
| XLK | `{"breakout_period": 50, "rsi_threshold": 55.0}` | 3043 | 1251 | 0.411 | -0.091% | -277.74 |

**Best for trend_follow:** XLK / `{"breakout_period": 50, "rsi_threshold": 55.0}` → EV -277.74 (WR 0.411, Trades 3043)

## 戦略: momentum_breakout

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"breakout_period": 78, "volume_multiplier": 1.5}` | 2965 | 1080 | 0.364 | -0.106% | -313.82 |
| SPY | `{"breakout_period": 78, "volume_multiplier": 2.0}` | 2468 | 872 | 0.353 | -0.109% | -268.07 |
| QQQ | `{"breakout_period": 78, "volume_multiplier": 1.5}` | 3115 | 1077 | 0.346 | -0.115% | -358.77 |
| QQQ | `{"breakout_period": 78, "volume_multiplier": 2.0}` | 2592 | 858 | 0.331 | -0.120% | -311.82 |
| IWM | `{"breakout_period": 78, "volume_multiplier": 1.5}` | 2300 | 791 | 0.344 | -0.122% | -279.51 |
| IWM | `{"breakout_period": 78, "volume_multiplier": 2.0}` | 1940 | 660 | 0.340 | -0.124% | -239.66 |
| DIA | `{"breakout_period": 78, "volume_multiplier": 1.5}` | 1902 | 760 | 0.400 | -0.098% | -186.14 |
| DIA | `{"breakout_period": 78, "volume_multiplier": 2.0}` | 1588 | 645 | 0.406 | -0.096% | -153.02 |
| XLK | `{"breakout_period": 78, "volume_multiplier": 1.5}` | 1437 | 585 | 0.407 | -0.090% | -130.01 |
| XLK | `{"breakout_period": 78, "volume_multiplier": 2.0}` | 1224 | 499 | 0.408 | -0.089% | -109.23 |

**Best for momentum_breakout:** XLK / `{"breakout_period": 78, "volume_multiplier": 2.0}` → EV -109.23 (WR 0.408, Trades 1224)

## 戦略: env_dependent_reversion

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"threshold": 0.4}` | 275 | 110 | 0.400 | -0.095% | -26.04 |
| SPY | `{"threshold": 0.5}` | 17 | 7 | 0.412 | -0.083% | -1.42 |
| QQQ | `{"threshold": 0.4}` | 298 | 115 | 0.386 | -0.092% | -27.56 |
| QQQ | `{"threshold": 0.5}` | 24 | 11 | 0.458 | -0.058% | -1.38 |
| IWM | `{"threshold": 0.4}` | 164 | 67 | 0.409 | -0.087% | -14.24 |
| IWM | `{"threshold": 0.5}` | 8 | 4 | 0.500 | -0.052% | -0.41 |
| DIA | `{"threshold": 0.4}` | 144 | 60 | 0.417 | -0.091% | -13.06 |
| DIA | `{"threshold": 0.5}` | 8 | 0 | 0.000 | -0.219% | -1.75 |
| XLK | `{"threshold": 0.4}` | 76 | 31 | 0.408 | -0.077% | -5.82 |
| XLK | `{"threshold": 0.5}` | 1 | 0 | 0.000 | -0.307% | -0.31 |

**Best for env_dependent_reversion:** XLK / `{"threshold": 0.5}` → EV -0.31 (WR 0.000, Trades 1)

## 戦略: multi_timeframe

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"rsi_15min_threshold": 35.0, "rsi_5min_threshold": 30.0, "rsi_60min_threshold": 40.0}` | 1041 | 413 | 0.397 | -0.096% | -100.19 |
| SPY | `{"rsi_15min_threshold": 30.0, "rsi_5min_threshold": 25.0, "rsi_60min_threshold": 35.0}` | 345 | 133 | 0.386 | -0.100% | -34.45 |
| QQQ | `{"rsi_15min_threshold": 35.0, "rsi_5min_threshold": 30.0, "rsi_60min_threshold": 40.0}` | 1177 | 473 | 0.402 | -0.088% | -104.11 |
| QQQ | `{"rsi_15min_threshold": 30.0, "rsi_5min_threshold": 25.0, "rsi_60min_threshold": 35.0}` | 403 | 175 | 0.434 | -0.076% | -30.56 |
| IWM | `{"rsi_15min_threshold": 35.0, "rsi_5min_threshold": 30.0, "rsi_60min_threshold": 40.0}` | 787 | 340 | 0.432 | -0.078% | -61.68 |
| IWM | `{"rsi_15min_threshold": 30.0, "rsi_5min_threshold": 25.0, "rsi_60min_threshold": 35.0}` | 244 | 103 | 0.422 | -0.084% | -20.55 |
| DIA | `{"rsi_15min_threshold": 35.0, "rsi_5min_threshold": 30.0, "rsi_60min_threshold": 40.0}` | 836 | 347 | 0.415 | -0.089% | -74.55 |
| DIA | `{"rsi_15min_threshold": 30.0, "rsi_5min_threshold": 25.0, "rsi_60min_threshold": 35.0}` | 293 | 108 | 0.369 | -0.106% | -31.10 |
| XLK | `{"rsi_15min_threshold": 35.0, "rsi_5min_threshold": 30.0, "rsi_60min_threshold": 40.0}` | 727 | 295 | 0.406 | -0.086% | -62.52 |
| XLK | `{"rsi_15min_threshold": 30.0, "rsi_5min_threshold": 25.0, "rsi_60min_threshold": 35.0}` | 257 | 100 | 0.389 | -0.088% | -22.63 |

**Best for multi_timeframe:** IWM / `{"rsi_15min_threshold": 30.0, "rsi_5min_threshold": 25.0, "rsi_60min_threshold": 35.0}` → EV -20.55 (WR 0.422, Trades 244)

## 戦略: analysis_driven_reversion

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.3}` | 387 | 157 | 0.406 | -0.102% | -39.31 |
| SPY | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.25}` | 611 | 245 | 0.401 | -0.096% | -58.92 |
| SPY | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.2}` | 3404 | 1173 | 0.345 | -0.112% | -380.38 |
| QQQ | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.3}` | 503 | 169 | 0.336 | -0.121% | -61.01 |
| QQQ | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.25}` | 745 | 267 | 0.358 | -0.111% | -82.71 |
| QQQ | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.2}` | 3432 | 1175 | 0.342 | -0.116% | -398.79 |
| IWM | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.3}` | 389 | 157 | 0.404 | -0.098% | -38.09 |
| IWM | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.25}` | 584 | 239 | 0.409 | -0.097% | -56.64 |
| IWM | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.2}` | 2787 | 999 | 0.358 | -0.116% | -322.65 |
| DIA | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.3}` | 255 | 109 | 0.427 | -0.094% | -23.97 |
| DIA | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.25}` | 404 | 163 | 0.403 | -0.098% | -39.53 |
| DIA | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.2}` | 2347 | 962 | 0.410 | -0.097% | -226.76 |
| XLK | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.3}` | 178 | 77 | 0.433 | -0.071% | -12.59 |
| XLK | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.25}` | 281 | 124 | 0.441 | -0.069% | -19.31 |
| XLK | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.2}` | 1786 | 741 | 0.415 | -0.105% | -188.29 |

**Best for analysis_driven_reversion:** XLK / `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.3}` → EV -12.59 (WR 0.433, Trades 178)

## 戦略: vwap_scalp

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"k_entry": 1.0}` | 39 | 17 | 0.436 | -0.086% | -3.36 |
| SPY | `{"k_entry": 1.5}` | 39 | 17 | 0.436 | -0.086% | -3.36 |
| SPY | `{"k_entry": 2.0}` | 37 | 16 | 0.432 | -0.087% | -3.22 |
| QQQ | `{"k_entry": 1.0}` | 56 | 22 | 0.393 | -0.097% | -5.44 |
| QQQ | `{"k_entry": 1.5}` | 52 | 20 | 0.385 | -0.100% | -5.20 |
| QQQ | `{"k_entry": 2.0}` | 46 | 19 | 0.413 | -0.090% | -4.14 |
| IWM | `{"k_entry": 1.0}` | 26 | 11 | 0.423 | -0.085% | -2.22 |
| IWM | `{"k_entry": 1.5}` | 24 | 12 | 0.500 | -0.053% | -1.27 |
| IWM | `{"k_entry": 2.0}` | 24 | 12 | 0.500 | -0.053% | -1.28 |
| DIA | `{"k_entry": 1.0}` | 0 | 0 | nan | nan% | nan |
| DIA | `{"k_entry": 1.5}` | 0 | 0 | nan | nan% | nan |
| DIA | `{"k_entry": 2.0}` | 0 | 0 | nan | nan% | nan |
| XLK | `{"k_entry": 1.0}` | 3 | 2 | 0.667 | 0.052% | 0.16 |
| XLK | `{"k_entry": 1.5}` | 3 | 2 | 0.667 | 0.052% | 0.16 |
| XLK | `{"k_entry": 2.0}` | 3 | 2 | 0.667 | 0.052% | 0.16 |

**Best for vwap_scalp:** XLK / `{"k_entry": 1.0}` → EV 0.16 (WR 0.667, Trades 3)

## 戦略: opening_range_breakout

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"or_window_bars": 6}` | 1159 | 248 | 0.214 | -0.125% | -144.76 |
| SPY | `{"or_window_bars": 12}` | 1140 | 287 | 0.252 | -0.139% | -158.11 |
| QQQ | `{"or_window_bars": 6}` | 1188 | 278 | 0.234 | -0.152% | -180.50 |
| QQQ | `{"or_window_bars": 12}` | 1176 | 284 | 0.241 | -0.172% | -202.15 |
| IWM | `{"or_window_bars": 6}` | 934 | 258 | 0.276 | -0.138% | -129.20 |
| IWM | `{"or_window_bars": 12}` | 922 | 301 | 0.326 | -0.153% | -141.18 |
| DIA | `{"or_window_bars": 6}` | 1075 | 241 | 0.224 | -0.120% | -129.21 |
| DIA | `{"or_window_bars": 12}` | 1018 | 344 | 0.338 | -0.105% | -106.73 |
| XLK | `{"or_window_bars": 6}` | 1018 | 392 | 0.385 | -0.100% | -101.38 |
| XLK | `{"or_window_bars": 12}` | 938 | 397 | 0.423 | -0.094% | -88.09 |

**Best for opening_range_breakout:** XLK / `{"or_window_bars": 12}` → EV -88.09 (WR 0.423, Trades 938)

## 戦略: gap_fill

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"gap_threshold": 0.003, "stop_extension": 0.005}` | 166 | 86 | 0.518 | -0.002% | -0.30 |
| SPY | `{"gap_threshold": 0.005, "stop_extension": 0.005}` | 81 | 40 | 0.494 | 0.038% | 3.08 |
| SPY | `{"gap_threshold": 0.01, "stop_extension": 0.01}` | 21 | 11 | 0.524 | 0.007% | 0.16 |
| QQQ | `{"gap_threshold": 0.003, "stop_extension": 0.005}` | 213 | 122 | 0.573 | 0.086% | 18.35 |
| QQQ | `{"gap_threshold": 0.005, "stop_extension": 0.005}` | 117 | 58 | 0.496 | 0.121% | 14.16 |
| QQQ | `{"gap_threshold": 0.01, "stop_extension": 0.01}` | 43 | 23 | 0.535 | 0.195% | 8.38 |
| IWM | `{"gap_threshold": 0.003, "stop_extension": 0.005}` | 194 | 85 | 0.438 | -0.095% | -18.41 |
| IWM | `{"gap_threshold": 0.005, "stop_extension": 0.005}` | 113 | 42 | 0.372 | -0.098% | -11.02 |
| IWM | `{"gap_threshold": 0.01, "stop_extension": 0.01}` | 33 | 19 | 0.576 | 0.151% | 4.97 |
| DIA | `{"gap_threshold": 0.003, "stop_extension": 0.005}` | 151 | 72 | 0.477 | -0.030% | -4.58 |
| DIA | `{"gap_threshold": 0.005, "stop_extension": 0.005}` | 75 | 34 | 0.453 | 0.040% | 3.02 |
| DIA | `{"gap_threshold": 0.01, "stop_extension": 0.01}` | 21 | 8 | 0.381 | -0.129% | -2.71 |
| XLK | `{"gap_threshold": 0.003, "stop_extension": 0.005}` | 241 | 120 | 0.498 | -0.027% | -6.52 |
| XLK | `{"gap_threshold": 0.005, "stop_extension": 0.005}` | 143 | 63 | 0.441 | -0.030% | -4.32 |
| XLK | `{"gap_threshold": 0.01, "stop_extension": 0.01}` | 52 | 18 | 0.346 | -0.131% | -6.80 |

**Best for gap_fill:** QQQ / `{"gap_threshold": 0.003, "stop_extension": 0.005}` → EV 18.35 (WR 0.573, Trades 213)

## 戦略: intraday_momentum

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"_max_hold_bars": 5, "entry_bar_pos": 71, "threshold": 0.0}` | 958 | 284 | 0.296 | -0.090% | -86.23 |
| SPY | `{"_max_hold_bars": 5, "entry_bar_pos": 71, "threshold": 0.001}` | 390 | 132 | 0.338 | -0.088% | -34.39 |
| SPY | `{"_max_hold_bars": 5, "entry_bar_pos": 71, "threshold": 0.003}` | 68 | 25 | 0.368 | -0.111% | -7.54 |
| SPY | `{"_max_hold_bars": 11, "entry_bar_pos": 65, "threshold": 0.001}` | 390 | 145 | 0.372 | -0.111% | -43.23 |
| SPY | `{"_max_hold_bars": 11, "entry_bar_pos": 65, "threshold": 0.003}` | 68 | 24 | 0.353 | -0.139% | -9.47 |
| QQQ | `{"_max_hold_bars": 5, "entry_bar_pos": 71, "threshold": 0.0}` | 943 | 366 | 0.388 | -0.089% | -83.60 |
| QQQ | `{"_max_hold_bars": 5, "entry_bar_pos": 71, "threshold": 0.001}` | 480 | 189 | 0.394 | -0.103% | -49.24 |
| QQQ | `{"_max_hold_bars": 5, "entry_bar_pos": 71, "threshold": 0.003}` | 125 | 49 | 0.392 | -0.113% | -14.11 |
| QQQ | `{"_max_hold_bars": 11, "entry_bar_pos": 65, "threshold": 0.001}` | 480 | 193 | 0.402 | -0.104% | -49.87 |
| QQQ | `{"_max_hold_bars": 11, "entry_bar_pos": 65, "threshold": 0.003}` | 125 | 44 | 0.352 | -0.183% | -22.89 |
| IWM | `{"_max_hold_bars": 5, "entry_bar_pos": 71, "threshold": 0.0}` | 917 | 308 | 0.336 | -0.116% | -106.53 |
| IWM | `{"_max_hold_bars": 5, "entry_bar_pos": 71, "threshold": 0.001}` | 519 | 173 | 0.333 | -0.125% | -64.79 |
| IWM | `{"_max_hold_bars": 5, "entry_bar_pos": 71, "threshold": 0.003}` | 112 | 45 | 0.402 | -0.110% | -12.30 |
| IWM | `{"_max_hold_bars": 11, "entry_bar_pos": 65, "threshold": 0.001}` | 519 | 230 | 0.443 | -0.094% | -48.93 |
| IWM | `{"_max_hold_bars": 11, "entry_bar_pos": 65, "threshold": 0.003}` | 112 | 54 | 0.482 | -0.087% | -9.74 |
| DIA | `{"_max_hold_bars": 5, "entry_bar_pos": 71, "threshold": 0.0}` | 927 | 194 | 0.209 | -0.103% | -95.02 |
| DIA | `{"_max_hold_bars": 5, "entry_bar_pos": 71, "threshold": 0.001}` | 476 | 117 | 0.246 | -0.101% | -48.26 |
| DIA | `{"_max_hold_bars": 5, "entry_bar_pos": 71, "threshold": 0.003}` | 98 | 25 | 0.255 | -0.125% | -12.26 |
| DIA | `{"_max_hold_bars": 11, "entry_bar_pos": 65, "threshold": 0.001}` | 476 | 155 | 0.326 | -0.083% | -39.68 |
| DIA | `{"_max_hold_bars": 11, "entry_bar_pos": 65, "threshold": 0.003}` | 98 | 36 | 0.367 | -0.050% | -4.87 |
| XLK | `{"_max_hold_bars": 5, "entry_bar_pos": 71, "threshold": 0.0}` | 891 | 247 | 0.277 | -0.096% | -85.31 |
| XLK | `{"_max_hold_bars": 5, "entry_bar_pos": 71, "threshold": 0.001}` | 629 | 174 | 0.277 | -0.102% | -64.41 |
| XLK | `{"_max_hold_bars": 5, "entry_bar_pos": 71, "threshold": 0.003}` | 266 | 69 | 0.259 | -0.112% | -29.74 |
| XLK | `{"_max_hold_bars": 11, "entry_bar_pos": 65, "threshold": 0.001}` | 629 | 215 | 0.342 | -0.114% | -71.92 |
| XLK | `{"_max_hold_bars": 11, "entry_bar_pos": 65, "threshold": 0.003}` | 266 | 93 | 0.350 | -0.133% | -35.51 |

**Best for intraday_momentum:** DIA / `{"_max_hold_bars": 11, "entry_bar_pos": 65, "threshold": 0.003}` → EV -4.87 (WR 0.367, Trades 98)

## 戦略: pre_fomc_drift

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"_max_hold_bars": 129, "entry_bar_pos": 0}` | 57 | 27 | 0.474 | -0.137% | -7.78 |
| SPY | `{"_max_hold_bars": 95, "entry_bar_pos": 36}` | 57 | 26 | 0.456 | -0.014% | -0.82 |
| QQQ | `{"_max_hold_bars": 129, "entry_bar_pos": 0}` | 57 | 29 | 0.509 | -0.068% | -3.88 |
| QQQ | `{"_max_hold_bars": 95, "entry_bar_pos": 36}` | 57 | 31 | 0.544 | -0.005% | -0.29 |
| IWM | `{"_max_hold_bars": 129, "entry_bar_pos": 0}` | 57 | 22 | 0.386 | -0.143% | -8.16 |
| IWM | `{"_max_hold_bars": 95, "entry_bar_pos": 36}` | 57 | 27 | 0.474 | 0.008% | 0.47 |
| DIA | `{"_max_hold_bars": 129, "entry_bar_pos": 0}` | 57 | 27 | 0.474 | -0.112% | -6.39 |
| DIA | `{"_max_hold_bars": 95, "entry_bar_pos": 36}` | 57 | 26 | 0.456 | 0.038% | 2.19 |
| XLK | `{"_max_hold_bars": 129, "entry_bar_pos": 0}` | 57 | 32 | 0.561 | 0.383% | 21.81 |
| XLK | `{"_max_hold_bars": 95, "entry_bar_pos": 36}` | 57 | 37 | 0.649 | 0.541% | 30.83 |

**Best for pre_fomc_drift:** XLK / `{"_max_hold_bars": 95, "entry_bar_pos": 36}` → EV 30.83 (WR 0.649, Trades 57)

## 戦略: turn_of_month

| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |
|--------|--------|--------|------|----------|---------|----------------------|
| SPY | `{"_max_hold_bars": 70, "entry_bar_pos": 0}` | 332 | 137 | 0.413 | -0.129% | -42.95 |
| SPY | `{"_max_hold_bars": 60, "entry_bar_pos": 12}` | 332 | 140 | 0.422 | -0.120% | -39.81 |
| QQQ | `{"_max_hold_bars": 70, "entry_bar_pos": 0}` | 332 | 146 | 0.440 | -0.127% | -42.32 |
| QQQ | `{"_max_hold_bars": 60, "entry_bar_pos": 12}` | 332 | 142 | 0.428 | -0.123% | -40.79 |
| IWM | `{"_max_hold_bars": 70, "entry_bar_pos": 0}` | 332 | 153 | 0.461 | -0.209% | -69.33 |
| IWM | `{"_max_hold_bars": 60, "entry_bar_pos": 12}` | 332 | 157 | 0.473 | -0.181% | -60.19 |
| DIA | `{"_max_hold_bars": 70, "entry_bar_pos": 0}` | 331 | 145 | 0.438 | -0.135% | -44.74 |
| DIA | `{"_max_hold_bars": 60, "entry_bar_pos": 12}` | 332 | 139 | 0.419 | -0.118% | -39.07 |
| XLK | `{"_max_hold_bars": 70, "entry_bar_pos": 0}` | 330 | 156 | 0.473 | -0.137% | -45.30 |
| XLK | `{"_max_hold_bars": 60, "entry_bar_pos": 12}` | 330 | 159 | 0.482 | -0.084% | -27.71 |

**Best for turn_of_month:** XLK / `{"_max_hold_bars": 60, "entry_bar_pos": 12}` → EV -27.71 (WR 0.482, Trades 330)

## 横断比較：戦略別ベスト

| Rank | Strategy | Symbol | Params | EV | Win Rate | Trades |
|------|----------|--------|--------|-----|----------|--------|
| 1 | pre_fomc_drift | XLK | `{"_max_hold_bars": 95, "entry_bar_pos": 36}` | 30.83 | 0.649 | 57 |
| 2 | gap_fill | QQQ | `{"gap_threshold": 0.003, "stop_extension": 0.005}` | 18.35 | 0.573 | 213 |
| 3 | vwap_scalp | XLK | `{"k_entry": 1.0}` | 0.16 | 0.667 | 3 |
| 4 | mean_reversion | IWM | `{"threshold": 0.6}` | -0.26 | 0.000 | 1 |
| 5 | env_dependent_reversion | XLK | `{"threshold": 0.5}` | -0.31 | 0.000 | 1 |
| 6 | intraday_momentum | DIA | `{"_max_hold_bars": 11, "entry_bar_pos": 65, "threshold": 0.003}` | -4.87 | 0.367 | 98 |
| 7 | analysis_driven_reversion | XLK | `{"block_lunch_hours": [11, 12], "require_spy_up": true, "threshold": 0.3}` | -12.59 | 0.433 | 178 |
| 8 | multi_timeframe | IWM | `{"rsi_15min_threshold": 30.0, "rsi_5min_threshold": 25.0, "rsi_60min_threshold": 35.0}` | -20.55 | 0.422 | 244 |
| 9 | turn_of_month | XLK | `{"_max_hold_bars": 60, "entry_bar_pos": 12}` | -27.71 | 0.482 | 330 |
| 10 | opening_range_breakout | XLK | `{"or_window_bars": 12}` | -88.09 | 0.423 | 938 |
| 11 | momentum_breakout | XLK | `{"breakout_period": 78, "volume_multiplier": 2.0}` | -109.23 | 0.408 | 1224 |
| 12 | trend_follow | XLK | `{"breakout_period": 50, "rsi_threshold": 55.0}` | -277.74 | 0.411 | 3043 |

## 推奨：**pre_fomc_drift** （XLK、EV 30.83）

## 次のステップ

1. このレポートを人間がレビュー、最良戦略を確認
2. 推奨戦略を Plan 2 の本実装の対象とする
3. 必要に応じて、上位2戦略をアンサンブル運用も検討