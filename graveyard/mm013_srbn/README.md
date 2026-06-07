# MM-013: Support/Resistance Bounce (SRBN)

**Status:** ❌ KILLED  
**Date Killed:** 2025-06-07  
**Reason:** Static levels without liquidity concept. Levels get swept.

## Kill Reason
Support and resistance levels identified from swing points are static price levels that ignore the dynamic nature of liquidity. These levels consistently get swept by institutional order flow before reversing — the strategy enters at the exact level where stops are being hunted.

## Original Hypothesis
Key support and resistance levels, identified by multiple swing-point touches, act as barriers where price reverses. Trading bounces off these levels with ATR stops should capture high-probability reversal entries. The minimum touch count (2+) validates the level's significance.

## Why It Failed
Static levels without liquidity concept. Levels get swept. The market doesn't respect static price levels — it respects liquidity pools. What looks like "support" is often a resting zone for stop-loss orders that institutions target. Each "bounce" entry is actually a stop-hunt entry, and the strategy gets stopped out before the real move.

## Artifact
- `mm013_srbn.py` — Original strategy implementation
