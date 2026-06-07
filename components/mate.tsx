"use client"

import { useState, useEffect, useCallback } from "react"
import { useSession } from "next-auth/react"
import Link from "next/link"
import { X, Send, Activity, Database, Wrench, ChevronDown, Lock } from "lucide-react"
import { cn } from "@/lib/utils"

type SystemState = "stable" | "uncertain" | "volatile"
type ActiveTab = "chat" | "state" | "tools"

interface MarketBias {
  symbol: string
  bias: "Bullish" | "Bearish" | "Neutral"
  confidence: number
  reason: string[]
  state: string
}

interface StateSnapshot {
  activeInstruments: string[]
  lastScan: string
  overallConviction: number
  recentBiases: MarketBias[]
}

const SCAN_PHASES = [
  "SCANNING MARKET STATE...",
  "ACCESSING STATE ENGINE...",
  "EVALUATING STRUCTURE...",
  "COMPILING RESPONSE...",
]

// Simulated market data
const mockStateSnapshot: StateSnapshot = {
  activeInstruments: ["XAUUSD", "EURUSD", "BTCUSD", "GBPUSD", "US30"],
  lastScan: "2 seconds ago",
  overallConviction: 0.68,
  recentBiases: [
    {
      symbol: "XAUUSD",
      bias: "Bearish",
      confidence: 0.74,
      reason: ["HTF structure confirms lower highs", "Liquidity sweep incomplete"],
      state: "ACTIVE_TREND_MODE",
    },
    {
      symbol: "BTCUSD",
      bias: "Bullish",
      confidence: 0.62,
      reason: ["Consolidation breakout pending", "Volume accumulation detected"],
      state: "RANGE_EXPANSION_WATCH",
    },
    {
      symbol: "EURUSD",
      bias: "Neutral",
      confidence: 0.45,
      reason: ["Mixed signals across timeframes", "Awaiting liquidity event"],
      state: "CONSOLIDATION_MODE",
    },
  ],
}

export function MATE() {
  const [isOpen, setIsOpen] = useState(false)
  const [systemState, setSystemState] = useState<SystemState>("stable")
  const [activeTab, setActiveTab] = useState<ActiveTab>("chat")
  const [query, setQuery] = useState("")
  const [isScanning, setIsScanning] = useState(false)
  const [scanPhase, setScanPhase] = useState(0)
  const [responses, setResponses] = useState<MarketBias[]>([])
  const [stateSnapshot, setStateSnapshot] = useState<StateSnapshot>(mockStateSnapshot)
  const { data: session, status } = useSession()
  const isAuthenticated = status === "authenticated"

  // Simulate system state changes
  useEffect(() => {
    const interval = setInterval(() => {
      const states: SystemState[] = ["stable", "stable", "stable", "uncertain", "volatile"]
      setSystemState(states[Math.floor(Math.random() * states.length)])
    }, 5000)
    return () => clearInterval(interval)
  }, [])

  // Update last scan time
  useEffect(() => {
    const interval = setInterval(() => {
      setStateSnapshot((prev) => ({
        ...prev,
        lastScan: `${Math.floor(Math.random() * 10) + 1} seconds ago`,
      }))
    }, 3000)
    return () => clearInterval(interval)
  }, [])

  // Scan animation
  useEffect(() => {
    if (isScanning) {
      const interval = setInterval(() => {
        setScanPhase((prev) => (prev + 1) % SCAN_PHASES.length)
      }, 600)
      return () => clearInterval(interval)
    }
  }, [isScanning])

  const handleQuery = useCallback(async () => {
    if (!query.trim() || !isAuthenticated) return

    setIsScanning(true)
    setScanPhase(0)

    // Simulate processing
    await new Promise((resolve) => setTimeout(resolve, 2400))

    // Generate mock response based on query
    const symbols = ["XAUUSD", "EURUSD", "BTCUSD", "GBPUSD"]
    const mentionedSymbol = symbols.find((s) => query.toUpperCase().includes(s)) || "XAUUSD"

    const mockResponse: MarketBias = {
      symbol: mentionedSymbol,
      bias: Math.random() > 0.5 ? "Bearish" : "Bullish",
      confidence: Math.round((0.5 + Math.random() * 0.4) * 100) / 100,
      reason: [
        "H4 structure confirms directional bias",
        "Liquidity sweep analysis complete",
        "Volume profile supports continuation",
      ],
      state: ["ACTIVE_TREND_MODE", "RANGE_EXPANSION_WATCH", "CONSOLIDATION_MODE"][
        Math.floor(Math.random() * 3)
      ],
    }

    setResponses((prev) => [mockResponse, ...prev])
    setIsScanning(false)
    setQuery("")
  }, [query, isAuthenticated])

  const stateColor = {
    stable: "bg-emerald-500",
    uncertain: "bg-amber-500",
    volatile: "bg-red-500",
  }

  const statePulseColor = {
    stable: "bg-emerald-500/50",
    uncertain: "bg-amber-500/50",
    volatile: "bg-red-500/50",
  }

  return (
    <>
      {/* Floating Intelligence Core */}
      <button
        onClick={() => setIsOpen(true)}
        className={cn(
          "fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full border border-border bg-card shadow-2xl transition-all duration-300 hover:scale-105",
          isOpen && "pointer-events-none opacity-0"
        )}
      >
        <div className="relative flex items-center justify-center">
          {/* Pulse ring */}
          <span
            className={cn(
              "absolute h-8 w-8 animate-ping rounded-full opacity-75",
              statePulseColor[systemState]
            )}
          />
          {/* Core indicator */}
          <span
            className={cn(
              "relative h-4 w-4 rounded-full transition-colors duration-500",
              stateColor[systemState]
            )}
          />
        </div>
      </button>

      {/* Expanded Panel */}
      <div
        className={cn(
          "fixed bottom-0 right-0 z-50 flex h-[600px] w-full flex-col border-l border-t border-border bg-card shadow-2xl transition-all duration-300 md:bottom-6 md:right-6 md:h-[580px] md:w-[420px] md:rounded-lg md:border",
          isOpen ? "translate-y-0 opacity-100" : "pointer-events-none translate-y-full opacity-0 md:translate-y-4"
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="relative flex items-center justify-center">
              <span
                className={cn(
                  "absolute h-5 w-5 animate-pulse rounded-full opacity-50",
                  statePulseColor[systemState]
                )}
              />
              <span
                className={cn(
                  "relative h-2.5 w-2.5 rounded-full",
                  stateColor[systemState]
                )}
              />
            </div>
            <div>
              <p className="font-mono text-xs font-semibold tracking-wider text-foreground">
                MATE
              </p>
              <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                Active Intelligence Layer
              </p>
            </div>
          </div>
          <button
            onClick={() => setIsOpen(false)}
            className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Not authenticated - show auth gate */}
        {!isAuthenticated ? (
          <div className="flex flex-1 flex-col items-center justify-center p-6 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-secondary border border-border mb-4">
              <Lock className="h-8 w-8 text-muted-foreground" />
            </div>
            <p className="font-mono text-sm font-semibold text-foreground mb-2">
              Sign in to access MATE
            </p>
            <p className="text-xs text-muted-foreground mb-6 max-w-[260px]">
              MATE AI provides real-time market interpretation, conviction analysis, and state intelligence for authenticated users.
            </p>
            <Link
              href="/login"
              onClick={() => setIsOpen(false)}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
            >
              Sign In
            </Link>
            <p className="mt-3 text-xs text-muted-foreground">
              Don&apos;t have an account?{" "}
              <Link href="/signup" onClick={() => setIsOpen(false)} className="text-primary hover:underline">
                Create one
              </Link>
            </p>
          </div>
        ) : (
          <>
            {/* Authenticated content */}
            {/* Status Bar */}
            <div className="border-b border-border bg-secondary/30 px-4 py-2">
              <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                Status: <span className="text-emerald-400">Listening to Market State...</span>
              </p>
              <p className="mt-0.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                Context: <span className="text-foreground">{stateSnapshot.activeInstruments.slice(0, 3).join(", ")}</span>
              </p>
            </div>

            {/* Tabs */}
            <div className="flex border-b border-border">
              {[
                { id: "chat" as const, label: "Chat", icon: Activity },
                { id: "state" as const, label: "State", icon: Database },
                { id: "tools" as const, label: "Tools", icon: Wrench },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    "flex flex-1 items-center justify-center gap-2 py-2.5 font-mono text-xs uppercase tracking-wider transition-colors",
                    activeTab === tab.id
                      ? "border-b-2 border-accent text-accent"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <tab.icon className="h-3.5 w-3.5" />
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-y-auto">
              {activeTab === "chat" && (
                <div className="flex h-full flex-col">
                  {/* Responses */}
                  <div className="flex-1 space-y-3 overflow-y-auto p-4">
                    {isScanning && (
                      <div className="rounded-md border border-accent/30 bg-accent/5 p-3">
                        <div className="flex items-center gap-2">
                          <div className="flex gap-1">
                            {[0, 1, 2].map((i) => (
                              <span
                                key={i}
                                className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent"
                                style={{ animationDelay: `${i * 150}ms` }}
                              />
                            ))}
                          </div>
                          <p className="font-mono text-xs uppercase tracking-wider text-accent">
                            {SCAN_PHASES[scanPhase]}
                          </p>
                        </div>
                      </div>
                    )}

                    {responses.length === 0 && !isScanning && (
                      <div className="flex h-full flex-col items-center justify-center text-center">
                        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-secondary">
                          <Activity className="h-6 w-6 text-muted-foreground" />
                        </div>
                        <p className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
                          Query the market state
                        </p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          Ask about any instrument or market condition
                        </p>
                      </div>
                    )}

                    {responses.map((response, i) => (
                      <ResponseCard key={i} response={response} />
                    ))}
                  </div>

                  {/* Input */}
                  <div className="border-t border-border p-4">
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && handleQuery()}
                        placeholder="Ask about market / system / performance"
                        className="flex-1 rounded-md border border-border bg-secondary/50 px-3 py-2 font-mono text-sm text-foreground placeholder:text-muted-foreground focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
                        disabled={isScanning}
                      />
                      <button
                        onClick={handleQuery}
                        disabled={isScanning || !query.trim()}
                        className="flex h-10 w-10 items-center justify-center rounded-md bg-accent text-accent-foreground transition-colors hover:bg-accent/80 disabled:opacity-50"
                      >
                        <Send className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === "state" && (
                <div className="space-y-4 p-4">
                  {/* Overall Status */}
                  <div className="rounded-md border border-border bg-secondary/30 p-3">
                    <p className="mb-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                      System Overview
                    </p>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <p className="text-2xl font-bold text-foreground">
                          {(stateSnapshot.overallConviction * 100).toFixed(0)}%
                        </p>
                        <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                          Overall Conviction
                        </p>
                      </div>
                      <div>
                        <p className="text-2xl font-bold text-foreground">
                          {stateSnapshot.activeInstruments.length}
                        </p>
                        <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                          Active Instruments
                        </p>
                      </div>
                    </div>
                    <p className="mt-3 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                      Last Scan: <span className="text-emerald-400">{stateSnapshot.lastScan}</span>
                    </p>
                  </div>

                  {/* Active Instruments */}
                  <div>
                    <p className="mb-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                      Active Instruments
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {stateSnapshot.activeInstruments.map((instrument) => (
                        <span
                          key={instrument}
                          className="rounded border border-border bg-secondary px-2 py-1 font-mono text-xs text-foreground"
                        >
                          {instrument}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Recent Biases */}
                  <div>
                    <p className="mb-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                      Recent Bias Snapshot
                    </p>
                    <div className="space-y-2">
                      {stateSnapshot.recentBiases.map((bias, i) => (
                        <div
                          key={i}
                          className="flex items-center justify-between rounded-md border border-border bg-secondary/30 p-2"
                        >
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-sm font-semibold text-foreground">
                              {bias.symbol}
                            </span>
                            <span
                              className={cn(
                                "rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase",
                                bias.bias === "Bullish" && "bg-emerald-500/20 text-emerald-400",
                                bias.bias === "Bearish" && "bg-red-500/20 text-red-400",
                                bias.bias === "Neutral" && "bg-amber-500/20 text-amber-400"
                              )}
                            >
                              {bias.bias}
                            </span>
                          </div>
                          <span className="font-mono text-xs text-muted-foreground">
                            {(bias.confidence * 100).toFixed(0)}%
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {activeTab === "tools" && (
                <div className="space-y-3 p-4">
                  <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                    Quick Actions
                  </p>
                  {[
                    { label: "Force State Rescan", desc: "Trigger immediate market scan" },
                    { label: "Clear Response Cache", desc: "Reset stored interpretations" },
                    { label: "Export State Snapshot", desc: "Download current state as JSON" },
                    { label: "Toggle Debug Mode", desc: "Show raw state engine output" },
                  ].map((tool, i) => (
                    <button
                      key={i}
                      className="flex w-full items-center justify-between rounded-md border border-border bg-secondary/30 p-3 text-left transition-colors hover:bg-secondary/50"
                    >
                      <div>
                        <p className="font-mono text-sm font-medium text-foreground">{tool.label}</p>
                        <p className="font-mono text-[10px] text-muted-foreground">{tool.desc}</p>
                      </div>
                      <ChevronDown className="h-4 w-4 rotate-[-90deg] text-muted-foreground" />
                    </button>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </>
  )
}

function ResponseCard({ response }: { response: MarketBias }) {
  return (
    <div className="rounded-md border border-border bg-secondary/30 p-3">
      {/* Symbol Header */}
      <div className="mb-2 flex items-center justify-between">
        <span className="font-mono text-sm font-bold text-foreground">{response.symbol}</span>
        <span
          className={cn(
            "rounded px-2 py-0.5 font-mono text-[10px] font-semibold uppercase",
            response.bias === "Bullish" && "bg-emerald-500/20 text-emerald-400",
            response.bias === "Bearish" && "bg-red-500/20 text-red-400",
            response.bias === "Neutral" && "bg-amber-500/20 text-amber-400"
          )}
        >
          {response.bias}
        </span>
      </div>

      {/* Confidence */}
      <div className="mb-3">
        <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
          Confidence
        </p>
        <div className="mt-1 flex items-center gap-2">
          <div className="h-1.5 flex-1 rounded-full bg-secondary">
            <div
              className={cn(
                "h-full rounded-full transition-all",
                response.confidence >= 0.7 && "bg-emerald-500",
                response.confidence >= 0.5 && response.confidence < 0.7 && "bg-amber-500",
                response.confidence < 0.5 && "bg-red-500"
              )}
              style={{ width: `${response.confidence * 100}%` }}
            />
          </div>
          <span className="font-mono text-xs font-semibold text-foreground">
            {(response.confidence * 100).toFixed(0)}%
          </span>
        </div>
      </div>

      {/* Reason */}
      <div className="mb-3">
        <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
          Reason
        </p>
        <ul className="mt-1 space-y-0.5">
          {response.reason.map((r, i) => (
            <li key={i} className="flex items-start gap-1.5 text-xs text-foreground">
              <span className="mt-1.5 h-1 w-1 flex-shrink-0 rounded-full bg-accent" />
              {r}
            </li>
          ))}
        </ul>
      </div>

      {/* State */}
      <div>
        <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
          State
        </p>
        <span className="mt-1 inline-block rounded border border-accent/30 bg-accent/10 px-2 py-0.5 font-mono text-[10px] text-accent">
          {response.state}
        </span>
      </div>
    </div>
  )
}
