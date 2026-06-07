/**
 * MarketMate TypeScript SDK
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Official TypeScript/JavaScript client for the MarketMate API.
 *
 * @example
 * ```typescript
 * import { MarketMate } from '@marketmate/sdk';
 *
 * const client = new MarketMate({ apiKey: 'mk_live_...' });
 *
 * // Get market state
 * const state = await client.getMarketState('BTC-USD');
 * console.log(`Regime: ${state.regime}, Conviction: ${state.conviction}`);
 *
 * // Get signals
 * const signals = await client.getSignals();
 * for (const signal of signals.signals) {
 *   console.log(`${signal.symbol} ${signal.direction} RR:${signal.risk_reward}`);
 * }
 * ```
 */

// ============ TYPES ============

export interface KeyLevels {
  support: number[];
  resistance: number[];
}

export interface Trend {
  direction: 'bullish' | 'bearish' | 'neutral';
  strength: number;
  timeframe: string;
}

export interface PriceData {
  current: number;
  change_24h: number;
  high_24h: number;
  low_24h: number;
  volume_24h: number;
  quote_volume_24h: number;
}

export interface MarketState {
  symbol: string;
  regime: 'trending_bullish' | 'trending_bearish' | 'ranging' | 'volatile';
  conviction: number;
  volatility: 'low' | 'normal' | 'elevated' | 'extreme';
  liquidity: number;
  price?: PriceData;
  key_levels?: KeyLevels;
  trend?: Trend;
  source: string;
  updated_at: string;
}

export interface EntryZone {
  low: number;
  high: number;
  mid: number;
}

export interface Signal {
  signal_id: string;
  symbol: string;
  direction: 'LONG' | 'SHORT';
  entry_zone: EntryZone;
  stop_loss: number;
  take_profit_1: number;
  take_profit_2?: number;
  take_profit_3?: number;
  risk_reward: number;
  conviction: 'HIGH' | 'MEDIUM' | 'LOW';
  zone_type: string;
  confirmation: string;
  status: string;
  source?: string;
  disclaimer?: string;
  created_at: string;
  [key: string]: unknown;
}

export interface SignalsResponse {
  signals: Signal[];
  count: number;
  source?: string;
  note?: string;
  timestamp: string;
}

export interface LiquidityPool {
  level: number;
  type: 'demand' | 'supply';
  volume: string;
  quantity: number;
  strength: number;
}

export interface LiquiditySweep {
  level: number;
  direction: 'bearish' | 'bullish';
  thin_liquidity?: string;
  wall_above?: string;
  wall_below?: string;
}

export interface LiquidityBalance {
  bid_depth: number;
  ask_depth: number;
  ratio: number;
  pressure: 'buying' | 'selling' | 'neutral';
}

export interface OrderbookSummary {
  best_bid: number;
  best_ask: number;
  spread: number;
  spread_pct: number;
}

export interface LiquidityAnalysis {
  symbol: string;
  current_price: number;
  score: number;
  balance?: LiquidityBalance;
  pools: LiquidityPool[];
  sweeps: LiquiditySweep[];
  orderbook_summary?: OrderbookSummary;
  volume_24h: number;
  source: string;
  disclaimer?: string;
  updated_at: string;
}

export interface HistoricalDataPoint {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  regime: string;
  conviction: number;
  volatility: string;
  liquidity_score: number;
}

export interface HistoricalPeriod {
  start?: string;
  end?: string;
  candles: number;
}

export interface HistoricalSummary {
  start_price: number;
  end_price: number;
  change_pct: number;
  high: number;
  low: number;
  total_volume: number;
  regime_distribution: Record<string, number>;
}

export interface HistoricalResponse {
  symbol: string;
  interval: string;
  period?: HistoricalPeriod;
  summary?: HistoricalSummary;
  data: HistoricalDataPoint[];
  source: string;
  updated_at: string;
}

export interface MarketMateOptions {
  apiKey: string;
  baseUrl?: string;
  timeout?: number;
}

// ============ ERROR CLASSES ============

export class MarketMateError extends Error {
  constructor(
    message: string,
    public readonly statusCode?: number,
    public readonly errorType?: string,
    public readonly response?: Record<string, unknown>,
  ) {
    super(message);
    this.name = 'MarketMateError';
  }
}

export class AuthenticationError extends MarketMateError {
  constructor(message: string, response?: Record<string, unknown>) {
    super(message, 401, 'unauthorized', response);
    this.name = 'AuthenticationError';
  }
}

export class RateLimitError extends MarketMateError {
  constructor(message: string, response?: Record<string, unknown>) {
    super(message, 429, 'rate_limited', response);
    this.name = 'RateLimitError';
  }
}

// ============ CLIENT ============

const DEFAULT_BASE_URL = 'https://marketmate-website.onrender.com';
const DEFAULT_TIMEOUT = 30000;
const SDK_VERSION = '2.1.0';

/**
 * MarketMate API client.
 *
 * @example
 * ```typescript
 * const client = new MarketMate({ apiKey: 'mk_live_...' });
 *
 * // Get market state
 * const state = await client.getMarketState('BTC-USD');
 *
 * // Get signals
 * const signals = await client.getSignals({ symbol: 'BTC-USD' });
 *
 * // Get liquidity
 * const liquidity = await client.getLiquidity('BTC-USD');
 *
 * // Get historical data
 * const history = await client.getHistorical('BTC-USD', { hours: 24 });
 * ```
 */
export class MarketMate {
  private readonly apiKey: string;
  private readonly baseUrl: string;
  private readonly timeout: number;

  constructor(options: MarketMateOptions) {
    if (!options.apiKey) {
      throw new Error(
        "API key is required. Get one at https://marketmate-website.onrender.com/dashboard/api-keys",
      );
    }

    this.apiKey = options.apiKey;
    this.baseUrl = (options.baseUrl || DEFAULT_BASE_URL).replace(/\/$/, '');
    this.timeout = options.timeout || DEFAULT_TIMEOUT;
  }

  private async request<T>(path: string, params?: Record<string, string>): Promise<T> {
    const url = new URL(`${this.baseUrl}${path}`);
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
          url.searchParams.set(key, value);
        }
      });
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url.toString(), {
        headers: {
          Authorization: `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json',
          'User-Agent': `marketmate-typescript/${SDK_VERSION}`,
        },
        signal: controller.signal,
      });

      if (response.status === 401) {
        const data = await response.json().catch(() => ({}));
        throw new AuthenticationError(
          data.message || 'Invalid or missing API key.',
          data,
        );
      }

      if (response.status === 429) {
        throw new RateLimitError('Rate limit exceeded. Please slow down your requests.');
      }

      if (response.status >= 500) {
        throw new MarketMateError(
          'MarketMate API is temporarily unavailable.',
          response.status,
          'server_error',
        );
      }

      if (response.status >= 400) {
        const data = await response.json().catch(() => ({}));
        throw new MarketMateError(
          data.message || data.error || `Request failed with status ${response.status}`,
          response.status,
          data.error,
          data,
        );
      }

      return response.json() as Promise<T>;
    } catch (error) {
      if (error instanceof MarketMateError) throw error;
      if (error instanceof DOMException && error.name === 'AbortError') {
        throw new MarketMateError('Request timed out.', undefined, 'timeout');
      }
      throw new MarketMateError(
        error instanceof Error ? error.message : 'Unknown error occurred.',
        undefined,
        'network_error',
      );
    } finally {
      clearTimeout(timeoutId);
    }
  }

  /**
   * Verify your API key is valid.
   */
  async verify(): Promise<{ valid: boolean; environment: string }> {
    return this.request('/api/v1/verify');
  }

  /**
   * Get real-time market state for a trading pair.
   *
   * @param symbol - Trading pair (e.g., "BTC-USD"). Default: "BTC-USD"
   */
  async getMarketState(symbol: string = 'BTC-USD'): Promise<MarketState> {
    return this.request<MarketState>('/api/v1/market-state', { symbol });
  }

  /**
   * Get active trading signals.
   *
   * @param options - Filter options
   * @param options.symbol - Filter by trading pair
   * @param options.conviction - Filter by conviction level ("HIGH", "MEDIUM", "LOW")
   */
  async getSignals(options?: { symbol?: string; conviction?: string }): Promise<SignalsResponse> {
    return this.request<SignalsResponse>('/api/v1/signals', {
      symbol: options?.symbol || '',
      conviction: options?.conviction || '',
    });
  }

  /**
   * Get real-time liquidity analysis from orderbook data.
   *
   * @param symbol - Trading pair. Default: "BTC-USD"
   */
  async getLiquidity(symbol: string = 'BTC-USD'): Promise<LiquidityAnalysis> {
    return this.request<LiquidityAnalysis>('/api/v1/liquidity', { symbol });
  }

  /**
   * Get historical market data with regime analysis.
   *
   * @param symbol - Trading pair. Default: "BTC-USD"
   * @param options - Query options
   * @param options.hours - Number of hours of history (1-720). Default: 24
   * @param options.interval - Candle interval ("1m", "5m", "15m", "30m", "1h", "4h", "1d"). Default: "1h"
   */
  async getHistorical(
    symbol: string = 'BTC-USD',
    options?: { hours?: number; interval?: string },
  ): Promise<HistoricalResponse> {
    return this.request<HistoricalResponse>('/api/v1/historical', {
      symbol,
      hours: String(options?.hours || 24),
      interval: options?.interval || '1h',
    });
  }
}

export default MarketMate;
