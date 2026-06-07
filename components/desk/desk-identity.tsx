import { Brain, Radio, Zap, Database, BarChart3, Cpu, Send, Users, Activity, Clock, RefreshCw, LineChart } from "lucide-react"

export function DeskIdentity() {
  return (
    <section className="py-24 border-t border-border">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        {/* Section header */}
        <div className="text-center mb-16">
          <p className="text-sm font-medium text-primary uppercase tracking-wider mb-3">Architecture</p>
          <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4 text-balance">
            Two Systems. Clear Separation.
          </h2>
          <p className="text-muted-foreground max-w-xl mx-auto text-pretty">
            MarketMate is the brain. Desk is the execution stream.
          </p>
        </div>
        
        {/* Two column comparison */}
        <div className="grid md:grid-cols-2 gap-8 max-w-5xl mx-auto">
          {/* MarketMate - The Brain */}
          <div className="relative p-8 rounded-lg border border-border bg-card">
            <div className="absolute -top-3 left-6">
              <span className="px-3 py-1 text-xs font-medium bg-secondary text-muted-foreground rounded-full border border-border">
                Intelligence Infrastructure
              </span>
            </div>
            
            <div className="flex items-center gap-3 mb-6 mt-2">
              <div className="p-2 rounded-lg bg-secondary">
                <Brain className="h-5 w-5 text-primary" />
              </div>
              <h3 className="text-xl font-semibold text-foreground">MarketMate</h3>
            </div>
            
            <p className="text-sm text-muted-foreground mb-6">
              The analytical core. Processes raw market data into structured intelligence.
            </p>
            
            <div className="space-y-3">
              {[
                { icon: Cpu, label: "State Engine" },
                { icon: BarChart3, label: "Market Intelligence" },
                { icon: Zap, label: "MATE AI System" },
                { icon: Activity, label: "Signal Generation" },
                { icon: Database, label: "APIs & Infrastructure" },
                { icon: LineChart, label: "Analytics" },
              ].map((item) => (
                <div key={item.label} className="flex items-center gap-3 text-sm">
                  <item.icon className="h-4 w-4 text-muted-foreground" />
                  <span className="text-foreground">{item.label}</span>
                </div>
              ))}
            </div>
          </div>
          
          {/* Desk - The Execution Stream */}
          <div className="relative p-8 rounded-lg border border-primary/50 bg-card">
            <div className="absolute -top-3 left-6">
              <span className="px-3 py-1 text-xs font-medium bg-primary text-primary-foreground rounded-full">
                Distribution Layer
              </span>
            </div>
            
            <div className="flex items-center gap-3 mb-6 mt-2">
              <div className="p-2 rounded-lg bg-primary/10">
                <Radio className="h-5 w-5 text-primary" />
              </div>
              <h3 className="text-xl font-semibold text-foreground">Desk</h3>
            </div>
            
            <p className="text-sm text-muted-foreground mb-6">
              The execution stream. Delivers intelligence to traders in real-time.
            </p>
            
            <div className="space-y-3">
              {[
                { icon: Send, label: "Signal Broadcasting" },
                { icon: Users, label: "Telegram Delivery" },
                { icon: RefreshCw, label: "Signal Lifecycle" },
                { icon: Activity, label: "Live State Updates" },
                { icon: Clock, label: "Trade Management Flow" },
                { icon: Zap, label: "Execution Relay" },
              ].map((item) => (
                <div key={item.label} className="flex items-center gap-3 text-sm">
                  <item.icon className="h-4 w-4 text-primary" />
                  <span className="text-foreground">{item.label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
        
        {/* Analogy */}
        <div className="mt-12 text-center">
          <p className="text-sm text-muted-foreground italic">
            Think: Bloomberg Terminal intelligence delivered through tactical Telegram operations.
          </p>
        </div>
      </div>
    </section>
  )
}
