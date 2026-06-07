import { NextRequest, NextResponse } from "next/server"
import { validateApiKey } from "@/lib/api-keys"

// Symbol mapping
function toBinanceSymbol(symbol: string): string {
  return symbol.replace("-", "").replace("USD", "USDT").toUpperCase()
}

interface OrderbookLevel {
  price: number
  quantity: number
  total: number
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
  const binanceSymbol = toBinanceSymbol(symbol)

  try {
    // Fetch real orderbook data from Binance
    const [orderbookRes, tickerRes] = await Promise.all([
      fetch(`https://api.binance.com/api/v3/depth?symbol=${binanceSymbol}&limit=50`, {
        next: { revalidate: 15 },
        signal: AbortSignal.timeout(8000),
      }),
      fetch(`https://api.binance.com/api/v3/ticker/24hr?symbol=${binanceSymbol}`, {
        next: { revalidate: 30 },
        signal: AbortSignal.timeout(8000),
      }),
    ])

    if (!orderbookRes.ok || !tickerRes.ok) {
      throw new Error("Binance API error")
    }

    const orderbook = await orderbookRes.json()
    const ticker = await tickerRes.json()

    const lastPrice = parseFloat(ticker.lastPrice)
    const volume24h = parseFloat(ticker.volume)

    // Process bid side (demand) - aggregate and find significant levels
    const bidLevels: OrderbookLevel[] = []
    let bidTotal = 0
    for (const [price, qty] of orderbook.bids.slice(0, 20)) {
      const p = parseFloat(price)
      const q = parseFloat(qty)
      bidTotal += p * q
      bidLevels.push({ price: p, quantity: q, total: bidTotal })
    }

    // Process ask side (supply) - aggregate and find significant levels
    const askLevels: OrderbookLevel[] = []
    let askTotal = 0
    for (const [price, qty] of orderbook.asks.slice(0, 20)) {
      const p = parseFloat(price)
      const q = parseFloat(qty)
      askTotal += p * q
      bidTotal += p * q
      askLevels.push({ price: p, quantity: q, total: askTotal })
    }

    // Find significant liquidity pools (large orders)
    const avgBidQty = bidLevels.reduce((s, l) => s + l.quantity, 0) / bidLevels.length
    const avgAskQty = askLevels.reduce((s, l) => s + l.quantity, 0) / askLevels.length

    const significantBids = bidLevels
      .filter(l => l.quantity > avgBidQty * 2)
      .map(l => ({
        level: Math.round(l.price * 100) / 100,
        type: "demand" as const,
        volume: `${Math.round(l.quantity * 100) / 100} ${symbol.split("-")[0]}`,
        quantity: Math.round(l.quantity * 100) / 100,
        strength: Math.round((l.quantity / avgBidQty) * 100) / 100,
      }))

    const significantAsks = askLevels
      .filter(l => l.quantity > avgAskQty * 2)
      .map(l => ({
        level: Math.round(l.price * 100) / 100,
        type: "supply" as const,
        volume: `${Math.round(l.quantity * 100) / 100} ${symbol.split("-")[0]}`,
        quantity: Math.round(l.quantity * 100) / 100,
        strength: Math.round((l.quantity / avgAskQty) * 100) / 100,
      }))

    // Calculate liquidity score
    const totalBidDepth = bidLevels.slice(0, 10).reduce((s, l) => s + l.quantity * l.price, 0)
    const totalAskDepth = askLevels.slice(0, 10).reduce((s, l) => s + l.quantity * l.price, 0)
    const totalDepth = totalBidDepth + totalAskDepth
    const balanceRatio = totalBidDepth / totalDepth // >0.5 = buy pressure, <0.5 = sell pressure

    const liquidityScore = Math.round(
      Math.min(1, Math.max(0.1, (totalDepth / 100_000_000) * 0.5 + 0.3))
      * 100
    ) / 100

    // Detect potential sweep levels (price levels with thin liquidity that could be swept)
    const sweeps = []
    for (let i = 1; i < bidLevels.length; i++) {
      if (bidLevels[i].quantity < avgBidQty * 0.3 && bidLevels[i - 1].quantity > avgBidQty) {
        sweeps.push({
          level: Math.round(bidLevels[i].price * 100) / 100,
          direction: "bearish",
          thin_liquidity: `${Math.round(bidLevels[i].quantity * 100) / 100} ${symbol.split("-")[0]}`,
          wall_above: `${Math.round(bidLevels[i - 1].quantity * 100) / 100} ${symbol.split("-")[0]}`,
        })
      }
    }
    for (let i = 1; i < askLevels.length; i++) {
      if (askLevels[i].quantity < avgAskQty * 0.3 && askLevels[i - 1].quantity > avgAskQty) {
        sweeps.push({
          level: Math.round(askLevels[i].price * 100) / 100,
          direction: "bullish",
          thin_liquidity: `${Math.round(askLevels[i].quantity * 100) / 100} ${symbol.split("-")[0]}`,
          wall_below: `${Math.round(askLevels[i - 1].quantity * 100) / 100} ${symbol.split("-")[0]}`,
        })
      }
    }

    const result = {
      symbol,
      current_price: lastPrice,
      score: liquidityScore,
      balance: {
        bid_depth: Math.round(totalBidDepth),
        ask_depth: Math.round(totalAskDepth),
        ratio: Math.round(balanceRatio * 100) / 100,
        pressure: balanceRatio > 0.55 ? "buying" : balanceRatio < 0.45 ? "selling" : "neutral",
      },
      pools: [...significantBids, ...significantAsks].slice(0, 8),
      sweeps: sweeps.slice(0, 5),
      orderbook_summary: {
        best_bid: Math.round(bidLevels[0].price * 100) / 100,
        best_ask: Math.round(askLevels[0].price * 100) / 100,
        spread: Math.round((askLevels[0].price - bidLevels[0].price) * 100) / 100,
        spread_pct: Math.round(((askLevels[0].price - bidLevels[0].price) / lastPrice) * 10000) / 100,
      },
      volume_24h: volume24h,
      source: "binance",
      disclaimer: "Liquidity analysis derived from real-time Binance orderbook data. Orderbook depth is a snapshot and may change rapidly.",
      updated_at: new Date().toISOString(),
    }

    return NextResponse.json(result)
  } catch (error) {
    console.error("Liquidity fetch error:", error)
    return NextResponse.json(
      { error: "Liquidity data temporarily unavailable", message: "Could not fetch live orderbook data." },
      { status: 503 }
    )
  }
}
