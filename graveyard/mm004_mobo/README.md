# MM-004: Momentum Breakout (MOBO)

**Status:** ❌ KILLED  
**Date Killed:** 2025-06-07  
**Reason:** Chases breakouts without liquidity context. Whipsawed in ranges.

## Kill Reason
Donchian channel breakouts with volume and RSI confirmation sound robust, but the strategy chases moves after they've already started — entering late on momentum that often reverses. Without understanding liquidity dynamics, it gets whipsawed repeatedly in ranging markets.

## Original Hypothesis
When price breaks above/below a Donchian channel with volume confirmation (volume > 1.2× MA) and momentum alignment (RSI > 55 for buys, < 45 for sells), the breakout has conviction and should continue. ATR-based stops and 3:1 reward targets should capture trend moves.

## Why It Failed
Chases breakouts without liquidity context. Whipsawed in ranges. The Donchian channel + volume + RSI combination is a well-known momentum system that has been largely arbed away. Breakouts without liquidity context are indistinguishable from traps.

## Artifact
- `mm004_mobo.py` — Original strategy implementation
