"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Copy, Check } from "lucide-react"

const codeExamples = {
  curl: `curl -X GET "https://api.marketmate.io/v1/state/BTC-USD" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: application/json"

# Response
{
  "symbol": "BTC-USD",
  "timestamp": "2024-01-15T14:30:00Z",
  "state": {
    "regime": "trending_bullish",
    "conviction": 0.82,
    "volatility": "elevated",
    "liquidity_score": 0.76
  },
  "signals": {
    "sweep_detected": false,
    "absorption_zone": [67200, 67450],
    "key_levels": [66800, 67500, 68200]
  }
}`,
  python: `import marketmate

# Initialize client
client = marketmate.Client(api_key="YOUR_API_KEY")

# Get real-time market state
state = client.get_state("BTC-USD")

print(f"Regime: {state.regime}")
print(f"Conviction: {state.conviction}")
print(f"Key Levels: {state.signals.key_levels}")

# Subscribe to real-time updates
def on_state_change(event):
    if event.conviction > 0.8:
        print(f"High conviction signal: {event}")

client.subscribe("BTC-USD", on_state_change)`,
  typescript: `import { MarketMate } from '@marketmate/sdk';

// Initialize client
const client = new MarketMate({
  apiKey: process.env.MARKETMATE_API_KEY
});

// Get real-time market state
const state = await client.getState('BTC-USD');

console.log('Regime:', state.regime);
console.log('Conviction:', state.conviction);
console.log('Key Levels:', state.signals.keyLevels);

// Subscribe to real-time updates
client.subscribe('BTC-USD', (event) => {
  if (event.conviction > 0.8) {
    console.log('High conviction signal:', event);
  }
});`,
}

export function CodeDemo() {
  const [activeTab, setActiveTab] = useState("typescript")
  const [copied, setCopied] = useState(false)

  const copyCode = () => {
    navigator.clipboard.writeText(codeExamples[activeTab as keyof typeof codeExamples])
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <section id="developers" className="py-24">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="grid lg:grid-cols-2 gap-12 items-center">
          <div>
            <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4">
              Built for Developers
            </h2>
            <p className="text-muted-foreground text-lg mb-6 text-pretty">
              Clean, well-documented APIs that integrate seamlessly with your 
              trading systems, bots, and analytics platforms.
            </p>
            <ul className="space-y-4">
              {[
                "RESTful API with WebSocket support",
                "Official SDKs for Python, TypeScript, and Go",
                "Comprehensive documentation and examples",
                "Sandbox environment for testing",
              ].map((item) => (
                <li key={item} className="flex items-center gap-3">
                  <div className="w-1.5 h-1.5 rounded-full bg-accent" />
                  <span className="text-muted-foreground">{item}</span>
                </li>
              ))}
            </ul>
            <div className="mt-8">
              <Button className="bg-primary text-primary-foreground hover:bg-primary/90">
                View API Docs
              </Button>
            </div>
          </div>
          
          <div className="relative">
            <div className="rounded-xl bg-card border border-border overflow-hidden">
              <Tabs value={activeTab} onValueChange={setActiveTab}>
                <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-secondary/50">
                  <TabsList className="bg-transparent p-0 h-auto">
                    {Object.keys(codeExamples).map((lang) => (
                      <TabsTrigger
                        key={lang}
                        value={lang}
                        className="px-3 py-1.5 text-sm data-[state=active]:bg-background data-[state=active]:text-foreground text-muted-foreground rounded-md"
                      >
                        {lang}
                      </TabsTrigger>
                    ))}
                  </TabsList>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={copyCode}
                    className="text-muted-foreground hover:text-foreground"
                  >
                    {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                  </Button>
                </div>
                {Object.entries(codeExamples).map(([lang, code]) => (
                  <TabsContent key={lang} value={lang} className="m-0">
                    <pre className="p-4 overflow-x-auto text-sm">
                      <code className="text-muted-foreground font-mono whitespace-pre">{code}</code>
                    </pre>
                  </TabsContent>
                ))}
              </Tabs>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
