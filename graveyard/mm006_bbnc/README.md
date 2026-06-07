# MM-006: Bollinger Band Narrow Contract (BBNC)

**Status:** ❌ KILLED  
**Date Killed:** 2025-06-07  
**Reason:** Compression detection without directional bias. Random exits.

## Kill Reason
Detecting price touching Bollinger Bands and expecting mean reversion is a textbook setup that fails in practice. The strategy detects compression (band narrowness) and touches (price at outer band) but has no directional bias — exits are essentially random.

## Original Hypothesis
When price touches an outer Bollinger Band and reverses with RSI confirmation (oversold for buys, overbought for sells), the market is reverting to the mean. Taking profit at the middle band with tight ATR stops should capture high-probability reversion moves.

## Why It Failed
Compression detection without directional bias. Random exits. Bollinger Band touches in strong trends are not reversals — they represent momentum. The RSI oversold/overbought filter adds no structural context, and TP at the middle band cuts winners short while the strategy holds losers through band expansion.

## Artifact
- `mm006_bbnc.py` — Original strategy implementation
