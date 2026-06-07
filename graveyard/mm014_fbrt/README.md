# MM-014: Fibonacci Retracement (FBRT)

**Status:** ❌ KILLED  
**Date Killed:** 2025-06-07  
**Reason:** Fib levels without order flow context. Subjective and noisy.

## Kill Reason
Fibonacci retracement levels (0.618 golden ratio zone) are widely watched but have no basis in order flow dynamics. The "zone width" parameter (0.05%) is essentially subjective tuning, and without understanding the institutional order flow behind pullbacks, Fib levels produce noisy, unprofitable signals.

## Original Hypothesis
After a significant swing move, price tends to retrace to Fibonacci levels before continuing. The 0.618 retracement (golden ratio) is the most watched level and should act as a high-probability entry zone. Entering on a bullish candle within the Fib zone with a stop below the swing low and TP at the 127.2% extension should capture trend continuations.

## Why It Failed
Fib levels without order flow context. Subjective and noisy. Fibonacci levels are a self-fulfilling prophecy that stopped working once too many traders watched them. The "zone width" is curve-fitting — making the zone wider catches more trades but reduces precision; making it narrower misses the real entries. Without order flow context, pullbacks to Fib levels are indistinguishable from trend reversals.

## Artifact
- `mm014_fbrt.py` — Original strategy implementation
