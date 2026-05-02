# ML Final Evaluation — Plan ML7

**Period:** 2024-05-01 to 2026-05-01
**Strict baseline aggregate EV:** **+42.41%** (5 ensembles, ML6 reference)

## Original Result (ML6): Per-ensemble walk-forward GBM classification

See `ml_evaluation_report.md` for full table. Summary:

- 4 of 5 ensembles had < 60 candidates → skipped ML
- Only XLK mean_reversion ran ML: AUC = 0.426
- ML filter aggregate EV: **-2.98%** vs strict **+42.41%**
- Verdict: ML classification failed.

## Approach 1: Pooled gap_fill GBM classification (4 ETFs, symbol as one-hot feature)

- Pooled candidate count: **176**
- Mean AUC (walk-forward OOF): **0.497**

| Threshold | Trades kept | Win Rate | Total EV |
|-----------|-------------|----------|----------|
| p ≥ 0.50 | 32 | 0.719 | +9.08% |
| p ≥ 0.60 | 28 | 0.679 | +6.70% |
| p ≥ 0.70 | 22 | 0.636 | +3.62% |

## Approach 2: Regression on pnl_pct (per-ensemble, threshold by predicted PnL)

| Symbol | Strategy | n_total | r≥0 n / EV | r≥+0.1% n / EV | r≥+0.3% n / EV |
|--------|----------|---------|------------|----------------|----------------|
| SPY | gap_fill | 61 | 0 / +0.00% | 0 / +0.00% | 0 / +0.00% |
| XLK | mean_reversion | 1072 | 67 / -13.63% | 4 / -0.67% | 0 / +0.00% |

**Aggregate at threshold 0:** -13.63%
**Aggregate at +0.1%:** -0.67%
**Aggregate at +0.3%:** +0.00%

## Verdict

**Hand-tuned strict thresholds remain optimal.** Best ML aggregate +9.08% vs strict +42.41%. ML does not add value for per-trade entry filtering on this dataset.

### Why ML didn't help

1. **Sample sizes are too small.** Even pooled gap_fill across 4 ETFs yields only ~176 candidates over 2 years. Mean-reversion has more (~1000) but is dominated by a long bear-reversion regime rather than learnable patterns. AUC of 0.497 confirms features have no predictive signal beyond noise.

2. **Strict thresholds are implicit ML.** The 5-signal weighted score in mean_reversion (RSI, Bollinger, VWAP, volume, momentum) IS a hand-engineered linear classifier. Phase 0 threshold optimization already found the optimal operating point. GBM on the same features gives no marginal lift.

3. **Regression also failed.** Predicting pnl_pct magnitude out-of-sample is even harder than classifying win/loss, as the model must learn a continuous noisy target from a small sample. OOF regression filtering did not outperform the strict baseline at any threshold.

### What to do instead

- **Plan 2.0 Paper MVP recommendation stands.** Use the strict-threshold 5-ensemble system (4 gap_fill ETFs + XLK mean_reversion). 4-12 weeks of paper trading will validate whether +42% backtested EV survives out-of-sample.
- **If ML is revisited, more promising directions are:**
  - *Regime detection* (daily/weekly classifier to disable strategies in trending markets)
  - *Position sizing by predicted edge* (scale lot size by predicted pnl_pct on confirmed signals)
  - *Cross-asset features* (VIX term structure, credit spreads, intermarket correlations)
  - *Larger backtest history* (5-10 years instead of 2 years to provide enough sample for GBM to generalise)

**Bottom line:** ML for per-trade entry filtering is not the answer with 2 years of daily-frequency signals. The hand-tuned strict threshold system is more reliable and interpretable. Ship the paper trader.
