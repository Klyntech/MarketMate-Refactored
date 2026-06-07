"use client"

import { useTrades, usePerformance, type Signal } from "@/hooks/use-signals"
import { cn } from "@/lib/utils"
import { RefreshCw, TrendingUp, TrendingDown, Clock, Target, AlertTriangle, Lock } from "lucide-react"
import Link from "next/link"

function formatPrice(price: number): string {
  if (price >= 1000) return price.toFixed(2)
  if (price >= 1) return price.toFixed(4)
  return price.toFixed(6)
}

function formatTime(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
}

function SignalCard({ signal }: { signal: Signal }) {
  const isBuy = signal.direction === "BUY"
  
  return (
    <div className="bg-[#0e1621] rounded-lg border border-border/50 p-4 font-mono text-sm">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className={cn(
            "px-2 py-0.5 rounded text-xs font-semibold",
            isBuy ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"
          )}>
            {signal.direction}
          </span>
          <span className="text-foreground font-semibold">{signal.symbol}</span>
        </div>
        <span className={cn(
          "text-xs px-2 py-0.5 rounded",
          signal.status === "ACTIVE" && "bg-emerald-500/20 text-emerald-400",
          signal.status === "PENDING" && "bg-amber-500/20 text-amber-400",
          signal.status === "TP1_HIT" && "bg-blue-500/20 text-blue-400",
          signal.status === "CLOSED" && "bg-muted text-muted-foreground"
        )}>
          {signal.status.replace("_", " ")}
        </span>
      </div>

      {/* Entry & SL */}
      <div className="grid grid-cols-2 gap-2 mb-3 text-xs">
        <div>
          <span className="text-muted-foreground">Entry: </span>
          <span className="text-foreground">{formatPrice(signal.entry_mid)}</span>
        </div>
        <div>
          <span className="text-muted-foreground">SL: </span>
          <span className="text-red-400">{formatPrice(signal.stop_loss)}</span>
        </div>
      </div>

      {/* Targets */}
      <div className="flex gap-3 text-xs mb-3">
        <div>
          <span className="text-muted-foreground">TP1: </span>
          <span className="text-emerald-400">{formatPrice(signal.tp1)}</span>
        </div>
        <div>
          <span className="text-muted-foreground">TP2: </span>
          <span className="text-emerald-400">{formatPrice(signal.tp2)}</span>
        </div>
        {signal.tp3 && (
          <div>
            <span className="text-muted-foreground">TP3: </span>
            <span className="text-emerald-400">{formatPrice(signal.tp3)}</span>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between text-xs text-muted-foreground pt-2 border-t border-border/30">
        <span>RR: {signal.rr.toFixed(1)}</span>
        <span className={cn(
          signal.confidence === "HIGH" && "text-emerald-400",
          signal.confidence === "MEDIUM" && "text-amber-400",
          signal.confidence === "LOW" && "text-red-400"
        )}>
          {signal.confidence}
        </span>
        <span>{formatTime(signal.generated_at)}</span>
      </div>
    </div>
  )
}

function StatCard({ 
  label, 
  value, 
  subValue,
  trend,
  icon: Icon 
}: { 
  label: string
  value: string | number
  subValue?: string
  trend?: "up" | "down" | "neutral"
  icon?: typeof TrendingUp
}) {
  return (
    <div className="bg-secondary/50 border border-border rounded-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-muted-foreground uppercase tracking-wider">{label}</span>
        {Icon && <Icon className="w-4 h-4 text-muted-foreground" />}
      </div>
      <div className="flex items-baseline gap-2">
        <span className={cn(
          "text-2xl font-semibold",
          trend === "up" && "text-emerald-400",
          trend === "down" && "text-red-400",
          !trend && "text-foreground"
        )}>
          {value}
        </span>
        {subValue && (
          <span className="text-xs text-muted-foreground">{subValue}</span>
        )}
      </div>
    </div>
  )
}

export function LiveSignalsDashboard() {
  const { trades, count, isLoading: tradesLoading, isAuthRequired, isBackendDown, refresh: refreshTrades } = useTrades({
    refreshInterval: 15000,
  })
  const { stats7Day, isLoading: statsLoading, isAuthRequired: statsAuthRequired, refresh: refreshStats } = usePerformance({
    refreshInterval: 60000,
  })

  const isLoading = tradesLoading || statsLoading
  const needsAuth = isAuthRequired || statsAuthRequired

  return (
    <section className="py-24 border-t border-border">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        {/* Section header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <p className="text-sm font-medium text-primary uppercase tracking-wider mb-1">Live Feed</p>
            <h2 className="text-2xl font-bold text-foreground">Active Signals</h2>
          </div>
          <button
            onClick={() => { refreshTrades(); refreshStats(); }}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-secondary border border-border text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <RefreshCw className={cn("w-4 h-4", isLoading && "animate-spin")} />
            Refresh
          </button>
        </div>

        {/* Stats grid — only show when authenticated and data available */}
        {stats7Day && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <StatCard
              label="Win Rate (7D)"
              value={`${(stats7Day.win_rate * 100).toFixed(0)}%`}
              trend={stats7Day.win_rate >= 0.6 ? "up" : stats7Day.win_rate < 0.4 ? "down" : "neutral"}
              icon={Target}
            />
            <StatCard
              label="Avg RR"
              value={stats7Day.avg_rr.toFixed(2)}
              subValue="risk:reward"
              icon={TrendingUp}
            />
            <StatCard
              label="Signals (7D)"
              value={stats7Day.total_signals}
              icon={Clock}
            />
            <StatCard
              label="P&L (7D)"
              value={`${stats7Day.total_pnl >= 0 ? "+" : ""}${stats7Day.total_pnl.toFixed(1)}R`}
              trend={stats7Day.total_pnl >= 0 ? "up" : "down"}
              icon={stats7Day.total_pnl >= 0 ? TrendingUp : TrendingDown}
            />
          </div>
        )}

        {/* Auth required banner */}
        {needsAuth && !isLoading && (
          <div className="flex items-center gap-3 p-4 rounded-lg bg-secondary/50 border border-border mb-8">
            <Lock className="w-5 h-5 text-primary shrink-0" />
            <div className="flex-1">
              <p className="text-sm text-foreground font-medium">Sign in to view live signals</p>
              <p className="text-xs text-muted-foreground">
                Active signals and performance stats are available to subscribed members.
              </p>
            </div>
            <Link
              href="/login"
              className="shrink-0 inline-flex items-center gap-2 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
            >
              Sign In
            </Link>
          </div>
        )}

        {/* Backend down banner */}
        {isBackendDown && !isLoading && (
          <div className="flex items-center gap-3 p-4 rounded-lg bg-amber-500/10 border border-amber-500/30 mb-8">
            <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0" />
            <div>
              <p className="text-sm text-amber-400 font-medium">Connection Issue</p>
              <p className="text-xs text-muted-foreground">
                Unable to connect to MarketMate API. Retrying automatically.
              </p>
            </div>
          </div>
        )}

        {/* Signals grid — only show when authenticated */}
        {needsAuth ? (
          <div className="text-center py-16 bg-secondary/30 rounded-lg border border-border">
            <div className="w-12 h-12 rounded-full bg-secondary border border-border flex items-center justify-center mx-auto mb-4">
              <Lock className="w-6 h-6 text-muted-foreground" />
            </div>
            <p className="text-muted-foreground text-sm">
              Sign in to view active signals
            </p>
            <p className="text-xs text-muted-foreground/60 mt-1">
              Real-time signals are published during London and NY sessions
            </p>
            <Link
              href="/login"
              className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
            >
              Sign In to Continue
            </Link>
          </div>
        ) : trades.length > 0 ? (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {trades.map((signal) => (
              <SignalCard key={signal.signal_id || signal.id} signal={signal} />
            ))}
          </div>
        ) : (
          <div className="text-center py-16 bg-secondary/30 rounded-lg border border-border">
            <div className="w-12 h-12 rounded-full bg-secondary border border-border flex items-center justify-center mx-auto mb-4">
              <Clock className="w-6 h-6 text-muted-foreground" />
            </div>
            <p className="text-muted-foreground text-sm">
              {isLoading ? "Loading signals..." : "No active signals at the moment"}
            </p>
            <p className="text-xs text-muted-foreground/60 mt-1">
              Signals are published during London and NY sessions
            </p>
          </div>
        )}

        {/* Active count */}
        {count > 0 && !needsAuth && (
          <div className="mt-6 text-center">
            <span className="text-xs text-muted-foreground">
              {count} active signal{count !== 1 ? "s" : ""} being tracked
            </span>
          </div>
        )}
      </div>
    </section>
  )
}
