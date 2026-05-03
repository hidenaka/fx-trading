# Phase A search — internal valid (2022-01-01 → 2024-04-30)

**Threshold (Q2 A)**: ann ≥ -3%/yr, MaxDD ≤ 20%, worst trade ≤ 5%, Sharpe ≥ -0.3

| variant | ann | MaxDD | worst | Sharpe | n trades | passes? |
|---|---:|---:|---:|---:|---:|:---:|
| orb_default_v0_capped | -21.37% | -42.82% | -5.10% | -2.71 | 940 | ❌ ann/MaxDD/worst/Sharpe |
| orb_default_v0_capped_concur1 | -13.58% | -28.80% | -5.10% | -2.71 | 940 | ❌ ann/MaxDD/worst/Sharpe |
| orb_default_v0_capped_concur1_vix22 | -11.42% | -24.60% | -5.10% | -3.16 | 797 | ❌ ann/MaxDD/worst/Sharpe |
| orb_default_v0_capped_size12 | -11.26% | -24.26% | -5.10% | -2.71 | 940 | ❌ ann/MaxDD/worst/Sharpe |
| orb_default_v0_capped_size12_vix22 | -9.70% | -21.12% | -5.10% | -3.16 | 797 | ❌ ann/MaxDD/worst/Sharpe |
| orb_default_v0_capped_vix22 | -18.54% | -37.93% | -5.10% | -3.16 | 797 | ❌ ann/MaxDD/worst/Sharpe |

## No candidate passes

Phase A step 1 (6 candidates) yielded no passing variant. Escalate to step 2 (12 candidates) by adding `target_mult ∈ {1.0, 1.5}` to the search dimensions, or to step 3 (24 candidates, +daily_halt_pct), or to Phase B (new strategies / universe) per `docs/superpowers/specs/2026-05-04-strategy-rethink-design.md` §8.
