/**
 * MarketMate API Client
 * 
 * Handles all communication with the MarketMate backend API.
 * The backend runs separately (Python FastAPI) and this client
 * proxies requests through Next.js API routes for security.
 */

// Types matching the backend signal schema
export interface Signal {
  id: string
  signal_id: string
  symbol: string
  direction: "BUY" | "SELL"
  entry_low: number
  entry_high: number
  entry_mid: number
  stop_loss: number
  tp1: number
  tp2: number
  tp3?: number
  rr: number
  position_size: number
  confidence: "HIGH" | "MEDIUM" | "LOW"
  zone_type: string
  confirm_type: string
  confirm_tf: string
  status: "PENDING" | "ACTIVE" | "TP1_HIT" | "TP2_HIT" | "TP3_HIT" | "CLOSED" | "EXPIRED"
  outcome?: "WIN" | "LOSS" | "BREAKEVEN" | "BE" | "EXPIRED"
  generated_at: string
  closed_at?: string
  final_pnl?: number
}

export interface PerformanceStats {
  total_signals: number
  wins: number
  losses: number
  breakeven: number
  win_rate: number
  avg_rr: number
  total_pnl: number
  best_trade: number
  worst_trade: number
}

export interface TradesResponse {
  trades: Signal[]
  count: number
}

export interface PerformanceResponse {
  "7_day": PerformanceStats
  "30_day": PerformanceStats
}

export interface HealthResponse {
  status: "ok" | "error"
  uptime?: number
  backend_down?: boolean
  message?: string
}

// API base URL - defaults to relative path for same-origin, 
// or use NEXT_PUBLIC_API_URL for external backend
const API_BASE = process.env.NEXT_PUBLIC_MARKETMATE_API_URL || ""

class MarketMateAPI {
  private baseUrl: string

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`
    
    const response = await fetch(url, {
      ...options,
      credentials: "include", // Include cookies for session auth
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: "Unknown error" }))
      throw new Error(error.error || `API request failed: ${response.status}`)
    }

    return response.json()
  }

  // Health check
  async health(): Promise<HealthResponse> {
    return this.request<HealthResponse>("/api/health")
  }

  // Get open trades/signals
  async getTrades(): Promise<TradesResponse> {
    return this.request<TradesResponse>("/api/trades")
  }

  // Get performance stats
  async getPerformance(): Promise<PerformanceResponse> {
    return this.request<PerformanceResponse>("/api/performance")
  }

  // MATE AI query
  async queryMATE(query: string, queryType?: string): Promise<{ response: string; sources?: string[] }> {
    return this.request("/api/mate", {
      method: "POST",
      body: JSON.stringify({ query, query_type: queryType }),
    })
  }
}

// Singleton instance
export const api = new MarketMateAPI()

// Export class for custom instances
export { MarketMateAPI }
