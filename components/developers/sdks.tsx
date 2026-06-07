import { Button } from "@/components/ui/button"
import { Download, FileCode, Package, Terminal } from "lucide-react"
import Link from "next/link"

const sdks = [
  {
    name: "Python SDK",
    icon: "🐍",
    version: "v2.1.0",
    description: "Official Python client for MarketMate API",
    install: "pip install marketmate",
    features: ["Pydantic models", "Type hints", "Error handling"],
    href: "/developers/docs/getting-started",
  },
  {
    name: "TypeScript SDK",
    icon: "📘",
    version: "v2.1.0",
    description: "TypeScript/JavaScript client with full type safety",
    install: "npm install @marketmate/sdk",
    features: ["Full TypeScript", "Zero deps", "Error classes"],
    href: "/developers/docs/getting-started",
  },
  {
    name: "Go SDK",
    icon: "🔵",
    version: "v2.0.1",
    description: "High-performance Go client for server applications",
    install: "go get github.com/marketmate/go-sdk",
    features: ["Context support", "Concurrent safe", "Coming soon"],
    href: "/developers/docs/getting-started",
  },
  {
    name: "Rust SDK",
    icon: "🦀",
    version: "v1.2.0",
    description: "Memory-safe Rust client for low-latency systems",
    install: "cargo add marketmate",
    features: ["Async/await", "Tokio runtime", "Coming soon"],
    href: "/developers/docs/getting-started",
  },
]

const tools = [
  {
    icon: Terminal,
    name: "CLI Tool",
    description: "Command-line interface for testing and debugging",
    action: "Install CLI",
    href: "/developers/docs/getting-started#installation",
  },
  {
    icon: FileCode,
    name: "Postman Collection",
    description: "Ready-to-use API request collection for testing",
    action: "Download",
    href: "/api/download?type=postman",
  },
  {
    icon: Package,
    name: "OpenAPI Spec",
    description: "Full OpenAPI 3.0 specification for code generation",
    action: "Download",
    href: "/api/download?type=openapi",
  },
]

export function SDKs() {
  return (
    <section id="sdks" className="py-24">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mb-12">
          <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4">
            SDKs & Integration Tools
          </h2>
          <p className="text-muted-foreground text-lg max-w-2xl">
            Official client libraries for your preferred language, plus tools 
            to accelerate your integration workflow.
          </p>
        </div>
        
        <div className="grid md:grid-cols-2 gap-6 mb-12">
          {sdks.map((sdk) => (
            <div
              key={sdk.name}
              className="p-6 rounded-xl bg-card border border-border hover:border-accent/50 transition-colors"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <span className="text-2xl">{sdk.icon}</span>
                  <div>
                    <h3 className="font-semibold text-foreground">{sdk.name}</h3>
                    <span className="text-xs text-muted-foreground">{sdk.version}</span>
                  </div>
                </div>
                <Button size="sm" variant="outline" className="gap-2" asChild>
                  <Link href={sdk.href}>
                    <Download className="w-3 h-3" />
                    Docs
                  </Link>
                </Button>
              </div>
              
              <p className="text-sm text-muted-foreground mb-4">
                {sdk.description}
              </p>
              
              <div className="p-3 rounded-lg bg-secondary font-mono text-sm text-muted-foreground mb-4">
                {sdk.install}
              </div>
              
              <div className="flex flex-wrap gap-2">
                {sdk.features.map((feature) => (
                  <span
                    key={feature}
                    className="px-2 py-1 text-xs bg-background rounded-md text-muted-foreground border border-border"
                  >
                    {feature}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
        
        <div className="grid md:grid-cols-3 gap-6">
          {tools.map((tool) => (
            <div
              key={tool.name}
              className="flex items-center gap-4 p-5 rounded-xl bg-card border border-border"
            >
              <div className="p-3 rounded-lg bg-secondary">
                <tool.icon className="w-5 h-5 text-accent" />
              </div>
              <div className="flex-1">
                <h3 className="font-medium text-foreground text-sm">{tool.name}</h3>
                <p className="text-xs text-muted-foreground">{tool.description}</p>
              </div>
              <Button size="sm" variant="ghost" className="text-accent" asChild>
                <Link href={tool.href}>
                  {tool.action}
                </Link>
              </Button>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
