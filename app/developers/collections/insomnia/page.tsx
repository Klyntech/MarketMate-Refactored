import { Header } from "@/components/header"
import { Footer } from "@/components/footer"
import { Button } from "@/components/ui/button"
import { 
  Download, 
  ArrowLeft, 
  ExternalLink,
  FileJson,
  Key,
  Globe,
  Folder,
  ChevronRight,
  Sparkles
} from "lucide-react"
import Link from "next/link"

export const metadata = {
  title: "Insomnia Collection | MarketMate Developers",
  description: "Full MarketMate API collection for Insomnia REST client with environments, request chaining, and code generation.",
}

const endpoints = [
  {
    folder: "Health",
    routes: [
      { method: "GET", path: "/health", description: "API health check" },
    ]
  },
  {
    folder: "Authentication",
    routes: [
      { method: "POST", path: "/auth/login", description: "Login with credentials" },
      { method: "POST", path: "/auth/logout", description: "Logout current session" },
      { method: "GET", path: "/auth/me", description: "Get current user" },
    ]
  },
  {
    folder: "Signals",
    routes: [
      { method: "GET", path: "/trades", description: "Get open signals" },
      { method: "GET", path: "/trades/{id}", description: "Get signal by ID" },
      { method: "GET", path: "/performance", description: "Get performance stats" },
    ]
  },
  {
    folder: "MATE AI",
    routes: [
      { method: "POST", path: "/api/mate", description: "Query MATE intelligence" },
    ]
  },
  {
    folder: "Market Data",
    routes: [
      { method: "GET", path: "/market/state/{symbol}", description: "Current market state" },
      { method: "GET", path: "/market/history/{symbol}", description: "Historical states" },
      { method: "GET", path: "/market/levels/{symbol}", description: "Key price levels" },
    ]
  },
]

const environments = [
  { name: "Production", baseUrl: "https://api.marketmate.io", color: "emerald" },
  { name: "Staging", baseUrl: "https://staging-api.marketmate.io", color: "amber" },
  { name: "Local", baseUrl: "http://localhost:8000", color: "blue" },
]

const features = [
  {
    title: "Environment Switching",
    description: "Quickly switch between production, staging, and local environments with pre-configured variables.",
    icon: Globe,
  },
  {
    title: "Request Chaining",
    description: "Automatically chain responses - login once and reuse tokens across all authenticated requests.",
    icon: ChevronRight,
  },
  {
    title: "Code Generation",
    description: "Generate client code in 20+ languages directly from any request in the collection.",
    icon: Sparkles,
  },
  {
    title: "Response Validation",
    description: "Built-in JSON schema validation for response structure verification.",
    icon: FileJson,
  },
]

export default function InsomniaCollectionPage() {
  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main className="pt-24 pb-16">
        <div className="mx-auto max-w-4xl px-6 lg:px-8">
          {/* Breadcrumb */}
          <div className="mb-8">
            <Link 
              href="/developers#resources" 
              className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to Developer Resources
            </Link>
          </div>

          {/* Header */}
          <div className="mb-12">
            <div className="flex items-center gap-4 mb-6">
              <div className="p-3 rounded-xl bg-[#5849BE]/10 border border-[#5849BE]/20">
                <FileJson className="w-8 h-8 text-[#5849BE]" />
              </div>
              <div>
                <h1 className="text-3xl md:text-4xl font-bold text-foreground">
                  Insomnia Collection
                </h1>
                <p className="text-muted-foreground mt-1">
                  Full API collection for Insomnia REST client
                </p>
              </div>
            </div>

            <div className="flex flex-wrap gap-3">
              <Button className="gap-2 bg-[#5849BE] hover:bg-[#5849BE]/90 text-white">
                <Download className="w-4 h-4" />
                Download Collection
              </Button>
              <Button variant="outline" className="gap-2">
                <ExternalLink className="w-4 h-4" />
                Import to Insomnia
              </Button>
            </div>
          </div>

          {/* Quick Setup */}
          <section className="mb-12">
            <h2 className="text-xl font-semibold text-foreground mb-4">Quick Setup</h2>
            <div className="space-y-4">
              <div className="p-4 rounded-lg bg-card border border-border">
                <div className="flex items-start gap-3">
                  <span className="flex items-center justify-center w-6 h-6 rounded-full bg-primary text-primary-foreground text-sm font-medium shrink-0">1</span>
                  <div>
                    <h3 className="font-medium text-foreground">Download and Import</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      Download the collection file and import it via Insomnia&apos;s Import/Export menu (Ctrl+Shift+I).
                    </p>
                  </div>
                </div>
              </div>
              
              <div className="p-4 rounded-lg bg-card border border-border">
                <div className="flex items-start gap-3">
                  <span className="flex items-center justify-center w-6 h-6 rounded-full bg-primary text-primary-foreground text-sm font-medium shrink-0">2</span>
                  <div>
                    <h3 className="font-medium text-foreground">Select Environment</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      Choose your target environment (Production, Staging, or Local) from the environment dropdown.
                    </p>
                  </div>
                </div>
              </div>
              
              <div className="p-4 rounded-lg bg-card border border-border">
                <div className="flex items-start gap-3">
                  <span className="flex items-center justify-center w-6 h-6 rounded-full bg-primary text-primary-foreground text-sm font-medium shrink-0">3</span>
                  <div>
                    <h3 className="font-medium text-foreground">Configure API Key</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      Open the environment settings and add your API key. It will be automatically applied to all requests.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* Environments */}
          <section className="mb-12">
            <h2 className="text-xl font-semibold text-foreground mb-4 flex items-center gap-2">
              <Key className="w-5 h-5 text-muted-foreground" />
              Included Environments
            </h2>
            <div className="grid md:grid-cols-3 gap-4">
              {environments.map((env) => (
                <div key={env.name} className="p-4 rounded-lg bg-card border border-border">
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`w-2 h-2 rounded-full ${
                      env.color === "emerald" ? "bg-emerald-500" :
                      env.color === "amber" ? "bg-amber-500" : "bg-blue-500"
                    }`} />
                    <h3 className="font-medium text-foreground">{env.name}</h3>
                  </div>
                  <code className="text-xs font-mono text-muted-foreground break-all">
                    {env.baseUrl}
                  </code>
                </div>
              ))}
            </div>
          </section>

          {/* Features */}
          <section className="mb-12">
            <h2 className="text-xl font-semibold text-foreground mb-4">Collection Features</h2>
            <div className="grid md:grid-cols-2 gap-4">
              {features.map((feature) => (
                <div key={feature.title} className="p-4 rounded-lg bg-card border border-border">
                  <div className="flex items-center gap-2 mb-2">
                    <feature.icon className="w-4 h-4 text-accent" />
                    <h3 className="font-medium text-foreground">{feature.title}</h3>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {feature.description}
                  </p>
                </div>
              ))}
            </div>
          </section>

          {/* Included Endpoints */}
          <section className="mb-12">
            <h2 className="text-xl font-semibold text-foreground mb-4 flex items-center gap-2">
              <Globe className="w-5 h-5 text-muted-foreground" />
              Included Endpoints
            </h2>
            <div className="space-y-4">
              {endpoints.map((folder) => (
                <div key={folder.folder} className="rounded-lg border border-border overflow-hidden">
                  <div className="px-4 py-3 bg-secondary flex items-center gap-2">
                    <Folder className="w-4 h-4 text-muted-foreground" />
                    <span className="font-medium text-foreground">{folder.folder}</span>
                    <span className="text-xs text-muted-foreground">({folder.routes.length})</span>
                  </div>
                  <div className="divide-y divide-border">
                    {folder.routes.map((route) => (
                      <div key={route.path} className="px-4 py-3 bg-card flex items-center gap-3">
                        <span className={`px-2 py-0.5 text-xs font-mono font-medium rounded ${
                          route.method === "GET" ? "bg-emerald-500/10 text-emerald-500" :
                          route.method === "POST" ? "bg-blue-500/10 text-blue-500" :
                          route.method === "PUT" ? "bg-amber-500/10 text-amber-500" :
                          "bg-red-500/10 text-red-500"
                        }`}>
                          {route.method}
                        </span>
                        <code className="text-sm font-mono text-foreground">{route.path}</code>
                        <ChevronRight className="w-4 h-4 text-muted-foreground ml-auto hidden md:block" />
                        <span className="text-sm text-muted-foreground hidden md:block">{route.description}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Other Collections */}
          <section>
            <h2 className="text-xl font-semibold text-foreground mb-4">Other Testing Tools</h2>
            <div className="grid md:grid-cols-2 gap-4">
              <Link 
                href="/developers/collections/postman"
                className="p-4 rounded-lg bg-card border border-border hover:border-accent/50 transition-colors group"
              >
                <h3 className="font-medium text-foreground group-hover:text-accent transition-colors">
                  Postman Collection
                </h3>
                <p className="text-sm text-muted-foreground mt-1">
                  Ready-to-import collection with all API endpoints
                </p>
              </Link>
              <Link 
                href="/developers/collections/httpie"
                className="p-4 rounded-lg bg-card border border-border hover:border-accent/50 transition-colors group"
              >
                <h3 className="font-medium text-foreground group-hover:text-accent transition-colors">
                  HTTPie Examples
                </h3>
                <p className="text-sm text-muted-foreground mt-1">
                  Command-line examples for HTTPie users
                </p>
              </Link>
            </div>
          </section>
        </div>
      </main>
      <Footer />
    </div>
  )
}
