# P2: Univariate Pattern Discovery

**Total samples:** 74278 (train: 4155, test: 70123)

## Baseline WR by strategy/split

| Strategy | Train n | Train WR | Test n | Test WR |
|----------|---------|----------|--------|---------|
| gap_fill | 30 | 0.167 | 564 | 0.601 |
| mean_reversion | 4016 | 0.342 | 69559 | 0.431 |
| vwap_scalp | 109 | 0.349 | 0 | nan |

## gap_fill

_Skipped — insufficient samples (train=30, test=564)_

## mean_reversion

_No robust patterns found for mean_reversion._

## vwap_scalp

_Skipped — insufficient samples (train=109, test=0)_

## Top robust patterns across all strategies (by WR×n)

_No patterns met the robustness criteria (train and test WR ≥ 0.65, n ≥ 20)._

## Interpretation

No single feature provided robust filtering. Move to bivariate (P3).
