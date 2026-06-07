"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { 
  FileText, 
  Key, 
  Webhook, 
  Database, 
  GitBranch, 
  BookOpen,
  ArrowRight,
  ExternalLink
} from "lucide-react"
import Link from "next/link"

const docCategories = [
  {
    id: "getting-started",
    icon: BookOpen,
    title: "Getting Started",
    description: "Quick setup and first API call",
    items: [
      { name: "Installation", href: "/developers/docs/getting-started#installation" },
      { name: "Authentication", href: "/developers/docs/getting-started#authentication" },
      { name: "Your First Request", href: "/developers/docs/getting-started#first-request" },
      { name: "Rate Limits", href: "/developers/docs/getting-started#rate-limits" },
    ]
  },
  {
    id: "api-reference",
    icon: FileText,
    title: "API Reference",
    description: "Complete endpoint documentation",
    items: [
      { name: "Market State", href: "/developers/docs/api-reference#market-state" },
      { name: "Conviction Signals", href: "/developers/docs/api-reference#signals" },
      { name: "Liquidity Analysis", href: "/developers/docs/api-reference#liquidity" },
      { name: "Historical Data", href: "/developers/docs/api-reference#historical" },
    ]
  },
  {
    id: "authentication",
    icon: Key,
    title: "Authentication",
    description: "API keys, OAuth, and security",
    items: [
      { name: "API Key Management", href: "/developers/docs/authentication#api-key-management" },
      { name: "OAuth 2.0 Flow", href: "/developers/docs/authentication#oauth" },
      { name: "Scopes & Permissions", href: "/developers/docs/authentication#scopes" },
      { name: "Security Best Practices", href: "/developers/docs/authentication#security" },
    ]
  },
  {
    id: "websockets",
    icon: Webhook,
    title: "WebSocket Events",
    description: "Real-time data streaming",
    items: [
      { name: "Connection Setup", href: "/developers/docs/websocket#connection-setup" },
      { name: "Event Types", href: "/developers/docs/websocket#event-types" },
      { name: "Subscription Management", href: "/developers/docs/websocket#subscription-management" },
      { name: "Reconnection Handling", href: "/developers/docs/websocket#reconnection" },
    ]
  },
  {
    id: "schemas",
    icon: Database,
    title: "Event Schemas",
    description: "Data structures and types",
    items: [
      { name: "State Objects", href: "/developers/docs/event-schemas#state-objects" },
      { name: "Signal Payloads", href: "/developers/docs/event-schemas#signal-payloads" },
      { name: "Error Responses", href: "/developers/docs/event-schemas#error-responses" },
      { name: "Webhook Payloads", href: "/developers/docs/event-schemas#webhook-payloads" },
    ]
  },
  {
    id: "changelog",
    icon: GitBranch,
    title: "Changelog",
    description: "API updates and versioning",
    items: [
      { name: "v2.1.0 - Latest", href: "/developers/docs/changelog#v210", badge: "New" },
      { name: "v2.0.0", href: "/developers/docs/changelog#v200" },
      { name: "v1.5.0", href: "/developers/docs/changelog#v150" },
      { name: "Migration Guides", href: "/developers/docs/changelog#migration" },
    ]
  },
]

export function Documentation() {
  const [activeCategory, setActiveCategory] = useState("getting-started")
  
  return (
    <section id="documentation" className="py-24 bg-card/50">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mb-12">
          <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4">
            Documentation
          </h2>
          <p className="text-muted-foreground text-lg max-w-2xl">
            Comprehensive guides, API references, and examples to integrate 
            MarketMate into your trading infrastructure.
          </p>
        </div>
        
        <div className="grid lg:grid-cols-3 gap-6">
          {docCategories.map((category) => (
            <div
              key={category.id}
              className="group p-6 rounded-xl bg-background border border-border hover:border-accent/50 transition-colors cursor-pointer"
              onClick={() => { setActiveCategory(category.id); window.location.href = category.items[0].href; }}
            >
              <div className="flex items-start justify-between mb-4">
                <div className="p-2 rounded-lg bg-secondary">
                  <category.icon className="w-5 h-5 text-accent" />
                </div>
                <ArrowRight className="w-4 h-4 text-muted-foreground group-hover:text-accent transition-colors" />
              </div>
              
              <h3 className="text-lg font-semibold text-foreground mb-1">
                {category.title}
              </h3>
              <p className="text-sm text-muted-foreground mb-4">
                {category.description}
              </p>
              
              <ul className="space-y-2">
                {category.items.map((item) => (
                  <li key={item.name}>
                    <a 
                      href={item.href}
                      className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
                    >
                      <span className="w-1 h-1 rounded-full bg-border" />
                      {item.name}
                      {"badge" in item && (
                        <span className="px-1.5 py-0.5 text-xs font-medium bg-accent/20 text-accent rounded">
                          {item.badge}
                        </span>
                      )}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        
        <div className="mt-8 text-center">
          <Button variant="outline" className="gap-2" asChild>
            <Link href="/developers/docs/getting-started">
              <ExternalLink className="w-4 h-4" />
              Open Full Documentation
            </Link>
          </Button>
        </div>
      </div>
    </section>
  )
}
