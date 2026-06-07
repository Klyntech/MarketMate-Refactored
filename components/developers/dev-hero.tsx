import { Button } from "@/components/ui/button"
import { Code2, Zap, Shield, Globe } from "lucide-react"
import Link from "next/link"

const stats = [
  { label: "API Uptime", value: "99.99%" },
  { label: "Avg Latency", value: "<50ms" },
  { label: "Active Integrations", value: "2,500+" },
]

export function DevHero() {
  return (
    <section className="relative pt-32 pb-20 overflow-hidden">
      <div className="absolute inset-0 -z-10">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-accent/10 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-accent/5 rounded-full blur-3xl" />
      </div>
      
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="max-w-3xl">
          <div className="flex items-center gap-2 mb-6">
            <Code2 className="w-5 h-5 text-accent" />
            <span className="text-sm font-medium text-accent">Developer Resources Hub</span>
          </div>
          
          <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold text-foreground mb-6 text-balance">
            Build with Market Intelligence Infrastructure
          </h1>
          
          <p className="text-lg md:text-xl text-muted-foreground mb-8 text-pretty">
            Everything you need to integrate real-time market state, conviction signals, 
            and liquidity analysis into your trading systems, bots, dashboards, and applications.
          </p>
          
          <div className="flex flex-wrap gap-4 mb-12">
            <Button size="lg" className="bg-primary text-primary-foreground hover:bg-primary/90" asChild>
              <Link href="/dashboard/api-keys">Get API Key</Link>
            </Button>
            <Button size="lg" variant="outline" asChild>
              <Link href="/developers/docs/getting-started">Quickstart Guide</Link>
            </Button>
          </div>
          
          <div className="grid grid-cols-3 gap-8 pt-8 border-t border-border">
            {stats.map((stat) => (
              <div key={stat.label}>
                <div className="text-2xl md:text-3xl font-bold text-foreground">{stat.value}</div>
                <div className="text-sm text-muted-foreground">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
        
        <div className="mt-16 grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { icon: Code2, title: "REST & WebSocket", desc: "Full API access" },
            { icon: Zap, title: "Real-time Events", desc: "Sub-50ms latency" },
            { icon: Shield, title: "Enterprise Security", desc: "SOC 2 compliant" },
            { icon: Globe, title: "Global CDN", desc: "Edge deployment" },
          ].map((item) => (
            <div key={item.title} className="flex items-center gap-3 p-4 rounded-lg bg-card border border-border">
              <item.icon className="w-5 h-5 text-accent" />
              <div>
                <div className="font-medium text-foreground text-sm">{item.title}</div>
                <div className="text-xs text-muted-foreground">{item.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
