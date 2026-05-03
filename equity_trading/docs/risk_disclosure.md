# Risk Disclosure — Equity Bot (敏腕モード v2)

## 1. Structural concentration

The bot trades 5 symbols: TECL, TQQQ, TNA, UPRO, UDOW.

| symbol | leverage | underlying | factor | rebalance |
|---|---|---|---|---|
| TECL | 3x | XLK (US tech) | growth | daily |
| TQQQ | 3x | NDX (US large-cap tech) | growth | daily |
| TNA | 3x | RUT (US small-cap) | smid | daily |
| UPRO | 3x | SPX (US large-cap blend) | broad | daily |
| UDOW | 3x | DJIA (US blue-chip) | broad | daily |

All five collapse to **3x · US equity index · long-tilt · daily-rebalanced**.
In a market-wide sell-off, all positions go the same direction.
**There is no diversification benefit across these five symbols.**

## 2. Historical correlation (computed from train data)

Re-compute with: `PYTHONPATH=. python3 equity_trading/scripts/compute_correlation.py`.

### Daily-return correlation (train)

|   | TECL | TQQQ | TNA | UPRO | UDOW |
|---|---:|---:|---:|---:|---:|
| TECL | 1.00 | 0.82 | 0.67 | 0.79 | 0.69 |
| TQQQ | 0.82 | 1.00 | 0.68 | 0.90 | 0.69 |
| TNA | 0.67 | 0.68 | 1.00 | 0.80 | 0.79 |
| UPRO | 0.79 | 0.90 | 0.80 | 1.00 | 0.84 |
| UDOW | 0.69 | 0.69 | 0.79 | 0.84 | 1.00 |

### 5min-return correlation (train)

|   | TECL | TQQQ | TNA | UPRO | UDOW |
|---|---:|---:|---:|---:|---:|
| TECL | 1.00 | 0.79 | 0.58 | 0.75 | 0.66 |
| TQQQ | 0.79 | 1.00 | 0.74 | 0.92 | 0.78 |
| TNA | 0.58 | 0.74 | 1.00 | 0.81 | 0.76 |
| UPRO | 0.75 | 0.92 | 0.81 | 1.00 | 0.91 |
| UDOW | 0.66 | 0.78 | 0.76 | 0.91 | 1.00 |

Off-diagonal values are typically > 0.7 daily and > 0.85 in 5min bars.
TECL/TQQQ are near 0.95 (both QQQ-anchored).

## 3. Volatility drag (3x ETF math)

Daily-rebalanced 3x ETFs decay in choppy markets:
- A 5% up day followed by a 5% down day on the underlying:
  `(1 + 3 * 0.05)(1 - 3 * 0.05) = 1.15 * 0.85 = 0.9775` — **-2.25%** on the 3x ETF
  versus `(1.05)(0.95) = 0.9975` — **-0.25%** on the 1x.
- General formula: cumulative two-day loss ≈ **9 * r²** for the 3x vs **r²** for 1x.
- Real example: 2022 calendar year, NDX returned -33% but TQQQ returned **-79%** —
  the difference is entirely volatility drag.

The bot mitigates this by holding only during RTH (no overnight, with the
exception of LHM which holds <1 day). But within-day volatility still costs.

## 4. PDT (Pattern Day Trader) constraint

US brokerages enforce: under $25,000 equity, you may not place more than
**3 day-trades in any rolling 5-business-day window**. Since the bot does
1-2 round-trips per active day across ORB+LHM, **the seed capital must be
≥ $25,000 (≈ ¥3,750,000 at 150 JPY/USD) for live deployment**. Below that,
many entries will be rejected by the broker even if the strategy fires.

## 5. Where the +13.75%/yr 7-yr backtest comes from

Looking at the monthly P&L breakdown in `phase0/replay_7yr.md`:

- **2020-06**: +$13,770   (post-COVID liquidity rally)
- **2020-07**: +$13,376   (continuation)
- **2020-11**: +$20,301   (election + vaccine news)
- **2020-12**: +$13,070   (year-end melt-up)
- **2024-11**: +$19,099   (Fed-pivot rally)

These five months alone contributed **>$79,000** of the **$118,845** total profit
(67% of the gain from 5 of 84 months). The strategy harvests 3x beta during
sustained low-vol uptrends. In sideways or fast-moving markets it underperforms
or loses. Expect **annual variance of ±20pp around the mean**; do not anchor
on the +13.75% headline as a base case.

**2026-05-04 update**: post-warmup-fix holdout (2024-05 → 2026-05) returned
**-22.60%/yr / -42% MaxDD** on `orb_default_v0`, and Phase A variant search
on internal valid2 (2022 hike cycle window) found 0 passing candidates against
even a relaxed -3%/yr threshold. The strategy is regime-mismatched in
choppy/down markets. See `docs/RUNBOOK.md` for the Phase A outcome and
`docs/superpowers/specs/2026-05-04-strategy-rethink-design.md` for the
rethink design.

## 6. What this means for sizing decisions

- The bot is **not a diversifier** in a broader portfolio. Treat it as one
  concentrated position in 3x US-equity beta.
- Max DD seen in 7-yr replay was **-16.33%**; post-warmup-fix holdout shows
  -42% in the 2024-2026 regime. The realistic worst-case in a 2020-style
  crash is **-30% to -50%** on the bot's equity over a few weeks.
- Catastrophic-stop: setting `catastrophic_stop_pct: 5.0` in variant config
  caps single-trade losses at -5%, at the cost of some upside. Recommended
  for live deployment (see `configs/phase_a/v0_capped*.yaml`).
- Scenario A 25%×3 sizing on a $100k seed risks **up to $75k of capital
  deployed at any time**. Scenario A 12.5%×3 (`v0_capped_size12.yaml`)
  halves that. Smaller sizing materially improves the survival profile in
  bad regimes (see Phase A search results).
