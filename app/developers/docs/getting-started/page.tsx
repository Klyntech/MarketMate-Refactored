"use client"

import { useState } from "react"
import { Header } from "@/components/header"
import { Footer } from "@/components/footer"
import { Button } from "@/components/ui/button"
import {
  ChevronRight,
  Copy,
  Check,
  BookOpen,
  Key,
  Zap,
  Clock,
  Terminal,
  Package,
  ArrowRight,
} from "lucide-react"
import Link from "next/link"

const sidebarSections = [
  { id: "installation", label: "Installation", icon: Package },
  { id: "authentication", label: "Authentication", icon: Key },
  { id: "first-request", label: "Your First Request", icon: Zap },
  { id: "rate-limits", label: "Rate Limits", icon: Clock },
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

export default function GettingStartedPage() {
  const [activeSection, setActiveSection] = useState("installation")

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
            <span className="text-foreground">Getting Started</span>
          </nav>

          {/* Header */}
          <div className="mb-12">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 rounded-lg bg-secondary">
                <BookOpen className="w-5 h-5 text-accent" />
              </div>
            </div>
            <h1 className="text-4xl md:text-5xl font-bold text-foreground mb-4">
              Getting Started
            </h1>
            <p className="text-lg text-muted-foreground max-w-2xl">
              Set up your development environment and make your first MarketMate API call in under 5 minutes.
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
                    Next Steps
                  </p>
                  <Link
                    href="/developers/docs/api-reference"
                    className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
                  >
                    API Reference
                    <ArrowRight className="w-3 h-3" />
                  </Link>
                  <Link
                    href="/developers/docs/authentication"
                    className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
                  >
                    Authentication
                    <ArrowRight className="w-3 h-3" />
                  </Link>
                  <Link
                    href="/developers/docs/websocket"
                    className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
                  >
                    WebSocket Events
                    <ArrowRight className="w-3 h-3" />
                  </Link>
                </div>
              </div>
            </aside>

            {/* Main Content */}
            <div className="flex-1 min-w-0 space-y-16">
              {/* Installation */}
              <section id="installation">
                <h2 className="text-2xl font-bold text-foreground mb-4">Installation</h2>
                <p className="text-muted-foreground mb-6">
                  Choose your preferred language and install the MarketMate SDK, or use the REST API directly with any HTTP client.
                </p>

                <div className="space-y-6">
                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">Node.js / TypeScript</h3>
                    <CodeBlock
                      filename="terminal"
                      code={`# Install the MarketMate SDK
npm install @marketmate/sdk

# Or with yarn
yarn add @marketmate/sdk

# Or with pnpm
pnpm add @marketmate/sdk`}
                    />
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">Python</h3>
                    <CodeBlock
                      filename="terminal"
                      code={`# Install the MarketMate Python client
pip install marketmate

# Or with poetry
poetry add marketmate`}
                    />
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">REST API (cURL)</h3>
                    <p className="text-muted-foreground mb-3">
                      No SDK needed. Use any HTTP client to make requests directly to the MarketMate API.
                    </p>
                    <CodeBlock
                      filename="terminal"
                      code={`# Test your API key
curl -H "Authorization: Bearer YOUR_API_KEY" \\
  "https://marketmate-website.onrender.com/api/v1/market-state?symbol=BTC-USD"`}
                    />
                  </div>

                  <div className="p-6 rounded-xl bg-card border border-border">
                    <h3 className="text-lg font-semibold text-foreground mb-2">SDK Features</h3>
                    <p className="text-muted-foreground mb-4">
                      Both SDKs provide type-safe access to all API endpoints, automatic retries, and WebSocket support out of the box.
                    </p>
                    <ul className="space-y-2 text-sm text-muted-foreground">
                      <li className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-accent" />
                        Full TypeScript type definitions
                      </li>
                      <li className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-accent" />
                        Automatic request retries with exponential backoff
                      </li>
                      <li className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-accent" />
                        Built-in WebSocket client for real-time streaming
                      </li>
                      <li className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-accent" />
                        Webhook signature verification helpers
                      </li>
                    </ul>
                  </div>
                </div>
              </section>

              {/* Authentication */}
              <section id="authentication">
                <h2 className="text-2xl font-bold text-foreground mb-4">Authentication</h2>
                <p className="text-muted-foreground mb-6">
                  All MarketMate API requests require an API key. You can create and manage your keys from the dashboard.
                </p>

                <div className="space-y-6">
                  <div className="p-6 rounded-xl bg-card border border-border">
                    <h3 className="text-lg font-semibold text-foreground mb-2">Get Your API Key</h3>
                    <p className="text-muted-foreground mb-4">
                      Navigate to the API Keys section in your dashboard to create a new key. Each key can be scoped to specific permissions and environments.
                    </p>
                    <Button asChild>
                      <Link href="/dashboard/api-keys">
                        <Key className="w-4 h-4 mr-2" />
                        Go to API Keys
                      </Link>
                    </Button>
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">Include Your API Key</h3>
                    <p className="text-muted-foreground mb-3">
                      Pass your API key in the <code className="px-1.5 py-0.5 rounded bg-secondary text-sm font-mono text-accent">Authorization</code> header using the Bearer token scheme:
                    </p>
                    <CodeBlock
                      filename="request-header"
                      code={`Authorization: Bearer mk_live_abc123def456ghi789`}
                    />
                  </div>

                  <div className="p-4 rounded-lg bg-accent/10 border border-accent/20">
                    <p className="text-sm text-foreground">
                      <strong>Important:</strong> Never expose your API key in client-side code or public repositories. 
                      Always use environment variables and server-side proxies in production.
                    </p>
                  </div>
                </div>
              </section>

              {/* Your First Request */}
              <section id="first-request">
                <h2 className="text-2xl font-bold text-foreground mb-4">Your First Request</h2>
                <p className="text-muted-foreground mb-6">
                  Let&apos;s make your first API call to get the current market state for Bitcoin.
                </p>

                <div className="space-y-6">
                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">Using Fetch (JavaScript)</h3>
                    <CodeBlock
                      filename="index.ts"
                      code={`const response = await fetch('https://marketmate-website.onrender.com/api/v1/market-state?symbol=BTC-USD', {
  headers: {
    'Authorization': 'Bearer YOUR_API_KEY'
  }
});

const data = await response.json();

console.log(data);
// {
//   symbol: "BTC-USD",
//   regime: "trending_bullish",
//   conviction: 0.82,
//   volatility: "elevated",
//   liquidity: 0.76,
//   key_levels: {
//     support: [67850, 67200, 66500],
//     resistance: [69500, 70200, 71500]
//   },
//   trend: {
//     direction: "bullish",
//     strength: 0.74,
//     timeframe: "4H"
//   },
//   updated_at: "2024-01-15T10:30:00Z"
// }`}
                    />
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">Using the SDK</h3>
                    <CodeBlock
                      filename="app.ts"
                      code={`import { MarketMate } from '@marketmate/sdk';

const client = new MarketMate({
  apiKey: process.env.MARKETMATE_API_KEY
});

// Get current market state
const state = await client.getState('BTC-USD');

console.log({
  regime: state.regime,           // "trending_bullish"
  conviction: state.conviction,   // 0.82
  volatility: state.volatility,   // "elevated"
  liquidityScore: state.liquidity // 0.76
});`}
                    />
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">Using Python</h3>
                    <CodeBlock
                      filename="main.py"
                      code={`import marketmate

client = marketmate.Client(api_key="YOUR_API_KEY")

# Get current market state
state = client.get_state("BTC-USD")

print(f"Regime: {state.regime}")
print(f"Conviction: {state.conviction}")
print(f"Volatility: {state.volatility}")`}
                    />
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">Using cURL</h3>
                    <CodeBlock
                      filename="terminal"
                      code={`curl -X GET \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  "https://marketmate-website.onrender.com/api/v1/market-state?symbol=BTC-USD"`}
                    />
                  </div>
                </div>
              </section>

              {/* Rate Limits */}
              <section id="rate-limits">
                <h2 className="text-2xl font-bold text-foreground mb-4">Rate Limits</h2>
                <p className="text-muted-foreground mb-6">
                  MarketMate enforces rate limits to ensure fair usage and API stability. Rate limits are applied per API key.
                </p>

                <div className="space-y-6">
                  <div className="overflow-x-auto rounded-lg border border-border">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b border-border bg-secondary/50">
                          <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Plan</th>
                          <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Requests / Minute</th>
                          <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Requests / Day</th>
                          <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">WebSocket Connections</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border">
                        <tr>
                          <td className="px-4 py-3 text-sm text-foreground">Free</td>
                          <td className="px-4 py-3 text-sm text-foreground">100</td>
                          <td className="px-4 py-3 text-sm text-foreground">10,000</td>
                          <td className="px-4 py-3 text-sm text-foreground">1</td>
                        </tr>
                        <tr>
                          <td className="px-4 py-3 text-sm text-foreground">Pro</td>
                          <td className="px-4 py-3 text-sm text-foreground">1,000</td>
                          <td className="px-4 py-3 text-sm text-foreground">100,000</td>
                          <td className="px-4 py-3 text-sm text-foreground">5</td>
                        </tr>
                        <tr>
                          <td className="px-4 py-3 text-sm text-foreground">Enterprise</td>
                          <td className="px-4 py-3 text-sm text-foreground">10,000</td>
                          <td className="px-4 py-3 text-sm text-foreground">Unlimited</td>
                          <td className="px-4 py-3 text-sm text-foreground">Unlimited</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">Rate Limit Headers</h3>
                    <p className="text-muted-foreground mb-3">
                      Every API response includes headers to help you track your usage:
                    </p>
                    <CodeBlock
                      filename="response-headers"
                      code={`X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1705312800`}
                    />
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">Handling Rate Limits</h3>
                    <p className="text-muted-foreground mb-3">
                      When you exceed your rate limit, the API returns a <code className="px-1.5 py-0.5 rounded bg-secondary text-sm font-mono text-accent">429 Too Many Requests</code> response:
                    </p>
                    <CodeBlock
                      filename="error-response.json"
                      code={`{
  "error": "rate_limit_exceeded",
  "message": "Rate limit of 100 requests per minute exceeded. Retry after 45 seconds.",
  "retry_after": 45
}`}
                    />
                  </div>

                  <div className="p-6 rounded-xl bg-card border border-border">
                    <h3 className="text-lg font-semibold text-foreground mb-2">Best Practices</h3>
                    <ul className="space-y-2 text-sm text-muted-foreground">
                      <li className="flex items-start gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-accent mt-1.5 shrink-0" />
                        Monitor the <code className="px-1 py-0.5 rounded bg-secondary text-xs font-mono text-accent">X-RateLimit-Remaining</code> header to avoid hitting limits
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-accent mt-1.5 shrink-0" />
                        Implement exponential backoff when receiving 429 responses
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-accent mt-1.5 shrink-0" />
                        Use WebSocket connections for real-time data instead of polling
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-accent mt-1.5 shrink-0" />
                        Cache responses when appropriate to reduce API calls
                      </li>
                    </ul>
                  </div>
                </div>
              </section>
            </div>
          </div>

          {/* Mobile sidebar toggle */}
          <div className="lg:hidden fixed bottom-6 right-6 z-50">
            <div className="flex flex-col gap-2 items-end">
              {sidebarSections.map((section) => (
                <button
                  key={section.id}
                  onClick={() => scrollToSection(section.id)}
                  className={`px-4 py-2 rounded-full text-sm font-medium shadow-lg transition-colors ${
                    activeSection === section.id
                      ? "bg-primary text-primary-foreground"
                      : "bg-card border border-border text-muted-foreground"
                  }`}
                >
                  {section.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      <Footer />
    </main>
  )
}
