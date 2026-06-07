import { Users, MessageSquare, Bot, Eye, Lock, Zap } from "lucide-react"

export function TelegramArchitecture() {
  return (
    <section id="architecture" className="py-24 border-t border-border">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        {/* Section header */}
        <div className="text-center mb-16">
          <p className="text-sm font-medium text-primary uppercase tracking-wider mb-3">Telegram Architecture</p>
          <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4 text-balance">
            Three Channels. Clear Purpose.
          </h2>
          <p className="text-muted-foreground max-w-xl mx-auto text-pretty">
            The website is trust architecture. Telegram is the battlefield.
          </p>
        </div>

        {/* Channel cards */}
        <div className="grid md:grid-cols-3 gap-6 max-w-5xl mx-auto">
          {/* Public Channel */}
          <div className="p-6 rounded-lg border border-border bg-card">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 rounded-lg bg-secondary">
                <Eye className="h-5 w-5 text-muted-foreground" />
              </div>
              <div>
                <h3 className="font-semibold text-foreground">Public Channel</h3>
                <span className="text-xs text-muted-foreground">Marketing Layer</span>
              </div>
            </div>
            
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li className="flex items-center gap-2">
                <span className="w-1 h-1 rounded-full bg-muted-foreground" />
                Performance snapshots
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1 h-1 rounded-full bg-muted-foreground" />
                Selected wins
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1 h-1 rounded-full bg-muted-foreground" />
                Brand positioning
              </li>
            </ul>
          </div>

          {/* Private Signal Channel */}
          <div className="p-6 rounded-lg border border-primary/50 bg-card relative overflow-hidden">
            <div className="absolute top-0 right-0 w-24 h-24 bg-primary/5 rounded-full -translate-y-1/2 translate-x-1/2" />
            
            <div className="relative">
              <div className="flex items-center gap-3 mb-4">
                <div className="p-2 rounded-lg bg-primary/10">
                  <Lock className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <h3 className="font-semibold text-foreground">Private Signal Channel</h3>
                  <span className="text-xs text-primary">Core Product</span>
                </div>
              </div>
              
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li className="flex items-center gap-2">
                  <span className="w-1 h-1 rounded-full bg-primary" />
                  Real signals only
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-1 h-1 rounded-full bg-primary" />
                  One-way broadcast
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-1 h-1 rounded-full bg-primary" />
                  Lifecycle updates
                </li>
              </ul>
            </div>
          </div>

          {/* MATE Assistant Bot */}
          <div className="p-6 rounded-lg border border-border bg-card">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 rounded-lg bg-secondary">
                <Bot className="h-5 w-5 text-muted-foreground" />
              </div>
              <div>
                <h3 className="font-semibold text-foreground">MATE Assistant</h3>
                <span className="text-xs text-muted-foreground">DM or Group</span>
              </div>
            </div>
            
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li className="flex items-center gap-2">
                <span className="w-1 h-1 rounded-full bg-muted-foreground" />
                Questions & answers
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1 h-1 rounded-full bg-muted-foreground" />
                Market explanations
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1 h-1 rounded-full bg-muted-foreground" />
                Trade interpretation
              </li>
            </ul>
          </div>
        </div>

        {/* Design principles */}
        <div className="mt-16 max-w-3xl mx-auto">
          <h3 className="text-lg font-semibold text-foreground mb-6 text-center">Signal Channel Principles</h3>
          
          <div className="grid sm:grid-cols-2 gap-4">
            {[
              { 
                title: "Clean", 
                desc: "No memes. No motivational nonsense. No \"GOOD MORNING TRADERS\".",
                positive: false
              },
              { 
                title: "Structured", 
                desc: "Consistent format. Clear parameters. Predictable layout.",
                positive: true
              },
              { 
                title: "Fast", 
                desc: "Information density without noise. Scan in seconds.",
                positive: true
              },
              { 
                title: "Silent", 
                desc: "Silence is branding. Quiet systems signal competence.",
                positive: true
              },
            ].map((item) => (
              <div key={item.title} className="p-4 rounded-lg bg-secondary/30 border border-border">
                <div className="text-sm font-medium text-foreground mb-1">{item.title}</div>
                <div className="text-xs text-muted-foreground leading-relaxed">{item.desc}</div>
              </div>
            ))}
          </div>

          {/* Quiet note */}
          <div className="mt-8 text-center">
            <p className="text-xs text-muted-foreground/80 italic max-w-md mx-auto">
              Banks don&apos;t type &quot;LET&apos;S GOOO&quot; after every transaction. Neither do we.
            </p>
          </div>
        </div>

        {/* Future vision */}
        <div className="mt-20 p-8 rounded-lg border border-border bg-card max-w-3xl mx-auto">
          <div className="flex items-center gap-2 mb-4">
            <Zap className="h-4 w-4 text-primary" />
            <span className="text-xs font-medium text-primary uppercase tracking-wider">Roadmap</span>
          </div>
          
          <h3 className="text-lg font-semibold text-foreground mb-3">
            Desk is Phase 1. Telegram is the Start.
          </h3>
          
          <p className="text-sm text-muted-foreground mb-6">
            The execution stream will eventually become a full distribution network:
          </p>
          
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {[
              "API Delivery Network",
              "Execution Feed Layer",
              "Broker Integrations",
              "Automation Relay",
              "Copy Execution Bridge",
              "Webhook Distribution",
            ].map((item) => (
              <div key={item} className="text-xs text-muted-foreground py-2 px-3 rounded bg-secondary/50 border border-border">
                {item}
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
