"use client"

import { Header } from "@/components/header"
import { Footer } from "@/components/footer"
import { Button } from "@/components/ui/button"
import { 
  Copy, 
  Check, 
  ArrowLeft, 
  Terminal,
  Key,
  Globe,
  ChevronRight
} from "lucide-react"
import Link from "next/link"
import { useState } from "react"

const examples = [
  {
    category: "Health Check",
    commands: [
      {
        title: "Check API Status",
        description: "Verify the API is running and accessible",
        command: `http GET https://api.marketmate.io/health`,
      },
    ],
  },
  {
    category: "Authentication",
    commands: [
      {
        title: "Login",
        description: "Authenticate and receive session token",
        command: `http POST https://api.marketmate.io/auth/login \\
  email=user@example.com \\
  password=your_password`,
      },
      {
        title: "Get Current User",
        description: "Retrieve authenticated user profile",
        command: `http GET https://api.marketmate.io/auth/me \\
  Authorization:"Bearer $TOKEN"`,
      },
    ],
  },
  {
    category: "Signals",
    commands: [
      {
        title: "Get Open Signals",
        description: "Retrieve all currently active trading signals",
        command: `http GET https://api.marketmate.io/trades \\
  Authorization:"Bearer $TOKEN"`,
      },
      {
        title: "Get Signal by ID",
        description: "Retrieve a specific signal by its ID",
        command: `http GET https://api.marketmate.io/trades/sig_abc123 \\
  Authorization:"Bearer $TOKEN"`,
      },
      {
        title: "Get Performance Stats",
        description: "Retrieve 7-day and 30-day performance metrics",
        command: `http GET https://api.marketmate.io/performance \\
  Authorization:"Bearer $TOKEN"`,
      },
    ],
  },
  {
    category: "MATE AI",
    commands: [
      {
        title: "Query MATE Intelligence",
        description: "Ask MATE for market analysis or strategy insights",
        command: `http POST https://api.marketmate.io/api/mate \\
  Authorization:"Bearer $TOKEN" \\
  query="What is the current BTC market regime?" \\
  query_type=analysis`,
      },
    ],
  },
  {
    category: "Market Data",
    commands: [
      {
        title: "Get Market State",
        description: "Current regime, conviction, and volatility for a symbol",
        command: `http GET https://api.marketmate.io/market/state/BTC-USD \\
  Authorization:"Bearer $TOKEN"`,
      },
      {
        title: "Get Historical States",
        description: "Query historical market states with date range",
        command: `http GET https://api.marketmate.io/market/history/BTC-USD \\
  Authorization:"Bearer $TOKEN" \\
  start==2024-01-01 \\
  end==2024-01-15 \\
  interval==1h`,
      },
      {
        title: "Get Key Levels",
        description: "Support, resistance, and liquidity zones",
        command: `http GET https://api.marketmate.io/market/levels/BTC-USD \\
  Authorization:"Bearer $TOKEN"`,
      },
    ],
  },
]

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  
  const copy = () => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  
  return (
    <Button
      size="sm"
      variant="ghost"
      onClick={copy}
      className="text-muted-foreground hover:text-foreground"
    >
      {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
    </Button>
  )
}

export default function HTTPieExamplesPage() {
  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main className="pt-24 pb-16">
        <div className="mx-auto max-w-4xl px-6 lg:px-8">
          {/* Breadcrumb */}
          <div className="mb-8">
            <Link 
              href="/developers#resources" 
              className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to Developer Resources
            </Link>
          </div>

          {/* Header */}
          <div className="mb-12">
            <div className="flex items-center gap-4 mb-6">
              <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
                <Terminal className="w-8 h-8 text-emerald-500" />
              </div>
              <div>
                <h1 className="text-3xl md:text-4xl font-bold text-foreground">
                  HTTPie Examples
                </h1>
                <p className="text-muted-foreground mt-1">
                  Command-line examples for HTTPie users
                </p>
              </div>
            </div>

            <p className="text-muted-foreground mb-6 max-w-2xl">
              HTTPie is a user-friendly command-line HTTP client. These examples demonstrate 
              how to interact with the MarketMate API using clean, readable syntax.
            </p>

            <Button variant="outline" className="gap-2" asChild>
              <a href="https://httpie.io" target="_blank" rel="noopener noreferrer">
                <Terminal className="w-4 h-4" />
                Install HTTPie
              </a>
            </Button>
          </div>

          {/* Quick Setup */}
          <section className="mb-12">
            <h2 className="text-xl font-semibold text-foreground mb-4">Quick Setup</h2>
            <div className="space-y-4">
              <div className="p-4 rounded-lg bg-card border border-border">
                <div className="flex items-start gap-3">
                  <span className="flex items-center justify-center w-6 h-6 rounded-full bg-primary text-primary-foreground text-sm font-medium shrink-0">1</span>
                  <div className="flex-1">
                    <h3 className="font-medium text-foreground">Install HTTPie</h3>
                    <p className="text-sm text-muted-foreground mt-1 mb-3">
                      Install via your package manager or pip:
                    </p>
                    <div className="rounded-lg bg-secondary p-3 font-mono text-sm">
                      <span className="text-muted-foreground"># macOS</span><br />
                      brew install httpie<br /><br />
                      <span className="text-muted-foreground"># pip</span><br />
                      pip install httpie
                    </div>
                  </div>
                </div>
              </div>
              
              <div className="p-4 rounded-lg bg-card border border-border">
                <div className="flex items-start gap-3">
                  <span className="flex items-center justify-center w-6 h-6 rounded-full bg-primary text-primary-foreground text-sm font-medium shrink-0">2</span>
                  <div className="flex-1">
                    <h3 className="font-medium text-foreground">Set Up Environment Variable</h3>
                    <p className="text-sm text-muted-foreground mt-1 mb-3">
                      Export your token for easy reuse:
                    </p>
                    <div className="rounded-lg bg-secondary p-3 font-mono text-sm">
                      export TOKEN=&quot;your_api_token_here&quot;
                    </div>
                  </div>
                </div>
              </div>
              
              <div className="p-4 rounded-lg bg-card border border-border">
                <div className="flex items-start gap-3">
                  <span className="flex items-center justify-center w-6 h-6 rounded-full bg-primary text-primary-foreground text-sm font-medium shrink-0">3</span>
                  <div>
                    <h3 className="font-medium text-foreground">Start Making Requests</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      Copy any example below and run it in your terminal. HTTPie will format the JSON response automatically.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* HTTPie Syntax Guide */}
          <section className="mb-12">
            <h2 className="text-xl font-semibold text-foreground mb-4 flex items-center gap-2">
              <Key className="w-5 h-5 text-muted-foreground" />
              HTTPie Syntax Guide
            </h2>
            <div className="rounded-lg border border-border overflow-hidden">
              <table className="w-full">
                <thead className="bg-secondary">
                  <tr>
                    <th className="text-left text-sm font-medium text-foreground px-4 py-3">Syntax</th>
                    <th className="text-left text-sm font-medium text-foreground px-4 py-3">Meaning</th>
                    <th className="text-left text-sm font-medium text-foreground px-4 py-3 hidden md:table-cell">Example</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  <tr className="bg-card">
                    <td className="px-4 py-3"><code className="text-sm font-mono text-accent">:</code></td>
                    <td className="px-4 py-3 text-sm text-muted-foreground">HTTP header</td>
                    <td className="px-4 py-3 text-sm font-mono text-muted-foreground hidden md:table-cell">Authorization:Bearer token</td>
                  </tr>
                  <tr className="bg-card">
                    <td className="px-4 py-3"><code className="text-sm font-mono text-accent">=</code></td>
                    <td className="px-4 py-3 text-sm text-muted-foreground">JSON string field</td>
                    <td className="px-4 py-3 text-sm font-mono text-muted-foreground hidden md:table-cell">email=user@example.com</td>
                  </tr>
                  <tr className="bg-card">
                    <td className="px-4 py-3"><code className="text-sm font-mono text-accent">:=</code></td>
                    <td className="px-4 py-3 text-sm text-muted-foreground">Non-string JSON (number, bool)</td>
                    <td className="px-4 py-3 text-sm font-mono text-muted-foreground hidden md:table-cell">limit:=10</td>
                  </tr>
                  <tr className="bg-card">
                    <td className="px-4 py-3"><code className="text-sm font-mono text-accent">==</code></td>
                    <td className="px-4 py-3 text-sm text-muted-foreground">Query parameter</td>
                    <td className="px-4 py-3 text-sm font-mono text-muted-foreground hidden md:table-cell">start==2024-01-01</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          {/* Examples */}
          <section className="mb-12">
            <h2 className="text-xl font-semibold text-foreground mb-4 flex items-center gap-2">
              <Globe className="w-5 h-5 text-muted-foreground" />
              API Examples
            </h2>
            <div className="space-y-8">
              {examples.map((category) => (
                <div key={category.category}>
                  <h3 className="text-lg font-medium text-foreground mb-4">{category.category}</h3>
                  <div className="space-y-4">
                    {category.commands.map((cmd) => (
                      <div key={cmd.title} className="rounded-lg border border-border overflow-hidden">
                        <div className="px-4 py-3 bg-secondary flex items-center justify-between">
                          <div>
                            <h4 className="font-medium text-foreground text-sm">{cmd.title}</h4>
                            <p className="text-xs text-muted-foreground">{cmd.description}</p>
                          </div>
                          <CopyButton text={cmd.command} />
                        </div>
                        <pre className="p-4 bg-card overflow-x-auto">
                          <code className="text-sm font-mono text-emerald-400 whitespace-pre">
                            {cmd.command}
                          </code>
                        </pre>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Tips */}
          <section className="mb-12">
            <h2 className="text-xl font-semibold text-foreground mb-4">Pro Tips</h2>
            <div className="grid md:grid-cols-2 gap-4">
              <div className="p-4 rounded-lg bg-card border border-border">
                <h3 className="font-medium text-foreground mb-2">Save Sessions</h3>
                <p className="text-sm text-muted-foreground mb-2">
                  Use HTTPie sessions to persist headers across requests:
                </p>
                <code className="text-xs font-mono text-muted-foreground">
                  http --session=mm GET .../trades
                </code>
              </div>
              <div className="p-4 rounded-lg bg-card border border-border">
                <h3 className="font-medium text-foreground mb-2">Pretty Print</h3>
                <p className="text-sm text-muted-foreground mb-2">
                  HTTPie automatically formats JSON. Use --print for control:
                </p>
                <code className="text-xs font-mono text-muted-foreground">
                  http --print=b GET .../health
                </code>
              </div>
              <div className="p-4 rounded-lg bg-card border border-border">
                <h3 className="font-medium text-foreground mb-2">Download Files</h3>
                <p className="text-sm text-muted-foreground mb-2">
                  Download response to a file:
                </p>
                <code className="text-xs font-mono text-muted-foreground">
                  http GET .../export --download
                </code>
              </div>
              <div className="p-4 rounded-lg bg-card border border-border">
                <h3 className="font-medium text-foreground mb-2">Verbose Mode</h3>
                <p className="text-sm text-muted-foreground mb-2">
                  See full request/response headers:
                </p>
                <code className="text-xs font-mono text-muted-foreground">
                  http -v GET .../health
                </code>
              </div>
            </div>
          </section>

          {/* Other Collections */}
          <section>
            <h2 className="text-xl font-semibold text-foreground mb-4">Other Testing Tools</h2>
            <div className="grid md:grid-cols-2 gap-4">
              <Link 
                href="/developers/collections/postman"
                className="p-4 rounded-lg bg-card border border-border hover:border-accent/50 transition-colors group"
              >
                <h3 className="font-medium text-foreground group-hover:text-accent transition-colors">
                  Postman Collection
                </h3>
                <p className="text-sm text-muted-foreground mt-1">
                  Ready-to-import collection with all API endpoints
                </p>
              </Link>
              <Link 
                href="/developers/collections/insomnia"
                className="p-4 rounded-lg bg-card border border-border hover:border-accent/50 transition-colors group"
              >
                <h3 className="font-medium text-foreground group-hover:text-accent transition-colors">
                  Insomnia Collection
                </h3>
                <p className="text-sm text-muted-foreground mt-1">
                  Full API collection for Insomnia REST client
                </p>
              </Link>
            </div>
          </section>
        </div>
      </main>
      <Footer />
    </div>
  )
}
