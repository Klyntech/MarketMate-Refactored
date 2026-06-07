"use client"

import { useState } from "react"
import { Header } from "@/components/header"
import { Footer } from "@/components/footer"
import { Button } from "@/components/ui/button"
import {
  ChevronRight,
  Copy,
  Check,
  Key,
  Shield,
  Eye,
  EyeOff,
  ArrowRight,
  Plus,
  RotateCcw,
  AlertTriangle,
  Zap,
} from "lucide-react"
import Link from "next/link"

const sidebarSections = [
  { id: "api-key-management", label: "API Key Management", icon: Key },
  { id: "using-your-api-key", label: "Using Your API Key", icon: Shield },
  { id: "key-types", label: "Key Types", icon: Eye },
  { id: "security-best-practices", label: "Security Best Practices", icon: AlertTriangle },
  { id: "error-responses", label: "Error Responses", icon: RotateCcw },
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

export default function AuthenticationPage() {
  const [activeSection, setActiveSection] = useState("api-key-management")

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
            <span className="text-foreground">Authentication</span>
          </nav>

          {/* Header */}
          <div className="mb-12">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 rounded-lg bg-secondary">
                <Key className="w-5 h-5 text-accent" />
              </div>
            </div>
            <h1 className="text-4xl md:text-5xl font-bold text-foreground mb-4">
              Authentication
            </h1>
            <p className="text-lg text-muted-foreground max-w-2xl">
              Learn how to create, manage, and secure your API keys for authenticating requests to the MarketMate API.
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
              {/* API Key Management */}
              <section id="api-key-management">
                <h2 className="text-2xl font-bold text-foreground mb-4">API Key Management</h2>
                <p className="text-muted-foreground mb-6">
                  API keys are the primary method for authenticating with the MarketMate API. You can create, view, and revoke keys from your dashboard.
                </p>

                <div className="space-y-6">
                  <div className="p-6 rounded-xl bg-card border border-border">
                    <h3 className="text-lg font-semibold text-foreground mb-2">Creating an API Key</h3>
                    <p className="text-muted-foreground mb-4">
                      Navigate to the API Keys section in your dashboard and click &quot;Create New Key&quot;. You can assign a name and set permissions for each key.
                    </p>
                    <ol className="space-y-3 text-sm text-muted-foreground">
                      <li className="flex items-start gap-3">
                        <span className="flex items-center justify-center w-6 h-6 rounded-full bg-secondary text-accent text-xs font-bold shrink-0">1</span>
                        Go to the <Link href="/dashboard/api-keys" className="text-accent hover:underline">API Keys dashboard</Link>
                      </li>
                      <li className="flex items-start gap-3">
                        <span className="flex items-center justify-center w-6 h-6 rounded-full bg-secondary text-accent text-xs font-bold shrink-0">2</span>
                        Click &quot;Create New Key&quot; and enter a descriptive name (e.g., &quot;Production Bot&quot;, &quot;Backtest Script&quot;)
                      </li>
                      <li className="flex items-start gap-3">
                        <span className="flex items-center justify-center w-6 h-6 rounded-full bg-secondary text-accent text-xs font-bold shrink-0">3</span>
                        Select the environment: Live or Test
                      </li>
                      <li className="flex items-start gap-3">
                        <span className="flex items-center justify-center w-6 h-6 rounded-full bg-secondary text-accent text-xs font-bold shrink-0">4</span>
                        Copy and securely store the key — it will only be shown once
                      </li>
                    </ol>
                  </div>

                  <div className="p-4 rounded-lg bg-accent/10 border border-accent/20">
                    <p className="text-sm text-foreground">
                      <strong>Important:</strong> Your full API key is only displayed once at creation time. Make sure to copy it immediately and store it securely. If you lose your key, you&apos;ll need to revoke it and create a new one.
                    </p>
                  </div>

                  <div className="p-6 rounded-xl bg-card border border-border">
                    <h3 className="text-lg font-semibold text-foreground mb-2">Viewing & Revoking Keys</h3>
                    <p className="text-muted-foreground mb-4">
                      From the API Keys dashboard, you can:
                    </p>
                    <ul className="space-y-2 text-sm text-muted-foreground">
                      <li className="flex items-center gap-2">
                        <Eye className="w-4 h-4 text-accent shrink-0" />
                        View the key prefix (e.g., <code className="px-1.5 py-0.5 rounded bg-secondary text-xs font-mono text-accent">mk_live_abc...***</code>)
                      </li>
                      <li className="flex items-center gap-2">
                        <RotateCcw className="w-4 h-4 text-accent shrink-0" />
                        Rotate a key to generate a new secret while keeping the same key ID
                      </li>
                      <li className="flex items-center gap-2">
                        <EyeOff className="w-4 h-4 text-accent shrink-0" />
                        Revoke a key to immediately disable all requests using that key
                      </li>
                      <li className="flex items-center gap-2">
                        <Plus className="w-4 h-4 text-accent shrink-0" />
                        Create additional keys for different use cases or environments
                      </li>
                    </ul>
                  </div>
                </div>
              </section>

              {/* Using Your API Key */}
              <section id="using-your-api-key">
                <h2 className="text-2xl font-bold text-foreground mb-4">Using Your API Key</h2>
                <p className="text-muted-foreground mb-6">
                  Include your API key in the Authorization header of every request using the Bearer token scheme.
                </p>

                <div className="space-y-6">
                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">Authorization Header</h3>
                    <p className="text-muted-foreground mb-3">
                      All authenticated requests must include the following header:
                    </p>
                    <CodeBlock
                      filename="request-header"
                      code={`Authorization: Bearer mk_live_abc123def456ghi789`}
                    />
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">Using the SDK</h3>
                    <CodeBlock
                      filename="sdk-setup.ts"
                      code={`import { MarketMate } from '@marketmate/sdk';

// Initialize with your API key
const client = new MarketMate({
  apiKey: process.env.MARKETMATE_API_KEY
});

// All subsequent requests are automatically authenticated
const state = await client.getState('BTC-USD');`}
                    />
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">Using Environment Variables</h3>
                    <p className="text-muted-foreground mb-3">
                      Store your API key in an environment variable and never hardcode it in your source code:
                    </p>
                    <CodeBlock
                      filename=".env"
                      code={`MARKETMATE_API_KEY=mk_live_abc123def456ghi789`}
                    />
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">Python Example</h3>
                    <CodeBlock
                      filename="main.py"
                      code={`import marketmate
import os

client = marketmate.Client(
    api_key=os.environ.get("MARKETMATE_API_KEY")
)

state = client.get_state("BTC-USD")`}
                    />
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">cURL Example</h3>
                    <CodeBlock
                      filename="terminal"
                      code={`curl -H "Authorization: Bearer $MARKETMATE_API_KEY" \\
  "https://marketmate-website.onrender.com/api/v1/market-state?symbol=BTC-USD"`}
                    />
                  </div>
                </div>
              </section>

              {/* Key Types */}
              <section id="key-types">
                <h2 className="text-2xl font-bold text-foreground mb-4">Key Types</h2>
                <p className="text-muted-foreground mb-6">
                  MarketMate provides two types of API keys for different environments and use cases.
                </p>

                <div className="grid md:grid-cols-2 gap-6">
                  <div className="p-6 rounded-xl bg-card border border-border">
                    <div className="flex items-center gap-3 mb-4">
                      <div className="p-2 rounded-lg bg-emerald-500/10">
                        <Zap className="w-5 h-5 text-emerald-500" />
                      </div>
                      <div>
                        <h3 className="text-lg font-semibold text-foreground">Live Keys</h3>
                        <code className="text-xs font-mono text-muted-foreground">mk_live_...</code>
                      </div>
                    </div>
                    <p className="text-sm text-muted-foreground mb-4">
                      Live keys access real-time market data and production endpoints. Use these in your production trading systems.
                    </p>
                    <ul className="space-y-2 text-sm text-muted-foreground">
                      <li className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                        Access to all production API endpoints
                      </li>
                      <li className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                        Real-time market data and signals
                      </li>
                      <li className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                        Full rate limits based on your plan
                      </li>
                      <li className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                        WebSocket connections to live streams
                      </li>
                    </ul>
                  </div>

                  <div className="p-6 rounded-xl bg-card border border-border">
                    <div className="flex items-center gap-3 mb-4">
                      <div className="p-2 rounded-lg bg-amber-500/10">
                        <Shield className="w-5 h-5 text-amber-500" />
                      </div>
                      <div>
                        <h3 className="text-lg font-semibold text-foreground">Test Keys</h3>
                        <code className="text-xs font-mono text-muted-foreground">mk_test_...</code>
                      </div>
                    </div>
                    <p className="text-sm text-muted-foreground mb-4">
                      Test keys use sandbox data and are safe for development and testing. No real market data is accessed.
                    </p>
                    <ul className="space-y-2 text-sm text-muted-foreground">
                      <li className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                        Returns simulated market data
                      </li>
                      <li className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                        No impact on rate limits or billing
                      </li>
                      <li className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                        Perfect for integration testing
                      </li>
                      <li className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                        Mock responses with realistic structures
                      </li>
                    </ul>
                  </div>
                </div>
              </section>

              {/* Security Best Practices */}
              <section id="security-best-practices">
                <h2 className="text-2xl font-bold text-foreground mb-4">Security Best Practices</h2>
                <p className="text-muted-foreground mb-6">
                  Follow these guidelines to keep your API keys secure and prevent unauthorized access to your account.
                </p>

                <div className="space-y-4">
                  <div className="p-6 rounded-xl bg-card border border-border">
                    <div className="flex items-start gap-4">
                      <div className="p-2 rounded-lg bg-red-500/10 shrink-0">
                        <AlertTriangle className="w-5 h-5 text-red-500" />
                      </div>
                      <div>
                        <h3 className="text-lg font-semibold text-foreground mb-2">Never Expose Keys in Client-Side Code</h3>
                        <p className="text-muted-foreground mb-3">
                          API keys should never appear in frontend JavaScript, React components, or any code that runs in the browser. Always make API calls from a backend server.
                        </p>
                        <CodeBlock
                          filename="nextjs-route.ts"
                          code={`// ✅ DO: Call MarketMate from a server-side API route
import { NextResponse } from 'next/server';

export async function GET() {
  const response = await fetch(
    'https://marketmate-website.onrender.com/api/v1/market-state?symbol=BTC-USD',
    {
      headers: {
        'Authorization': \`Bearer \${process.env.MARKETMATE_API_KEY}\`
      }
    }
  );
  const data = await response.json();
  return NextResponse.json(data);
}`}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="p-6 rounded-xl bg-card border border-border">
                    <h3 className="text-lg font-semibold text-foreground mb-2">Rotate Keys Regularly</h3>
                    <p className="text-muted-foreground">
                      Create a new key, update your application to use it, then revoke the old key. This limits the damage window if a key is compromised. We recommend rotating keys at least every 90 days.
                    </p>
                  </div>

                  <div className="p-6 rounded-xl bg-card border border-border">
                    <h3 className="text-lg font-semibold text-foreground mb-2">Use Separate Keys for Different Environments</h3>
                    <p className="text-muted-foreground">
                      Create distinct keys for development, staging, and production. Use test keys (<code className="px-1.5 py-0.5 rounded bg-secondary text-xs font-mono text-accent">mk_test_...</code>) for development and live keys (<code className="px-1.5 py-0.5 rounded bg-secondary text-xs font-mono text-accent">mk_live_...</code>) only in production.
                    </p>
                  </div>

                  <div className="p-6 rounded-xl bg-card border border-border">
                    <h3 className="text-lg font-semibold text-foreground mb-2">Never Commit Keys to Version Control</h3>
                    <p className="text-muted-foreground">
                      Add <code className="px-1.5 py-0.5 rounded bg-secondary text-xs font-mono text-accent">.env</code> files to your <code className="px-1.5 py-0.5 rounded bg-secondary text-xs font-mono text-accent">.gitignore</code>. Use secret management tools like AWS Secrets Manager, HashiCorp Vault, or GitHub Secrets for CI/CD pipelines.
                    </p>
                  </div>

                  <div className="p-6 rounded-xl bg-card border border-border">
                    <h3 className="text-lg font-semibold text-foreground mb-2">Monitor API Key Usage</h3>
                    <p className="text-muted-foreground">
                      Regularly review your API key usage in the dashboard. Look for unexpected spikes in request volume or requests from unusual IP addresses, which may indicate a compromised key.
                    </p>
                  </div>

                  <div className="p-6 rounded-xl bg-card border border-border">
                    <h3 className="text-lg font-semibold text-foreground mb-2">Revoke Compromised Keys Immediately</h3>
                    <p className="text-muted-foreground">
                      If you suspect a key has been exposed, revoke it immediately from the dashboard and create a new one. There is no cooldown period — revoked keys are disabled instantly.
                    </p>
                  </div>
                </div>
              </section>

              {/* Error Responses */}
              <section id="error-responses">
                <h2 className="text-2xl font-bold text-foreground mb-4">Error Responses</h2>
                <p className="text-muted-foreground mb-6">
                  The API returns specific error responses when authentication fails. Handle these gracefully in your application.
                </p>

                <div className="space-y-6">
                  <div className="overflow-x-auto rounded-lg border border-border">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b border-border bg-secondary/50">
                          <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Status Code</th>
                          <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Error</th>
                          <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Description</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border">
                        <tr className="hover:bg-card/50 transition-colors">
                          <td className="px-4 py-3 text-sm">
                            <span className="px-2 py-0.5 rounded bg-red-500/20 text-red-400 text-xs font-mono font-bold">401</span>
                          </td>
                          <td className="px-4 py-3 text-sm font-mono text-accent">missing_key</td>
                          <td className="px-4 py-3 text-sm text-muted-foreground">No Authorization header provided in the request.</td>
                        </tr>
                        <tr className="hover:bg-card/50 transition-colors">
                          <td className="px-4 py-3 text-sm">
                            <span className="px-2 py-0.5 rounded bg-red-500/20 text-red-400 text-xs font-mono font-bold">401</span>
                          </td>
                          <td className="px-4 py-3 text-sm font-mono text-accent">invalid_key</td>
                          <td className="px-4 py-3 text-sm text-muted-foreground">The provided API key is invalid or malformed.</td>
                        </tr>
                        <tr className="hover:bg-card/50 transition-colors">
                          <td className="px-4 py-3 text-sm">
                            <span className="px-2 py-0.5 rounded bg-red-500/20 text-red-400 text-xs font-mono font-bold">401</span>
                          </td>
                          <td className="px-4 py-3 text-sm font-mono text-accent">revoked_key</td>
                          <td className="px-4 py-3 text-sm text-muted-foreground">The API key has been revoked and is no longer valid.</td>
                        </tr>
                        <tr className="hover:bg-card/50 transition-colors">
                          <td className="px-4 py-3 text-sm">
                            <span className="px-2 py-0.5 rounded bg-red-500/20 text-red-400 text-xs font-mono font-bold">401</span>
                          </td>
                          <td className="px-4 py-3 text-sm font-mono text-accent">expired_key</td>
                          <td className="px-4 py-3 text-sm text-muted-foreground">The API key has expired. Create a new key in the dashboard.</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">Example Error Response</h3>
                    <CodeBlock
                      filename="401-response.json"
                      code={`{
  "error": "Unauthorized",
  "message": "API key required. Include Authorization: Bearer <your-api-key> header."
}`}
                    />
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">Handling Auth Errors</h3>
                    <CodeBlock
                      filename="error-handling.ts"
                      code={`async function fetchMarketState(symbol: string) {
  const response = await fetch(
    \`https://marketmate-website.onrender.com/api/v1/market-state?symbol=\${symbol}\`,
    {
      headers: {
        'Authorization': \`Bearer \${process.env.MARKETMATE_API_KEY}\`
      }
    }
  );

  if (response.status === 401) {
    const error = await response.json();
    console.error('Auth failed:', error.message);
    // Alert your monitoring system
    // Attempt to rotate the key if automated
    throw new Error('Authentication failed: ' + error.message);
  }

  return response.json();
}`}
                    />
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
