# Strategy Research Review and Gap Analysis

Date: 2026-05-02
Scope: Honest assessment of our 9-strategy intraday ETF bot against published literature, with explicit gaps in coverage and methodology.

---

## 1. Strategies We Tested vs Literature

| Our strategy | Literature equivalent | Reported edge in literature | Our result |
|---|---|---|---|
| MeanReversion (RSI/BB/VWAP weighted) | Connors RSI(2)/RSI 25/75; classic short-horizon reversal | Connors RSI(2) ~70-80% WR on equities, asymmetric (winners < losers) — see [QuantifiedStrategies RSI 25/75](https://www.quantifiedstrategies.com/larry-connors-rsi-25-rsi-75/) | XLK +1.01 EV, others marginal — directionally consistent (works, modest edge) |
| TrendFollow (200d MA + 20-bar HH + RSI>50) | Donchian breakout / 200d-MA filter trend follow | Long-term trend follow well documented, but typically positive on multi-month holds, not intraday | Negative across all ETFs — consistent: trend-follow on 5-min ETF data is fighting the documented short-horizon mean reversion regime |
| MomentumBreakout (78-bar HH + 1.5x volume + 200d MA) | Day-trading momentum / Bollinger expansion breakout | Mixed; short-horizon equity index breakouts often fade — see [Quantified Strategies day-trading momentum](https://www.quantifiedstrategies.com/day-trading-momentum-strategy/) | All negative — consistent with the literature finding that index ETFs show short-horizon mean reversion, not momentum, intraday |
| EnvDependentReversion | MeanReversion + intraday-time-of-day filter (lunch dip) | Time-of-day patterns documented; lunchtime is a known low-volume, mean-reverting window | XLK +0.38 EV — directionally OK but small |
| MultiTimeframe (5/15/60-min RSI confluence) | "Triple-screen" / Elder-style multi-TF | Marginal in published tests; tends to over-filter | Slightly negative — consistent (over-filtered) |
| AnalysisDrivenReversion | Regime-conditioned MR | Regime filters help on average | Failed in our test — but the SPY-up filter was probably too coarse |
| VWAPScalp | VWAP reversion (oversold-of-VWAP) | [QuantifiedStrategies VWAP backtest on SPY](https://www.quantifiedstrategies.com/volume-weighted-average-price/) shows PF ~1.69 with simple long-below-VWAP rule | Failed for us — our deviation×ATR formulation may have been too restrictive; literature uses simpler triggers |
| OpeningRangeBreakout (first 30min OR + breakout) | Classic ORB; Zarattini/Aziz/Barbon noise-area variant | Reported [ORB on SPY/QQQ/IWM/DIA](https://tosindicators.com/research/orb-backtest-spy-vs-aapl) shows mid-week (Tue/Wed) WR is best; pure long-only often loses on QQQ in volatile windows. Vanilla ORB on indices is a coin flip — the recent academic version uses a noise-area band + dual VWAP trailing stop | Negative EV — matches literature for vanilla ORB on indices. We did NOT test the noise-area / VWAP-stop variant |
| GapFill (gap_threshold + target=prev_close) | Classic gap fade; widely documented | [Trade That Swing](https://tradethatswing.com/sp-500-spy-es-gap-fill-strategy-and-statistics/), [TradingStats](https://tradingstats.net/gap-fill-indicator/): tiny gaps fill ~78%, common gaps ~90%, large gaps only ~8%. Overall ~60% same-day fill on SPY | XLK +23.85 EV (best); pooled +42% over 2yr — consistent with published 60-90% fill rates for small-to-medium gaps |

**Net read:** Our results are not anomalous vs literature. Where the literature says "works" (gap fill, RSI mean reversion on indices), we got a positive edge. Where it says "doesn't work intraday" (raw breakout/trend-follow on broad-index ETFs), we got negative EV. That's a reassuring sanity check on infrastructure correctness.

---

## 2. Strategies We Did NOT Test (Most Relevant Gaps)

### 2.1 Intraday Momentum (Heston-Korajczyk-Sadka / Zarattini-Aziz-Barbon)
- **Description:** First half-hour return predicts the **last half-hour** return on broad-index ETFs. Predictive R² ~1.6%, rising to 2.6% with the 12th half-hour added. Published in [Heston/Korajczyk/Sadka 2014](https://c.mql5.com/forextsd/forum/173/intraday_momentum_-_the_first_half-hour_return_predicts_the_last_half-hour_return.pdf); strengthened on high-volatility, high-volume, recession, and macro-news days. A more recent variant by [Zarattini/Aziz/Barbon (SSRN 2024)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4824172) uses a 14-day average-absolute-deviation noise band as ORB triggers with VWAP+band trailing stops, reporting 1985% total return / 19.6% annualized / 1.33 Sharpe on SPY 2007-2024 (gross of cost concerns flagged in [QuantConnect community replication](https://www.quantconnect.com/forum/discussion/17091/beat-the-market-an-effective-intraday-momentum-strategy-for-s-amp-p500-etf-spy/), where realistic costs cut Sharpe to ~0.4).
- **Why it matters for us:** Directly applies to SPY/QQQ/IWM/DIA; uses 5-min bars; entries are 1-2 per day per symbol — fits our infrastructure. We never tested a "first 30-min predicts last 30-min" overlay on any of our strategies.
- **Feasibility:** High. Add a feature `first_30m_return` and a strategy that holds in the last 30-min direction.

### 2.2 Pairs / Statistical Arbitrage (SPY-IWM, SPY-DIA, XLK-QQQ)
- **Description:** Cointegration-based mean reversion of the spread between two correlated ETFs. [QuantStart SPY-IWM 1-min backtest](https://www.quantstart.com/articles/Backtesting-An-Intraday-Mean-Reversion-Pairs-Strategy-Between-SPY-And-IWM/) documents the reference implementation. Note that [Cunha 2025](https://link.springer.com/article/10.1057/s41260-025-00416-0) finds QQQ/XLK do NOT pass full cointegration over long windows but have exploitable shorter regimes.
- **Why it matters for us:** We hold up to 5 ETFs that are highly correlated. A market-neutral spread trade hedges out the regime risk that drives much of our equity curve dispersion.
- **Feasibility:** Medium. Requires running rolling cointegration test (Engle-Granger) and z-score thresholds. Adds short-leg execution complexity (Alpaca paper supports shorts).

### 2.3 Pre-FOMC Drift / Macro-Day Tilt
- **Description:** [Lucca & Moench 2015 (J. Finance)](https://onlinelibrary.wiley.com/doi/10.1111/jofi.12196) document +49 bps S&P 500 average return in the 24 hrs before scheduled FOMC announcements — accounting for >80% of the equity premium 1994-2011. [Disappearing pre-FOMC drift (Cieslak et al.)](https://www.sciencedirect.com/science/article/abs/pii/S1544612320315956) finds the effect has weakened post-2015 but is not gone.
- **Why it matters for us:** 8 FOMC dates/year = essentially free directional EV. Trivial to encode.
- **Feasibility:** Trivial — overlay an "is_pre_fomc_24h" boolean and either bias long or skip mean-reversion shorts on those windows.

### 2.4 Sector Momentum Rotation (cross-sectional, weekly)
- **Description:** Rank XLK/XLF/XLE/XLU/XLV/etc by trailing 1m/3m/6m return; hold top-N. [Faber's sector rotation](https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/fabers-sector-rotation-trading-strategy) and [Quantpedia sector momentum](https://quantpedia.com/strategies/sector-momentum-rotational-system) show ~5%/yr excess return historically. Faber's strategy is monthly, not intraday.
- **Why it matters for us:** Our universe is too narrow (SPY/QQQ/IWM/DIA + XLK only). A sector rotation overlay needs at least the 9 sector SPDRs.
- **Feasibility:** Medium. Universe expansion required. Different rebalance cadence than our intraday loop.

### 2.5 Turn-of-the-Month Tilt
- **Description:** Last trading day + first 3 of following month earn 10-20 bps/day vs ~0 elsewhere. [Lakonishok-Smidt 1988](https://business.purdue.edu/faculty/mcconnell/publications/Equity-Returns-at-the-Turn-of-the-Month.pdf) and [McConnell-Xu update](https://business.purdue.edu/faculty/mcconnell/publications/Equity-Returns-at-the-Turn-of-the-Month.pdf) confirm it persists. **Caveat:** [Quantseeker 2024](https://www.quantseeker.com/p/turn-of-the-month-strategies-do-they) and the recent meta-analysis suggest the effect has weakened post-2015, possibly arbitraged away.
- **Why it matters for us:** Cheap to encode as a feature. Combined with our gap-fill on TOM days could be informative.
- **Feasibility:** Trivial — `is_tom = day in {-1, +1, +2, +3}`.

### 2.6 VIX-Regime Conditioning
- **Description:** [VIX regime filter for momentum/mean-reversion](https://options.cafe/blog/momentum-rsi-strategy-backtest-results/) reports 81% WR vs ~60% baseline when applied to RSI strategies; VIX-mean-reversion entries after spikes >30 yield 68% WR. Mean-reversion outperforms when VIX is high; trend-follow when VIX is low and rising.
- **Why it matters for us:** Our strategies are flat-conditioned. VIX is a free regime variable.
- **Feasibility:** High. Pull VIX daily close from any free source; add as feature.

### 2.7 End-of-Day Last-Hour Momentum
- **Description:** [Quantified Strategies last-hour SPY rule](https://www.quantifiedstrategies.com/last-hour-trading-strategy/): if SPY is up >1.25% from open by 3pm, the last hour rallies further (13 wins / 18 fills). Related to MOC ETF flow imbalances.
- **Why it matters for us:** Our trading day cuts off before EOD; we're not capturing this. Adds 1 trade/day potential.
- **Feasibility:** Medium — requires extending the run-window and a clean MOC exit.

---

## 3. Calendar / Regime Effects We Missed (Add vs Skip)

| Effect | Status | Recommendation |
|---|---|---|
| Pre-FOMC drift | Strong literature, weakening post-2015 | **ADD** — trivial overlay, bias long, 8 events/yr |
| Turn-of-the-month | Documented but [recently weakening](https://www.quantseeker.com/p/turn-of-the-month-strategies-do-they) | **ADD AS FEATURE** — cheap to encode, test interaction with gap_fill |
| Monday/weekend effect | [Meta-analysis 2024](https://link.springer.com/article/10.1007/s40822-024-00293-9) confirms but weakened in S&P 500 due to institutional arb | **ALREADY USING** (our P5 finding) — but be cautious about signal strength |
| Quarter-end window dressing | Documented, modest | **SKIP** for now — small effect, 4 events/yr |
| Santa Claus rally | Last 5 trading days + first 2 of January | **OPTIONAL** — easy overlay |
| January effect | Largely arbitraged away in large-cap | **SKIP** for SPY/QQQ universe |
| Pre-holiday drift | Modest positive bias day before holidays | **OPTIONAL** |
| VIX regime | Strong evidence | **ADD** — pull VIX feature, condition strategies |

---

## 4. Methodology Weaknesses We Found

### 4.1 Stop evaluated on close, not low-of-bar — UNDERESTIMATES LOSSES
This is the single biggest methodology gap. Real fills happen at the stop price during the bar (or worse with slippage), not at the favorable close. On a 5-min bar that touches your stop at the low and closes well above it, our backtest counts that as a win when reality counts it as a loss. Direction of bias: **all our reported EVs are systematically too optimistic**. Magnitude likely 10-30% of reported edge per strategy depending on stop tightness vs ATR.

**Fix:** Switch stop evaluation to bar low (long) / bar high (short) within the bar. Trivial 1-line change in the backtest harness.

### 4.2 Transaction cost assumption (0.10% round-trip) — likely OK for SPY, OPTIMISTIC for XLK
- SPY/QQQ: typical spread is [1-2 bps](https://www.alphaexcapital.com/etfs/etf-investing-basics/how-do-etfs-work/bid-ask-spread-in-etfs), commission 0 on Alpaca. Round-trip 2-4 bps + slippage 1-2 bps = ~5 bps total. Our 10 bps is conservative (good).
- XLK: spread is wider (~3-5 bps in normal hours); plus our backtest fills at close — actual execution likely 2-3 bps worse per side. Round-trip realistic: 8-12 bps. Our 10 bps is approximately right but could be 20% optimistic in volatile windows.
- IWM/DIA: similar to XLK.

[Alpha Architect documents](https://alphaarchitect.com/trading-costs-wipe-out-the-overnight-return-anomaly/) that the overnight anomaly disappears after realistic costs. Our high-frequency strategies (ORB, MultiTimeframe) are more cost-sensitive than gap_fill (lower trade count). The cost assumption is most dangerous for the high-freq strategies that already test negative — could mean they're MORE negative than reported, not less.

### 4.3 Sample size on the P5 Monday-Bull-Gap finding — UNDERPOWERED
51 trades with 90.2% win rate. Per the [statistical-significance benchmarks](https://www.backtestbase.com/education/how-many-trades-for-backtest), 30 trades is the floor for CLT, 100 the floor for "basic reliability", and 200-500 for institutional-grade confidence. 51 is on the low end. The 90% WR is suspicious — it implies probability of being a real ≥80% WR effect is plausible but a 50-60% true rate plus regime tailwind is also consistent with the data.

### 4.4 Multiple comparisons — partial Bonferroni applied, [Deflated Sharpe Ratio (Bailey/López de Prado)](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf) NOT applied
We tried 9 strategies × 5 ETFs = 45 base configs, plus pattern discovery P1-P5 over many feature combinations. The P5 composite filter was selected from likely hundreds of candidate filter combinations. Even with Bonferroni at the strategy level, the P5 selection step is not corrected. Best-in-class fix is the [Deflated Sharpe Ratio](https://en.wikipedia.org/wiki/Deflated_sharpe_ratio) which explicitly accounts for the number of trials.

### 4.5 Walk-forward CV is OK but not [CPCV](https://en.wikipedia.org/wiki/Purged_cross-validation)
Single-path walk-forward (180/30/1/30) is high variance — one historical path. [Combinatorial Purged Cross-Validation](https://towardsai.net/p/l/the-combinatorial-purged-cross-validation-method) generates many paths and is superior for measuring overfit risk. Worth implementing if we keep iterating on ML or filter selection.

### 4.6 PDT rule — REAL constraint for live
[Alpaca PDT rules](https://alpaca.markets/support/what-is-the-pattern-day-trading-pdt-rule) require $25k minimum equity to day-trade more than 3 round-trips per 5 business days. Paper accounts simulate this. If our live capital is under $25k, our strategy mix is constrained to ≤3 day-trades per 5-day window. Our current 3-concurrent + 9 strategies easily blows past this in beta mode. Need a PDT-aware governor or commit to ≥$25k seed capital for live.

### 4.7 Position sizing — fixed-fractional 25% capped at $2.5k is fine for paper, naive for capital growth
[Half-Kelly](https://en.wikipedia.org/wiki/Kelly_criterion) is the professional default. With our small trade samples (<100/strategy), full Kelly would be wildly miscalibrated; quarter-Kelly is the safer practical choice. Worth implementing once any strategy crosses 100 trades with stable EV.

---

## 5. Verdict on the Monday-Bull-Gap-Fill Finding

**Read the literature, then read our own caveats:**

- Gap fill on SPY-style ETFs has a ~60-90% baseline fill rate (small-to-medium gaps). 90% is at the **high end** of that range, not impossible.
- Monday-specific premium: the [meta-analysis](https://link.springer.com/article/10.1007/s40822-024-00293-9) notes Mondays *historically had lower returns*, not higher, in large-cap. So our "Monday + bullish regime → fill" doesn't have a clean published mechanism. The closest interpretation: in a bull regime (`daily_20d_return > 0`), the Monday open weakness — which is what creates the gap — is more likely to be bought back into the trend.
- Sample: 51 trades, late-2025-to-2026 OOS window. The 2025-late through 2026 period was a bullish regime by construction of the filter; the test mostly measures "do gaps fill in bull regimes?" — answer: yes, well-documented (~78-90%).

**Honest verdict:** The finding is **plausible-but-likely-overstated**. The Monday component is the most fragile leg; we'd expect the same composite without the Monday filter to show 70-85% WR (consistent with literature). The 90% WR is partly real edge from the bull-regime filter, partly sampling variance from a small N, partly survivorship of the search process across many candidate filters (multiple-comparisons).

Realistic expectation for live: 65-75% WR with similar EV per trade — still tradeable, but not the headline 90%.

---

## 6. Top 3-5 Prioritized Next Experiments

### Experiment A: Fix stop evaluation to bar low/high — RE-RUN ALL BACKTESTS
- **Effort:** ~1 hour code change + full re-run.
- **Information gain:** HIGH. Recalibrates every reported EV. Could invalidate marginal strategies (MR, EnvDependent) and tighten our confidence in the strong ones (gap_fill).
- **Why first:** Fixes the largest known optimism bias. Everything downstream depends on accurate baseline numbers.

### Experiment B: Validate Monday-Bull-Gap with bootstrap + holdout + drop-Monday ablation
- **Effort:** ~3 hours.
- **Information gain:** HIGH for the central live-trading decision.
- **Method:**
  1. Bootstrap 1000 resamples of the 51 trades; report 95% CI on WR (likely [78%, 96%] — wide).
  2. Run the same composite WITHOUT the `is_monday` filter. If WR drops by <5 pts, Monday is decoration; the regime filter is doing the work.
  3. Re-run on a different holdout split (different OOS window). If WR drops below 75%, regime artifact confirmed.

### Experiment C: Add Intraday-Momentum strategy (first-30min predicts last-30min)
- **Effort:** ~4 hours (new strategy file + features).
- **Information gain:** MEDIUM-HIGH. Best-documented intraday edge in academic literature, directly applies to our universe, complementary to gap_fill (different time of day, different signal).
- **Variants worth testing:** (a) plain Heston/Korajczyk/Sadka direction match; (b) Zarattini noise-area ORB with VWAP trailing stop.

### Experiment D: VIX regime feature + condition existing strategies
- **Effort:** ~2 hours (data feed + retag backtests).
- **Information gain:** MEDIUM. Could improve EV of borderline strategies (TrendFollow in low-VIX, MR in high-VIX). Cheap insurance.

### Experiment E: Pre-FOMC overlay
- **Effort:** ~1 hour (FOMC date list is public).
- **Information gain:** MEDIUM. Small number of events but high per-event edge. Easy win if it survives our 2-yr window (8-16 events).

**Skip for now:** Pairs trading (good idea, but big infra lift — short execution + cointegration + new strategy class), sector rotation (universe expansion needed), full ML re-do (AUC ~0.5 prior runs suggest features, not algorithm, are the bottleneck — fix feature engineering instead).

---

## Sources

### Strategies
- [Heston, Korajczyk, Sadka — Intraday Momentum (PDF)](https://c.mql5.com/forextsd/forum/173/intraday_momentum_-_the_first_half-hour_return_predicts_the_last_half-hour_return.pdf)
- [Zarattini/Aziz/Barbon — Beat the Market intraday SPY (SSRN)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4824172)
- [QuantConnect community replication](https://www.quantconnect.com/forum/discussion/17091/beat-the-market-an-effective-intraday-momentum-strategy-for-s-amp-p500-etf-spy/)
- [QuantStart — SPY-IWM Pairs Trading](https://www.quantstart.com/articles/Backtesting-An-Intraday-Mean-Reversion-Pairs-Strategy-Between-SPY-And-IWM/)
- [Cunha 2025 — ETF cointegration (Springer)](https://link.springer.com/article/10.1057/s41260-025-00416-0)
- [QuantifiedStrategies — VWAP backtest](https://www.quantifiedstrategies.com/volume-weighted-average-price/)
- [Connors RSI 25/75](https://www.quantifiedstrategies.com/larry-connors-rsi-25-rsi-75/)
- [TosIndicators ORB SPY/QQQ/AAPL backtest](https://tosindicators.com/research/orb-backtest-spy-vs-aapl)
- [Faber's Sector Rotation](https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/fabers-sector-rotation-trading-strategy)
- [Quantpedia — Sector Momentum Rotational System](https://quantpedia.com/strategies/sector-momentum-rotational-system)
- [Trade That Swing — SPY gap fill statistics](https://tradethatswing.com/sp-500-spy-es-gap-fill-strategy-and-statistics/)
- [TradingStats — Gap fill probability](https://tradingstats.net/gap-fill-indicator/)
- [QuantifiedStrategies — Last-hour trading rule](https://www.quantifiedstrategies.com/last-hour-trading-strategy/)

### Calendar / Regime
- [Lucca & Moench — Pre-FOMC Drift (J. Finance 2015)](https://onlinelibrary.wiley.com/doi/10.1111/jofi.12196)
- [Disappearing Pre-FOMC drift (Finance Research Letters)](https://www.sciencedirect.com/science/article/abs/pii/S1544612320315956)
- [Lakonishok-Smidt / McConnell-Xu — Turn-of-the-month (Purdue)](https://business.purdue.edu/faculty/mcconnell/publications/Equity-Returns-at-the-Turn-of-the-Month.pdf)
- [Quantseeker — TOM still working?](https://www.quantseeker.com/p/turn-of-the-month-strategies-do-they)
- [Quantpedia — TOM in Equity Indexes](https://quantpedia.com/strategies/turn-of-the-month-in-equity-indexes)
- [Day-of-week meta-analysis (Springer 2024)](https://link.springer.com/article/10.1007/s40822-024-00293-9)
- [VIX regime filter — Options Cafe momentum-RSI backtest](https://options.cafe/blog/momentum-rsi-strategy-backtest-results/)
- [iPresage — VIX mean reversion](https://www.ipresage.com/research/vix-mean-reversion)

### Methodology
- [Bailey & López de Prado — Deflated Sharpe Ratio](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)
- [Wikipedia — Deflated Sharpe Ratio](https://en.wikipedia.org/wiki/Deflated_sharpe_ratio)
- [Combinatorial Purged Cross-Validation (Towards AI)](https://towardsai.net/p/l/the-combinatorial-purged-cross-validation-method)
- [Wikipedia — Purged cross-validation](https://en.wikipedia.org/wiki/Purged_cross-validation)
- [BacktestBase — How many trades for a valid backtest](https://www.backtestbase.com/education/how-many-trades-for-backtest)
- [Trading Dude — Statistical significance in backtesting](https://medium.com/@trading.dude/how-many-trades-are-enough-a-guide-to-statistical-significance-in-backtesting-093c2eac6f05)
- [Frontiers — Practical Kelly implementation](https://www.frontiersin.org/journals/applied-mathematics-and-statistics/articles/10.3389/fams.2020.577050/full)
- [Wikipedia — Kelly criterion](https://en.wikipedia.org/wiki/Kelly_criterion)

### Costs / Infrastructure
- [Natixis — Understanding ETF bid-ask spread](https://www.im.natixis.com/en-us/insights/portfolio-construction/2024/etf-cost-bid-ask-spread)
- [AlphaEx Capital — ETF bid-ask spread fundamentals](https://www.alphaexcapital.com/etfs/etf-investing-basics/how-do-etfs-work/bid-ask-spread-in-etfs)
- [Alpha Architect — Trading costs and overnight anomaly](https://alphaarchitect.com/trading-costs-wipe-out-the-overnight-return-anomaly/)
- [Alpaca — PDT rule](https://alpaca.markets/support/what-is-the-pattern-day-trading-pdt-rule)
- [Alpaca — User Protections / PDT](https://docs.alpaca.markets/docs/user-protection)
