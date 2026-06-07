# MM-009: Liquidity Sweep Quick Reversal (LSQR)

**Status**: MARGINAL REJECT  
**Alpha Family**: Liquidity Alpha  
**Type**: Reversal (Instrument-Locked)  
**Allowed Instruments**: NAS100, ETHUSD, XAGUSD, US30

## Performance

| Metric | Portfolio | ETHUSD Only |
|--------|-----------|-------------|
| Profit Factor | 0.84 | 2.0 |
| Win Rate | 45.6% | 67% |
| Avg R | -0.087 | — |
| Trades | 46 | — |

## Verdict

PF 0.84 portfolio-wide despite instrument locking. Was marginally profitable in earlier tests but V4 shows deterioration. ETHUSD pair alone PF 2.0 (67% WR) but tiny sample.

The liquidity sweep concept is valid but better executed through the full 8-Gate SMC pipeline (Gate 5). Standalone is too noisy.

## Revival Condition

ETHUSD-only deployment after 90-day paper confirmation.

## Relationship to SMC

This strategy is effectively Gate 5 (Liquidity Sweep) of the 8-Gate SMC pipeline extracted as a standalone. It generates more signals but with lower quality because it lacks the G4 (HTF Bias), G6 (Entry Zone), and G7 (LTF Confirmation) filters that make the full pipeline profitable.
