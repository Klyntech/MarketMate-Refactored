# SMC 8-Gate Pipeline

**Status**: PAPER TRADE CANDIDATE  
**Profit Factor**: 3.65 (V4: 2.65)  
**Win Rate**: 67% (V4: 63.2%)  
**Max Drawdown**: 20.3%  
**Signal Frequency**: ~2.80 signals/week  
**Instruments**: All (18 instruments validated)

## The 8 Gates

| Gate | Name | Function | I/O Cost |
|------|------|----------|----------|
| G1 | Session Filter | London/NY session check | Zero |
| G2 | Daily Limits | Max trades, drawdown protection | In-memory |
| G3 | News Filter | High-impact event detection | Cached HTTP |
| G4 | HTF Bias | Daily + H4 EMA200 alignment | OHLCV fetch |
| G5 | Liquidity Sweep | Swing level sweep + close inside | Uses H4 data |
| G6 | Entry Zone | Order Block or Fair Value Gap | Uses H4 data |
| G7 | LTF Confirmation | BOS/CHoCH on M15/M5 | M15/M5 fetch |
| G8 | RR Validation | Minimum 1.5R reward-to-risk | Pure math |

## Files

- `strategy/engine.py` — SignalEngine (G1→G8 pipeline)
- `strategy/bias.py` — G4: HTF bias detection
- `strategy/liquidity.py` — G5: Liquidity sweep detection
- `strategy/zones.py` — G6: Entry zone identification (OB/FVG)
- `strategy/confirmations.py` — G7: LTF BOS/CHoCH confirmation
- `strategy/gates.py` — G3: News filter
- `strategy/scoring.py` — Multi-factor confidence scoring
- `strategy/dedup.py` — ATR-relative deduplication
- `strategy/features.py` — Enriched feature dataclasses
- `strategy/models.py` — Domain models (Signal, GateResult, etc.)

## Critical Data Limitation

H4 data limited to ~2-3 years. LTF confirmation only available for ~60 days.
Requires 90-day paper trading before any capital deployment.

## Validation Results

- Portfolio PF: 3.08 across 18 instruments
- Portfolio Sharpe: 8.79
- Monte Carlo: 0.00% ruin probability
- Cross-market: Profitable in 4/5 asset classes
- Walk-forward: Mixed (some windows profitable, some not)
- Classification: Level 3 — PAPER TRADE
