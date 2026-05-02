# RTH-only diagnostic — does pre-market data inflate EV?

Compares strategy EV on full extended-hours data vs regular-trading-hours-only.

## gap_fill

| Symbol | Params | Trades | WR | EV |
|--------|--------|-------:|----:|---:|
| SPY | {"gap_threshold": 0.003, "stop_extension": 0.005} | 229 | 0.424 | -27.50 |
| SPY | {"gap_threshold": 0.005, "stop_extension": 0.005} | 139 | 0.374 | -19.64 |
| SPY | {"gap_threshold": 0.01, "stop_extension": 0.01} | 50 | 0.520 | -2.79 |
| QQQ | {"gap_threshold": 0.003, "stop_extension": 0.005} | 291 | 0.385 | -33.23 |
| QQQ | {"gap_threshold": 0.005, "stop_extension": 0.005} | 195 | 0.369 | -23.39 |
| QQQ | {"gap_threshold": 0.01, "stop_extension": 0.01} | 79 | 0.481 | -7.21 |
| IWM | {"gap_threshold": 0.003, "stop_extension": 0.005} | 265 | 0.351 | -27.47 |
| IWM | {"gap_threshold": 0.005, "stop_extension": 0.005} | 186 | 0.360 | -17.78 |
| IWM | {"gap_threshold": 0.01, "stop_extension": 0.01} | 73 | 0.575 | +0.75 |
| DIA | {"gap_threshold": 0.003, "stop_extension": 0.005} | 220 | 0.400 | -30.33 |
| DIA | {"gap_threshold": 0.005, "stop_extension": 0.005} | 122 | 0.328 | -21.46 |
| DIA | {"gap_threshold": 0.01, "stop_extension": 0.01} | 37 | 0.514 | -2.90 |
| XLK | {"gap_threshold": 0.003, "stop_extension": 0.005} | 296 | 0.389 | -19.90 |
| XLK | {"gap_threshold": 0.005, "stop_extension": 0.005} | 214 | 0.393 | -10.44 |
| XLK | {"gap_threshold": 0.01, "stop_extension": 0.01} | 94 | 0.436 | -5.22 |

## pre_fomc_drift

| Symbol | Params | Trades | WR | EV |
|--------|--------|-------:|----:|---:|
| SPY | {"_max_hold_bars": 130, "entry_bar_pos": 0} | 57 | 0.526 | +16.42 |
| SPY | {"_max_hold_bars": 94, "entry_bar_pos": 36} | 57 | 0.526 | +3.72 |
| SPY | {"_max_hold_bars": 41, "entry_bar_pos": 36} | 57 | 0.456 | +2.18 |
| QQQ | {"_max_hold_bars": 130, "entry_bar_pos": 0} | 57 | 0.561 | +23.43 |
| QQQ | {"_max_hold_bars": 94, "entry_bar_pos": 36} | 57 | 0.579 | +12.21 |
| QQQ | {"_max_hold_bars": 41, "entry_bar_pos": 36} | 57 | 0.526 | +8.89 |
| IWM | {"_max_hold_bars": 130, "entry_bar_pos": 0} | 57 | 0.579 | +23.21 |
| IWM | {"_max_hold_bars": 94, "entry_bar_pos": 36} | 57 | 0.491 | +12.95 |
| IWM | {"_max_hold_bars": 41, "entry_bar_pos": 36} | 57 | 0.579 | +5.83 |
| DIA | {"_max_hold_bars": 130, "entry_bar_pos": 0} | 57 | 0.509 | +10.82 |
| DIA | {"_max_hold_bars": 94, "entry_bar_pos": 36} | 57 | 0.526 | -2.33 |
| DIA | {"_max_hold_bars": 41, "entry_bar_pos": 36} | 57 | 0.474 | -1.28 |
| XLK | {"_max_hold_bars": 130, "entry_bar_pos": 0} | 57 | 0.596 | +29.14 |
| XLK | {"_max_hold_bars": 94, "entry_bar_pos": 36} | 57 | 0.596 | +17.16 |
| XLK | {"_max_hold_bars": 41, "entry_bar_pos": 36} | 57 | 0.614 | +10.33 |

## mean_reversion

| Symbol | Params | Trades | WR | EV |
|--------|--------|-------:|----:|---:|
| SPY | {"threshold": 0.4} | 189 | 0.354 | -22.05 |
| SPY | {"threshold": 0.5} | 27 | 0.296 | -3.70 |
| SPY | {"threshold": 0.6} | 0 | nan | +nan |
| QQQ | {"threshold": 0.4} | 215 | 0.358 | -23.21 |
| QQQ | {"threshold": 0.5} | 41 | 0.390 | -3.97 |
| QQQ | {"threshold": 0.6} | 0 | nan | +nan |
| IWM | {"threshold": 0.4} | 167 | 0.413 | -13.34 |
| IWM | {"threshold": 0.5} | 28 | 0.321 | -3.94 |
| IWM | {"threshold": 0.6} | 0 | nan | +nan |
| DIA | {"threshold": 0.4} | 196 | 0.388 | -18.02 |
| DIA | {"threshold": 0.5} | 35 | 0.200 | -6.00 |
| DIA | {"threshold": 0.6} | 0 | nan | +nan |
| XLK | {"threshold": 0.4} | 193 | 0.373 | -18.51 |
| XLK | {"threshold": 0.5} | 38 | 0.368 | -4.17 |
| XLK | {"threshold": 0.6} | 1 | 1.000 | +0.27 |

## intraday_momentum

| Symbol | Params | Trades | WR | EV |
|--------|--------|-------:|----:|---:|
| SPY | {"_max_hold_bars": 5, "entry_bar_pos": 71, "threshold": 0.001} | 644 | 0.262 | -77.30 |
| SPY | {"_max_hold_bars": 5, "entry_bar_pos": 71, "threshold": 0.003} | 230 | 0.304 | -27.98 |
| QQQ | {"_max_hold_bars": 5, "entry_bar_pos": 71, "threshold": 0.001} | 749 | 0.298 | -73.42 |
| QQQ | {"_max_hold_bars": 5, "entry_bar_pos": 71, "threshold": 0.003} | 428 | 0.290 | -44.01 |
| IWM | {"_max_hold_bars": 5, "entry_bar_pos": 71, "threshold": 0.001} | 734 | 0.294 | -82.68 |
| IWM | {"_max_hold_bars": 5, "entry_bar_pos": 71, "threshold": 0.003} | 484 | 0.304 | -54.95 |
| DIA | {"_max_hold_bars": 5, "entry_bar_pos": 71, "threshold": 0.001} | 643 | 0.249 | -70.08 |
| DIA | {"_max_hold_bars": 5, "entry_bar_pos": 71, "threshold": 0.003} | 283 | 0.247 | -34.37 |
| XLK | {"_max_hold_bars": 5, "entry_bar_pos": 71, "threshold": 0.001} | 777 | 0.346 | -70.13 |
| XLK | {"_max_hold_bars": 5, "entry_bar_pos": 71, "threshold": 0.003} | 489 | 0.344 | -45.21 |
