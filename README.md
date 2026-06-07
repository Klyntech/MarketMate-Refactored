# MarketMate — Gate-Based SMC Trading Signal Bot

A production-ready, modular trading signal bot using Smart Money Concepts (SMC).
**Signal quality over quantity.** Every trade passes 7 strict sequential gates.

---

## Architecture

```
marketmate/
├── main.py                    # Entry point, scan loop
├── config/
│   └── settings.py            # All config (env-driven)
├── data/
│   ├── market_data.py         # Multi-source OHLCV (Binance → Twelve Data → AV)
│   └── validators.py          # Data integrity checks
├── strategy/
│   ├── gates.py               # Gate orchestrator (runs all gates)
│   ├── htf_bias.py            # Gate 3: H4+Daily EMA200 + structure
│   ├── liquidity.py           # Gate 4: Swing sweep detection
│   ├── entry_zones.py         # Gate 5: Order Block / FVG
│   └── ltf_confirm.py         # Gate 6: M5/M15 BOS or CHoCH
├── risk/
│   └── manager.py             # ATR-SL, position sizing, RR validation
├── signals/
│   ├── builder.py             # Signal object construction
│   └── deduplicator.py        # Prevents duplicate signals
├── delivery/
│   └── telegram_bot.py        # Telegram formatted messages
├── lifecycle/
│   └── trade_manager.py       # TP/SL monitoring, BE logic
├── analytics/
│   └── tracker.py             # Win rate, RR, P&L tracking
├── db/
│   └── database.py            # SQLite async (aiosqlite)
├── utils/
│   ├── logger.py              # Structured logging (structlog)
│   └── queue_manager.py       # Async event queue
├── tests/
│   └── test_strategy.py       # Unit tests (no API calls)
└── deploy/
    ├── Dockerfile
    ├── docker-compose.yml
    ├── railway.toml            # Railway.app free tier
    ├── render.yaml             # Render.com free tier
    └── marketmate.service      # Systemd (VPS)
```

---

## Gate Flow

```
PAIR SCAN
   │
   ▼
[G1] Session?          → London (07:00–12:00 UTC) or NY (12:00–17:00 UTC)
   │
   ▼
[G2] Daily limit?      → Max 5 trades/day | Max 3 consecutive losses
   │
   ▼
[G3] HTF Bias?         → Price above/below EMA200 on BOTH H4 + Daily
                         + confirmed market structure (HH+HL or LH+LL)
   │
   ▼
[G4] Liquidity Sweep?  → Wick beyond swing high/low, ideally close back inside
   │
   ▼
[G5] Entry Zone?       → Order Block (last opposing candle before displacement)
                         OR Fair Value Gap (candle imbalance, min size enforced)
   │
   ▼
[G6] LTF Confirm?      → BOS or CHoCH on M15 or M5
   │
   ▼
[G7] RR Valid?         → Minimum 1:1.5 (configurable)
   │
   ▼
 SIGNAL ISSUED
```

---

## Example Signal Output

```
📈 BUY — BTCUSDT
🔥 Confidence: HIGH

📊 Entry Zone: `49,900.00` – `50,100.00`
🛑 Stop Loss:  `49,350.00`
• TP1:  `50,650.00` (1:1)
• TP2:  `51,200.00` (1:2)
• TP3:  `52,400.00` (liquidity)

⚖️ Risk/Reward: `1:2.0`
📐 Size:  `0.02` units
🕐 TF:   H4 | M15 CHoCH
🎯 Zone:  Order Block

🆔 `A3F8B1` | 2024-01-15 09:32 UTC
```

---

## Setup Guide

### 1. Clone & Install

```bash
git clone https://github.com/yourname/marketmate.git
cd marketmate
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
nano .env                         # Fill in all values
```

**Minimum required values:**
```
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
BINANCE_API_KEY=...               # or leave blank for public endpoints
PAIRS=BTCUSDT,ETHUSDT
```

### 3. Get a Telegram Bot

1. Open Telegram → search `@BotFather`
2. Send `/newbot` → follow prompts
3. Copy the token → `TELEGRAM_BOT_TOKEN`
4. Send a message to your bot, then visit:
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
5. Copy `chat.id` → `TELEGRAM_CHAT_ID`

### 4. Get Free API Keys

| API | Free Tier | Link |
|-----|-----------|------|
| Binance | Public OHLCV (no key needed for basic) | binance.com |
| Twelve Data | 800 req/day | twelvedata.com |
| Alpha Vantage | 25 req/day | alphavantage.co |

### 5. Run Locally

```bash
python main.py
```

### 6. Run Tests

```bash
python -m pytest tests/ -v
```

---

## Deployment Options

### Option A: Docker (recommended)

```bash
# Build image
docker build -f deploy/Dockerfile -t marketmate .

# Run with auto-restart
docker compose -f deploy/docker-compose.yml up -d

# View logs
docker compose -f deploy/docker-compose.yml logs -f
```

### Option B: Railway.app (free tier)

1. Push repo to GitHub
2. Connect repo at [railway.app](https://railway.app)
3. Add environment variables in Railway dashboard
4. Railway reads `deploy/railway.toml` automatically
5. Deploy → bot runs 24/7 free

### Option C: Render.com (free tier)

1. Push repo to GitHub
2. Create a new **Background Worker** at [render.com](https://render.com)
3. Point to `render.yaml`
4. Set secret env vars in Render dashboard
5. Deploy

### Option D: Linux VPS (systemd)

```bash
# Copy files to VPS
scp -r . user@your-vps:/opt/marketmate

# On VPS:
cd /opt/marketmate
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install service
sudo cp deploy/marketmate.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable marketmate
sudo systemctl start marketmate

# Check status
sudo systemctl status marketmate
sudo journalctl -u marketmate -f
```

---

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `PAIRS` | `BTCUSDT,ETHUSDT` | Pairs to scan (comma-separated) |
| `MAX_TRADES_PER_DAY` | `5` | Daily trade ceiling |
| `MIN_RR` | `1.5` | Minimum risk-reward ratio |
| `RISK_PER_TRADE_PCT` | `1.0` | % of account risked per trade |
| `ACCOUNT_SIZE` | `10000` | Account size in USD |
| `MAX_CONSECUTIVE_LOSSES` | `3` | Drawdown protection — stops bot after N losses |
| `LONDON_OPEN` | `07:00` | UTC session times |
| `NY_CLOSE` | `17:00` | UTC session times |
| `DEBUG` | `false` | Enable verbose logging |

---

## Risk Disclaimer

This software is for **educational purposes only**.
It does not constitute financial advice.
Trading involves substantial risk of loss.
Always test thoroughly on paper before live use.
Past performance of any strategy does not guarantee future results.
