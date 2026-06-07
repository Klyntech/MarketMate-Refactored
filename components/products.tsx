import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Code2, Brain, GraduationCap, LayoutDashboard, ArrowRight } from "lucide-react"
import Link from "next/link"

const products = [
  {
    icon: Code2,
    name: "MarketMate API",
    description: "Real-time market intelligence and event infrastructure. Query structured market state, conviction scores, and regime data via REST or WebSocket.",
    features: ["REST & WebSocket", "Real-time updates", "Historical replay"],
    href: "#",
  },
  {
    icon: Brain,
    name: "MATE",
    description: "AI-powered market interpreter built on compiled market state. Natural language queries for market context and analysis.",
    features: ["Natural language", "Context-aware", "Multi-asset"],
    href: "#",
  },
  {
    icon: GraduationCap,
    name: "MMAcademy",
    description: "Structured trading education ecosystem. Learn market structure, liquidity analysis, and systematic trading strategies.",
    features: ["Video courses", "Live sessions", "Community"],
    href: "#",
  },
  {
    icon: LayoutDashboard,
    name: "MarketMate Desk",
    description: "Execution, monitoring, and analytics interfaces. Professional-grade tools for traders and portfolio managers.",
    features: ["Real-time charts", "Order management", "Analytics"],
    href: "#",
  },
]

export function Products() {
  return (
    <section id="products" className="py-24 relative">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4">
            The MarketMate Platform
          </h2>
          <p className="text-muted-foreground text-lg max-w-2xl mx-auto text-pretty">
            A complete ecosystem for structured financial intelligence. 
            Build, learn, and trade with institutional-grade market context.
          </p>
        </div>
        
        <div className="grid md:grid-cols-2 gap-6">
          {products.map((product) => (
            <Card 
              key={product.name}
              className="bg-card border-border hover:border-accent/50 transition-all duration-300 group"
            >
              <CardHeader>
                <div className="flex items-center gap-4 mb-2">
                  <div className="flex items-center justify-center w-12 h-12 rounded-lg bg-secondary">
                    <product.icon className="w-6 h-6 text-accent" />
                  </div>
                  <CardTitle className="text-xl text-foreground">{product.name}</CardTitle>
                </div>
                <CardDescription className="text-muted-foreground text-base">
                  {product.description}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2 mb-4">
                  {product.features.map((feature) => (
                    <span 
                      key={feature}
                      className="px-3 py-1 rounded-full bg-secondary text-xs font-medium text-muted-foreground"
                    >
                      {feature}
                    </span>
                  ))}
                </div>
                <Link 
                  href={product.href}
                  className="inline-flex items-center text-sm font-medium text-accent hover:text-accent/80 transition-colors"
                >
                  Learn more
                  <ArrowRight className="ml-1 h-4 w-4 group-hover:translate-x-1 transition-transform" />
                </Link>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  )
}
