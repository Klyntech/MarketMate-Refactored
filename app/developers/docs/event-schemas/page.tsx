"use client"

import { useState } from "react"
import { Header } from "@/components/header"
import { Footer } from "@/components/footer"
import { Button } from "@/components/ui/button"
import {
  ChevronRight,
  Copy,
  Check,
  Database,
  BarChart3,
  Zap,
  AlertTriangle,
  Webhook,
  ArrowRight,
} from "lucide-react"
import Link from "next/link"

const sidebarSections = [
  { id: "state-objects", label: "State Objects", icon: BarChart3 },
  { id: "signal-payloads", label: "Signal Payloads", icon: Zap },
  { id: "error-responses", label: "Error Responses", icon: AlertTriangle },
  { id: "webhook-payloads", label: "Webhook Payloads", icon: Webhook },
]

function CodeBlock({ filename, code }: { filename: string; code: string }) {
  const [copied, setCopied] = useState(false)

  const copyCode = () => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="rounded-xl bg-background border border-border overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-secondary/50">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-destructive/50" />
          <div className="w-3 h-3 rounded-full bg-chart-3/50" />
          <div className="w-3 h-3 rounded-full bg-chart-2/50" />
          <span className="ml-3 text-sm text-muted-foreground">{filename}</span>
        </div>
        <Button size="sm" variant="ghost" onClick={copyCode} className="text-muted-foreground hover:text-foreground">
          {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
        </Button>
      </div>
      <pre className="p-6 overflow-x-auto text-sm">
        <code className="text-muted-foreground font-mono whitespace-pre">{code}</code>
      </pre>
    </div>
  )
}

function SchemaTable({ fields }: { fields: { name: string; type: string; required: boolean; description: string }[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full">
        <thead>
          <tr className="border-b border-border bg-secondary/50">
            <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Field</th>
            <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Type</th>
            <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Required</th>
            <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Description</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {fields.map((field) => (
            <tr key={field.name} className="hover:bg-card/50 transition-colors">
              <td className="px-4 py-3 text-sm font-mono text-accent">{field.name}</td>
              <td className="px-4 py-3 text-sm text-muted-foreground">{field.type}</td>
              <td className="px-4 py-3 text-sm">
                {field.required ? (
                  <span className="px-2 py-0.5 rounded bg-accent/20 text-accent text-xs font-medium">Required</span>
                ) : (
                  <span className="px-2 py-0.5 rounded bg-secondary text-muted-foreground text-xs font-medium">Optional</span>
                )}
              </td>
              <td className="px-4 py-3 text-sm text-muted-foreground">{field.description}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function EventSchemasPage() {
  const [activeSection, setActiveSection] = useState("state-objects")

  const scrollToSection = (id: string) => {
    setActiveSection(id)
    const el = document.getElementById(id)
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" })
  }

  return (
    <main className="min-h-screen bg-background">
      <Header />

      <div className="pt-32 pb-24">
        <div className="mx-auto max-w-7xl px-6 lg:px-8">
          {/* Breadcrumb */}
          <nav className="flex items-center gap-2 text-sm text-muted-foreground mb-8">
            <Link href="/developers" className="hover:text-foreground transition-colors">
              Developers
            </Link>
            <ChevronRight className="w-4 h-4" />
            <Link href="/developers#documentation" className="hover:text-foreground transition-colors">
              Documentation
            </Link>
            <ChevronRight className="w-4 h-4" />
            <span className="text-foreground">Event Schemas</span>
          </nav>

          {/* Header */}
          <div className="mb-12">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 rounded-lg bg-secondary">
                <Database className="w-5 h-5 text-accent" />
              </div>
            </div>
            <h1 className="text-4xl md:text-5xl font-bold text-foreground mb-4">
              Event Schemas
            </h1>
            <p className="text-lg text-muted-foreground max-w-2xl">
              Detailed data structures and type definitions for all MarketMate events, responses, and webhook payloads.
            </p>
          </div>

          {/* Two-column layout */}
          <div className="flex gap-8">
            {/* Sidebar */}
            <aside className="hidden lg:block w-64 shrink-0">
              <div className="sticky top-32 space-y-1">
                {sidebarSections.map((section) => (
                  <button
                    key={section.id}
                    onClick={() => scrollToSection(section.id)}
                    className={`flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm text-left transition-colors ${
                      activeSection === section.id
                        ? "bg-secondary text-foreground"
                        : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"
                    }`}
                  >
                    <section.icon className="w-4 h-4 shrink-0" />
                    {section.label}
                  </button>
                ))}

                <div className="pt-6 mt-6 border-t border-border">
                  <p className="px-3 text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">
                    Related
                  </p>
                  <Link
                    href="/developers/docs/websocket"
                    className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
                  >
                    WebSocket Events
                    <ArrowRight className="w-3 h-3" />
                  </Link>
                  <Link
                    href="/developers/docs/api-reference"
                    className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
                  >
                    API Reference
                    <ArrowRight className="w-3 h-3" />
                  </Link>
                </div>
              </div>
            </aside>

            {/* Main Content */}
            <div className="flex-1 min-w-0 space-y-16">
              {/* State Objects */}
              <section id="state-objects">
                <h2 className="text-2xl font-bold text-foreground mb-4">State Objects</h2>
                <p className="text-muted-foreground mb-6">
                  The market state object is the core data structure returned by the Market State API and emitted via <code className="px-1.5 py-0.5 rounded bg-secondary text-xs font-mono text-accent">state_change</code> WebSocket events.
                </p>

                <div className="space-y-6">
                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">MarketState</h3>
                    <SchemaTable
                      fields={[
                        { name: "symbol", type: "string", required: true, description: "Trading pair symbol (e.g., BTC-USD, ETH-USD)" },
                        { name: "regime", type: "string", required: true, description: 'Current market regime: "trending_bullish", "trending_bearish", "ranging", "volatile"' },
                        { name: "conviction", type: "number", required: true, description: "Market conviction score from 0 to 1 (higher = stronger directional bias)" },
                        { name: "volatility", type: "string", required: true, description: 'Volatility level: "low", "normal", "elevated", "extreme"' },
                        { name: "liquidity", type: "number", required: true, description: "Liquidity score from 0 to 1 (higher = more liquid)" },
                        { name: "key_levels", type: "object", required: true, description: "Key support and resistance levels (see KeyLevels schema)" },
                        { name: "trend", type: "object", required: true, description: "Current trend information (see Trend schema)" },
                        { name: "updated_at", type: "string", required: true, description: "ISO 8601 timestamp of the last update" },
                      ]}
                    />
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">KeyLevels</h3>
                    <SchemaTable
                      fields={[
                        { name: "support", type: "number[]", required: true, description: "Array of support price levels, ordered by proximity to current price" },
                        { name: "resistance", type: "number[]", required: true, description: "Array of resistance price levels, ordered by proximity to current price" },
                      ]}
                    />
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">Trend</h3>
                    <SchemaTable
                      fields={[
                        { name: "direction", type: "string", required: true, description: 'Trend direction: "bullish", "bearish", "neutral"' },
                        { name: "strength", type: "number", required: true, description: "Trend strength from 0 to 1" },
                        { name: "timeframe", type: "string", required: true, description: "Primary timeframe for trend detection (e.g., 4H, 1D)" },
                      ]}
                    />
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">Example Object</h3>
                    <CodeBlock
                      filename="market-state.json"
                      code={`{
  "symbol": "BTC-USD",
  "regime": "trending_bullish",
  "conviction": 0.82,
  "volatility": "elevated",
  "liquidity": 0.76,
  "key_levels": {
    "support": [67850, 67200, 66500],
    "resistance": [69500, 70200, 71500]
  },
  "trend": {
    "direction": "bullish",
    "strength": 0.74,
    "timeframe": "4H"
  },
  "updated_at": "2024-01-15T10:30:00Z"
}`}
                    />
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">LiquidityState</h3>
                    <SchemaTable
                      fields={[
                        { name: "symbol", type: "string", required: true, description: "Trading pair symbol" },
                        { name: "score", type: "number", required: true, description: "Overall liquidity score from 0 to 1" },
                        { name: "pools", type: "LiquidityPool[]", required: true, description: "Array of liquidity pool objects" },
                        { name: "sweeps", type: "LiquiditySweep[]", required: true, description: "Array of recent liquidity sweep events" },
                        { name: "updated_at", type: "string", required: true, description: "ISO 8601 timestamp of last update" },
                      ]}
                    />
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">LiquidityPool</h3>
                    <SchemaTable
                      fields={[
                        { name: "level", type: "number", required: true, description: "Price level of the liquidity pool" },
                        { name: "type", type: "string", required: true, description: 'Pool type: "demand" or "supply"' },
                        { name: "strength", type: "number", required: true, description: "Pool strength from 0 to 1" },
                        { name: "volume", type: "string", required: true, description: "Estimated volume at this level (e.g., 24.5 BTC)" },
                      ]}
                    />
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">LiquiditySweep</h3>
                    <SchemaTable
                      fields={[
                        { name: "level", type: "number", required: true, description: "Price level that was swept" },
                        { name: "direction", type: "string", required: true, description: 'Sweep direction: "bullish" or "bearish"' },
                        { name: "swept_at", type: "string", required: true, description: "ISO 8601 timestamp of when the sweep occurred" },
                        { name: "volume", type: "string", required: true, description: "Volume swept through the level" },
                      ]}
                    />
                  </div>
                </div>
              </section>

              {/* Signal Payloads */}
              <section id="signal-payloads">
                <h2 className="text-2xl font-bold text-foreground mb-4">Signal Payloads</h2>
                <p className="text-muted-foreground mb-6">
                  Signal payloads are returned by the Signals API and emitted via <code className="px-1.5 py-0.5 rounded bg-secondary text-xs font-mono text-accent">signal_opened</code> and <code className="px-1.5 py-0.5 rounded bg-secondary text-xs font-mono text-accent">signal_closed</code> WebSocket events.
                </p>

                <div className="space-y-6">
                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">Signal</h3>
                    <SchemaTable
                      fields={[
                        { name: "signal_id", type: "string", required: true, description: "Unique signal identifier (e.g., sig_550e8400)" },
                        { name: "symbol", type: "string", required: true, description: "Trading pair symbol" },
                        { name: "direction", type: "string", required: true, description: 'Trade direction: "LONG" or "SHORT"' },
                        { name: "entry_zone", type: "object", required: true, description: "Entry zone bounds (see EntryZone schema)" },
                        { name: "stop_loss", type: "number", required: true, description: "Stop loss price level" },
                        { name: "take_profit_1", type: "number", required: true, description: "First take profit level" },
                        { name: "take_profit_2", type: "number | null", required: false, description: "Second take profit level" },
                        { name: "take_profit_3", type: "number | null", required: false, description: "Third take profit level" },
                        { name: "risk_reward", type: "number", required: true, description: "Risk-to-reward ratio" },
                        { name: "conviction", type: "string", required: true, description: 'Conviction level: "HIGH", "MEDIUM", or "LOW"' },
                        { name: "zone_type", type: "string", required: true, description: 'Zone type: "demand_zone", "supply_zone", "liquidity_pool"' },
                        { name: "confirmation", type: "string", required: true, description: 'Confirmation type: "order_block", "fair_value_gap", "break_of_structure"' },
                        { name: "status", type: "string", required: true, description: 'Signal status: "ACTIVE", "CLOSED", "CANCELLED", "EXPIRED"' },
                        { name: "created_at", type: "string", required: true, description: "ISO 8601 timestamp of signal creation" },
                      ]}
                    />
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">EntryZone</h3>
                    <SchemaTable
                      fields={[
                        { name: "low", type: "number", required: true, description: "Lower bound of the entry zone" },
                        { name: "high", type: "number", required: true, description: "Upper bound of the entry zone" },
                        { name: "mid", type: "number", required: true, description: "Midpoint of the entry zone" },
                      ]}
                    />
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">SignalsResponse</h3>
                    <SchemaTable
                      fields={[
                        { name: "signals", type: "Signal[]", required: true, description: "Array of signal objects" },
                        { name: "count", type: "number", required: true, description: "Number of signals in the response" },
                        { name: "timestamp", type: "string", required: true, description: "ISO 8601 timestamp of the response" },
                      ]}
                    />
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">Example Signal Object</h3>
                    <CodeBlock
                      filename="signal.json"
                      code={`{
  "signal_id": "sig_550e8400",
  "symbol": "BTC-USD",
  "direction": "LONG",
  "entry_zone": {
    "low": 67850,
    "high": 68200,
    "mid": 68025
  },
  "stop_loss": 67100,
  "take_profit_1": 69500,
  "take_profit_2": 71000,
  "take_profit_3": 72800,
  "risk_reward": 3.2,
  "conviction": "HIGH",
  "zone_type": "demand_zone",
  "confirmation": "order_block",
  "status": "ACTIVE",
  "created_at": "2024-01-15T09:30:00Z"
}`}
                    />
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">HistoricalState</h3>
                    <SchemaTable
                      fields={[
                        { name: "timestamp", type: "string", required: true, description: "ISO 8601 timestamp for this data point" },
                        { name: "regime", type: "string", required: true, description: "Market regime at this point in time" },
                        { name: "conviction", type: "number", required: true, description: "Conviction score at this point in time" },
                        { name: "volatility", type: "string", required: true, description: "Volatility level at this point in time" },
                        { name: "liquidity_score", type: "number", required: true, description: "Liquidity score at this point in time" },
                      ]}
                    />
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">HistoricalResponse</h3>
                    <SchemaTable
                      fields={[
                        { name: "symbol", type: "string", required: true, description: "Trading pair symbol" },
                        { name: "interval", type: "string", required: true, description: "Data interval used (e.g., 1h, 4h, 1d)" },
                        { name: "data", type: "HistoricalState[]", required: true, description: "Array of historical state data points" },
                        { name: "count", type: "number", required: true, description: "Number of data points in the response" },
                        { name: "timestamp", type: "string", required: true, description: "ISO 8601 timestamp of the response" },
                      ]}
                    />
                  </div>
                </div>
              </section>

              {/* Error Responses */}
              <section id="error-responses">
                <h2 className="text-2xl font-bold text-foreground mb-4">Error Responses</h2>
                <p className="text-muted-foreground mb-6">
                  All API errors follow a consistent structure, making it easy to handle errors programmatically.
                </p>

                <div className="space-y-6">
                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">ErrorEnvelope</h3>
                    <SchemaTable
                      fields={[
                        { name: "error", type: "string", required: true, description: "Machine-readable error code (e.g., rate_limit_exceeded, unauthorized)" },
                        { name: "message", type: "string", required: true, description: "Human-readable error description with actionable guidance" },
                        { name: "retry_after", type: "number", required: false, description: "Seconds until the request can be retried (only for 429 errors)" },
                        { name: "details", type: "object", required: false, description: "Additional error details for validation errors" },
                      ]}
                    />
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">Common Error Codes</h3>
                    <div className="overflow-x-auto rounded-lg border border-border">
                      <table className="w-full">
                        <thead>
                          <tr className="border-b border-border bg-secondary/50">
                            <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">HTTP Status</th>
                            <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Error Code</th>
                            <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Description</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border">
                          <tr className="hover:bg-card/50 transition-colors">
                            <td className="px-4 py-3 text-sm"><span className="px-2 py-0.5 rounded bg-red-500/20 text-red-400 text-xs font-mono font-bold">401</span></td>
                            <td className="px-4 py-3 text-sm font-mono text-accent">unauthorized</td>
                            <td className="px-4 py-3 text-sm text-muted-foreground">Missing or invalid API key</td>
                          </tr>
                          <tr className="hover:bg-card/50 transition-colors">
                            <td className="px-4 py-3 text-sm"><span className="px-2 py-0.5 rounded bg-red-500/20 text-red-400 text-xs font-mono font-bold">401</span></td>
                            <td className="px-4 py-3 text-sm font-mono text-accent">revoked_key</td>
                            <td className="px-4 py-3 text-sm text-muted-foreground">API key has been revoked</td>
                          </tr>
                          <tr className="hover:bg-card/50 transition-colors">
                            <td className="px-4 py-3 text-sm"><span className="px-2 py-0.5 rounded bg-red-500/20 text-red-400 text-xs font-mono font-bold">400</span></td>
                            <td className="px-4 py-3 text-sm font-mono text-accent">bad_request</td>
                            <td className="px-4 py-3 text-sm text-muted-foreground">Invalid request parameters</td>
                          </tr>
                          <tr className="hover:bg-card/50 transition-colors">
                            <td className="px-4 py-3 text-sm"><span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-400 text-xs font-mono font-bold">429</span></td>
                            <td className="px-4 py-3 text-sm font-mono text-accent">rate_limit_exceeded</td>
                            <td className="px-4 py-3 text-sm text-muted-foreground">Too many requests per time window</td>
                          </tr>
                          <tr className="hover:bg-card/50 transition-colors">
                            <td className="px-4 py-3 text-sm"><span className="px-2 py-0.5 rounded bg-red-500/20 text-red-400 text-xs font-mono font-bold">500</span></td>
                            <td className="px-4 py-3 text-sm font-mono text-accent">internal_error</td>
                            <td className="px-4 py-3 text-sm text-muted-foreground">Unexpected server error</td>
                          </tr>
                          <tr className="hover:bg-card/50 transition-colors">
                            <td className="px-4 py-3 text-sm"><span className="px-2 py-0.5 rounded bg-red-500/20 text-red-400 text-xs font-mono font-bold">503</span></td>
                            <td className="px-4 py-3 text-sm font-mono text-accent">service_unavailable</td>
                            <td className="px-4 py-3 text-sm text-muted-foreground">Service temporarily unavailable</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">Example Error Responses</h3>
                    <CodeBlock
                      filename="401-error.json"
                      code={`{
  "error": "Unauthorized",
  "message": "API key required. Include Authorization: Bearer <your-api-key> header."
}`}
                    />
                    <div className="mt-4">
                      <CodeBlock
                        filename="429-error.json"
                        code={`{
  "error": "rate_limit_exceeded",
  "message": "Rate limit of 100 requests per minute exceeded. Retry after 45 seconds.",
  "retry_after": 45
}`}
                      />
                    </div>
                    <div className="mt-4">
                      <CodeBlock
                        filename="400-error.json"
                        code={`{
  "error": "bad_request",
  "message": "Invalid parameter value.",
  "details": {
    "field": "hours",
    "constraint": "Must be between 1 and 168",
    "provided": 200
  }
}`}
                      />
                    </div>
                  </div>
                </div>
              </section>

              {/* Webhook Payloads */}
              <section id="webhook-payloads">
                <h2 className="text-2xl font-bold text-foreground mb-4">Webhook Payloads</h2>
                <p className="text-muted-foreground mb-6">
                  Webhook deliveries include event data wrapped in a standard envelope with metadata for verification and processing.
                </p>

                <div className="space-y-6">
                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">WebhookEnvelope</h3>
                    <SchemaTable
                      fields={[
                        { name: "id", type: "string", required: true, description: "Unique delivery ID for this webhook event" },
                        { name: "type", type: "string", required: true, description: "Event type (e.g., signal_opened, regime_shift, high_conviction_signal)" },
                        { name: "timestamp", type: "string", required: true, description: "ISO 8601 timestamp of when the event occurred" },
                        { name: "data", type: "object", required: true, description: "Event-specific payload data (varies by type)" },
                        { name: "delivery_attempt", type: "number", required: true, description: "Current delivery attempt number (starts at 1)" },
                      ]}
                    />
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">Webhook Headers</h3>
                    <p className="text-muted-foreground mb-3">
                      Each webhook delivery includes these HTTP headers for verification:
                    </p>
                    <SchemaTable
                      fields={[
                        { name: "X-MarketMate-Signature", type: "string", required: true, description: "HMAC-SHA256 signature of the payload body using your webhook secret" },
                        { name: "X-MarketMate-Delivery", type: "string", required: true, description: "Unique delivery ID matching the payload id field" },
                        { name: "X-MarketMate-Event", type: "string", required: true, description: "Event type matching the payload type field" },
                        { name: "Content-Type", type: "string", required: true, description: 'Always "application/json"' },
                      ]}
                    />
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">Example Webhook Payload</h3>
                    <CodeBlock
                      filename="webhook-payload.json"
                      code={`{
  "id": "evt_abc123def456",
  "type": "high_conviction_signal",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "signal_id": "sig_550e8400",
    "symbol": "BTC-USD",
    "direction": "LONG",
    "conviction": "HIGH",
    "entry_zone": {
      "low": 67850,
      "high": 68200,
      "mid": 68025
    },
    "stop_loss": 67100,
    "take_profit_1": 69500,
    "risk_reward": 3.2,
    "zone_type": "demand_zone",
    "confirmation": "order_block"
  },
  "delivery_attempt": 1
}`}
                    />
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">Verifying Webhook Signatures</h3>
                    <p className="text-muted-foreground mb-3">
                      Always verify webhook signatures to ensure the payload was sent by MarketMate and not a third party:
                    </p>
                    <CodeBlock
                      filename="verify-webhook.ts"
                      code={`import crypto from 'crypto';

function verifyWebhookSignature(
  payload: string,
  signature: string,
  secret: string
): boolean {
  const expectedSignature = crypto
    .createHmac('sha256', secret)
    .update(payload)
    .digest('hex');

  return crypto.timingSafeEqual(
    Buffer.from(signature),
    Buffer.from(expectedSignature)
  );
}

// Usage in Next.js API route
export async function POST(request: Request) {
  const body = await request.text();
  const signature = request.headers.get('X-MarketMate-Signature');

  if (!signature || !verifyWebhookSignature(body, signature, process.env.WEBHOOK_SECRET!)) {
    return new Response('Invalid signature', { status: 401 });
  }

  const event = JSON.parse(body);
  // Process the event...
  return new Response('OK', { status: 200 });
}`}
                    />
                  </div>

                  <div className="p-4 rounded-lg bg-accent/10 border border-accent/20">
                    <p className="text-sm text-foreground">
                      <strong>Retry Policy:</strong> Failed webhook deliveries (non-2xx responses) are retried up to 5 times with exponential backoff: 1min, 5min, 30min, 2hr, 12hr.
                    </p>
                  </div>
                </div>
              </section>
            </div>
          </div>
        </div>
      </div>

      <Footer />
    </main>
  )
}
