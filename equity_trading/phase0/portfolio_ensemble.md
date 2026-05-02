# Portfolio Ensemble Backtest

Combines top post-fix strategies into one $100k account simulation.

**Selected strategies:**
- gap_fill_SPY: GapFillStrategy(SPY, {'gap_threshold': 0.003, 'stop_extension': 0.005})
- gap_fill_QQQ: GapFillStrategy(QQQ, {'gap_threshold': 0.003, 'stop_extension': 0.005})
- gap_fill_DIA: GapFillStrategy(DIA, {'gap_threshold': 0.003, 'stop_extension': 0.005})
- gap_fill_XLK: GapFillStrategy(XLK, {'gap_threshold': 0.005, 'stop_extension': 0.005})
- pre_fomc_XLK: PreFOMCDriftStrategy(XLK, {'entry_bar_pos': 36, '_max_hold_bars': 95})
- mean_rev_XLK: MeanReversionStrategy(XLK, {'threshold': 0.4})

## Results

| Scenario | Position Size | Max Concurrent | Trades Taken | Final Equity | Annualized Return (mean) | 95% CI | Max DD |
|----------|---------------|----------------|--------------|--------------|--------------------------|--------|--------|
| A: Plan 2.0 baseline (25%/pos × 3) |  | | 176 / 187 | $106,258 | +3.28% | [+1.42, +5.05]% | -1.02% |
| B: Aggressive (50%/pos × 2) |  | | 148 / 187 | $109,952 | +5.17% | [+2.50, +8.09]% | -2.06% |
| C: Full size, 1 at a time |  | | 105 / 187 | $114,525 | +7.47% | [+3.01, +9.36]% | -3.13% |

## Trade Counts by Strategy

| Strategy | Trades | Avg P&L | Total Contribution |
|----------|--------|---------|--------------------|
| gap_fill_DIA | 34 | +0.028% | +0.95% |
| gap_fill_QQQ | 45 | +0.174% | +7.84% |
| gap_fill_SPY | 39 | +0.116% | +4.53% |
| gap_fill_XLK | 17 | +0.193% | +3.29% |
| mean_rev_XLK | 36 | +0.019% | +0.69% |
| pre_fomc_XLK | 16 | +0.615% | +9.84% |

## Honest Projection

- **Plan 2.0 baseline (Scenario A)**: annualized +3.28% (95% CI [+1.42, +5.05]), max DD -1.02%
- **Aggressive (Scenario B)**: annualized +5.17% (95% CI [+2.50, +8.09]), max DD -2.06%
- **Full-size sequential (Scenario C)**: annualized +7.47% (95% CI [+3.01, +9.36]), max DD -3.13%

CIs from 300 bootstrap resamples of the trade list (with replacement).
**Caveat:** the 2-yr window includes a structurally bullish 2025 sub-period; live performance is likely below the mean estimate.