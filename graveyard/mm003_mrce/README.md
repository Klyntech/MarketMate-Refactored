# MM-003: Mean Reversion Channel Entry (MRCE)

**Status:** ❌ KILLED  
**Date Killed:** 2025-06-07  
**Reason:** Classic mean reversion without structural context. Fades strong trends.

## Kill Reason
Classic mean reversion approach that fades breakouts expecting fake-outs, but without structural context it systematically fades strong trend moves — the exact moves you want to be riding, not fighting.

## Original Hypothesis
When price breaks out of a compression range, many breakouts are false (fake-outs). By waiting for a reversal candle after the breakout and entering against the breakout direction, with stops beyond the breakout extreme and take-profit at the opposite compression boundary, the strategy captures mean reversion moves back into the range.

## Why It Failed
Classic mean reversion without structural context. Fades strong trends. The fake-out detection (% reversal threshold) cannot distinguish between a genuine reversal and a brief pause before continuation — it systematically takes the wrong side of real moves.

## Artifact
- `mm003_mrce.py` — Original strategy implementation
