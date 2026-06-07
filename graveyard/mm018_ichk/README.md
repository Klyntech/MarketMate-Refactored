# MM-018: Ichimoku Cloud (ICHK)

**Status:** ❌ KILLED  
**Date Killed:** 2025-06-07  
**Reason:** Too many parameters, curve-fitted.

## Kill Reason
The full Ichimoku system (Tenkan/Kijun cross, cloud breakout, chikou confirmation) has too many interacting parameters (9, 26, 52, displacement) that were optimized for 1930s Japanese rice markets. The parameter sensitivity means the system is curve-fitted to historical data and fails in modern forex/crypto markets.

## Original Hypothesis
The Ichimoku Cloud system provides a complete trading framework in a single indicator: trend direction (cloud position), momentum (TK cross), support/resistance (cloud boundaries), and entry timing (TK cross + cloud breakout). Combining all components should produce robust signals with built-in confluence.

## Why It Failed
Too many parameters, curve-fitted. The Ichimoku system's standard parameters (9/26/52) are arbitrary and specific to the market/timeframe they were designed for. Optimizing these parameters for forex/crypto is curve-fitting — the system looks good on past data but fails forward. The multiple confirmation layers (TK cross + cloud + breakout) create so many condition combinations that any apparent edge is a data-mining artifact.

## Artifact
- `mm018_ichk.py` — Original strategy implementation
