# MM-002: Volatility Compression Expansion (VCE)

**Status:** ❌ KILLED  
**Date Killed:** 2025-06-07  
**Reason:** Indicator-only, no edge. Low PF, no structural logic.

## Kill Reason
Pure indicator play with no structural market context. Low profit factor confirmed across validation — ATR compression ratios don't predict breakout direction without understanding where liquidity sits.

## Original Hypothesis
When volatility compresses (short ATR / long ATR < threshold), the market is coiling for a directional expansion. Entering on the breakout from the compression range with ATR-based stops and an EMA trend filter should capture momentum moves.

## Why It Failed
Indicator-only, no edge. Low PF, no structural logic. Volatility compression identifies a state but not a direction — without knowing where liquidity pools sit, breakouts are essentially coin flips. The EMA trend filter adds lag, not edge.

## Artifact
- `mm002_vce.py` — Original strategy implementation
