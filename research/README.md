# Research Lab

Strategies under validation. Not yet production.

## Promotion Path

```
Research → Validation → Paper Trade → Production
```

A strategy must survive each stage before advancing:
1. **Research**: Initial backtest shows PF > 1.0
2. **Validation**: Walk-forward, spread stress, Monte Carlo pass
3. **Paper Trade**: 90-day forward test with real-time data
4. **Production**: Deployed with capital

## Alpha Families

### Liquidity Alpha
Order blocks, FVGs, market structure shifts, session raids.
- **Warning**: All four failed as standalone strategies. They are pipeline filters (Gate 5/6 components of the 8-Gate SMC system), not independent signal generators.
- **Revival path**: Only as refinement layers inside the 8-Gate pipeline.

### Session Alpha
London and New York session-specific patterns.
- **Warning**: Both failed. Session-based strategies are well-known and appear to be arbed away in modern markets.

### Volatility Alpha
ATR compression/expansion, RSI divergence.
- **MM-005 RSI Divergence**: PF 2.0 but only 6 trades — unvalidated noise.
- **MM-025 ATR Compression**: PF 0.45 on 208 trades — compression doesn't predict expansion direction.

### Gap & Auction Alpha
Weekend and Monday gap fills.
- **MM-002** and **MM-012** are cross-listed here from Production because they trade the gap phenomenon.
- Both are regime-dependent: profitable in RANGING/LOW_VOL, unprofitable in TRENDING/HIGH_VOL.

## Lessons

The biggest risk is not lack of strategies. The biggest risk is convincing yourself that a backtest portfolio with PF 1.17 and a handful of strong instrument-specific edges is already a finished trading business. What you have now is enough to justify building a research dashboard, a regime engine, and a live paper-trading portfolio monitor. Those three projects will likely improve results more than strategy MM-026 through MM-040 ever will.
