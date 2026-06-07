"use client"

import { useState } from "react"
import { Header } from "@/components/header"
import { Footer } from "@/components/footer"
import { Button } from "@/components/ui/button"
import {
  ChevronRight,
  Copy,
  Check,
  Webhook,
  Wifi,
  Activity,
  ArrowRight,
  RefreshCcw,
  Plug,
  Radio,
} from "lucide-react"
import Link from "next/link"

const sidebarSections = [
  { id: "connection-setup", label: "Connection Setup", icon: Plug },
  { id: "event-types", label: "Event Types", icon: Radio },
  { id: "subscription-management", label: "Subscription Management", icon: Wifi },
  { id: "reconnection-handling", label: "Reconnection Handling", icon: RefreshCcw },
  { id: "example-code", label: "Example Code", icon: Activity },
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

const eventTypes = [
  {
    name: "state_change",
    description: "Fired when the market state is updated with new regime, conviction, or volatility data.",
    frequency: "Every 15 seconds per symbol",
    payload: `{
  "type": "state_change",
  "data": {
    "symbol": "BTC-USD",
    "regime": "trending_bullish",
    "conviction": 0.82,
    "volatility": "elevated",
    "liquidity": 0.76
  },
  "timestamp": "2024-01-15T10:30:15Z"
}`,
  },
  {
    name: "sweep_detected",
    description: "Fired when a liquidity sweep is detected at a key level.",
    frequency: "On detection",
    payload: `{
  "type": "sweep_detected",
  "data": {
    "symbol": "BTC-USD",
    "level": 67850,
    "direction": "bearish",
    "volume": "45.2 BTC",
    "strength": 0.85
  },
  "timestamp": "2024-01-15T10:30:15Z"
}`,
  },
  {
    name: "regime_shift",
    description: "Fired when the market regime changes (e.g., from ranging to trending).",
    frequency: "On regime transition",
    payload: `{
  "type": "regime_shift",
  "data": {
    "symbol": "BTC-USD",
    "from": "ranging",
    "to": "trending_bullish",
    "conviction": 0.78
  },
  "timestamp": "2024-01-15T10:30:15Z"
}`,
  },
  {
    name: "signal_opened",
    description: "Fired when a new high-conviction trading signal is generated.",
    frequency: "On signal creation",
    payload: `{
  "type": "signal_opened",
  "data": {
    "signal_id": "sig_550e8400",
    "symbol": "BTC-USD",
    "direction": "LONG",
    "conviction": "HIGH",
    "entry_zone": { "low": 67850, "high": 68200 },
    "stop_loss": 67100,
    "risk_reward": 3.2
  },
  "timestamp": "2024-01-15T10:30:15Z"
}`,
  },
  {
    name: "signal_closed",
    description: "Fired when an active signal is closed (hit TP, SL, or expired).",
    frequency: "On signal closure",
    payload: `{
  "type": "signal_closed",
  "data": {
    "signal_id": "sig_550e8400",
    "symbol": "BTC-USD",
    "direction": "LONG",
    "result": "take_profit_1",
    "pnl_pct": 2.48,
    "duration_seconds": 14400
  },
  "timestamp": "2024-01-15T10:30:15Z"
}`,
  },
]

export default function WebSocketPage() {
  const [activeSection, setActiveSection] = useState("connection-setup")

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
            <span className="text-foreground">WebSocket Events</span>
          </nav>

          {/* Header */}
          <div className="mb-12">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 rounded-lg bg-secondary">
                <Webhook className="w-5 h-5 text-accent" />
              </div>
            </div>
            <h1 className="text-4xl md:text-5xl font-bold text-foreground mb-4">
              WebSocket Events
            </h1>
            <p className="text-lg text-muted-foreground max-w-2xl">
              Stream real-time market data, signals, and state changes via the MarketMate WebSocket API. Subscribe to specific events and symbols for low-latency updates.
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
                    href="/developers/docs/event-schemas"
                    className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
                  >
                    Event Schemas
                    <ArrowRight className="w-3 h-3" />
                  </Link>
                  <Link
                    href="/developers/docs/authentication"
                    className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
                  >
                    Authentication
                    <ArrowRight className="w-3 h-3" />
                  </Link>
                </div>
              </div>
            </aside>

            {/* Main Content */}
            <div className="flex-1 min-w-0 space-y-16">
              {/* Connection Setup */}
              <section id="connection-setup">
                <h2 className="text-2xl font-bold text-foreground mb-4">Connection Setup</h2>
                <p className="text-muted-foreground mb-6">
                  Connect to the MarketMate WebSocket endpoint and authenticate using your API key.
                </p>

                <div className="space-y-6">
                  <div className="p-6 rounded-xl bg-card border border-border">
                    <h3 className="text-lg font-semibold text-foreground mb-2">WebSocket URL</h3>
                    <code className="px-3 py-1.5 rounded bg-secondary text-sm font-mono text-accent block mb-4">
                      wss://marketmate-website.onrender.com/ws
                    </code>
                    <p className="text-sm text-muted-foreground">
                      All WebSocket connections must be made over <code className="px-1.5 py-0.5 rounded bg-secondary text-xs font-mono text-accent">wss://</code> (secure WebSocket). Plain <code className="px-1.5 py-0.5 rounded bg-secondary text-xs font-mono text-accent">ws://</code> connections are rejected.
                    </p>
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">Authentication</h3>
                    <p className="text-muted-foreground mb-3">
                      Authenticate your WebSocket connection by sending an <code className="px-1.5 py-0.5 rounded bg-secondary text-xs font-mono text-accent">auth</code> message immediately after connecting. The connection will be closed if authentication is not completed within 10 seconds.
                    </p>
                    <CodeBlock
                      filename="auth-message.json"
                      code={`{
  "action": "auth",
  "api_key": "mk_live_abc123def456ghi789"
}`}
                    />
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">Authentication Response</h3>
                    <CodeBlock
                      filename="auth-response.json"
                      code={`{
  "type": "auth_success",
  "message": "Authenticated successfully",
  "connection_id": "conn_abc123",
  "timestamp": "2024-01-15T10:30:00Z"
}`}
                    />
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">Connection Limits</h3>
                    <div className="overflow-x-auto rounded-lg border border-border">
                      <table className="w-full">
                        <thead>
                          <tr className="border-b border-border bg-secondary/50">
                            <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Plan</th>
                            <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Max Connections</th>
                            <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Max Subscriptions</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border">
                          <tr>
                            <td className="px-4 py-3 text-sm text-foreground">Free</td>
                            <td className="px-4 py-3 text-sm text-foreground">1</td>
                            <td className="px-4 py-3 text-sm text-foreground">3</td>
                          </tr>
                          <tr>
                            <td className="px-4 py-3 text-sm text-foreground">Pro</td>
                            <td className="px-4 py-3 text-sm text-foreground">5</td>
                            <td className="px-4 py-3 text-sm text-foreground">25</td>
                          </tr>
                          <tr>
                            <td className="px-4 py-3 text-sm text-foreground">Enterprise</td>
                            <td className="px-4 py-3 text-sm text-foreground">Unlimited</td>
                            <td className="px-4 py-3 text-sm text-foreground">Unlimited</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              </section>

              {/* Event Types */}
              <section id="event-types">
                <h2 className="text-2xl font-bold text-foreground mb-4">Event Types</h2>
                <p className="text-muted-foreground mb-6">
                  The WebSocket API emits the following event types. Subscribe to specific events to control which data you receive.
                </p>

                <div className="space-y-6">
                  {eventTypes.map((event) => (
                    <div key={event.name} className="p-6 rounded-xl bg-card border border-border">
                      <div className="flex items-start justify-between mb-3">
                        <div>
                          <h3 className="text-lg font-semibold text-foreground">
                            <code className="px-2 py-0.5 rounded bg-secondary text-accent text-base">{event.name}</code>
                          </h3>
                        </div>
                        <span className="px-2 py-1 rounded bg-secondary text-xs text-muted-foreground">
                          {event.frequency}
                        </span>
                      </div>
                      <p className="text-sm text-muted-foreground mb-4">{event.description}</p>
                      <CodeBlock
                        filename={`${event.name}.json`}
                        code={event.payload}
                      />
                    </div>
                  ))}
                </div>
              </section>

              {/* Subscription Management */}
              <section id="subscription-management">
                <h2 className="text-2xl font-bold text-foreground mb-4">Subscription Management</h2>
                <p className="text-muted-foreground mb-6">
                  Control which events and symbols you receive by subscribing and unsubscribing after authentication.
                </p>

                <div className="space-y-6">
                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">Subscribe to Events</h3>
                    <p className="text-muted-foreground mb-3">
                      After authenticating, send a <code className="px-1.5 py-0.5 rounded bg-secondary text-xs font-mono text-accent">subscribe</code> message to start receiving events:
                    </p>
                    <CodeBlock
                      filename="subscribe.json"
                      code={`{
  "action": "subscribe",
  "channels": [
    {
      "symbol": "BTC-USD",
      "events": ["state_change", "sweep_detected", "regime_shift"]
    },
    {
      "symbol": "ETH-USD",
      "events": ["signal_opened", "signal_closed"]
    }
  ]
}`}
                    />
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">Subscription Confirmation</h3>
                    <CodeBlock
                      filename="subscribe-response.json"
                      code={`{
  "type": "subscribe_success",
  "channels": [
    { "symbol": "BTC-USD", "events": ["state_change", "sweep_detected", "regime_shift"] },
    { "symbol": "ETH-USD", "events": ["signal_opened", "signal_closed"] }
  ],
  "timestamp": "2024-01-15T10:30:00Z"
}`}
                    />
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">Unsubscribe from Events</h3>
                    <CodeBlock
                      filename="unsubscribe.json"
                      code={`{
  "action": "unsubscribe",
  "channels": [
    {
      "symbol": "ETH-USD",
      "events": ["signal_opened", "signal_closed"]
    }
  ]
}`}
                    />
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">List Active Subscriptions</h3>
                    <CodeBlock
                      filename="list-subscriptions.json"
                      code={`{
  "action": "list_subscriptions"
}`}
                    />
                  </div>

                  <div className="p-4 rounded-lg bg-accent/10 border border-accent/20">
                    <p className="text-sm text-foreground">
                      <strong>Tip:</strong> Subscribe only to the events you need. Unnecessary subscriptions consume your subscription quota and may increase latency for critical events.
                    </p>
                  </div>
                </div>
              </section>

              {/* Reconnection Handling */}
              <section id="reconnection-handling">
                <h2 className="text-2xl font-bold text-foreground mb-4">Reconnection Handling</h2>
                <p className="text-muted-foreground mb-6">
                  Build robust WebSocket clients that handle disconnections gracefully with proper reconnection strategies.
                </p>

                <div className="space-y-6">
                  <div className="p-6 rounded-xl bg-card border border-border">
                    <h3 className="text-lg font-semibold text-foreground mb-2">Exponential Backoff</h3>
                    <p className="text-muted-foreground mb-4">
                      When a connection drops, use exponential backoff to avoid overwhelming the server. Start with a 1-second delay and double on each failure, up to a maximum of 30 seconds.
                    </p>
                    <div className="overflow-x-auto rounded-lg border border-border">
                      <table className="w-full">
                        <thead>
                          <tr className="border-b border-border bg-secondary/50">
                            <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Retry</th>
                            <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Delay</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border">
                          <tr><td className="px-4 py-2 text-sm text-foreground">1st</td><td className="px-4 py-2 text-sm text-foreground">1 second</td></tr>
                          <tr><td className="px-4 py-2 text-sm text-foreground">2nd</td><td className="px-4 py-2 text-sm text-foreground">2 seconds</td></tr>
                          <tr><td className="px-4 py-2 text-sm text-foreground">3rd</td><td className="px-4 py-2 text-sm text-foreground">4 seconds</td></tr>
                          <tr><td className="px-4 py-2 text-sm text-foreground">4th</td><td className="px-4 py-2 text-sm text-foreground">8 seconds</td></tr>
                          <tr><td className="px-4 py-2 text-sm text-foreground">5th</td><td className="px-4 py-2 text-sm text-foreground">16 seconds</td></tr>
                          <tr><td className="px-4 py-2 text-sm text-foreground">6th+</td><td className="px-4 py-2 text-sm text-foreground">30 seconds (max)</td></tr>
                        </tbody>
                      </table>
                    </div>
                  </div>

                  <div className="p-6 rounded-xl bg-card border border-border">
                    <h3 className="text-lg font-semibold text-foreground mb-2">Ping / Pong</h3>
                    <p className="text-muted-foreground mb-4">
                      The server sends a <code className="px-1.5 py-0.5 rounded bg-secondary text-xs font-mono text-accent">ping</code> message every 30 seconds. You must respond with a <code className="px-1.5 py-0.5 rounded bg-secondary text-xs font-mono text-accent">pong</code> within 10 seconds, or the connection will be closed.
                    </p>
                    <CodeBlock
                      filename="ping-pong.json"
                      code={`// Server sends:
{ "type": "ping", "timestamp": "2024-01-15T10:30:00Z" }

// Client must respond:
{ "action": "pong" }`}
                    />
                  </div>

                  <div className="p-6 rounded-xl bg-card border border-border">
                    <h3 className="text-lg font-semibold text-foreground mb-2">Close Codes</h3>
                    <div className="overflow-x-auto rounded-lg border border-border">
                      <table className="w-full">
                        <thead>
                          <tr className="border-b border-border bg-secondary/50">
                            <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Code</th>
                            <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Name</th>
                            <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Description</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border">
                          <tr><td className="px-4 py-2 text-sm font-mono text-accent">1000</td><td className="px-4 py-2 text-sm text-foreground">Normal</td><td className="px-4 py-2 text-sm text-muted-foreground">Normal closure</td></tr>
                          <tr><td className="px-4 py-2 text-sm font-mono text-accent">1001</td><td className="px-4 py-2 text-sm text-foreground">Going Away</td><td className="px-4 py-2 text-sm text-muted-foreground">Server shutting down or client navigating away</td></tr>
                          <tr><td className="px-4 py-2 text-sm font-mono text-accent">1008</td><td className="px-4 py-2 text-sm text-foreground">Policy Violation</td><td className="px-4 py-2 text-sm text-muted-foreground">Failed authentication or invalid messages</td></tr>
                          <tr><td className="px-4 py-2 text-sm font-mono text-accent">1011</td><td className="px-4 py-2 text-sm text-foreground">Internal Error</td><td className="px-4 py-2 text-sm text-muted-foreground">Server encountered an unexpected condition</td></tr>
                          <tr><td className="px-4 py-2 text-sm font-mono text-accent">4001</td><td className="px-4 py-2 text-sm text-foreground">Auth Timeout</td><td className="px-4 py-2 text-sm text-muted-foreground">No auth message received within 10 seconds</td></tr>
                          <tr><td className="px-4 py-2 text-sm font-mono text-accent">4002</td><td className="px-4 py-2 text-sm text-foreground">Rate Limited</td><td className="px-4 py-2 text-sm text-muted-foreground">Too many messages sent in a short period</td></tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              </section>

              {/* Example Code */}
              <section id="example-code">
                <h2 className="text-2xl font-bold text-foreground mb-4">Example Code</h2>
                <p className="text-muted-foreground mb-6">
                  A complete JavaScript WebSocket client implementation with authentication, subscriptions, and reconnection handling.
                </p>

                <div className="space-y-6">
                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">JavaScript Client</h3>
                    <CodeBlock
                      filename="marketmate-ws.js"
                      code={`class MarketMateWS {
  constructor(apiKey) {
    this.apiKey = apiKey;
    this.ws = null;
    this.retries = 0;
    this.maxRetries = 10;
    this.subscriptions = [];
  }

  connect() {
    this.ws = new WebSocket('wss://marketmate-website.onrender.com/ws');

    this.ws.onopen = () => {
      console.log('Connected to MarketMate WebSocket');
      this.retries = 0;
      // Authenticate immediately
      this.send({ action: 'auth', api_key: this.apiKey });
    };

    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);

      switch (message.type) {
        case 'auth_success':
          console.log('Authenticated:', message.connection_id);
          // Re-subscribe to channels
          this.resubscribe();
          break;
        case 'ping':
          this.send({ action: 'pong' });
          break;
        case 'state_change':
          this.onStateChange?.(message.data);
          break;
        case 'sweep_detected':
          this.onSweepDetected?.(message.data);
          break;
        case 'regime_shift':
          this.onRegimeShift?.(message.data);
          break;
        case 'signal_opened':
          this.onSignalOpened?.(message.data);
          break;
        case 'signal_closed':
          this.onSignalClosed?.(message.data);
          break;
      }
    };

    this.ws.onclose = (event) => {
      console.log('Disconnected:', event.code, event.reason);
      if (event.code !== 1000) {
        this.reconnect();
      }
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  }

  reconnect() {
    if (this.retries >= this.maxRetries) {
      console.error('Max reconnection attempts reached');
      return;
    }

    const delay = Math.min(1000 * Math.pow(2, this.retries), 30000);
    this.retries++;

    console.log(\`Reconnecting in \${delay}ms (attempt \${this.retries})\`);
    setTimeout(() => this.connect(), delay);
  }

  send(data) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  subscribe(channels) {
    this.subscriptions = channels;
    this.send({ action: 'subscribe', channels });
  }

  resubscribe() {
    if (this.subscriptions.length > 0) {
      this.send({ action: 'subscribe', channels: this.subscriptions });
    }
  }

  disconnect() {
    this.ws?.close(1000, 'Client disconnect');
  }
}

// Usage
const client = new MarketMateWS(process.env.MARKETMATE_API_KEY);

client.onStateChange = (data) => {
  console.log('State update:', data.symbol, data.regime);
};

client.onSignalOpened = (data) => {
  console.log('New signal:', data.signal_id, data.direction);
};

client.connect();

// Subscribe to events
client.subscribe([
  {
    symbol: 'BTC-USD',
    events: ['state_change', 'sweep_detected', 'regime_shift']
  }
]);`}
                    />
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-foreground mb-3">Using the SDK</h3>
                    <CodeBlock
                      filename="sdk-streaming.ts"
                      code={`import { MarketMate } from '@marketmate/sdk';

const client = new MarketMate({
  apiKey: process.env.MARKETMATE_API_KEY
});

// Subscribe to real-time state changes
const subscription = client.subscribe('BTC-USD', {
  events: ['state_change', 'sweep_detected', 'regime_shift'],

  onStateChange: (state) => {
    console.log('New state:', state.regime);
  },

  onSweepDetected: (sweep) => {
    console.log('Liquidity sweep:', sweep.direction, sweep.volume);
  },

  onRegimeShift: (shift) => {
    console.log('Regime changed:', shift.from, '->', shift.to);
  }
});

// Clean up when done
subscription.unsubscribe();`}
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
