# MarketMate Python SDK

Official Python client for the [MarketMate API](https://marketmate-website.onrender.com/developers) — real-time market intelligence infrastructure.

## Install

```bash
pip install marketmate
```

## Quick Start

```python
from marketmate import MarketMate

client = MarketMate(api_key="mk_live_your_key_here")

# Get real-time market state
state = client.get_market_state("BTC-USD")
print(f"Regime: {state.regime}, Conviction: {state.conviction}")
print(f"Price: ${state.price.current:,.2f}")

# Get trading signals
signals = client.get_signals()
for signal in signals.signals:
    print(f"{signal.symbol} {signal.direction} RR:{signal.risk_reward}")

# Get liquidity analysis
liq = client.get_liquidity("BTC-USD")
print(f"Liquidity Score: {liq.score}")
print(f"Pressure: {liq.balance.pressure}")

# Get historical data
history = client.get_historical("BTC-USD", hours=24, interval="1h")
for point in history.data:
    print(f"{point.timestamp}: {point.regime} @ {point.close}")
```

## API Key

Get your free API key at [marketmate-website.onrender.com/dashboard/api-keys](https://marketmate-website.onrender.com/dashboard/api-keys).

## Features

- **Market State** — Real-time regime detection, conviction scoring, key levels
- **Trading Signals** — AI-powered and technically-derived trading signals
- **Liquidity Analysis** — Orderbook depth, pool detection, sweep levels
- **Historical Data** — OHLCV with regime/convention/volatility per candle
- **Type Safety** — Full Pydantic models for all responses
- **Error Handling** — Specific exception types for auth, rate limit, and server errors
- **Context Manager** — Use `with MarketMate(api_key=...) as client:` for auto-cleanup

## Error Handling

```python
from marketmate import MarketMate, AuthenticationError, RateLimitError, MarketMateError

try:
    client = MarketMate(api_key="invalid_key")
    state = client.get_market_state("BTC-USD")
except AuthenticationError as e:
    print(f"Auth failed: {e.message}")
except RateLimitError as e:
    print(f"Slow down: {e.message}")
except MarketMateError as e:
    print(f"API error: {e.message} (status: {e.status_code})")
```

## License

MIT
