import { NextRequest, NextResponse } from "next/server"
import { validateApiKey } from "@/lib/api-keys"

const BACKEND_URL = process.env.MARKETMATE_API_URL || "http://localhost:8000"

// Symbol mapping
function toBinanceSymbol(symbol: string): string {
  return symbol.replace("-", "").replace("USD", "USDT").toUpperCase()
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

  const symbol = request.nextUrl.searchParams.get("symbol")
  const conviction = request.nextUrl.searchParams.get("conviction")

  // Step 1: Try MarketMate backend for real trading signals
  try {
    const backendResponse = await fetch(`${BACKEND_URL}/trades`, {
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    })

    const data = await backendResponse.json().catch(() => ({}))

    // If backend returned real trades (not unauthorized/error)
    if (backendResponse.ok && data.trades && Array.isArray(data.trades) && data.trades.length > 0) {
      let signals = data.trades

      // Apply filters
      if (symbol) {
        signals = signals.filter((s: { symbol?: string }) =>
          s.symbol?.toLowerCase().includes(symbol.toLowerCase())
        )
      }
      if (conviction) {
        signals = signals.filter((s: { confidence?: string }) =>
          s.confidence?.toUpperCase() === conviction.toUpperCase()
        )
      }

      return NextResponse.json({
        signals,
        count: signals.length,
        source: "marketmate",
        timestamp: new Date().toISOString(),
      })
    }
  } catch {
    // Backend unreachable, fall through to Binance-derived signals
  }

  // Step 2: Generate derived signals from real Binance market data
  try {
    const binanceSymbol = symbol ? toBinanceSymbol(symbol) : "BTCUSDT"

    // Fetch 24hr ticker for the symbol
    const tickerResponse = await fetch(
      `https://api.binance.com/api/v3/ticker/24hr?symbol=${binanceSymbol}`,
      { next: { revalidate: 30 }, signal: AbortSignal.timeout(8000) }
    )

    if (!tickerResponse.ok) {
      throw new Error(`Binance returned ${tickerResponse.status}`)
    }

    const ticker = await tickerResponse.json()

    // Fetch klines for technical analysis
    const klinesResponse = await fetch(
      `https://api.binance.com/api/v3/klines?symbol=${binanceSymbol}&interval=4h&limit=50`,
      { next: { revalidate: 60 }, signal: AbortSignal.timeout(8000) }
    )

    let signals: object[] = []

    if (klinesResponse.ok) {
      const klines = await klinesResponse.json()

      const lastPrice = parseFloat(ticker.lastPrice)
      const changePercent = parseFloat(ticker.priceChangePercent)
      const high24h = parseFloat(ticker.highPrice)
      const low24h = parseFloat(ticker.lowPrice)

      // Derive demand/supply zones from recent price action
      const recentLows = klines.slice(-20).map((k: string[]) => parseFloat(k[3])).sort((a: number, b: number) => a - b)
      const recentHighs = klines.slice(-20).map((k: string[]) => parseFloat(k[2])).sort((a: number, b: number) => b - a)

      // Find clustered support zones (demand)
      const demandZone = {
        low: recentLows[Math.floor(recentLows.length * 0.1)],
        high: recentLows[Math.floor(recentLows.length * 0.3)],
      }
      demandZone.high = Math.max(demandZone.high, demandZone.low)
      const demandMid = (demandZone.low + demandZone.high) / 2

      // Find clustered resistance zones (supply)
      const supplyZone = {
        low: recentHighs[Math.floor(recentHighs.length * 0.7)],
        high: recentHighs[Math.floor(recentHighs.length * 0.9)],
      }
      supplyZone.low = Math.min(supplyZone.low, supplyZone.high)
      const supplyMid = (supplyZone.low + supplyZone.high) / 2

      // Generate signal based on current trend
      const isBullish = changePercent > 0
      const signalDirection = isBullish ? "LONG" : "SHORT"

      const entryZone = isBullish
        ? { low: Math.round(demandZone.low * 100) / 100, high: Math.round(demandZone.high * 100) / 100, mid: Math.round(demandMid * 100) / 100 }
        : { low: Math.round(supplyZone.low * 100) / 100, high: Math.round(supplyZone.high * 100) / 100, mid: Math.round(supplyMid * 100) / 100 }

      const stopLoss = isBullish
        ? Math.round((demandZone.low - (demandZone.low * 0.01)) * 100) / 100
        : Math.round((supplyZone.high + (supplyZone.high * 0.01)) * 100) / 100

      const risk = Math.abs(lastPrice - stopLoss)
      const tp1 = isBullish
        ? Math.round((lastPrice + risk * 2) * 100) / 100
        : Math.round((lastPrice - risk * 2) * 100) / 100
      const tp2 = isBullish
        ? Math.round((lastPrice + risk * 3.5) * 100) / 100
        : Math.round((lastPrice - risk * 3.5) * 100) / 100
      const tp3 = isBullish
        ? Math.round((lastPrice + risk * 5) * 100) / 100
        : Math.round((lastPrice - risk * 5) * 100) / 100

      const rr = Math.round(Math.abs(tp1 - lastPrice) / risk * 100) / 100

      const convictionLevel = Math.abs(changePercent) > 2 ? "HIGH" : Math.abs(changePercent) > 0.8 ? "MEDIUM" : "LOW"

      // Only generate signal if conviction is at least LOW or higher
      if (!conviction || conviction.toUpperCase() === convictionLevel || (conviction.toUpperCase() === "HIGH" && convictionLevel === "HIGH") || (conviction.toUpperCase() === "MEDIUM" && ["MEDIUM", "HIGH"].includes(convictionLevel))) {
        signals.push({
          signal_id: `sig_${Date.now().toString(36)}`,
          symbol: symbol || "BTC-USD",
          direction: signalDirection,
          entry_zone: entryZone,
          stop_loss: stopLoss,
          take_profit_1: tp1,
          take_profit_2: tp2,
          take_profit_3: tp3,
          risk_reward: rr,
          conviction: convictionLevel,
          zone_type: isBullish ? "demand_zone" : "supply_zone",
          confirmation: "price_action",
          status: "ACTIVE",
          current_price: lastPrice,
          change_24h: `${changePercent}%`,
          range_24h: { high: high24h, low: low24h },
          source: "derived",
          disclaimer: "Signal derived from real-time market data analysis. Not financial advice. Always do your own research.",
          created_at: new Date().toISOString(),
        })
      }
    }

    // Apply conviction filter if specified
    let filtered = signals
    if (conviction) {
      filtered = signals.filter((s: any) => s.conviction === conviction.toUpperCase())
    }

    return NextResponse.json({
      signals: filtered,
      count: filtered.length,
      source: "binance_derived",
      note: "Signals derived from real-time Binance market data using technical analysis. Connect MarketMate bot for AI-powered signals.",
      timestamp: new Date().toISOString(),
    })
  } catch (error) {
    console.error("Signals fetch error:", error)
    return NextResponse.json(
      { error: "Signal data temporarily unavailable", message: "Could not fetch live market data for signal generation." },
      { status: 503 }
    )
  }
}
