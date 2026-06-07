# MarketMate

**Institutional-grade algorithmic trading research platform built on Smart Money Concepts.**

## Architecture

```
MarketMate
├── Production/           ← Deployed or paper-trading strategies
│   ├── smc_8gate/       ← 8-Gate SMC Pipeline (PF 2.65, WR 63.2%)
│   ├── mm002_mgf/       ← Monday Gap Fade
│   ├── mm009_lsqr/      ← Liquidity Sweep Quick Reversal
│   └── mm012_gpfl/      ← Gap Fill Weekend
│
├── Research/             ← Under validation, not yet production
│   ├── liquidity/       ← OB Retest, FVG Fill, MSS Entry, Session Raid
│   ├── session/         ← London Breakout, NY Reversal
│   ├── volatility/      ← ATR Compression Breakout, RSI Divergence
│   └── gap/             ← Monday Gap Fade, Gap Fill Weekend (cross-listed)
│
├── Risk Engine/          ← Portfolio governor (NOT alpha generators)
│   └── risk_manager.py  ← DCB + PWP + TMG + CLP + CCE + ECB
│
├── Graveyard/            ← Dead strategies with documented reasons
│   └── graveyard.json   ← MM-002 through MM-025 rejection records
│
├── Core/                 ← Shared infrastructure
│   ├── base/            ← Strategy base class, config, events, logger
│   ├── engine/          ← Backtest engine, strategy registry
│   ├── data/            ← Market data providers (Binance, yfinance, etc.)
│   ├── execution/       ← Position sizing, risk calculation
│   ├── delivery/        ← Telegram signal delivery
│   └── db/              ← MongoDB persistence (optional)
│
├── Validation/           ← Adversarial testing & deep validation
├── Regime/               ← Market regime detection engine
├── Paper Trade/          ← 30/60/90 day forward testing framework
└── Backtest/             ← Historical results and cached data
```

## Strategy Status

| Strategy | ID | Status | PF | WR | Instruments | Notes |
|----------|----|--------|----|----|-------------|-------|
| SMC 8-Gate | SMC_8G | **PAPER TRADE** | 3.65 | 67% | All | Core system, PF 2.65 on V4 |
| Monday Gap Fade | MM-002 | **FAILED VALIDATION** | 0.65 | 56% | All | 12yr daily = slow bleed; regime-conditional only |
| Liquidity Sweep | MM-009 | **INSTRUMENT-LOCKED** | 0.84 | 46% | NAS100, ETHUSD, XAGUSD, US30 | Better as Gate 5 filter |
| Gap Fill Weekend | MM-012 | **MARGINAL** | 1.23 | 55% | NAS100, US30, GBPUSD | Same alpha as MM-002 |
| RSI Divergence | MM-005 | **INSUFFICIENT SAMPLE** | 2.0 | 67% | EURUSD, XAGUSD | Only 6 trades — unvalidated |
| Order Block Retest | MM-019 | **REJECT** | 0.54 | 35% | All | Pipeline filter, not standalone |
| FVG Fill | MM-020 | **REJECT** | 0.53 | 35% | All | Pipeline filter, not standalone |
| MSS Entry | MM-021 | **REJECT** | 0.57 | 27% | All | Pipeline filter, not standalone |
| Session Raid | MM-022 | **REJECT** | 0.00 | 0% | All | Generated zero signals |
| London Breakout | MM-023 | **REJECT** | 0.70 | 41% | All | Arbed away |
| NY Reversal | MM-024 | **REJECT** | 0.11 | 10% | All | Catastrophic |
| ATR Compression | MM-025 | **REJECT** | 0.45 | 31% | All | Compression ≠ expansion |

## The 8-Gate SMC Pipeline

```
G1  Session Filter          (pure time check — zero I/O)
G2  Daily Limit + Drawdown  (in-memory or DB read)
G3  News Filter             (cached HTTP — 1 request/hour)
G4  HTF Bias                (H4 + Daily OHLCV)
G5  Liquidity Sweep         (uses H4 data already fetched)
G6  Entry Zone              (Order Block or FVG)
G7  LTF Confirmation        (M15 + M5 OHLCV)
G8  RR Validation           (pure math, min 1.5R)
```

**Gate Philosophy**: Fail-fast, cheapest first. If G1 fails, no data is fetched.

## Risk Engine

The risk engine is a **portfolio governor**, not an alpha generator. It runs BEFORE any signal is executed:

| Module | ID | Function |
|--------|----|----------|
| Drawdown Circuit Breaker | DCB | Halts at -3% daily, -7% weekly, -15% monthly |
| Pre-Weekend Protocol | PWP | Blocks Thursday 20:00+, Friday 18:00+, Sunday pre-21:00 |
| Thin Market Guard | TMG | Suspends if spread > 2× median, ATR < 30% avg, blocked hours |
| Consecutive Loss Protocol | CLP | 2-loss strategy cooldown, 3-loss size reduction, 5-loss halt |
| Correlation Cap | CCE | Blocks if correlation > 0.7, max 2 open positions |
| Equity Curve Brake | ECB | Half size below SMA, halt if 20% below SMA |

## Regime Detection

Classifies markets into regimes that determine which strategies should be active:

- **TRENDING** — Strong directional move (gap fades die here)
- **RANGING** — Mean-reverting (gap fades survive here)
- **HIGH_VOL** — Elevated volatility (wider stops needed)
- **LOW_VOL** — Compressed volatility (tighter stops possible)
- **RISK_ON** — Equities/crypto rising, safe havens falling
- **RISK_OFF** — Flight to safety

**Key insight**: MM-002 works ONLY in RANGING/LOW_VOL (PF 3.29 on EURUSD ranging). A mediocre strategy becomes excellent when deployed only in its favorable regime.

## Paper Trading Framework

30/60/90 day forward testing with strict rules:
1. **NO parameter changes** during the test period
2. Every modification **resets the clock**
3. Track every signal, every block, every fill
4. Deployment checklist: 30-day positive, 60-day positive, 90-day positive, PF > 1.1, no parameter changes

## Lessons Learned

1. **Indicator-based strategies consistently fail** — RSI, MACD, Bollinger, Stochastic, Ichimoku all failed across all instruments
2. **SMC is the only validated edge** — and only when all 8 gates are combined. Individual SMC components fail as standalones
3. **Session strategies are arbed away** — London Breakout, NY Reversal are well-known and no longer work
4. **Volatility compression ≠ expansion** — Compression often leads to more compression
5. **Gap fades are regime-dependent** — They work in ranging/low-vol and fail in trending/high-vol
6. **PF > 2.0 with < 30 trades is unvalidated noise** — Always check sample size
7. **H4 vs daily data can turn a "profitable" strategy into a loser** — Always validate on the longest available data window
8. **Strategies trading the same phenomenon share failure modes** — MM-002 and MM-012 have low correlation (0.06) but both die in trending markets

## Installation

```bash
git clone https://github.com/<username>/MarketMate.git
cd MarketMate
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Telegram bot token and chat ID
```

## Running the Signal Engine

```bash
python -m core.main
```

## Running Backtests

```bash
# Fast adversarial validation
python -m validation.fast_validation

# Deep validation with 12-year data
python -m validation.deep_validate

# Regime detection analysis
python -m regime.regime_detector
```

## License

Proprietary — All rights reserved.
