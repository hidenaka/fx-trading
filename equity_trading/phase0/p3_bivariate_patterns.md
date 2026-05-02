# P3: Bivariate Pattern Discovery

**Threshold:** train_n ≥ 15, test_n ≥ 15, train_WR ≥ 0.60, test_WR ≥ 0.60, |Δ WR| ≤ 0.15

**Total robust patterns found: 0**

**No 2-feature interaction met the robustness bar. Pattern discovery has hit its ceiling on this dataset.**

This is itself an honest finding: with 4,016 train and 69,559 test samples on mean_reversion, no single 2-feature condition reliably separates winners from losers above 60% WR. The signal is either:
- truly random within the loose-threshold candidate space, or
- emerges only with 3+ features (combinatorial explosion).

## Near-miss diagnostics

Of **1,912 cells** that had n ≥ 15 in both train and test, the best `min(train_WR, test_WR)` across all 105 feature pairs was **0.568** — well below the 0.60 threshold. Only **1 cell** cleared 0.55, and **25 cells** cleared 0.50. The median cell WR was ~0.34.

### Top 10 cells by min(train_WR, test_WR) (none met threshold)

| F1 / bucket | F2 / bucket | Train (n / WR / P&L%) | Test (n / WR / P&L%) | |Δ WR| |
|-------------|-------------|----------------------|----------------------|-------|
| vwap_dev / q4 | ny_hour / 15 | 95 / 0.568 / -0.047% | 20 / 0.550 / -0.062% | 0.018 |
| vwap_dev / q4 | gap_pct / q2 | 131 / 0.550 / -0.052% | 94 / 0.553 / -0.049% | 0.004 |
| daily_20d_return / q3 | ny_hour / 19 | 43 / 0.558 / -0.050% | 601 / 0.539 / -0.052% | 0.019 |
| intraday_change / q1 | daily_ma_distance / q1 | 91 / 0.538 / -0.055% | 129 / 0.543 / -0.053% | 0.004 |
| atr_ratio_5min / q3 | ny_hour / 14 | 89 / 0.562 / -0.053% | 490 / 0.537 / -0.050% | 0.025 |
| ny_hour / 17 | day_of_week / 3 | 24 / 0.625 / -0.018% | 423 / 0.532 / -0.051% | 0.093 |
| daily_5d_return / q1 | ny_hour / 16 | 54 / 0.556 / -0.045% | 131 / 0.527 / -0.050% | 0.029 |
| vwap_dev / q4 | ny_hour / 14 | 57 / 0.526 / -0.064% | 19 / 0.526 / -0.069% | 0.000 |
| daily_5d_return / q1 | ny_hour / 17 | 27 / 0.593 / -0.042% | 111 / 0.523 / -0.051% | 0.070 |
| bb_pct_b / q2 | ny_hour / 19 | 46 / 0.565 / -0.047% | 759 / 0.520 / -0.059% | 0.045 |

**Critical note:** all top cells show negative avg P&L even at WR ~0.55. This indicates the win/loss asymmetry is working against the strategy — winners are smaller than losers. A WR above 0.60 alone is insufficient; P&L must also be positive.

## Interpretation

1. **`vwap_dev` is the most-recurrent feature** in near-miss cells (appears in 3 of top 10), consistent with P2 finding it as the best univariate feature. Extreme positive vwap_dev (q4) paired with specific hours (14, 15) or moderate gaps (q2) shows mild WR lift, but P&L is still negative.

2. **`ny_hour` co-occurs in 7 of top 10 cells**, suggesting time-of-day is the dominant secondary filter. Hour 14-19 (2pm-7pm ET) slots appear repeatedly.

3. **`daily_5d_return q1`** (stocks that fell hard recently) paired with hours 16-17 shows some signal, but not enough to clear the bar.

4. **No cell showed positive avg P&L** among the top near-misses. The mean_reversion candidate set appears to have unfavorable risk/reward baked in regardless of feature conditioning.

## Verdict

P1, P2, and P3 together confirm: **the current mean_reversion candidate pipeline does not produce a trainable edge using rule-based feature conditioning up to 2-feature interactions.** The overall WR of the dataset is ~0.34 (base rate), and conditioning on any 1-2 features can push it to ~0.55–0.57 at best, with negative average P&L.

**Recommended next steps:**
- Revisit the candidate generation logic (entry/exit rules, hold period, stop placement) — the structural edge may be misconfigured
- Or proceed to ML-based modeling (P4) which can capture higher-order interactions simultaneously
- Do NOT invest further time in 3-feature exhaustive search (15× more cells, same dataset)
