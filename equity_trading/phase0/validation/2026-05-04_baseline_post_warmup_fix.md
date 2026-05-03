# Validation Report: orb_default_v0

- **Variant**: `orb_default_v0`
- **Baseline**: `orb_default_v0`
- **Generated**: 2026-05-03 16:56 UTC
- **Git SHA**: `2264103`
- **Data manifest hash**: `b0e816429556`
- **Holdout window**: 2024-05-01 → 2026-05-01

## Headline: ❌ **REJECT**

- ❌ Required gate `tail_risk` failed: worst single trade -7.73% exceeds limit -5.0%; portfolio drawdown 42.02% exceeds limit 20.0%

## Gate Results

### Gate 1: OOS holdout ✅

| metric | variant | baseline | diff |
|---|---:|---:|---:|
| Annual return | -22.60% | -22.60% | +0.00pp |
| Max drawdown | -42.02% | -42.02% | +0.00pp |
| Sharpe | -2.39 | -2.39 | +0.00 |

variant ann -22.60% vs baseline -22.60% (+0.00pp), Sharpe -2.39 vs -2.39


### Gate 2: Tail risk ❌

- worst single trade: **-7.73%** (limit -5.0%)
- portfolio MaxDD: **42.02%** (limit 20.0%)
- 30-day rolling loss: **9.24%** (limit 10.0%)

#### Catastrophic stop simulation (-5% cap on every trade)
- worst trade if cap were applied: **-5.00%**
- This is informational only. To apply, add a `catastrophic_stop_pct: 5.0` override in the variant config and re-validate.


### Gate 3: Sample size ✅

- holdout trades: **1136**
- threshold: **30** (FAIL below, WARN below 1.5x)
- n=1136 >= 1.5*min=45: adequate


## Reproducibility

```
git checkout 2264103
python3 -m equity_trading.validation.validate \
    --variant configs/orb_default_v0.yaml \
    --baseline configs/orb_default_v0.yaml
```

## Decision Log

(Fill in: APPROVED / REJECTED / reasoning)
