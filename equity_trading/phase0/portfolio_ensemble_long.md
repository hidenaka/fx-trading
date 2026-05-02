# Portfolio Ensemble Backtest

Combines top post-fix strategies into one $100k account simulation.

**Selected strategies:**
- gap_fill_QQQ: GapFillStrategy(QQQ, {'gap_threshold': 0.003, 'stop_extension': 0.005})
- gap_fill_QQQ_tight: GapFillStrategy(QQQ, {'gap_threshold': 0.005, 'stop_extension': 0.005})
- gap_fill_SPY: GapFillStrategy(SPY, {'gap_threshold': 0.005, 'stop_extension': 0.005})
- gap_fill_DIA: GapFillStrategy(DIA, {'gap_threshold': 0.005, 'stop_extension': 0.005})
- pre_fomc_XLK: PreFOMCDriftStrategy(XLK, {'entry_bar_pos': 36, '_max_hold_bars': 95})

## Results

| Scenario | Position Size | Max Concurrent | Trades Taken | Final Equity | Annualized Return (mean) | 95% CI | Max DD |
|----------|---------------|----------------|--------------|--------------|--------------------------|--------|--------|
| A: Plan 2.0 baseline (25%/pos × 3) |  | | 505 / 543 | $118,833 | +2.54% | [+1.39, +3.32]% | -1.55% |
| B: Aggressive (50%/pos × 2) |  | | 429 / 543 | $138,169 | +4.82% | [+2.39, +5.72]% | -2.76% |
| C: Full size, 1 at a time |  | | 294 / 543 | $161,768 | +7.26% | [+3.40, +7.22]% | -5.01% |

## Trade Counts by Strategy

| Strategy | Trades | Avg P&L | Total Contribution |
|----------|--------|---------|--------------------|
| gap_fill_DIA | 75 | +0.040% | +3.02% |
| gap_fill_QQQ | 213 | +0.086% | +18.35% |
| gap_fill_QQQ_tight | 117 | +0.121% | +14.16% |
| gap_fill_SPY | 81 | +0.038% | +3.08% |
| pre_fomc_XLK | 57 | +0.541% | +30.83% |

## Honest Projection

- **Plan 2.0 baseline (Scenario A)**: annualized +2.54% (95% CI [+1.39, +3.32]), max DD -1.55%
- **Aggressive (Scenario B)**: annualized +4.82% (95% CI [+2.39, +5.72]), max DD -2.76%
- **Full-size sequential (Scenario C)**: annualized +7.26% (95% CI [+3.40, +7.22]), max DD -5.01%

CIs from 300 bootstrap resamples of the trade list (with replacement).
**Caveat:** the 2-yr window includes a structurally bullish 2025 sub-period; live performance is likely below the mean estimate.