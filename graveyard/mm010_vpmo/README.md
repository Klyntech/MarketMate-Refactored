# MM-010: Volume Price Momentum (VPMO)

**Status:** ❌ KILLED  
**Date Killed:** 2025-06-07  
**Reason:** Volume signals without institutional context. Noisy.

## Kill Reason
Volume spikes are noisy signals without institutional context. A volume spike above 2× the moving average could be retail FOMO, stop-loss cascades, or institutional accumulation — the strategy cannot distinguish between them, so it trades noise.

## Original Hypothesis
High-volume nodes represent institutional interest. When volume spikes (> 2× the 20-period MA) and price simultaneously breaks above/below a recent price range, smart money is entering the market. Trading in the direction of the volume-confirmed breakout should follow institutional flow.

## Why It Failed
Volume signals without institutional context. Noisy. Volume spikes without understanding WHO is trading (institutional vs. retail) and WHY (accumulation vs. distribution vs. stop cascade) are not actionable. The price breakout confirmation adds nothing — it's just a Donchian breakout with extra volume noise.

## Artifact
- `mm010_vpmo.py` — Original strategy implementation
