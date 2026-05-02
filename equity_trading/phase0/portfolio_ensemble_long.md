# Portfolio Ensemble Backtest

Combines top post-fix strategies into one $100k account simulation.

**Selected strategies:**
- pre_fomc_TECL: PreFOMCDriftStrategy(TECL, {'entry_bar_pos': 0, '_max_hold_bars': 130, 'vix_min': 22}, cost=0.1%)
- pre_fomc_UPRO: PreFOMCDriftStrategy(UPRO, {'entry_bar_pos': 0, '_max_hold_bars': 130}, cost=0.1%)
- pre_fomc_UDOW: PreFOMCDriftStrategy(UDOW, {'entry_bar_pos': 0, '_max_hold_bars': 130}, cost=0.1%)
- orb_TECL: OpeningRangeBreakoutStrategy(TECL, {'or_window_bars': 12}, cost=0.1%)
- orb_TQQQ: OpeningRangeBreakoutStrategy(TQQQ, {'or_window_bars': 12}, cost=0.1%)
- orb_TNA: OpeningRangeBreakoutStrategy(TNA, {'or_window_bars': 12}, cost=0.1%)
- lhm_UPRO: LastHourMomentumStrategy(UPRO, {'threshold': 0.003, '_max_hold_bars': 60}, cost=0.1%)
- lhm_UDOW: LastHourMomentumStrategy(UDOW, {'threshold': 0.003, '_max_hold_bars': 60}, cost=0.1%)

## Results

| Scenario | Position Size | Max Concurrent | Trades Taken | Final Equity | Annualized Return (mean) | 95% CI | Max DD |
|----------|---------------|----------------|--------------|--------------|--------------------------|--------|--------|
| A: Plan 2.0 baseline (25%/pos × 3) |  | | 2208 / 2384 | $235,342 | +13.02% | [+3.46, +12.77]% | -16.77% |
| B: Aggressive (50%/pos × 2) |  | | 1888 / 2384 | $393,493 | +21.64% | [+5.95, +24.93]% | -34.92% |
| C: Full size, 1 at a time |  | | 1099 / 2384 | $363,306 | +20.26% | [+2.24, +33.10]% | -58.37% |

## Trade Counts by Strategy

| Strategy | Trades | Avg P&L | Total Contribution |
|----------|--------|---------|--------------------|
| lhm_UDOW | 407 | +0.079% | +32.29% |
| lhm_UPRO | 457 | +0.075% | +34.16% |
| orb_TECL | 486 | +0.223% | +108.38% |
| orb_TNA | 369 | +0.168% | +62.06% |
| orb_TQQQ | 531 | +0.145% | +76.96% |
| pre_fomc_TECL | 20 | +1.555% | +31.09% |
| pre_fomc_UDOW | 57 | +0.072% | +4.11% |
| pre_fomc_UPRO | 57 | +0.244% | +13.92% |

## Honest Projection

- **Plan 2.0 baseline (Scenario A)**: annualized +13.02% (95% CI [+3.46, +12.77]), max DD -16.77%
- **Aggressive (Scenario B)**: annualized +21.64% (95% CI [+5.95, +24.93]), max DD -34.92%
- **Full-size sequential (Scenario C)**: annualized +20.26% (95% CI [+2.24, +33.10]), max DD -58.37%

CIs from 300 bootstrap resamples of the trade list (with replacement).
**Caveat:** the 2-yr window includes a structurally bullish 2025 sub-period; live performance is likely below the mean estimate.