# MM-016: Stochastic Breakout (STOB)

**Status:** ❌ KILLED  
**Date Killed:** 2025-06-07  
**Reason:** Oscillator breakout hybrid. Conflicting signals.

## Kill Reason
Combining Stochastic oscillator extreme readings with breakout logic creates a strategy with internally conflicting signals. Stochastic says "exhaustion/reversal" while the breakout component says "continuation/momentum" — these are opposite market dynamics that cannot be reconciled.

## Original Hypothesis
When the Stochastic oscillator reaches extreme levels (%K > 80 overbought or < 20 oversold) and then crosses back, it signals exhaustion. Entering on the %K/%D cross from extreme zones should capture reversal moves as the exhausted side gives way.

## Why It Failed
Oscillator breakout hybrid. Conflicting signals. The Stochastic oscillator in extreme territory is supposed to signal reversal, but in trending markets, Stochastic can stay extreme for extended periods. The cross confirmation reduces signals but doesn't solve the core problem: oscillators and breakouts require opposite market conditions. In ranges, breakouts fail; in trends, oscillators give premature reversal signals.

## Artifact
- `mm016_stob.py` — Original strategy implementation
