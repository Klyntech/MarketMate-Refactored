# MM-012: Gap Fill Weekend (GPFL)

**Status**: MARGINAL  
**Alpha Family**: Gap & Auction Alpha  
**Type**: Mean Reversion (Instrument-Locked)  
**Allowed Instruments**: NAS100, US30, GBPUSD

## Performance

| Metric | Value |
|--------|-------|
| Profit Factor | 1.23 |
| Win Rate | 55.2% |
| Avg R | 0.105 |
| Trades | 134 |

## Verdict

Barely profitable. Same alpha source as MM-002 (weekend gap). Correlation with MM-002 is low (0.06) but both trade the same gap. Marginal edge at best.

## Key Risk

Low correlation with MM-002 is misleading — they trade the same phenomenon. Both die in trending markets. Deploying both doubles exposure without doubling alpha.

## Relationship to MM-002

- MM-002 uses ATR-based gap sizing (gap > 0.3× ATR)
- MM-012 uses percentage-based gap sizing (gap > 0.15%)
- MM-012 has instrument lock (NAS100, US30, GBPUSD)
- MM-002 trades all instruments
- They are different parameterizations of the same trade

## Recommendation

Do not deploy alongside MM-002. Choose one or the other, and only under RANGING/LOW_VOL regime conditions.
