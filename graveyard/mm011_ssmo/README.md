# MM-011: Stochastic Momentum (SSMO)

**Status:** ❌ KILLED  
**Date Killed:** 2025-06-07  
**Reason:** Oscillator-based without market structure. Overbought/oversold trap.

## Kill Reason
Using session directional bias (London/NY first-hours momentum) to trade continuation is an oscillator-derived approach that ignores market structure. The "momentum bias" from early session hours is frequently reversed by institutional order flow in later hours — classic overbought/oversold trap in a different disguise.

## Original Hypothesis
The first hours of the London and NY sessions establish a directional bias. If the session moves at least 0.1% in the first 2 hours, that direction should persist through the session. Entering on pullbacks within the session in the direction of the bias should capture intraday trends.

## Why It Failed
Oscillator-based without market structure. Overbought/oversold trap. Session momentum bias is a form of recency bias — early session direction doesn't predict continuation. Institutional activity often reverses early moves, trapping session-bias traders. Without structural confirmation (order blocks, liquidity levels), session direction is noise.

## Artifact
- `mm011_ssmo.py` — Original strategy implementation
