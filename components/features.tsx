import { Activity, BarChart3, Gauge, History, Network, Radio, Shield, Waves } from "lucide-react"

const features = [
  {
    icon: Activity,
    name: "Real-Time Market State",
    description: "Live tracking of market structure, price action, and microstructure signals across multiple timeframes.",
  },
  {
    icon: Gauge,
    name: "Conviction Analysis",
    description: "Quantified conviction scores derived from volume, momentum, and order flow patterns.",
  },
  {
    icon: Waves,
    name: "Liquidity Detection",
    description: "Identify liquidity sweeps, absorption zones, and institutional footprints in real-time.",
  },
  {
    icon: BarChart3,
    name: "Regime Recognition",
    description: "Automatic detection of market regimes: trending, ranging, volatile, or transitional states.",
  },
  {
    icon: Radio,
    name: "Event Infrastructure",
    description: "WebSocket streams for instant market events, signals, and state changes.",
  },
  {
    icon: History,
    name: "Historical Replay",
    description: "Backtest strategies against historical market state with full context preservation.",
  },
  {
    icon: Network,
    name: "Multi-Platform Distribution",
    description: "Access via REST API, WebSocket, Telegram bots, or custom dashboard integrations.",
  },
  {
    icon: Shield,
    name: "Enterprise Security",
    description: "SOC 2 compliant infrastructure with encrypted connections and rate limiting.",
  },
]

export function Features() {
  return (
    <section className="py-24 bg-secondary/30">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4">
            Core Capabilities
          </h2>
          <p className="text-muted-foreground text-lg max-w-2xl mx-auto text-pretty">
            Everything you need to integrate structured market intelligence 
            into your trading systems and applications.
          </p>
        </div>
        
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {features.map((feature) => (
            <div 
              key={feature.name}
              className="p-6 rounded-xl bg-card border border-border hover:border-accent/50 transition-colors"
            >
              <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-secondary mb-4">
                <feature.icon className="w-5 h-5 text-accent" />
              </div>
              <h3 className="text-lg font-semibold text-foreground mb-2">{feature.name}</h3>
              <p className="text-sm text-muted-foreground">{feature.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
