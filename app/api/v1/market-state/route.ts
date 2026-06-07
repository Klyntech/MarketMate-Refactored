import { NextRequest, NextResponse } from "next/server"
import { validateApiKey } from "@/lib/api-keys"

const BACKEND_URL = process.env.MARKETMATE_API_URL || "http://localhost:8000"

// Symbol mapping: MarketMate format -> Binance format
function toBinanceSymbol(symbol: string): string {
  return symbol.replace("-", "").replace("USD", "USDT").toUpperCase()
}

// Determine market regime from price action data
function determineRegime(changePercent: number, volatility: number): string {
  if (volatility > 0.04) return "volatile"
  if (changePercent > 1.5) return "trending_bullish"
  if (changePercent < -1.5) return "trending_bearish"
  if (Math.abs(changePercent) < 0.5) return "ranging"
  if (changePercent > 0) return "trending_bullish"
  return "trending_bearish"
}

// Determine volatility level
function determineVolatility(high: number, low: number, avg: number): string {
  const range = (high - low) / avg
  if (range > 0.05) return "extreme"
  if (range > 0.03) return "elevated"
  if (range > 0.015) return "normal"
  return "low"
}

export async function GET(request: NextRequest) {
  // Validate API key
  const authHeader = request.headers.get("Authorization")
  const apiKey = authHeader?.replace("Bearer ", "")

  if (!apiKey) {
    return NextResponse.json(
      { error: "Unauthorized", message: "API key required. Include Authorization: Bearer <your-api-key> header." },
      { status: 401 }
    )
  }

  const { valid } = await validateApiKey(apiKey)
  if (!valid) {
    return NextResponse.json(
      { error: "Unauthorized", message: "Invalid or revoked API key." },
      { status: 401 }
    )
  }

  const symbol = request.nextUrl.searchParams.get("symbol") || "BTC-USD"
  const binanceSymbol = toBinanceSymbol(symbol)

  try {
    // Fetch real 24hr ticker data from Binance
    const tickerResponse = await fetch(
      `https://api.binance.com/api/v3/ticker/24hr?symbol=${binanceSymbol}`,
      { next: { revalidate: 30 }, signal: AbortSignal.timeout(8000) }
    )

    if (!tickerResponse.ok) {
      throw new Error(`Binance API returned ${tickerResponse.status}`)
    }

    const ticker = await tickerResponse.json()

    const lastPrice = parseFloat(ticker.lastPrice)
    const highPrice = parseFloat(ticker.highPrice)
    const lowPrice = parseFloat(ticker.lowPrice)
    const changePercent = parseFloat(ticker.priceChangePercent)
    const volume = parseFloat(ticker.volume)
    const quoteVolume = parseFloat(ticker.quoteVolume)
    const avgPrice = parseFloat(ticker.weightedAvgPrice)

    // Fetch recent klines for key level analysis
    const klinesResponse = await fetch(
      `https://api.binance.com/api/v3/klines?symbol=${binanceSymbol}&interval=4h&limit=30`,
      { next: { revalidate: 60 }, signal: AbortSignal.timeout(8000) }
    )

    let keyLevels = { support: [] as number[], resistance: [] as number[] }
    let swingHighs: number[] = []
    let swingLows: number[] = []

    if (klinesResponse.ok) {
      const klines = await klinesResponse.json()

      // Find swing highs and lows from recent candlestick data
      for (let i = 2; i < klines.length - 2; i++) {
        const prevHigh = parseFloat(klines[i - 1][2])
        const currHigh = parseFloat(klines[i][2])
        const nextHigh = parseFloat(klines[i + 1][2])
        const prevLow = parseFloat(klines[i - 1][3])
        const currLow = parseFloat(klines[i][3])
        const nextLow = parseFloat(klines[i + 1][3])

        if (currHigh > prevHigh && currHigh > nextHigh) {
          swingHighs.push(currHigh)
        }
        if (currLow < prevLow && currLow < nextLow) {
          swingLows.push(currLow)
        }
      }

      // Sort and take top 3 closest support/resistance levels
      swingLows.sort((a, b) => b - a) // Closest to current price first
      swingHighs.sort((a, b) => a - b)

      keyLevels = {
        support: swingLows.slice(0, 3).map(p => Math.round(p * 100) / 100),
        resistance: swingHighs.slice(0, 3).map(p => Math.round(p * 100) / 100),
      }
    }

    // Calculate conviction score based on trend strength and volume
    const trendStrength = Math.min(Math.abs(changePercent) / 5, 1)
    const volumeFactor = Math.min(quoteVolume / 5_000_000_000, 1) // Normalize against $5B
    const conviction = Math.round((trendStrength * 0.6 + volumeFactor * 0.4) * 100) / 100

    const regime = determineRegime(changePercent, (highPrice - lowPrice) / avgPrice)
    const volatility = determineVolatility(highPrice, lowPrice, avgPrice)

    // Calculate a simple liquidity score from volume and spread
    const spread = (highPrice - lowPrice) / avgPrice
    const liquidityScore = Math.round(Math.max(0.1, Math.min(1, 1 - spread * 10 + volumeFactor * 0.3)) * 100) / 100

    const marketState = {
      symbol,
      regime,
      conviction,
      volatility,
      liquidity: liquidityScore,
      price: {
        current: lastPrice,
        change_24h: changePercent,
        high_24h: highPrice,
        low_24h: lowPrice,
        volume_24h: volume,
        quote_volume_24h: Math.round(quoteVolume),
      },
      key_levels: keyLevels,
      trend: {
        direction: changePercent > 0 ? "bullish" : changePercent < 0 ? "bearish" : "neutral",
        strength: Math.round(trendStrength * 100) / 100,
        timeframe: "4H",
      },
      source: "binance",
      updated_at: new Date().toISOString(),
    }

    return NextResponse.json(marketState)
  } catch (error) {
    console.error("Market state fetch error:", error)

    // If Binance fails, try MarketMate backend as fallback
    try {
      const backendResponse = await fetch(`${BACKEND_URL}/health`, {
        signal: AbortSignal.timeout(3000),
      })
      if (backendResponse.ok) {
        return NextResponse.json({
          symbol,
          error: "External market data source unavailable",
          fallback: "MarketMate backend is online but does not provide market state data directly. Try again later.",
          updated_at: new Date().toISOString(),
        })
      }
    } catch {
      // Backend also unreachable
    }

    return NextResponse.json(
      { error: "Market data temporarily unavailable", message: "Could not fetch live market data. Please try again in a moment." },
      { status: 503 }
    )
  }
}
