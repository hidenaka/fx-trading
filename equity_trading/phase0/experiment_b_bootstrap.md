# Experiment B: Statistical Validation of Monday-Bull-Gap Filter

Tests robustness of F3 (`20d_return>0 AND Monday`) and F7 (`F3 AND xlk_rs>0`)
using **post-fix realistic low/high-based PnL** outcomes.

**Dataset:** 594 gap_fill candidates (594 with all features), chronological 60/40 split (train=356, test=238)

## 1. Bootstrap 95% CIs (10,000 resamples)

| Subset | n | WR (mean / 95% CI) | Avg P&L%/trade (mean / 95% CI) |
|--------|---|--------------------|--------------------------------|
| baseline_train | 356 | 0.522 / [0.469, 0.573] | -0.008% / [-0.060, +0.042] |
| baseline_test | 238 | 0.601 / [0.538, 0.664] | +0.082% / [+0.009, +0.153] |
| F3_train (20d>0 AND Monday) | 59 | 0.712 / [0.593, 0.831] | +0.252% / [+0.126, +0.380] |
| F3_test  (20d>0 AND Monday) | 51 | 0.647 / [0.510, 0.784] | +0.179% / [+0.035, +0.318] |
| F7_train (F3 AND xlk_rs>0) | 39 | 0.615 / [0.462, 0.769] | +0.244% / [+0.066, +0.420] |
| F7_test  (F3 AND xlk_rs>0) | 32 | 0.750 / [0.594, 0.875] | +0.294% / [+0.095, +0.480] |

## 2. Drop-Monday Ablation

If Monday is the load-bearing factor, removing it should collapse the filter's edge.

| Subset | n | WR | Avg P&L%/trade |
|--------|---|------|----------------|
| 20d>0 AND NOT Monday  (train) | 229 | 0.533 | -0.033% |
| 20d>0 AND NOT Monday  (test) | 88 | 0.693 | +0.115% |

**Surprise finding:** In the test period, "20d>0 AND NOT Monday" has WR **0.693** — *higher* than F3 (Monday-only) WR 0.647. In the train period, F3 WR 0.712 vs non-Monday 0.533 — Monday clearly mattered. **The Monday-specific effect is a train-period artifact.** What persists out-of-sample is the bull-regime (20d>0) signal, not the Monday signal.

## 3. Alternate Holdout (rolling 6-month forward windows)

Tests whether F3's edge is concentrated in one specific 6-month period.

| Window | n_baseline | baseline WR | n_F3 | F3 WR | F3 avg P&L% |
|--------|------------|-------------|------|-------|-------------|
| 2024-11-01 – 2025-05-01 | 30 | 0.333 | 0 | nan | +nan% |
| 2025-05-01 – 2025-11-01 | 265 | 0.604 | 51 | 0.824 | +0.349% |
| 2025-11-01 – 2026-05-01 | 299 | 0.532 | 59 | 0.559 | +0.105% |

## 4. Honest Verdict

### Headline numbers (post-fix)

- **Baseline test:** n=238, WR=0.601 (CI [0.538, 0.664])
- **F3 test (Monday + 20d>0):** n=51, WR=0.647 (CI [0.510, 0.784])
- **F7 test (F3 + xlk_rs>0):** n=32, WR=0.750 (CI [0.594, 0.875]), avg P&L +0.294%/trade (CI [+0.095, +0.480])

### Three independent stress signals point the same way

1. **Stop-modeling fix alone collapsed F3 from 90% → 65% WR.** The original 26.75% total P&L was 66% an artifact of close-only stop evaluation.

2. **Drop-Monday ablation contradicts the Monday-Bull-Gap narrative.** In the test period, non-Monday days with 20d>0 had WR 0.693 — *better* than Monday's 0.647. Monday's apparent edge in train (0.712 vs 0.533) **did not persist out-of-sample**.

3. **Alternate holdout shows time-period concentration.** F3's edge is concentrated in 2025-05–2025-11 (WR 0.824, n=51). In 2025-11–2026-05, F3 WR drops to 0.559 (n=59), barely above baseline. The summer-2025 window was a structurally bullish slice that flattered any "buy the dip in uptrend" signal.

### Conclusion

- **F3 (Monday-Bull-Gap) is not a robust real-world law.** The Monday-specificity is a train-period artifact. The 20d_return>0 (bullish regime) is the real signal, but it weakens substantially in late-2025/2026 data.

- **F7 statistically clears the bar** (CI lower bound: WR 0.594, P&L +0.095%/trade), but n=32 is fragile and the edge will likely halve in a non-bull regime.

- **Realistic live expectation:** WR 60–70%, avg P&L +0.10–0.20%/trade, expectancy strongly regime-dependent. The headline 90% WR / +26.75% claim from pre-fix P5 is **rejected as overstated**.

### Implications for Plan 2.0 (Paper Trading)

- gap_fill XLK best EV dropped from **+23.85 → +3.29** under the same parameters with realistic stop modeling. That single XLK config is no longer the standout.
- New post-fix gap_fill best is **QQQ** (gap_threshold 0.003, EV +7.84). gap_fill QQQ + SPY + IWM (high gap threshold) are the most resilient.
- **Recommendation:** Revisit Plan 2.0 strategy selection before further Paper deployment. The current configuration was selected under inflated numbers.