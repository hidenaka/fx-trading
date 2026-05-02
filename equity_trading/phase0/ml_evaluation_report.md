# ML Phase 0 Evaluation Report

**Period:** 2024-05-01 to 2026-05-01 (cached parquet)
**Method:** Walk-forward (180d train / 30d test / 1d purge / 30d step), GBM (depth=3, lr=0.05, n_est=50)

## ETF x Strategy Results

| Symbol | Strategy | Strict n / WR / EV | Loose n / WR / EV | ML p>=0.5 n / WR / EV | ML p>=0.6 | ML p>=0.7 | AUC |
|--------|----------|--------------------|--------------------|----------------------|----------|----------|-----|
| SPY | gap_fill | 39/0.718/+5.37 | 61/0.639/+2.08 | 0/n/a/+0.00 | 0/n/a/+0.00 | 0/n/a/+0.00 | n/a |
| QQQ | gap_fill | 24/0.750/+7.04 | 51/0.569/+3.72 | 0/n/a/+0.00 | 0/n/a/+0.00 | 0/n/a/+0.00 | n/a |
| IWM | gap_fill | 13/0.692/+5.65 | 30/0.667/+8.24 | 0/n/a/+0.00 | 0/n/a/+0.00 | 0/n/a/+0.00 | n/a |
| XLK | gap_fill | 17/0.765/+23.85 | 34/0.471/+17.91 | 0/n/a/+0.00 | 0/n/a/+0.00 | 0/n/a/+0.00 | n/a |
| XLK | mean_reversion | 36/0.611/+0.50 | 1072/0.445/-74.74 | 106/0.245/-18.03 | 48/0.188/-9.56 | 17/0.235/-2.98 | 0.426 |

## Aggregate (5 ensembles total)

- Strict baseline total EV: **+42.41%**
- ML filter p>=0.50 total EV: **-18.03%**
- ML filter p>=0.60 total EV: **-9.56%**
- ML filter p>=0.70 total EV: **-2.98%**

**Verdict:** ML filter did NOT beat strict baseline (+42.41 vs best ML -2.98). Hand-crafted thresholds were already near-optimal.
