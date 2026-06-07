import { NextRequest, NextResponse } from "next/server"
import { validateApiKey } from "@/lib/api-keys"

// Symbol mapping
function toBinanceSymbol(symbol: string): string {
  return symbol.replace("-", "").replace("USD", "USDT").toUpperCase()
}

// Binance interval mapping
function toBinanceInterval(interval: string): string {
  const map: Record<string, string> = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
    "1w": "1w",
  }
  return map[interval] || "1h"
}

// Determine regime from candlestick data
function determineRegime(candles: { open: number; close: number; high: number; low: number }[]): string {
  if (candles.length < 3) return "ranging"

  let bullish = 0
  let bearish = 0
  let totalRange = 0
  let avgPrice = 0

  for (const c of candles) {
    if (c.close > c.open) bullish++
    else if (c.close < c.open) bearish++
    totalRange += (c.high - c.low) / c.close
    avgPrice += c.close
  }

  avgPrice /= candles.length
  const avgRange = totalRange / candles.length

  if (avgRange > 0.04) return "volatile"
  if (bullish > candles.length * 0.65) return "trending_bullish"
  if (bearish > candles.length * 0.65) return "trending_bearish"
  if (Math.abs(bullish - bearish) < candles.length * 0.2) return "ranging"
  return bullish > bearish ? "trending_bullish" : "trending_bearish"
}

export async function GET(request: NextRequest) {
  // Validate API key
  const authHeader = request.headers.get("Authorization")
  const apiKey = authHeader?.replace("Bearer ", "")

  if (!apiKey) {
    return NextResponse.json(
      { error: "Unauthorized", message: "API key required." },
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
  const hours = parseInt(request.nextUrl.searchParams.get("hours") || "24", 10)
  const interval = request.nextUrl.searchParams.get("interval") || "1h"

  const binanceSymbol = toBinanceSymbol(symbol)
  const binanceInterval = toBinanceInterval(interval)

  // Calculate kline limit based on requested hours and interval
  let klineLimit: number
  if (interval === "1m") klineLimit = Math.min(hours * 60, 1000)
  else if (interval === "5m") klineLimit = Math.min(hours * 12, 500)
  else if (interval === "15m") klineLimit = Math.min(hours * 4, 500)
  else if (interval === "30m") klineLimit = Math.min(hours * 2, 500)
  else if (interval === "1h") klineLimit = Math.min(hours, 500)
  else if (interval === "4h") klineLimit = Math.min(Math.ceil(hours / 4), 500)
  else if (interval === "1d") klineLimit = Math.min(Math.ceil(hours / 24), 500)
  else klineLimit = Math.min(hours, 500)

  // Max 7 days for minute-level data, 30 days for hourly
  klineLimit = Math.min(klineLimit, 500)

  try {
    const response = await fetch(
      `https://api.binance.com/api/v3/klines?symbol=${binanceSymbol}&interval=${binanceInterval}&limit=${klineLimit}`,
      { next: { revalidate: 30 }, signal: AbortSignal.timeout(10000) }
    )

    if (!response.ok) {
      throw new Error(`Binance API returned ${response.status}`)
    }

    const klines = await response.json()

    // Process klines into historical data points
    const candles = klines.map((k: string[]) => ({
      open: parseFloat(k[1]),
      high: parseFloat(k[2]),
      low: parseFloat(k[3]),
      close: parseFloat(k[4]),
      volume: parseFloat(k[5]),
    }))

    // Calculate rolling regime for each candle using a 5-candle window
    const dataPoints = klines.map((k: string[], i: number) => {
      const openTime = parseInt(k[0])
      const open = parseFloat(k[1])
      const high = parseFloat(k[2])
      const low = parseFloat(k[3])
      const close = parseFloat(k[4])
      const volume = parseFloat(k[5])

      // Use a 5-candle rolling window for regime detection
      const windowStart = Math.max(0, i - 4)
      const windowCandles = candles.slice(windowStart, i + 1)
      const regime = determineRegime(windowCandles)

      // Calculate conviction based on trend consistency and volume
      const changeInWindow = (close - windowCandles[0].open) / windowCandles[0].open
      const volumeAvg = candles.slice(Math.max(0, i - 20), i + 1).reduce((s: number, c: { volume: number }) => s + c.volume, 0) / Math.min(i + 1, 20)
      const volumeFactor = Math.min(volume / (volumeAvg || 1), 3) / 3

      const conviction = Math.round(
        Math.min(1, Math.abs(changeInWindow) * 20 * 0.6 + volumeFactor * 0.4)
        * 100
      ) / 100

      // Volatility from range
      const range = (high - low) / close
      const volatility = range > 0.03 ? "extreme" : range > 0.02 ? "elevated" : range > 0.01 ? "normal" : "low"

      // Liquidity score from volume
      const liquidityScore = Math.round(Math.min(1, Math.max(0.1, volumeFactor * 0.7 + 0.3)) * 100) / 100

      return {
        timestamp: new Date(openTime).toISOString(),
        open,
        high,
        low,
        close,
        volume,
        regime,
        conviction,
        volatility,
        liquidity_score: liquidityScore,
      }
    })

    // Calculate summary stats
    const prices = candles.map(c => c.close)
    const maxPrice = Math.max(...prices)
    const minPrice = Math.min(...prices)
    const startPrice = prices[0]
    const endPrice = prices[prices.length - 1]
    const totalChange = ((endPrice - startPrice) / startPrice) * 100
    const totalVolume = candles.reduce((s, c) => s + c.volume, 0)

    // Count regime distribution
    const regimeCounts: Record<string, number> = {}
    for (const dp of dataPoints) {
      regimeCounts[dp.regime] = (regimeCounts[dp.regime] || 0) + 1
    }

    return NextResponse.json({
      symbol,
      interval,
      period: {
        start: dataPoints[0]?.timestamp,
        end: dataPoints[dataPoints.length - 1]?.timestamp,
        candles: dataPoints.length,
      },
      summary: {
        start_price: Math.round(startPrice * 100) / 100,
        end_price: Math.round(endPrice * 100) / 100,
        change_pct: Math.round(totalChange * 100) / 100,
        high: Math.round(maxPrice * 100) / 100,
        low: Math.round(minPrice * 100) / 100,
        total_volume: Math.round(totalVolume * 100) / 100,
        regime_distribution: regimeCounts,
      },
      data: dataPoints,
      source: "binance",
      updated_at: new Date().toISOString(),
    })
  } catch (error) {
    console.error("Historical fetch error:", error)
    return NextResponse.json(
      { error: "Historical data temporarily unavailable", message: "Could not fetch candlestick data from exchange." },
      { status: 503 }
    )
  }
}
