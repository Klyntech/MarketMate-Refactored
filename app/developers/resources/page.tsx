"use client"

import { useState } from "react"
import { Header } from "@/components/header"
import { Footer } from "@/components/footer"
import { Button } from "@/components/ui/button"
import { 
  FileText, 
  FileJson, 
  Video, 
  Download, 
  ArrowLeft,
  BookOpen,
  Zap,
  AlertTriangle,
  Layers,
  Play,
  ExternalLink,
  Check
} from "lucide-react"
import Link from "next/link"
import { cn } from "@/lib/utils"

const resources = [
  {
    id: "strategy-state",
    title: "Strategy State Reference",
    description: "Complete reference for all strategy state objects, fields, and valid values",
    type: "PDF",
    size: "2.4 MB",
    icon: BookOpen,
    color: "text-red-500",
    bgColor: "bg-red-500/10",
    href: "/developers/resources/strategy-state",
  },
  {
    id: "event-schemas",
    title: "Event Schema Definitions",
    description: "JSON schemas for all API events, webhooks, and WebSocket messages",
    type: "JSON",
    size: "156 KB",
    icon: FileJson,
    color: "text-amber-500",
    bgColor: "bg-amber-500/10",
    href: "/developers/resources/event-schemas",
  },
  {
    id: "integration-guide",
    title: "Integration Architecture Guide",
    description: "Best practices for integrating MarketMate into trading systems",
    type: "PDF",
    size: "4.1 MB",
    icon: Layers,
    color: "text-blue-500",
    bgColor: "bg-blue-500/10",
    href: "/developers/resources/integration-guide",
  },
  {
    id: "websocket-spec",
    title: "WebSocket Protocol Spec",
    description: "Complete specification for real-time data streaming protocol",
    type: "PDF",
    size: "1.8 MB",
    icon: Zap,
    color: "text-emerald-500",
    bgColor: "bg-emerald-500/10",
    href: "/developers/resources/websocket-spec",
  },
  {
    id: "api-walkthrough",
    title: "Video: API Walkthrough",
    description: "30-minute deep dive into MarketMate API architecture",
    type: "Video",
    size: "32 min",
    icon: Video,
    color: "text-purple-500",
    bgColor: "bg-purple-500/10",
    href: "/developers/resources/api-walkthrough",
  },
  {
    id: "error-codes",
    title: "Error Codes Reference",
    description: "Complete list of error codes with troubleshooting guidance",
    type: "PDF",
    size: "890 KB",
    icon: AlertTriangle,
    color: "text-orange-500",
    bgColor: "bg-orange-500/10",
    href: "/developers/resources/error-codes",
  },
]

export default function ResourcesPage() {
  return (
    <main className="min-h-screen bg-background">
      <Header />
      
      <div className="pt-32 pb-24">
        <div className="mx-auto max-w-7xl px-6 lg:px-8">
          {/* Back navigation */}
          <Link 
            href="/developers#resources" 
            className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors mb-8"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Developer Resources
          </Link>
          
          {/* Header */}
          <div className="mb-12">
            <h1 className="text-4xl md:text-5xl font-bold text-foreground mb-4">
              Developer Resources
            </h1>
            <p className="text-lg text-muted-foreground max-w-2xl">
              Downloadable documentation, schemas, and reference materials for integrating 
              with the MarketMate API.
            </p>
          </div>
          
          {/* Resources Grid */}
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {resources.map((resource) => (
              <Link
                key={resource.id}
                href={resource.href}
                className="group p-6 rounded-xl bg-card border border-border hover:border-accent/50 transition-all hover:shadow-lg"
              >
                <div className="flex items-start justify-between mb-4">
                  <div className={cn("p-3 rounded-lg", resource.bgColor)}>
                    <resource.icon className={cn("w-6 h-6", resource.color)} />
                  </div>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span className="px-2 py-1 rounded bg-secondary font-medium">
                      {resource.type}
                    </span>
                    <span>{resource.size}</span>
                  </div>
                </div>
                
                <h3 className="text-lg font-semibold text-foreground mb-2 group-hover:text-accent transition-colors">
                  {resource.title}
                </h3>
                <p className="text-sm text-muted-foreground mb-4">
                  {resource.description}
                </p>
                
                <div className="flex items-center gap-2 text-sm font-medium text-accent">
                  <span>View Resource</span>
                  <ExternalLink className="w-4 h-4" />
                </div>
              </Link>
            ))}
          </div>
          
          {/* Additional Info */}
          <div className="mt-16 p-8 rounded-xl bg-card border border-border">
            <h2 className="text-xl font-semibold text-foreground mb-4">
              Need More Help?
            </h2>
            <p className="text-muted-foreground mb-6">
              These resources are designed to help you integrate MarketMate into your trading 
              infrastructure. For additional support, check our documentation or reach out to 
              our developer support team.
            </p>
            <div className="flex flex-wrap gap-4">
              <Button asChild>
                <Link href="/developers#documentation">
                  <BookOpen className="w-4 h-4 mr-2" />
                  Full Documentation
                </Link>
              </Button>
              <Button variant="outline" asChild>
                <Link href="/developers#collections">
                  <FileJson className="w-4 h-4 mr-2" />
                  API Collections
                </Link>
              </Button>
            </div>
          </div>
        </div>
      </div>
      
      <Footer />
    </main>
  )
}
