# Portfolio Ensemble Backtest

Combines top post-fix strategies into one $100k account simulation.

**Selected strategies:**
- pre_fomc_XLK: PreFOMCDriftStrategy(XLK, {'entry_bar_pos': 0, '_max_hold_bars': 130})
- pre_fomc_QQQ: PreFOMCDriftStrategy(QQQ, {'entry_bar_pos': 0, '_max_hold_bars': 130})
- pre_fomc_IWM: PreFOMCDriftStrategy(IWM, {'entry_bar_pos': 0, '_max_hold_bars': 130})
- pre_fomc_SPY: PreFOMCDriftStrategy(SPY, {'entry_bar_pos': 0, '_max_hold_bars': 130})
- pre_fomc_DIA: PreFOMCDriftStrategy(DIA, {'entry_bar_pos': 0, '_max_hold_bars': 130})
- orb_60min_QQQ: OpeningRangeBreakoutStrategy(QQQ, {'or_window_bars': 12})

## Results

| Scenario | Position Size | Max Concurrent | Trades Taken | Final Equity | Annualized Return (mean) | 95% CI | Max DD |
|----------|---------------|----------------|--------------|--------------|--------------------------|--------|--------|
| A: Plan 2.0 baseline (25%/pos × 3) |  | | 845 / 997 | $115,552 | +2.13% | [+1.14, +2.87]% | -3.85% |
| B: Aggressive (50%/pos × 2) |  | | 788 / 997 | $117,525 | +2.38% | [+1.17, +4.63]% | -7.69% |
| C: Full size, 1 at a time |  | | 731 / 997 | $116,709 | +2.28% | [-0.51, +6.22]% | -13.61% |

## Trade Counts by Strategy

| Strategy | Trades | Avg P&L | Total Contribution |
|----------|--------|---------|--------------------|
| orb_60min_QQQ | 712 | +0.011% | +7.78% |
| pre_fomc_DIA | 57 | +0.190% | +10.82% |
| pre_fomc_IWM | 57 | +0.407% | +23.21% |
| pre_fomc_QQQ | 57 | +0.411% | +23.43% |
| pre_fomc_SPY | 57 | +0.288% | +16.42% |
| pre_fomc_XLK | 57 | +0.511% | +29.14% |

## Honest Projection

- **Plan 2.0 baseline (Scenario A)**: annualized +2.13% (95% CI [+1.14, +2.87]), max DD -3.85%
- **Aggressive (Scenario B)**: annualized +2.38% (95% CI [+1.17, +4.63]), max DD -7.69%
- **Full-size sequential (Scenario C)**: annualized +2.28% (95% CI [-0.51, +6.22]), max DD -13.61%

CIs from 300 bootstrap resamples of the trade list (with replacement).
**Caveat:** the 2-yr window includes a structurally bullish 2025 sub-period; live performance is likely below the mean estimate.