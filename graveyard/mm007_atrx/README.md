# MM-007: ATR Expansion (ATRX)

**Status:** ❌ KILLED  
**Date Killed:** 2025-06-07  
**Reason:** Volatility expansion without structural framework. No edge over random.

## Kill Reason
ATR expansion signals that volatility has increased, but says nothing about direction or sustainability. The strategy enters on volatility expansion + price breakout + EMA filter, but this combination provides no edge over random entry — expansion is necessary but not sufficient for profitable breakout trading.

## Original Hypothesis
When short-term ATR expands rapidly above the long-term ATR baseline (ratio > 1.5×), a volatility breakout is occurring. Combined with a price breakout above/below a recent range and an EMA trend filter, this should capture the start of strong directional moves.

## Why It Failed
Volatility expansion without structural framework. No edge over random. ATR expansion is a lagging confirmation that something already happened — by the time the signal fires, the move is often exhausted. Without understanding why the expansion occurred (liquidity sweep, institutional order flow), the signal is noise.

## Artifact
- `mm007_atrx.py` — Original strategy implementation
