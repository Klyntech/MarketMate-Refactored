import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { 
  FileText, 
  Video, 
  Download, 
  ExternalLink,
  BookOpen,
  Code2
} from "lucide-react"

const resources = [
  {
    title: "Market Structure Cheatsheet",
    description: "Quick reference guide for identifying market structure patterns",
    type: "PDF",
    icon: FileText,
  },
  {
    title: "API Quick Start Guide",
    description: "Get up and running with MarketMate API in under 10 minutes",
    type: "Guide",
    icon: Code2,
  },
  {
    title: "Liquidity Concepts Video Series",
    description: "Visual explanations of liquidity behavior and detection",
    type: "Video",
    icon: Video,
  },
  {
    title: "Risk Calculator Template",
    description: "Spreadsheet template for position sizing and risk management",
    type: "Download",
    icon: Download,
  },
  {
    title: "Trading Journal Framework",
    description: "Structured template for tracking and analyzing your trades",
    type: "Download",
    icon: BookOpen,
  },
  {
    title: "Community Discord",
    description: "Join thousands of traders discussing market intelligence",
    type: "Link",
    icon: ExternalLink,
  },
]

export function Resources() {
  return (
    <section className="py-20 bg-card/50">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center mb-12">
          <h2 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
            Resources & Tools
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            Free downloads, templates, and tools to support your learning journey
          </p>
        </div>
        
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {resources.map((resource) => (
            <Card 
              key={resource.title}
              className="bg-card border-border hover:border-accent/50 transition-all cursor-pointer group"
            >
              <CardContent className="p-6">
                <div className="flex items-start gap-4">
                  <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-secondary shrink-0">
                    <resource.icon className="w-5 h-5 text-muted-foreground group-hover:text-accent transition-colors" />
                  </div>
                  <div>
                    <p className="text-xs text-accent uppercase tracking-wide mb-1">
                      {resource.type}
                    </p>
                    <h3 className="text-base font-semibold text-foreground group-hover:text-accent transition-colors">
                      {resource.title}
                    </h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      {resource.description}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  )
}
