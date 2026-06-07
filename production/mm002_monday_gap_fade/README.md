# MM-002: Monday Gap Fade (MGF-01)

**Status**: FAILED DEEP VALIDATION  
**Alpha Family**: Gap & Auction Alpha  
**Type**: Mean Reversion (Defensive Entry)

## Performance

| Metric | H4 Backtest | 12-Year Daily |
|--------|-------------|---------------|
| Profit Factor | 1.17 | 0.65 |
| Win Rate | 56.2% | 56.2% |
| Avg R | -0.05 | -0.187 |
| Max DD | — | 696.1R |

## Verdict

The 12-year daily data tells the truth. PF 0.65 portfolio-wide. Bootstrap P(PF<1) = 100%. NOT A SINGLE YEAR has PF > 1.1. The earlier H4 backtest showing PF 1.17 was a short-window artifact (2023-2026 only).

Gap fade works ONLY in RANGING/LOW_VOL regimes. Without a regime filter, this is a slow bleed.

## Revival Condition

RANGING/LOW_VOL regime filter + NZDUSD/USDCHF only + live paper trading confirmation.

## Key Finding

MM-002 and MM-012 trade the same phenomenon (weekend gap). Their month-to-month correlation is low (0.063) but they share the same failure mode: trending markets. Deploying both doubles exposure without doubling alpha.
