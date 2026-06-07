# MM-015: Multi-Timeframe Histogram (MHST)

**Status:** ❌ KILLED  
**Date Killed:** 2025-06-07  
**Reason:** Multi-TF divergence without structural confirmation. False signals.

## Kill Reason
MACD histogram shifts and zero-line crossovers across timeframes produce frequent divergence signals, but without structural confirmation (market structure shifts, order blocks, liquidity), these are false signals. Momentum divergence often precedes continuation, not reversal.

## Original Hypothesis
When the MACD histogram shifts direction — either rising from negative territory (bullish) or falling from positive territory (bearish) — momentum is changing. Zero-line crossovers confirm the shift. Trading in the direction of the histogram shift with ATR stops should capture momentum reversals early.

## Why It Failed
Multi-TF divergence without structural confirmation. False signals. MACD histogram shifts are extremely common and most don't lead to meaningful moves. The "shift" is just noise until confirmed by price structure. Without a structural framework to filter which shifts matter, the strategy takes every minor momentum wiggle as a signal.

## Artifact
- `mm015_mhst.py` — Original strategy implementation
