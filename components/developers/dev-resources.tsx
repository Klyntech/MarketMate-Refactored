import { Button } from "@/components/ui/button"
import { 
  FileJson, 
  FileText, 
  Video, 
  Download, 
  ExternalLink,
  BookOpen,
  Layers,
  AlertCircle,
  ArrowRight
} from "lucide-react"
import Link from "next/link"

const resources = [
  {
    icon: FileJson,
    title: "Strategy State Reference",
    description: "Complete reference for all strategy state objects, fields, and valid values",
    type: "PDF",
    size: "2.4 MB",
    href: "/developers/resources/strategy-state",
  },
  {
    icon: Layers,
    title: "Event Schema Definitions",
    description: "JSON schemas for all API events, webhooks, and WebSocket messages",
    type: "JSON",
    size: "156 KB",
    href: "/api/download?type=event-schemas",
  },
  {
    icon: FileText,
    title: "Integration Architecture Guide",
    description: "Best practices for integrating MarketMate into trading systems",
    type: "PDF",
    size: "4.1 MB",
    href: "/developers/docs/getting-started",
  },
  {
    icon: BookOpen,
    title: "WebSocket Protocol Spec",
    description: "Complete specification for real-time data streaming protocol",
    type: "PDF",
    size: "1.8 MB",
    href: "/developers/docs/websocket",
  },
  {
    icon: Video,
    title: "Video: API Walkthrough",
    description: "30-minute deep dive into MarketMate API architecture",
    type: "Video",
    size: "32 min",
    href: "/developers/docs/getting-started",
  },
  {
    icon: AlertCircle,
    title: "Error Codes Reference",
    description: "Complete list of error codes with troubleshooting guidance",
    type: "PDF",
    size: "890 KB",
    href: "/developers/docs/event-schemas#error-responses",
  },
]

const collections = [
  {
    name: "Postman Collection",
    description: "Ready-to-import collection with all API endpoints",
    href: "/developers/collections/postman",
  },
  {
    name: "Insomnia Collection",
    description: "Full API collection for Insomnia REST client",
    href: "/developers/collections/insomnia",
  },
  {
    name: "HTTPie Examples",
    description: "Command-line examples for HTTPie users",
    href: "/developers/collections/httpie",
  },
]

export function DevResources() {
  return (
    <section id="resources" className="py-24">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mb-12">
          <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4">
            Downloadable Resources
          </h2>
          <p className="text-muted-foreground text-lg max-w-2xl">
            Reference materials, specifications, and testing tools to support 
            your integration workflow.
          </p>
        </div>
        
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6 mb-12">
          {resources.map((resource) => (
            <a
              key={resource.title}
              href={resource.href}
              className="group p-5 rounded-xl bg-card border border-border hover:border-accent/50 transition-colors"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="p-2 rounded-lg bg-secondary">
                  <resource.icon className="w-5 h-5 text-accent" />
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">{resource.type}</span>
                  <span className="text-xs text-muted-foreground">•</span>
                  <span className="text-xs text-muted-foreground">{resource.size}</span>
                </div>
              </div>
              
              <h3 className="font-semibold text-foreground mb-1 group-hover:text-accent transition-colors">
                {resource.title}
              </h3>
              <p className="text-sm text-muted-foreground">
                {resource.description}
              </p>
              
              <div className="mt-4 flex items-center gap-2 text-sm text-accent opacity-0 group-hover:opacity-100 transition-opacity">
                <Download className="w-4 h-4" />
                Download
              </div>
            </a>
          ))}
        </div>
        
        <div className="p-6 rounded-xl bg-card border border-border">
          <h3 className="text-lg font-semibold text-foreground mb-4">
            Testing Collections
          </h3>
          <div className="grid md:grid-cols-3 gap-4">
            {collections.map((collection) => (
              <Link
                key={collection.name}
                href={collection.href}
                className="flex items-center justify-between p-4 rounded-lg bg-background border border-border hover:border-accent/50 transition-colors group"
              >
                <div>
                  <h4 className="font-medium text-foreground text-sm group-hover:text-accent transition-colors">{collection.name}</h4>
                  <p className="text-xs text-muted-foreground">{collection.description}</p>
                </div>
                <ArrowRight className="w-4 h-4 text-muted-foreground group-hover:text-accent transition-colors" />
              </Link>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
