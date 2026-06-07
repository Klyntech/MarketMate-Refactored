import { Header } from "@/components/header"
import { Footer } from "@/components/footer"
import { Button } from "@/components/ui/button"
import { 
  Download, 
  Copy, 
  Check, 
  ArrowLeft, 
  ExternalLink,
  FileJson,
  Key,
  Globe,
  Folder,
  ChevronRight
} from "lucide-react"
import Link from "next/link"

export const metadata = {
  title: "Postman Collection | MarketMate Developers",
  description: "Ready-to-import Postman collection with all MarketMate API endpoints, environment variables, and example requests.",
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

const environmentVariables = [
  { key: "base_url", value: "https://api.marketmate.io", description: "API base URL" },
  { key: "api_key", value: "your_api_key_here", description: "Your API key" },
  { key: "session_token", value: "", description: "Auto-populated after login" },
]

export default function PostmanCollectionPage() {
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
              <div className="p-3 rounded-xl bg-[#FF6C37]/10 border border-[#FF6C37]/20">
                <FileJson className="w-8 h-8 text-[#FF6C37]" />
              </div>
              <div>
                <h1 className="text-3xl md:text-4xl font-bold text-foreground">
                  Postman Collection
                </h1>
                <p className="text-muted-foreground mt-1">
                  Ready-to-import collection with all API endpoints
                </p>
              </div>
            </div>

            <div className="flex flex-wrap gap-3">
              <Button className="gap-2 bg-[#FF6C37] hover:bg-[#FF6C37]/90 text-white">
                <Download className="w-4 h-4" />
                Download Collection
              </Button>
              <Button variant="outline" className="gap-2">
                <ExternalLink className="w-4 h-4" />
                Run in Postman
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
                    <h3 className="font-medium text-foreground">Import the Collection</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      Open Postman, click Import, and drag the downloaded JSON file or paste the collection URL.
                    </p>
                  </div>
                </div>
              </div>
              
              <div className="p-4 rounded-lg bg-card border border-border">
                <div className="flex items-start gap-3">
                  <span className="flex items-center justify-center w-6 h-6 rounded-full bg-primary text-primary-foreground text-sm font-medium shrink-0">2</span>
                  <div>
                    <h3 className="font-medium text-foreground">Set Up Environment</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      Import the included environment file and update your API key in the environment variables.
                    </p>
                  </div>
                </div>
              </div>
              
              <div className="p-4 rounded-lg bg-card border border-border">
                <div className="flex items-start gap-3">
                  <span className="flex items-center justify-center w-6 h-6 rounded-full bg-primary text-primary-foreground text-sm font-medium shrink-0">3</span>
                  <div>
                    <h3 className="font-medium text-foreground">Start Testing</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      Select the MarketMate environment and run any request. Authentication tokens are automatically managed.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* Environment Variables */}
          <section className="mb-12">
            <h2 className="text-xl font-semibold text-foreground mb-4 flex items-center gap-2">
              <Key className="w-5 h-5 text-muted-foreground" />
              Environment Variables
            </h2>
            <div className="rounded-lg border border-border overflow-hidden">
              <table className="w-full">
                <thead className="bg-secondary">
                  <tr>
                    <th className="text-left text-sm font-medium text-foreground px-4 py-3">Variable</th>
                    <th className="text-left text-sm font-medium text-foreground px-4 py-3">Default Value</th>
                    <th className="text-left text-sm font-medium text-foreground px-4 py-3 hidden md:table-cell">Description</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {environmentVariables.map((variable) => (
                    <tr key={variable.key} className="bg-card">
                      <td className="px-4 py-3">
                        <code className="text-sm font-mono text-accent">{`{{${variable.key}}}`}</code>
                      </td>
                      <td className="px-4 py-3">
                        <code className="text-sm font-mono text-muted-foreground">{variable.value || "—"}</code>
                      </td>
                      <td className="px-4 py-3 text-sm text-muted-foreground hidden md:table-cell">
                        {variable.description}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
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

          {/* Collection Features */}
          <section className="mb-12">
            <h2 className="text-xl font-semibold text-foreground mb-4">Collection Features</h2>
            <div className="grid md:grid-cols-2 gap-4">
              <div className="p-4 rounded-lg bg-card border border-border">
                <h3 className="font-medium text-foreground mb-2">Pre-request Scripts</h3>
                <p className="text-sm text-muted-foreground">
                  Automatic token refresh and request signing for authenticated endpoints.
                </p>
              </div>
              <div className="p-4 rounded-lg bg-card border border-border">
                <h3 className="font-medium text-foreground mb-2">Test Scripts</h3>
                <p className="text-sm text-muted-foreground">
                  Built-in response validation and status code checks for each endpoint.
                </p>
              </div>
              <div className="p-4 rounded-lg bg-card border border-border">
                <h3 className="font-medium text-foreground mb-2">Example Responses</h3>
                <p className="text-sm text-muted-foreground">
                  Saved example responses for documentation and reference.
                </p>
              </div>
              <div className="p-4 rounded-lg bg-card border border-border">
                <h3 className="font-medium text-foreground mb-2">Collection Variables</h3>
                <p className="text-sm text-muted-foreground">
                  Dynamic variables for symbols, dates, and pagination parameters.
                </p>
              </div>
            </div>
          </section>

          {/* Other Collections */}
          <section>
            <h2 className="text-xl font-semibold text-foreground mb-4">Other Testing Tools</h2>
            <div className="grid md:grid-cols-2 gap-4">
              <Link 
                href="/developers/collections/insomnia"
                className="p-4 rounded-lg bg-card border border-border hover:border-accent/50 transition-colors group"
              >
                <h3 className="font-medium text-foreground group-hover:text-accent transition-colors">
                  Insomnia Collection
                </h3>
                <p className="text-sm text-muted-foreground mt-1">
                  Full API collection for Insomnia REST client
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
