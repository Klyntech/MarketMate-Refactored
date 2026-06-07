"use client"

import { Header } from "@/components/header"
import { Footer } from "@/components/footer"
import { Button } from "@/components/ui/button"
import { 
  ArrowLeft, 
  Download, 
  BookOpen,
  Copy,
  Check,
  ChevronRight
} from "lucide-react"
import Link from "next/link"
import { useState } from "react"

const stateFields = [
  {
    category: "Core State",
    fields: [
      { name: "signal_id", type: "string", description: "Unique identifier for the signal (UUID v4)" },
      { name: "symbol", type: "string", description: "Trading pair symbol (e.g., BTCUSDT, EURUSD)" },
      { name: "direction", type: "enum", values: ["LONG", "SHORT"], description: "Trade direction" },
      { name: "status", type: "enum", values: ["OPEN", "CLOSED", "CANCELLED", "EXPIRED"], description: "Current signal status" },
      { name: "created_at", type: "datetime", description: "ISO 8601 timestamp of signal creation" },
      { name: "updated_at", type: "datetime", description: "ISO 8601 timestamp of last update" },
    ]
  },
  {
    category: "Entry Configuration",
    fields: [
      { name: "entry_price", type: "number", description: "Target entry price for the position" },
      { name: "entry_type", type: "enum", values: ["LIMIT", "MARKET", "STOP"], description: "Order type for entry" },
      { name: "entry_zone_high", type: "number | null", description: "Upper bound of entry zone (optional)" },
      { name: "entry_zone_low", type: "number | null", description: "Lower bound of entry zone (optional)" },
      { name: "filled_price", type: "number | null", description: "Actual fill price (null if not filled)" },
    ]
  },
  {
    category: "Risk Management",
    fields: [
      { name: "stop_loss", type: "number", description: "Stop loss price level" },
      { name: "stop_loss_type", type: "enum", values: ["FIXED", "TRAILING", "BREAKEVEN"], description: "Stop loss behavior" },
      { name: "trailing_distance", type: "number | null", description: "Distance for trailing stop (in price or %)" },
      { name: "risk_reward_ratio", type: "number", description: "Calculated R:R based on entry and targets" },
      { name: "position_size_pct", type: "number", description: "Suggested position size as % of portfolio" },
    ]
  },
  {
    category: "Take Profit Levels",
    fields: [
      { name: "take_profit_1", type: "object", description: "First take profit target { price, percentage }" },
      { name: "take_profit_2", type: "object | null", description: "Second take profit target (optional)" },
      { name: "take_profit_3", type: "object | null", description: "Third take profit target (optional)" },
      { name: "tp_hit_flags", type: "array", description: "Boolean array tracking which TPs have been hit" },
    ]
  },
  {
    category: "Performance Metrics",
    fields: [
      { name: "current_pnl", type: "number", description: "Current unrealized P&L in quote currency" },
      { name: "current_pnl_pct", type: "number", description: "Current unrealized P&L as percentage" },
      { name: "max_drawdown", type: "number", description: "Maximum drawdown experienced" },
      { name: "max_favorable", type: "number", description: "Maximum favorable excursion" },
      { name: "duration_seconds", type: "number", description: "Time elapsed since entry" },
    ]
  },
  {
    category: "Conviction & Analysis",
    fields: [
      { name: "conviction_score", type: "number", description: "MATE AI conviction score (0-100)" },
      { name: "conviction_factors", type: "array", description: "Array of factors contributing to score" },
      { name: "market_regime", type: "enum", values: ["TRENDING", "RANGING", "VOLATILE", "QUIET"], description: "Detected market regime" },
      { name: "timeframe", type: "string", description: "Primary analysis timeframe (e.g., 4H, 1D)" },
      { name: "tags", type: "array", description: "Classification tags for the signal" },
    ]
  },
]

export default function StrategyStatePage() {
  const [copiedField, setCopiedField] = useState<string | null>(null)
  
  const copyToClipboard = (text: string, fieldName: string) => {
    navigator.clipboard.writeText(text)
    setCopiedField(fieldName)
    setTimeout(() => setCopiedField(null), 2000)
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
            <Link href="/developers/resources" className="hover:text-foreground transition-colors">
              Resources
            </Link>
            <ChevronRight className="w-4 h-4" />
            <span className="text-foreground">Strategy State Reference</span>
          </nav>
          
          {/* Header */}
          <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-6 mb-12">
            <div>
              <div className="flex items-center gap-3 mb-4">
                <div className="p-3 rounded-lg bg-red-500/10">
                  <BookOpen className="w-6 h-6 text-red-500" />
                </div>
                <div className="flex items-center gap-2">
                  <span className="px-2 py-1 rounded bg-secondary text-xs font-medium">PDF</span>
                  <span className="text-sm text-muted-foreground">2.4 MB</span>
                </div>
              </div>
              <h1 className="text-4xl font-bold text-foreground mb-4">
                Strategy State Reference
              </h1>
              <p className="text-lg text-muted-foreground max-w-2xl">
                Complete reference for all strategy state objects, fields, and valid values 
                used throughout the MarketMate API.
              </p>
            </div>
            
            <Button size="lg" className="shrink-0">
              <Download className="w-4 h-4 mr-2" />
              Download PDF
            </Button>
          </div>
          
          {/* Quick Reference */}
          <div className="mb-8 p-4 rounded-lg bg-accent/10 border border-accent/20">
            <p className="text-sm text-foreground">
              <strong>Quick Reference:</strong> This page provides an interactive preview of the 
              Strategy State schema. Download the full PDF for detailed examples, edge cases, 
              and implementation notes.
            </p>
          </div>
          
          {/* State Fields */}
          <div className="space-y-8">
            {stateFields.map((category) => (
              <div key={category.category} className="rounded-xl border border-border overflow-hidden">
                <div className="px-6 py-4 bg-card border-b border-border">
                  <h2 className="text-lg font-semibold text-foreground">{category.category}</h2>
                </div>
                
                <div className="divide-y divide-border">
                  {category.fields.map((field) => (
                    <div key={field.name} className="px-6 py-4 hover:bg-card/50 transition-colors">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-3 mb-1">
                            <code className="text-sm font-mono text-accent">{field.name}</code>
                            <span className="px-2 py-0.5 rounded bg-secondary text-xs text-muted-foreground">
                              {field.type}
                            </span>
                          </div>
                          <p className="text-sm text-muted-foreground">{field.description}</p>
                          {"values" in field && field.values && (
                            <div className="flex flex-wrap gap-2 mt-2">
                              {field.values.map((value) => (
                                <code key={value} className="px-2 py-0.5 rounded bg-secondary text-xs font-mono">
                                  {value}
                                </code>
                              ))}
                            </div>
                          )}
                        </div>
                        
                        <button
                          onClick={() => copyToClipboard(field.name, field.name)}
                          className="p-2 rounded hover:bg-secondary transition-colors shrink-0"
                          title="Copy field name"
                        >
                          {copiedField === field.name ? (
                            <Check className="w-4 h-4 text-emerald-500" />
                          ) : (
                            <Copy className="w-4 h-4 text-muted-foreground" />
                          )}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
          
          {/* Example Object */}
          <div className="mt-12 rounded-xl border border-border overflow-hidden">
            <div className="px-6 py-4 bg-card border-b border-border flex items-center justify-between">
              <h2 className="text-lg font-semibold text-foreground">Example State Object</h2>
              <button
                onClick={() => copyToClipboard(JSON.stringify({
                  signal_id: "550e8400-e29b-41d4-a716-446655440000",
                  symbol: "BTCUSDT",
                  direction: "LONG",
                  status: "OPEN",
                  entry_price: 42500.00,
                  stop_loss: 41800.00,
                  take_profit_1: { price: 44000.00, percentage: 50 },
                  conviction_score: 85
                }, null, 2), "example")}
                className="flex items-center gap-2 px-3 py-1.5 rounded bg-secondary text-sm hover:bg-secondary/80 transition-colors"
              >
                {copiedField === "example" ? (
                  <>
                    <Check className="w-4 h-4 text-emerald-500" />
                    Copied
                  </>
                ) : (
                  <>
                    <Copy className="w-4 h-4" />
                    Copy
                  </>
                )}
              </button>
            </div>
            <pre className="p-6 text-sm font-mono text-foreground overflow-x-auto">
{`{
  "signal_id": "550e8400-e29b-41d4-a716-446655440000",
  "symbol": "BTCUSDT",
  "direction": "LONG",
  "status": "OPEN",
  "created_at": "2024-01-15T09:30:00Z",
  "entry_price": 42500.00,
  "entry_type": "LIMIT",
  "filled_price": 42485.50,
  "stop_loss": 41800.00,
  "stop_loss_type": "TRAILING",
  "trailing_distance": 150.00,
  "take_profit_1": { "price": 44000.00, "percentage": 50 },
  "take_profit_2": { "price": 45500.00, "percentage": 30 },
  "take_profit_3": { "price": 48000.00, "percentage": 20 },
  "tp_hit_flags": [false, false, false],
  "conviction_score": 85,
  "conviction_factors": ["trend_alignment", "volume_confirmation", "support_level"],
  "market_regime": "TRENDING",
  "timeframe": "4H",
  "current_pnl": 156.50,
  "current_pnl_pct": 0.37
}`}
            </pre>
          </div>
          
          {/* Navigation */}
          <div className="mt-12 flex items-center justify-between">
            <Link 
              href="/developers/resources" 
              className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              All Resources
            </Link>
            <Link 
              href="/developers/resources/event-schemas" 
              className="flex items-center gap-2 text-accent hover:underline"
            >
              Event Schema Definitions
              <ChevronRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </div>
      
      <Footer />
    </main>
  )
}
