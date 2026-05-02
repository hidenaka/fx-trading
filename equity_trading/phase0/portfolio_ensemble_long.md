# Portfolio Ensemble Backtest

Combines top post-fix strategies into one $100k account simulation.

**Selected strategies:**
- pre_fomc_XLK: PreFOMCDriftStrategy(XLK, {'entry_bar_pos': 0, '_max_hold_bars': 130}, cost=0.1%)
- pre_fomc_QQQ: PreFOMCDriftStrategy(QQQ, {'entry_bar_pos': 0, '_max_hold_bars': 130}, cost=0.1%)
- pre_fomc_IWM: PreFOMCDriftStrategy(IWM, {'entry_bar_pos': 0, '_max_hold_bars': 130}, cost=0.1%)
- pre_fomc_SPY: PreFOMCDriftStrategy(SPY, {'entry_bar_pos': 0, '_max_hold_bars': 130}, cost=0.1%)
- pre_fomc_DIA: PreFOMCDriftStrategy(DIA, {'entry_bar_pos': 0, '_max_hold_bars': 130}, cost=0.1%)
- orb_60min_QQQ: OpeningRangeBreakoutStrategy(QQQ, {'or_window_bars': 12}, cost=0.1%)
- lhm_SPY: LastHourMomentumStrategy(SPY, {'threshold': 0.003, '_max_hold_bars': 60}, cost=0.1%)
- lhm_QQQ: LastHourMomentumStrategy(QQQ, {'threshold': 0.003, '_max_hold_bars': 60}, cost=0.1%)

## Results

| Scenario | Position Size | Max Concurrent | Trades Taken | Final Equity | Annualized Return (mean) | 95% CI | Max DD |
|----------|---------------|----------------|--------------|--------------|--------------------------|--------|--------|
| A: Plan 2.0 baseline (25%/pos × 3) |  | | 1077 / 1292 | $121,418 | +2.82% | [+1.24, +3.51]% | -4.28% |
| B: Aggressive (50%/pos × 2) |  | | 1021 / 1292 | $135,039 | +4.40% | [+1.37, +5.80]% | -7.42% |
| C: Full size, 1 at a time |  | | 851 / 1292 | $128,247 | +3.63% | [-0.00, +7.22]% | -13.11% |

## Trade Counts by Strategy

| Strategy | Trades | Avg P&L | Total Contribution |
|----------|--------|---------|--------------------|
| lhm_QQQ | 174 | +0.053% | +9.24% |
| lhm_SPY | 121 | +0.068% | +8.20% |
| orb_60min_QQQ | 712 | +0.011% | +7.78% |
| pre_fomc_DIA | 57 | +0.190% | +10.82% |
| pre_fomc_IWM | 57 | +0.407% | +23.21% |
| pre_fomc_QQQ | 57 | +0.411% | +23.43% |
| pre_fomc_SPY | 57 | +0.288% | +16.42% |
| pre_fomc_XLK | 57 | +0.511% | +29.14% |

## Honest Projection

- **Plan 2.0 baseline (Scenario A)**: annualized +2.82% (95% CI [+1.24, +3.51]), max DD -4.28%
- **Aggressive (Scenario B)**: annualized +4.40% (95% CI [+1.37, +5.80]), max DD -7.42%
- **Full-size sequential (Scenario C)**: annualized +3.63% (95% CI [-0.00, +7.22]), max DD -13.11%

CIs from 300 bootstrap resamples of the trade list (with replacement).
**Caveat:** the 2-yr window includes a structurally bullish 2025 sub-period; live performance is likely below the mean estimate.