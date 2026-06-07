"use client"

import { useState } from "react"
import { Header } from "@/components/header"
import { Footer } from "@/components/footer"
import { Button } from "@/components/ui/button"
import {
  ChevronRight,
  Copy,
  Check,
  FileText,
  ArrowRight,
  BarChart3,
  Zap,
  Droplets,
  Clock,
} from "lucide-react"
import Link from "next/link"

const sidebarEndpoints = [
  { id: "market-state", label: "Market State", icon: BarChart3, method: "GET" },
  { id: "signals", label: "Conviction Signals", icon: Zap, method: "GET" },
  { id: "liquidity", label: "Liquidity Analysis", icon: Droplets, method: "GET" },
  { id: "historical", label: "Historical Data", icon: Clock, method: "GET" },
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

function MethodBadge({ method }: { method: string }) {
  const colors: Record<string, string> = {
    GET: "bg-emerald-500/20 text-emerald-400",
    POST: "bg-blue-500/20 text-blue-400",
    PUT: "bg-amber-500/20 text-amber-400",
    DELETE: "bg-red-500/20 text-red-400",
  }
  return (
    <span className={`px-2 py-1 text-xs font-mono font-bold rounded ${colors[method] || "bg-secondary text-muted-foreground"}`}>
      {method}
    </span>
  )
}

function ParamTable({ params }: { params: { name: string; type: string; required: boolean; description: string }[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full">
        <thead>
          <tr className="border-b border-border bg-secondary/50">
            <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Parameter</th>
            <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Type</th>
            <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Required</th>
            <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Description</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {params.map((param) => (
            <tr key={param.name} className="hover:bg-card/50 transition-colors">
              <td className="px-4 py-3 text-sm font-mono text-accent">{param.name}</td>
              <td className="px-4 py-3 text-sm text-muted-foreground">{param.type}</td>
              <td className="px-4 py-3 text-sm">
                {param.required ? (
                  <span className="px-2 py-0.5 rounded bg-accent/20 text-accent text-xs font-medium">Required</span>
                ) : (
                  <span className="px-2 py-0.5 rounded bg-secondary text-muted-foreground text-xs font-medium">Optional</span>
                )}
              </td>
              <td className="px-4 py-3 text-sm text-muted-foreground">{param.description}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function ApiReferencePage() {
  const [activeSection, setActiveSection] = useState("market-state")

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
            <span className="text-foreground">API Reference</span>
          </nav>

          {/* Header */}
          <div className="mb-12">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 rounded-lg bg-secondary">
                <FileText className="w-5 h-5 text-accent" />
              </div>
              <span className="px-2 py-1 rounded bg-accent/20 text-accent text-xs font-medium">v1</span>
            </div>
            <h1 className="text-4xl md:text-5xl font-bold text-foreground mb-4">
              API Reference
            </h1>
            <p className="text-lg text-muted-foreground max-w-2xl">
              Complete documentation for all MarketMate API v1 endpoints. All endpoints require authentication via API key.
            </p>
          </div>

          {/* Base URL */}
          <div className="mb-12 p-6 rounded-xl bg-card border border-border">
            <h3 className="text-lg font-semibold text-foreground mb-2">Base URL</h3>
            <code className="px-3 py-1.5 rounded bg-secondary text-sm font-mono text-accent">
              https://marketmate-website.onrender.com/api/v1
            </code>
          </div>

          {/* Two-column layout */}
          <div className="flex gap-8">
            {/* Sidebar */}
            <aside className="hidden lg:block w-64 shrink-0">
              <div className="sticky top-32 space-y-1">
                <p className="px-3 text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">Endpoints</p>
                {sidebarEndpoints.map((endpoint) => (
                  <button
                    key={endpoint.id}
                    onClick={() => scrollToSection(endpoint.id)}
                    className={`flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm text-left transition-colors ${
                      activeSection === endpoint.id
                        ? "bg-secondary text-foreground"
                        : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"
                    }`}
                  >
                    <endpoint.icon className="w-4 h-4 shrink-0" />
                    {endpoint.label}
                  </button>
                ))}

                <div className="pt-6 mt-6 border-t border-border">
                  <p className="px-3 text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">Related</p>
                  <Link
                    href="/developers/docs/authentication"
                    className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
                  >
                    Authentication
                    <ArrowRight className="w-3 h-3" />
                  </Link>
                  <Link
                    href="/developers/docs/event-schemas"
                    className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
                  >
                    Event Schemas
                    <ArrowRight className="w-3 h-3" />
                  </Link>
                </div>
              </div>
            </aside>

            {/* Main Content */}
            <div className="flex-1 min-w-0 space-y-16">
              {/* Market State */}
              <section id="market-state">
                <div className="flex items-center gap-3 mb-6">
                  <MethodBadge method="GET" />
                  <code className="text-lg font-mono text-foreground">/api/v1/market-state</code>
                </div>
                <p className="text-muted-foreground mb-6">
                  Retrieve the current market state for a given symbol, including regime, conviction score, volatility, liquidity, key levels, and trend information.
                </p>

                <h3 className="text-lg font-semibold text-foreground mb-3">Parameters</h3>
                <div className="mb-6">
                  <ParamTable
                    params={[
                      { name: "symbol", type: "string", required: false, description: 'Trading pair symbol. Defaults to "BTC-USD". Supported: BTC-USD, ETH-USD, XAU-USD' },
                    ]}
                  />
                </div>

                <h3 className="text-lg font-semibold text-foreground mb-3">Example Request</h3>
                <div className="space-y-4 mb-6">
                  <CodeBlock
                    filename="cURL"
                    code={`curl -X GET \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  "https://marketmate-website.onrender.com/api/v1/market-state?symbol=BTC-USD"`}
                  />
                  <CodeBlock
                    filename="sdk.ts"
                    code={`import { MarketMate } from '@marketmate/sdk';

const client = new MarketMate({ apiKey: process.env.MARKETMATE_API_KEY });
const state = await client.getState('BTC-USD');`}
                  />
                </div>

                <h3 className="text-lg font-semibold text-foreground mb-3">Example Response</h3>
                <div className="mb-6">
                  <CodeBlock
                    filename="response.json"
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

                <h3 className="text-lg font-semibold text-foreground mb-3">Error Responses</h3>
                <div className="space-y-3">
                  <div className="p-4 rounded-lg border border-border bg-card">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="px-2 py-0.5 rounded bg-red-500/20 text-red-400 text-xs font-mono font-bold">401</span>
                      <span className="text-sm font-medium text-foreground">Unauthorized</span>
                    </div>
                    <p className="text-sm text-muted-foreground">Missing or invalid API key in the Authorization header.</p>
                  </div>
                  <div className="p-4 rounded-lg border border-border bg-card">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-400 text-xs font-mono font-bold">429</span>
                      <span className="text-sm font-medium text-foreground">Rate Limit Exceeded</span>
                    </div>
                    <p className="text-sm text-muted-foreground">Too many requests. Check the Retry-After header.</p>
                  </div>
                </div>
              </section>

              {/* Conviction Signals */}
              <section id="signals">
                <div className="flex items-center gap-3 mb-6">
                  <MethodBadge method="GET" />
                  <code className="text-lg font-mono text-foreground">/api/v1/signals</code>
                </div>
                <p className="text-muted-foreground mb-6">
                  Retrieve active conviction signals with entry zones, stop loss, take profit levels, risk/reward ratios, and confirmation types. Filter by symbol and conviction level.
                </p>

                <h3 className="text-lg font-semibold text-foreground mb-3">Parameters</h3>
                <div className="mb-6">
                  <ParamTable
                    params={[
                      { name: "symbol", type: "string", required: false, description: "Filter signals by trading pair symbol (e.g., BTC-USD, ETH-USD)" },
                      { name: "conviction", type: "string", required: false, description: 'Filter by conviction level. Values: "HIGH", "MEDIUM", "LOW"' },
                    ]}
                  />
                </div>

                <h3 className="text-lg font-semibold text-foreground mb-3">Example Request</h3>
                <div className="space-y-4 mb-6">
                  <CodeBlock
                    filename="cURL"
                    code={`curl -X GET \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  "https://marketmate-website.onrender.com/api/v1/signals?symbol=BTC-USD&conviction=HIGH"`}
                  />
                  <CodeBlock
                    filename="sdk.ts"
                    code={`import { MarketMate } from '@marketmate/sdk';

const client = new MarketMate({ apiKey: process.env.MARKETMATE_API_KEY });
const { signals } = await client.getSignals({
  symbol: 'BTC-USD',
  conviction: 'HIGH'
});`}
                  />
                </div>

                <h3 className="text-lg font-semibold text-foreground mb-3">Example Response</h3>
                <div className="mb-6">
                  <CodeBlock
                    filename="response.json"
                    code={`{
  "signals": [
    {
      "signal_id": "sig_550e8400",
      "symbol": "BTC-USD",
      "direction": "LONG",
      "entry_zone": { "low": 67850, "high": 68200, "mid": 68025 },
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
    }
  ],
  "count": 1,
  "timestamp": "2024-01-15T10:30:00Z"
}`}
                  />
                </div>

                <h3 className="text-lg font-semibold text-foreground mb-3">Error Responses</h3>
                <div className="space-y-3">
                  <div className="p-4 rounded-lg border border-border bg-card">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="px-2 py-0.5 rounded bg-red-500/20 text-red-400 text-xs font-mono font-bold">401</span>
                      <span className="text-sm font-medium text-foreground">Unauthorized</span>
                    </div>
                    <p className="text-sm text-muted-foreground">Missing or invalid API key.</p>
                  </div>
                  <div className="p-4 rounded-lg border border-border bg-card">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="px-2 py-0.5 rounded bg-red-500/20 text-red-400 text-xs font-mono font-bold">400</span>
                      <span className="text-sm font-medium text-foreground">Bad Request</span>
                    </div>
                    <p className="text-sm text-muted-foreground">Invalid conviction value. Must be HIGH, MEDIUM, or LOW.</p>
                  </div>
                </div>
              </section>

              {/* Liquidity Analysis */}
              <section id="liquidity">
                <div className="flex items-center gap-3 mb-6">
                  <MethodBadge method="GET" />
                  <code className="text-lg font-mono text-foreground">/api/v1/liquidity</code>
                </div>
                <p className="text-muted-foreground mb-6">
                  Retrieve current liquidity analysis including liquidity pools, strength scores, volume, and recent liquidity sweeps for the primary tracked symbol.
                </p>

                <h3 className="text-lg font-semibold text-foreground mb-3">Parameters</h3>
                <div className="mb-6">
                  <ParamTable
                    params={[
                      { name: "symbol", type: "string", required: false, description: 'Trading pair symbol. Defaults to "BTC-USD" if not provided.' },
                    ]}
                  />
                </div>

                <h3 className="text-lg font-semibold text-foreground mb-3">Example Request</h3>
                <div className="space-y-4 mb-6">
                  <CodeBlock
                    filename="cURL"
                    code={`curl -X GET \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  "https://marketmate-website.onrender.com/api/v1/liquidity"`}
                  />
                  <CodeBlock
                    filename="sdk.ts"
                    code={`import { MarketMate } from '@marketmate/sdk';

const client = new MarketMate({ apiKey: process.env.MARKETMATE_API_KEY });
const liquidity = await client.getLiquidity();`}
                  />
                </div>

                <h3 className="text-lg font-semibold text-foreground mb-3">Example Response</h3>
                <div className="mb-6">
                  <CodeBlock
                    filename="response.json"
                    code={`{
  "symbol": "BTC-USD",
  "score": 0.76,
  "pools": [
    { "level": 67850, "type": "demand", "strength": 0.85, "volume": "24.5 BTC" },
    { "level": 69500, "type": "supply", "strength": 0.72, "volume": "18.2 BTC" },
    { "level": 67200, "type": "demand", "strength": 0.68, "volume": "31.1 BTC" },
    { "level": 71000, "type": "supply", "strength": 0.61, "volume": "12.8 BTC" }
  ],
  "sweeps": [
    {
      "level": 67100,
      "direction": "bearish",
      "swept_at": "2024-01-14T10:30:00Z",
      "volume": "45.2 BTC"
    }
  ],
  "updated_at": "2024-01-15T10:30:00Z"
}`}
                  />
                </div>

                <h3 className="text-lg font-semibold text-foreground mb-3">Error Responses</h3>
                <div className="space-y-3">
                  <div className="p-4 rounded-lg border border-border bg-card">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="px-2 py-0.5 rounded bg-red-500/20 text-red-400 text-xs font-mono font-bold">401</span>
                      <span className="text-sm font-medium text-foreground">Unauthorized</span>
                    </div>
                    <p className="text-sm text-muted-foreground">Missing or invalid API key.</p>
                  </div>
                  <div className="p-4 rounded-lg border border-border bg-card">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-400 text-xs font-mono font-bold">429</span>
                      <span className="text-sm font-medium text-foreground">Rate Limit Exceeded</span>
                    </div>
                    <p className="text-sm text-muted-foreground">Too many requests. Retry after the period indicated in the response.</p>
                  </div>
                </div>
              </section>

              {/* Historical Data */}
              <section id="historical">
                <div className="flex items-center gap-3 mb-6">
                  <MethodBadge method="GET" />
                  <code className="text-lg font-mono text-foreground">/api/v1/historical</code>
                </div>
                <p className="text-muted-foreground mb-6">
                  Retrieve historical market state data for backtesting and analysis. Supports configurable time ranges up to 7 days with flexible intervals.
                </p>

                <h3 className="text-lg font-semibold text-foreground mb-3">Parameters</h3>
                <div className="mb-6">
                  <ParamTable
                    params={[
                      { name: "symbol", type: "string", required: false, description: 'Trading pair symbol. Defaults to "BTC-USD". Supported: BTC-USD, ETH-USD, XAU-USD' },
                      { name: "hours", type: "integer", required: false, description: "Number of hours of historical data to retrieve. Range: 1-168 (max 7 days). Default: 24" },
                      { name: "interval", type: "string", required: false, description: 'Data interval granularity. Values: "1m", "5m", "15m", "1h", "4h", "1d". Default: "1h"' },
                    ]}
                  />
                </div>

                <h3 className="text-lg font-semibold text-foreground mb-3">Example Request</h3>
                <div className="space-y-4 mb-6">
                  <CodeBlock
                    filename="cURL"
                    code={`curl -X GET \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  "https://marketmate-website.onrender.com/api/v1/historical?symbol=BTC-USD&hours=48&interval=1h"`}
                  />
                  <CodeBlock
                    filename="sdk.ts"
                    code={`import { MarketMate } from '@marketmate/sdk';

const client = new MarketMate({ apiKey: process.env.MARKETMATE_API_KEY });
const history = await client.getHistoricalStates('BTC-USD', {
  hours: 48,
  interval: '1h',
});`}
                  />
                </div>

                <h3 className="text-lg font-semibold text-foreground mb-3">Example Response</h3>
                <div className="mb-6">
                  <CodeBlock
                    filename="response.json"
                    code={`{
  "symbol": "BTC-USD",
  "interval": "1h",
  "data": [
    {
      "timestamp": "2024-01-13T10:30:00Z",
      "regime": "ranging",
      "conviction": 0.42,
      "volatility": "normal",
      "liquidity_score": 0.58
    },
    {
      "timestamp": "2024-01-13T11:30:00Z",
      "regime": "trending_bullish",
      "conviction": 0.67,
      "volatility": "elevated",
      "liquidity_score": 0.71
    }
  ],
  "count": 49,
  "timestamp": "2024-01-15T10:30:00Z"
}`}
                  />
                </div>

                <h3 className="text-lg font-semibold text-foreground mb-3">Error Responses</h3>
                <div className="space-y-3">
                  <div className="p-4 rounded-lg border border-border bg-card">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="px-2 py-0.5 rounded bg-red-500/20 text-red-400 text-xs font-mono font-bold">401</span>
                      <span className="text-sm font-medium text-foreground">Unauthorized</span>
                    </div>
                    <p className="text-sm text-muted-foreground">Missing or invalid API key.</p>
                  </div>
                  <div className="p-4 rounded-lg border border-border bg-card">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="px-2 py-0.5 rounded bg-red-500/20 text-red-400 text-xs font-mono font-bold">400</span>
                      <span className="text-sm font-medium text-foreground">Bad Request</span>
                    </div>
                    <p className="text-sm text-muted-foreground">Invalid hours parameter. Must be between 1 and 168.</p>
                  </div>
                  <div className="p-4 rounded-lg border border-border bg-card">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-400 text-xs font-mono font-bold">429</span>
                      <span className="text-sm font-medium text-foreground">Rate Limit Exceeded</span>
                    </div>
                    <p className="text-sm text-muted-foreground">Too many requests. Historical data requests count against your rate limit.</p>
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
