# @marketmate/sdk

Official TypeScript/JavaScript SDK for the [MarketMate API](https://marketmate-website.onrender.com/developers) — real-time market intelligence infrastructure.

## Install

```bash
npm install @marketmate/sdk
```

## Quick Start

```typescript
import { MarketMate } from '@marketmate/sdk';

const client = new MarketMate({ apiKey: 'mk_live_your_key_here' });

// Get real-time market state
const state = await client.getMarketState('BTC-USD');
console.log(`Regime: ${state.regime}, Conviction: ${state.conviction}`);
console.log(`Price: $${state.price?.current.toLocaleString()}`);

// Get trading signals
const signals = await client.getSignals();
for (const signal of signals.signals) {
  console.log(`${signal.symbol} ${signal.direction} RR:${signal.risk_reward}`);
}

// Get liquidity analysis
const liquidity = await client.getLiquidity('BTC-USD');
console.log(`Liquidity Score: ${liquidity.score}`);
console.log(`Pressure: ${liquidity.balance?.pressure}`);

// Get historical data
const history = await client.getHistorical('BTC-USD', { hours: 24, interval: '1h' });
for (const point of history.data) {
  console.log(`${point.timestamp}: ${point.regime} @ ${point.close}`);
}
```

## API Key

Get your free API key at [marketmate-website.onrender.com/dashboard/api-keys](https://marketmate-website.onrender.com/dashboard/api-keys).

## Features

- **Market State** — Real-time regime detection, conviction scoring, key levels
- **Trading Signals** — AI-powered and technically-derived trading signals
- **Liquidity Analysis** — Orderbook depth, pool detection, sweep levels
- **Historical Data** — OHLCV with regime/convention/volatility per candle
- **Full TypeScript** — Complete type definitions for all responses
- **Error Handling** — Specific error classes for auth, rate limit, and server errors
- **Zero Dependencies** — Uses native fetch, no external dependencies

## Error Handling

```typescript
import { MarketMate, AuthenticationError, RateLimitError, MarketMateError } from '@marketmate/sdk';

try {
  const client = new MarketMate({ apiKey: 'invalid_key' });
  const state = await client.getMarketState('BTC-USD');
} catch (error) {
  if (error instanceof AuthenticationError) {
    console.error(`Auth failed: ${error.message}`);
  } else if (error instanceof RateLimitError) {
    console.error(`Slow down: ${error.message}`);
  } else if (error instanceof MarketMateError) {
    console.error(`API error: ${error.message} (status: ${error.statusCode})`);
  }
}
```

## License

MIT
