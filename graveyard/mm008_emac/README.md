# MM-008: EMA Crossover (EMAC)

**Status:** ❌ KILLED  
**Date Killed:** 2025-06-07  
**Reason:** Classic crossover system. Lagging, no SMC confluence, whipsawed.

## Kill Reason
The 9/21 EMA crossover with a 100 EMA trend filter is perhaps the most well-known trading system, and also one of the worst-performing in live markets. It's lagging by definition, produces frequent false signals in ranging markets, and has zero Smart Money Concepts confluence.

## Original Hypothesis
When a fast EMA (9) crosses above a slow EMA (21) — a golden cross — while price is above the trend EMA (100), an uptrend is confirmed. The inverse for death crosses. ATR-based stops and 3:1 targets should capture trend moves while the trend filter prevents counter-trend entries.

## Why It Failed
Classic crossover system. Lagging, no SMC confluence, whipsawed. By the time EMAs cross, the move is often halfway done or reversing. In ranging markets, the 9/21 cross flips repeatedly, generating a stream of small losses. No structural context means no way to distinguish a real trend from noise.

## Artifact
- `mm008_emac.py` — Original strategy implementation
