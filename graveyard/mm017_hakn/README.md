# MM-017: Hull Average Knot (HAKN)

**Status:** ❌ KILLED  
**Date Killed:** 2025-06-07  
**Reason:** Advanced average crossover. Still just indicator stacking.

## Kill Reason
Using Heikin Ashi candles for smooth trend identification with consecutive same-color candle counting is just a more sophisticated version of moving average crossover logic. Despite the advanced smoothing, it's still indicator stacking with no connection to market structure or institutional order flow.

## Original Hypothesis
Heikin Ashi candles smooth out price noise, making trends easier to identify. When 3+ consecutive bullish HA candles with small wicks (wick/body ratio < 0.3) appear, a strong trend is underway. Entering in the trend direction with ATR stops should capture clean trend moves with reduced noise.

## Why It Failed
Advanced average crossover. Still just indicator stacking. Heikin Ashi smoothing is a mathematical transform of price data — it reveals nothing about market structure or order flow. Consecutive HA candles are just a smoothed version of "price went up for 3 bars," which any simple moving average could tell you. The wick ratio filter reduces entries but doesn't add structural edge.

## Artifact
- `mm017_hakn.py` — Original strategy implementation
