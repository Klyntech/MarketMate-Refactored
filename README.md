# MarketMate-Refactored

**Institutional-grade algorithmic trading research platform built on Smart Money Concepts.**

Full-stack platform: Python signal engine, Next.js frontend, 6 MATE AI models, Ollama integration, SDKs, monitoring, and a structured strategy research pipeline.

---

## Architecture

```
MarketMate-Refactored/
├── marketmate/              ← Python trading signal engine (181 files)
│   ├── agent/               ← Agent pipeline
│   ├── analytics/           ← Backtest, ML scoring, tracking
│   ├── api/                 ← REST API routes
│   ├── backup/              ← Dual-write + GDrive backup
│   ├── core/                ← Config, events, LLM, logger, scheduler
│   ├── data/                ← Market data providers (Binance, yfinance, etc.)
│   ├── db/                  ← MongoDB persistence
│   ├── delivery/            ← Telegram bot, charts
│   ├── execution/           ← Bridge, executor, MetaAPI, risk
│   ├── intelligence/        ← Atlas, Nova, Ops, Prism, Vanta, Vinni
│   ├── mate/                ← MATE chat agent (7-brain architecture)
│   ├── mate_ops/            ← Ops agent, anomaly detection, circuit breaker
│   ├── memory/              ← Vector store
│   ├── monitor/             ← Browser monitoring
│   ├── platform/            ← Academy, newsletter, social media
│   ├── state/               ← State engine + models
│   ├── strategy/            ← SMC 8-Gate pipeline (gates, bias, zones, scoring)
│   ├── tasks/               ← Celery task queue
│   └── virtual_account/     ← Virtual trading engine
│
├── Production/              ← Deployed or paper-trading strategies
│   ├── smc_8gate/           ← 8-Gate SMC Pipeline (PF 2.65, WR 63.2%)
│   ├── mm002_monday_gap_fade/
│   ├── mm009_liquidity_sweep/
│   └── mm012_gap_fill_weekend/
│
├── Research/                ← Under validation, not yet production
│   ├── liquidity/           ← OB Retest, FVG Fill, MSS Entry, Session Raid
│   ├── session/             ← London Breakout, NY Reversal
│   ├── volatility/          ← ATR Compression Breakout, RSI Divergence
│   └── gap/                 ← Monday Gap Fade, Gap Fill Weekend (cross-listed)
│
├── Risk Engine/             ← Portfolio governor (NOT alpha generators)
│   └── risk_manager.py      ← DCB + PWP + TMG + CLP + CCE + ECB
│
├── Graveyard/               ← Dead strategies with documented reasons
│   ├── mm002_vce/           ← Volatility Compression (indicator-only)
│   ├── mm003_mrce/          ← Mean Reversion (fades trends)
│   ├── ... (14 total)
│   └── mm018_ichk/          ← Ichimoku (curve-fitted)
│
├── Core/                    ← Shared infrastructure
│   ├── base/                ← Strategy base class, config, events, logger
│   ├── engine/              ← Backtest engine, strategy registry
│   ├── data/                ← Market data providers
│   ├── execution/           ← Position sizing, risk calculation
│   ├── delivery/            ← Telegram signal delivery
│   └── db/                  ← MongoDB persistence
│
├── app/                     ← Next.js app router (40 files)
│   ├── academy/             ← Academy page
│   ├── api/                 ← API routes (auth, keys, mate, signals, v1)
│   ├── dashboard/           ← Dashboard + API keys
│   ├── desk/                ← Desk page
│   ├── developers/          ← Developer docs, collections, resources
│   ├── mate/                ← MATE chat interface
│   └── ...                  ← Login, signup, terms, privacy
│
├── components/              ← 92 UI components
│   ├── academy/             ← Academy CTA, hero, courses, paths
│   ├── auth/                ← Auth provider
│   ├── desk/                ← Desk hero, live signals, architecture
│   ├── developers/          ← Code examples, docs, SDKs
│   ├── mate/                ← Chat header, input, message, sidebar
│   ├── ui/                  ← 48 shadcn/ui primitives
│   └── ...                  ← Hero, features, pricing, footer
│
├── ollama/                  ← Local AI models
│   ├── modelfiles/          ← Atlas, MateOps, Nova, Ops, Prism, Vanta, Vinni
│   ├── config/              ← LiteLLM config
│   └── scripts/             ← Build models script
│
├── docs/                    ← Documentation
│   ├── mma_ai/              ← AI review pipeline (Gemma, Llama, Mixtral)
│   ├── mma_curriculum/      ← 4-course SMC curriculum
│   ├── mma_doctrine/        ← Doctrine, terminology, tone rules
│   └── mma_ops/             ← Approval, chart gen, publishing pipelines
│
├── sdks/                    ← Client SDKs
│   ├── python/              ← MarketMate Python SDK v2.1.0
│   └── typescript/          ← MarketMate TypeScript SDK
│
├── monitoring/              ← Grafana + Prometheus setup
├── Validation/              ← Adversarial testing & deep validation
├── Regime/                  ← Market regime detection engine
├── Paper Trade/             ← 30/60/90 day forward testing framework
├── Backtest/                ← Historical results
├── Artifacts/               ← PDF reports, charts, simulation data
├── nginx/                   ← Ollama production config
├── scripts/                 ← Tunnel + Ollama startup
└── mate-telegram-bot/       ← Standalone MATE Telegram bot (Node.js)
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
| Thin Market Guard | TMG | Suspends if spread > 2x median, ATR < 30% avg, blocked hours |
| Consecutive Loss Protocol | CLP | 2-loss strategy cooldown, 3-loss size reduction, 5-loss halt |
| Correlation Cap | CCE | Blocks if correlation > 0.7, max 2 open positions |
| Equity Curve Brake | ECB | Half size below SMA, halt if 20% below SMA |

## MATE Intelligence System

6 AI models running via Ollama, each with a specialized role:

| Model | Role |
|-------|------|
| **Nova** | Market analysis brain — pattern recognition, bias detection |
| **Ops** | Operations controller — system health, anomaly detection |
| **Vanta** | Trading agent — execution decisions, risk assessment |
| **Vinni** | Monitor — performance tracking, equity curve analysis |
| **Atlas** | Strategy engine — backtest orchestration, optimization |
| **Prism** | Validator — signal quality verification, rejection filtering |

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
git clone https://github.com/Klyntech/MarketMate-Refactored.git
cd MarketMate-Refactored
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys and Telegram bot token
```

## Running the Signal Engine

```bash
python -m marketmate.main
```

## Running the Frontend

```bash
npm install
npm run dev
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
