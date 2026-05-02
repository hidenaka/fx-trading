# P4: gap_fill Winners vs Losers Deep Dive

**Sample:** 594 gap_fill candidates (all 5 ETFs × 3 thresholds)
**Baseline WR:** 0.579, baseline P&L: +0.148%

Each feature's top quartile (q4) vs bottom quartile (q1) WR difference. Larger absolute difference = more discriminative.

## Top 10 most-discriminating features (by |WR top − WR bot|)

| Feature | n_bot / WR_bot / P&L_bot | n_top / WR_top / P&L_top | WR diff | P&L diff | p-value |
|---------|---------------------------|---------------------------|---------|----------|---------|
| daily_20d_return | 149 / 0.423 / +0.303% | 149 / 0.698 / +0.241% | +0.275 | -0.062% | 0.000 |
| day_of_week | 152 / 0.724 / +0.354% | 209 / 0.450 / +0.156% | -0.274 | -0.198% | 0.000 |
| is_monday | 442 / 0.529 / +0.078% | 152 / 0.724 / +0.354% | +0.194 | +0.277% | 0.000 |
| xlk_relative_strength | 150 / 0.547 / +0.070% | 159 / 0.711 / +0.514% | +0.164 | +0.444% | 0.003 |
| gap_size_relative_to_atr | 149 / 0.664 / +0.626% | 149 / 0.517 / -0.089% | -0.148 | -0.715% | 0.010 |
| volume_ratio | 149 / 0.544 / +0.348% | 151 / 0.669 / +0.197% | +0.125 | -0.151% | 0.027 |
| atr_ratio_5min | 151 / 0.523 / -0.075% | 149 / 0.644 / +0.539% | +0.121 | +0.615% | 0.034 |
| spy_intraday | 154 / 0.429 / -0.003% | 153 / 0.549 / +0.273% | +0.120 | +0.276% | 0.035 |
| rsi_14 | 151 / 0.616 / +0.549% | 149 / 0.497 / -0.165% | -0.119 | -0.714% | 0.038 |
| intraday_change | 149 / 0.591 / +0.572% | 149 / 0.483 / -0.098% | -0.107 | -0.671% | 0.064 |

## Top 3 features — quintile breakdown

### daily_20d_return

| Quintile | Range | n | WR | Avg P&L |
|----------|-------|---|-----|---------|
| q1 | — | 121 | 0.388 | +0.320% |
| q2 | — | 119 | 0.588 | +0.134% |
| q3 | — | 117 | 0.590 | -0.046% |
| q4 | — | 119 | 0.630 | +0.071% |
| q5 | — | 118 | 0.703 | +0.258% |

### day_of_week

| Quintile | Range | n | WR | Avg P&L |
|----------|-------|---|-----|---------|
| q1 | — | 316 | 0.633 | +0.147% |
| q2 | — | 69 | 0.725 | +0.132% |
| q3 | — | 108 | 0.444 | -0.159% |
| q4 | — | 101 | 0.455 | +0.493% |

## Verdict

Features with |WR diff| > 0.10 AND p < 0.10: **13**

Statistically significant features:

- `daily_20d_return`: top q WR 0.698 vs bot q WR 0.423 (diff +0.275, p=0.000)
- `day_of_week`: top q WR 0.450 vs bot q WR 0.724 (diff -0.274, p=0.000)
- `is_monday`: top q WR 0.724 vs bot q WR 0.529 (diff +0.194, p=0.000)
- `xlk_relative_strength`: top q WR 0.711 vs bot q WR 0.547 (diff +0.164, p=0.003)
- `gap_size_relative_to_atr`: top q WR 0.517 vs bot q WR 0.664 (diff -0.148, p=0.010)
- `volume_ratio`: top q WR 0.669 vs bot q WR 0.544 (diff +0.125, p=0.027)
- `atr_ratio_5min`: top q WR 0.644 vs bot q WR 0.523 (diff +0.121, p=0.034)
- `spy_intraday`: top q WR 0.549 vs bot q WR 0.429 (diff +0.120, p=0.035)
- `rsi_14`: top q WR 0.497 vs bot q WR 0.616 (diff -0.119, p=0.038)
- `intraday_change`: top q WR 0.483 vs bot q WR 0.591 (diff -0.107, p=0.064)
- `score_value`: top q WR 0.640 vs bot q WR 0.537 (diff +0.103, p=0.071)
- `gap_pct`: top q WR 0.537 vs bot q WR 0.640 (diff -0.103, p=0.071)
- `consecutive_down_days`: top q WR 0.635 vs bot q WR 0.534 (diff +0.102, p=0.013)