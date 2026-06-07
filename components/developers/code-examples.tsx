"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Copy, Check, Play } from "lucide-react"
import Link from "next/link"

const examples = {
  "market-state": {
    title: "Get Market State",
    description: "Retrieve current market regime, conviction, and key levels",
    code: `import { MarketMate } from '@marketmate/sdk';

const client = new MarketMate({
  apiKey: process.env.MARKETMATE_API_KEY
});

// Get current market state for BTC-USD
const state = await client.getState('BTC-USD');

console.log({
  regime: state.regime,           // "trending_bullish"
  conviction: state.conviction,   // 0.82
  volatility: state.volatility,   // "elevated"
  liquidityScore: state.liquidity // 0.76
});`,
  },
  "websocket": {
    title: "Real-time Streaming",
    description: "Subscribe to live market state updates via WebSocket",
    code: `import { MarketMate } from '@marketmate/sdk';

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
subscription.unsubscribe();`,
  },
  "historical": {
    title: "Historical Replay",
    description: "Query historical market states for backtesting",
    code: `import { MarketMate } from '@marketmate/sdk';

const client = new MarketMate({
  apiKey: process.env.MARKETMATE_API_KEY
});

// Query historical states
const history = await client.getHistoricalStates('BTC-USD', {
  start: '2024-01-01T00:00:00Z',
  end: '2024-01-15T00:00:00Z',
  interval: '1h',
  include: ['regime', 'conviction', 'key_levels']
});

// Analyze regime transitions
const regimeShifts = history.filter((state, i) => 
  i > 0 && state.regime !== history[i - 1].regime
);

console.log(\`Found \${regimeShifts.length} regime shifts\`);`,
  },
  "webhook": {
    title: "Webhook Integration",
    description: "Configure webhooks for event-driven architectures",
    code: `// Next.js API Route handler for MarketMate webhooks
import { verifyWebhookSignature } from '@marketmate/sdk';

export async function POST(request: Request) {
  const body = await request.text();
  const signature = request.headers.get('x-marketmate-signature');
  
  // Verify webhook authenticity
  const isValid = verifyWebhookSignature(
    body,
    signature,
    process.env.WEBHOOK_SECRET
  );
  
  if (!isValid) {
    return new Response('Invalid signature', { status: 401 });
  }
  
  const event = JSON.parse(body);
  
  switch (event.type) {
    case 'high_conviction_signal':
      await handleHighConviction(event);
      break;
    case 'regime_shift':
      await handleRegimeShift(event);
      break;
  }
  
  return new Response('OK', { status: 200 });
}`,
  },
}

export function CodeExamples() {
  const [activeExample, setActiveExample] = useState<keyof typeof examples>("market-state")
  const [copied, setCopied] = useState(false)

  const copyCode = () => {
    navigator.clipboard.writeText(examples[activeExample].code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <section id="quickstart" className="py-24 bg-card/50">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mb-12">
          <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4">
            Sample Implementations
          </h2>
          <p className="text-muted-foreground text-lg max-w-2xl">
            Production-ready code examples to accelerate your integration 
            across common use cases.
          </p>
        </div>
        
        <div className="grid lg:grid-cols-4 gap-4 mb-6">
          {Object.entries(examples).map(([key, example]) => (
            <button
              key={key}
              onClick={() => setActiveExample(key as keyof typeof examples)}
              className={`p-4 rounded-lg border text-left transition-colors ${
                activeExample === key
                  ? "bg-background border-accent"
                  : "bg-background/50 border-border hover:border-accent/50"
              }`}
            >
              <h3 className="font-medium text-foreground text-sm mb-1">
                {example.title}
              </h3>
              <p className="text-xs text-muted-foreground line-clamp-2">
                {example.description}
              </p>
            </button>
          ))}
        </div>
        
        <div className="rounded-xl bg-background border border-border overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-secondary/50">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-destructive/50" />
              <div className="w-3 h-3 rounded-full bg-chart-3/50" />
              <div className="w-3 h-3 rounded-full bg-chart-2/50" />
              <span className="ml-3 text-sm text-muted-foreground">
                {examples[activeExample].title}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Button size="sm" variant="ghost" className="text-muted-foreground hover:text-foreground gap-2" asChild>
                <Link href="/developers/docs/api-reference">
                  <Play className="w-3 h-3" />
                  Run in Sandbox
                </Link>
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={copyCode}
                className="text-muted-foreground hover:text-foreground"
              >
                {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              </Button>
            </div>
          </div>
          <pre className="p-6 overflow-x-auto text-sm max-h-[500px]">
            <code className="text-muted-foreground font-mono whitespace-pre">
              {examples[activeExample].code}
            </code>
          </pre>
        </div>
      </div>
    </section>
  )
}
