"use client"

import { useState } from "react"
import { Header } from "@/components/header"
import { Footer } from "@/components/footer"
import { Button } from "@/components/ui/button"
import {
  ChevronRight,
  Copy,
  Check,
  GitBranch,
  ArrowRight,
  ArrowUpRight,
  Plus,
  RefreshCcw,
  Wrench,
  AlertOctagon,
} from "lucide-react"
import Link from "next/link"

const sidebarSections = [
  { id: "v2.1.0", label: "v2.1.0 (Latest)", icon: GitBranch },
  { id: "v2.0.0", label: "v2.0.0", icon: GitBranch },
  { id: "v1.5.0", label: "v1.5.0", icon: GitBranch },
  { id: "migration-guides", label: "Migration Guides", icon: ArrowUpRight },
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

type ChangeType = "added" | "changed" | "fixed" | "deprecated"

interface Change {
  type: ChangeType
  description: string
}

interface Version {
  version: string
  date: string
  latest?: boolean
  changes: Record<ChangeType, Change[]>
}

const versions: Version[] = [
  {
    version: "2.1.0",
    date: "January 15, 2025",
    latest: true,
    changes: {
      added: [
        { type: "added", description: "WebSocket support for real-time market state streaming (state_change, sweep_detected, regime_shift events)" },
        { type: "added", description: "signal_opened and signal_closed WebSocket event types for live signal tracking" },
        { type: "added", description: "X-RateLimit-Reset header to all API responses for better rate limit management" },
        { type: "added", description: "Webhook delivery system with HMAC-SHA256 signature verification" },
        { type: "added", description: "Test API keys (mk_test_*) for sandbox development and integration testing" },
      ],
      changed: [
        { type: "changed", description: "Improved conviction scoring algorithm with multi-timeframe alignment weighting" },
        { type: "changed", description: "Market state responses now include trend.direction, trend.strength, and trend.timeframe fields" },
        { type: "changed", description: "Rate limits increased for Pro tier from 500 to 1,000 requests per minute" },
        { type: "changed", description: "Historical data endpoint now supports up to 168 hours (7 days) instead of 72 hours" },
      ],
      fixed: [
        { type: "fixed", description: "Resolved intermittent 503 errors on the /api/v1/signals endpoint during high-traffic periods" },
        { type: "fixed", description: "Fixed timezone handling in historical data responses to always use UTC" },
        { type: "fixed", description: "Corrected conviction filter case sensitivity in the signals endpoint" },
      ],
      deprecated: [
        { type: "deprecated", description: "The X-RateLimit-Window header is deprecated in favor of X-RateLimit-Reset. Will be removed in v3.0.0" },
      ],
    },
  },
  {
    version: "2.0.0",
    date: "October 8, 2024",
    changes: {
      added: [
        { type: "added", description: "Complete v1 REST API with four endpoints: market-state, signals, liquidity, historical" },
        { type: "added", description: "API key authentication with Bearer token scheme" },
        { type: "added", description: "Node.js/TypeScript SDK (@marketmate/sdk) with full type definitions" },
        { type: "added", description: "Python SDK (marketmate) with async and sync client support" },
        { type: "added", description: "Conviction levels (HIGH, MEDIUM, LOW) for signal filtering" },
        { type: "added", description: "Entry zones with low/high/mid bounds for precision signal entries" },
      ],
      changed: [
        { type: "changed", description: "Breaking: Replaced single entry_price with entry_zone object containing low, high, and mid fields" },
        { type: "changed", description: "Breaking: Regime values changed from snake_case to more descriptive names (e.g., trending_bullish instead of bullish)" },
        { type: "changed", description: "Breaking: Response format for /api/v1/signals now wraps signals in an object with count and timestamp" },
        { type: "changed", description: "Liquidity endpoint now includes sweeps array with recent sweep events" },
      ],
      fixed: [
        { type: "fixed", description: "Fixed memory leak in long-running signal tracking connections" },
        { type: "fixed", description: "Resolved issue where historical data could return gaps for low-activity symbols" },
      ],
      deprecated: [],
    },
  },
  {
    version: "1.5.0",
    date: "June 22, 2024",
    changes: {
      added: [
        { type: "added", description: "Historical data endpoint (/api/v1/historical) for backtesting and analysis" },
        { type: "added", description: "Support for XAU-USD (Gold) symbol across all endpoints" },
        { type: "added", description: "Rate limit headers (X-RateLimit-Limit, X-RateLimit-Remaining) on all responses" },
        { type: "added", description: "Dashboard API key management with create, view prefix, and revoke actions" },
      ],
      changed: [
        { type: "changed", description: "Improved market regime detection accuracy by 15% with enhanced feature engineering" },
        { type: "changed", description: "Liquidity scoring now accounts for order book depth in addition to volume" },
        { type: "changed", description: "Signal risk_reward ratios now calculated using entry zone mid instead of low/high" },
      ],
      fixed: [
        { type: "fixed", description: "Fixed 500 error when requesting signals for an unsupported symbol" },
        { type: "fixed", description: "Resolved CORS issues for browser-based API key verification" },
        { type: "fixed", description: "Corrected UTC offset in timestamps for markets in different timezones" },
      ],
      deprecated: [
        { type: "deprecated", description: "The /api/v1/state endpoint is deprecated. Use /api/v1/market-state instead. Will be removed in v3.0.0" },
      ],
    },
  },
]

const changeTypeConfig: Record<ChangeType, { icon: typeof Plus; color: string; bgColor: string; label: string }> = {
  added: { icon: Plus, color: "text-emerald-400", bgColor: "bg-emerald-500/10", label: "Added" },
  changed: { icon: RefreshCcw, color: "text-blue-400", bgColor: "bg-blue-500/10", label: "Changed" },
  fixed: { icon: Wrench, color: "text-amber-400", bgColor: "bg-amber-500/10", label: "Fixed" },
  deprecated: { icon: AlertOctagon, color: "text-red-400", bgColor: "bg-red-500/10", label: "Deprecated" },
}

export default function ChangelogPage() {
  const [activeSection, setActiveSection] = useState("v2.1.0")

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
            <span className="text-foreground">Changelog</span>
          </nav>

          {/* Header */}
          <div className="mb-12">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 rounded-lg bg-secondary">
                <GitBranch className="w-5 h-5 text-accent" />
              </div>
            </div>
            <h1 className="text-4xl md:text-5xl font-bold text-foreground mb-4">
              Changelog
            </h1>
            <p className="text-lg text-muted-foreground max-w-2xl">
              Track API updates, new features, bug fixes, and deprecations across MarketMate API versions.
            </p>
          </div>

          {/* Two-column layout */}
          <div className="flex gap-8">
            {/* Sidebar */}
            <aside className="hidden lg:block w-64 shrink-0">
              <div className="sticky top-32 space-y-1">
                <p className="px-3 text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">Versions</p>
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
                    {section.id === "v2.1.0" && (
                      <span className="px-1.5 py-0.5 text-xs font-medium bg-accent/20 text-accent rounded">New</span>
                    )}
                  </button>
                ))}

                <div className="pt-6 mt-6 border-t border-border">
                  <p className="px-3 text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">
                    Related
                  </p>
                  <Link
                    href="/developers/docs/getting-started"
                    className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
                  >
                    Getting Started
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
              {/* Version Sections */}
              {versions.map((version) => (
                <section key={version.version} id={`v${version.version}`}>
                  <div className="flex items-center gap-4 mb-6">
                    <span className="px-3 py-1 rounded-lg bg-secondary text-lg font-mono font-bold text-foreground">
                      v{version.version}
                    </span>
                    {version.latest && (
                      <span className="px-2 py-1 text-xs font-medium bg-accent/20 text-accent rounded">
                        Latest
                      </span>
                    )}
                    <span className="text-sm text-muted-foreground">{version.date}</span>
                  </div>

                  <div className="space-y-8">
                    {(Object.entries(version.changes) as [ChangeType, Change[]][]).map(
                      ([changeType, changes]) => {
                        if (changes.length === 0) return null
                        const config = changeTypeConfig[changeType]
                        const Icon = config.icon

                        return (
                          <div key={changeType}>
                            <div className="flex items-center gap-2 mb-4">
                              <div className={`p-1.5 rounded ${config.bgColor}`}>
                                <Icon className={`w-4 h-4 ${config.color}`} />
                              </div>
                              <h3 className="text-lg font-semibold text-foreground">{config.label}</h3>
                            </div>
                            <div className="space-y-3 ml-7">
                              {changes.map((change, idx) => (
                                <div
                                  key={idx}
                                  className="p-4 rounded-lg bg-card border border-border"
                                >
                                  <p className="text-sm text-muted-foreground">{change.description}</p>
                                </div>
                              ))}
                            </div>
                          </div>
                        )
                      }
                    )}
                  </div>
                </section>
              ))}

              {/* Migration Guides */}
              <section id="migration-guides">
                <h2 className="text-2xl font-bold text-foreground mb-4">Migration Guides</h2>
                <p className="text-muted-foreground mb-6">
                  Follow these guides when upgrading between major versions to handle breaking changes.
                </p>

                <div className="space-y-6">
                  <div className="p-6 rounded-xl bg-card border border-border">
                    <div className="flex items-center justify-between mb-4">
                      <div>
                        <h3 className="text-lg font-semibold text-foreground">Migrating from v1.x to v2.0</h3>
                        <p className="text-sm text-muted-foreground mt-1">Major breaking changes introduced in v2.0.0</p>
                      </div>
                      <span className="px-2 py-1 rounded bg-red-500/20 text-red-400 text-xs font-mono font-bold">Breaking</span>
                    </div>
                    
                    <div className="space-y-4">
                      <div>
                        <h4 className="text-sm font-semibold text-foreground mb-2">1. Replace entry_price with entry_zone</h4>
                        <p className="text-sm text-muted-foreground mb-3">
                          The <code className="px-1.5 py-0.5 rounded bg-secondary text-xs font-mono text-accent">entry_price</code> field has been replaced with an <code className="px-1.5 py-0.5 rounded bg-secondary text-xs font-mono text-accent">entry_zone</code> object:
                        </p>
                        <CodeBlock
                          filename="migration-entry.ts"
                          code={`// Before (v1.x)
const entryPrice = signal.entry_price;

// After (v2.0)
const entryZone = signal.entry_zone;
const midPrice = entryZone.mid;    // Most common replacement
const lowPrice = entryZone.low;    // Conservative entry
const highPrice = entryZone.high;  // Aggressive entry`}
                        />
                      </div>

                      <div>
                        <h4 className="text-sm font-semibold text-foreground mb-2">2. Update regime value handling</h4>
                        <p className="text-sm text-muted-foreground mb-3">
                          Regime values have been renamed to be more descriptive:
                        </p>
                        <CodeBlock
                          filename="migration-regime.ts"
                          code={`// Before (v1.x)          // After (v2.0)
"bullish"     →    "trending_bullish"
"bearish"     →    "trending_bearish"
"sideways"    →    "ranging"
"volatile"    →    "volatile" (unchanged)`}
                        />
                      </div>

                      <div>
                        <h4 className="text-sm font-semibold text-foreground mb-2">3. Update signals response handling</h4>
                        <p className="text-sm text-muted-foreground mb-3">
                          The signals endpoint now returns a wrapper object instead of a bare array:
                        </p>
                        <CodeBlock
                          filename="migration-signals.ts"
                          code={`// Before (v1.x)
const signals = await response.json();

// After (v2.0)
const { signals, count, timestamp } = await response.json();`}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="p-6 rounded-xl bg-card border border-border">
                    <div className="flex items-center justify-between mb-4">
                      <div>
                        <h3 className="text-lg font-semibold text-foreground">Upgrading to v2.1</h3>
                        <p className="text-sm text-muted-foreground mt-1">No breaking changes. New features are additive.</p>
                      </div>
                      <span className="px-2 py-1 rounded bg-emerald-500/20 text-emerald-400 text-xs font-mono font-bold">Non-Breaking</span>
                    </div>
                    
                    <div className="space-y-4">
                      <div>
                        <h4 className="text-sm font-semibold text-foreground mb-2">1. Adopt WebSocket streaming (optional)</h4>
                        <p className="text-sm text-muted-foreground mb-3">
                          v2.1 adds WebSocket support, but you can continue using REST API polling if preferred. See the <Link href="/developers/docs/websocket" className="text-accent hover:underline">WebSocket Events</Link> guide for setup instructions.
                        </p>
                      </div>

                      <div>
                        <h4 className="text-sm font-semibold text-foreground mb-2">2. Replace X-RateLimit-Window usage</h4>
                        <p className="text-sm text-muted-foreground mb-3">
                          The <code className="px-1.5 py-0.5 rounded bg-secondary text-xs font-mono text-accent">X-RateLimit-Window</code> header is deprecated. Use <code className="px-1.5 py-0.5 rounded bg-secondary text-xs font-mono text-accent">X-RateLimit-Reset</code> instead:
                        </p>
                        <CodeBlock
                          filename="migration-ratelimit.ts"
                          code={`// Before (v2.0)
const window = response.headers.get('X-RateLimit-Window');

// After (v2.1)
const resetAt = response.headers.get('X-RateLimit-Reset');
const retryAfter = Math.max(0, parseInt(resetAt) - Math.floor(Date.now() / 1000));`}
                        />
                      </div>

                      <div>
                        <h4 className="text-sm font-semibold text-foreground mb-2">3. Start using test keys (recommended)</h4>
                        <p className="text-sm text-muted-foreground mb-3">
                          Create test keys (<code className="px-1.5 py-0.5 rounded bg-secondary text-xs font-mono text-accent">mk_test_*</code>) for development and CI/CD pipelines. They don&apos;t count against rate limits or billing.
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="p-4 rounded-lg bg-accent/10 border border-accent/20">
                    <p className="text-sm text-foreground">
                      <strong>Need help migrating?</strong> If you encounter issues during migration, check the <Link href="/developers/docs/authentication" className="text-accent hover:underline">Authentication</Link> guide or reach out to our developer support team for assistance.
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
