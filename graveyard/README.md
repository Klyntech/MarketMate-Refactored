# Strategy Graveyard

**Dead strategies are institutional memory. Do not delete them.**

Six months from now, someone will "discover" the exact same failed idea. This file prevents that.

## Rejection Summary

| Strategy | ID | PF | WR | Verdict |
|----------|----|----|----|---------|
| Monday Gap Fade | MM-002 | 0.65 | 56% | Works only in RANGING/LOW_VOL; unconditional = slow bleed |
| Key Level Fade | MM-003 | 0.55 | 35% | Wick rejections don't produce follow-through |
| Liquidity Sweep | MM-009 | 0.84 | 46% | Better as Gate 5 filter in 8-Gate pipeline |
| Order Block Retest | MM-019 | 0.54 | 35% | Pipeline filter, not standalone signal generator |
| FVG Fill | MM-020 | 0.53 | 35% | Pipeline filter, not standalone signal generator |
| MSS Entry | MM-021 | 0.57 | 27% | Pipeline filter, not standalone signal generator |
| Session Raid | MM-022 | 0.00 | 0% | Generated zero signals; too restrictive |
| London Breakout | MM-023 | 0.70 | 41% | Classic setup, largely arbed away |
| NY Reversal | MM-024 | 0.11 | 10% | Catastrophic: London extremes extend, don't reverse |
| ATR Compression | MM-025 | 0.45 | 31% | Compression often leads to more compression |

## Detailed Records

See `graveyard.json` for complete rejection records including:
- Profit factor, Sharpe, trade counts
- Verdict and reasoning
- Revival conditions (where applicable)
- Burial date

## Anti-Patterns to Avoid

1. **Don't extract pipeline filters as standalone strategies** — OB, FVG, MSS are Gate 5/6 components, not alpha generators
2. **Don't deploy session strategies** — London Breakout, NY Reversal are well-known and arbed away
3. **Don't assume compression = expansion** — ATR contraction often leads to more contraction
4. **Don't trust small samples** — PF > 2.0 with < 30 trades is noise
5. **Don't deploy gap fades unconditionally** — They are regime-dependent
