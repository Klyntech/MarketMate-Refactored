"use client"

import { Button } from "@/components/ui/button"
import { ArrowRight, Radio } from "lucide-react"
import Link from "next/link"
import { useHealth } from "@/hooks/use-signals"
import { cn } from "@/lib/utils"

export function DeskHero() {
  const { isHealthy, isLoading, isBackendDown } = useHealth()
  
  return (
    <section className="relative min-h-[90vh] flex items-center justify-center overflow-hidden pt-20">
      {/* Subtle gradient background */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[600px] h-[600px] bg-primary/10 rounded-full blur-[150px] opacity-40" />
      </div>
      
      <div className="relative z-10 mx-auto max-w-7xl px-6 lg:px-8 text-center">
        {/* Status indicator */}
        <div className="inline-flex items-center gap-3 px-4 py-2 rounded-full bg-secondary border border-border mb-10">
          <span className="relative flex h-2 w-2">
            <span className={cn(
              "animate-ping absolute inline-flex h-full w-full rounded-full opacity-75",
              isHealthy ? "bg-emerald-400" : isLoading ? "bg-amber-400" : "bg-red-400"
            )}></span>
            <span className={cn(
              "relative inline-flex rounded-full h-2 w-2",
              isHealthy ? "bg-emerald-500" : isLoading ? "bg-amber-500" : "bg-red-500"
            )}></span>
          </span>
          <span className="text-sm font-medium text-muted-foreground">
            {isHealthy ? "Live Signal Stream Active" : isLoading ? "Connecting..." : isBackendDown ? "API Offline — Sign In Required" : "Stream Offline"}
          </span>
        </div>
        
        {/* Main headline */}
        <h1 className="text-5xl md:text-7xl lg:text-8xl font-bold tracking-tight text-foreground mb-6">
          <span className="block text-balance">MarketMate</span>
          <span className="block text-primary text-balance">Desk</span>
        </h1>
        
        {/* Subtitle - institutional, not hype */}
        <p className="mx-auto max-w-2xl text-lg md:text-xl text-muted-foreground mb-4 text-pretty">
          The execution stream for MarketMate intelligence.
        </p>
        <p className="mx-auto max-w-xl text-base text-muted-foreground/80 mb-12 text-pretty">
          Real-time signal delivery. Lifecycle management. Tactical distribution.
        </p>
        
        {/* Single, focused CTA */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <Button size="lg" className="bg-primary text-primary-foreground hover:bg-primary/90 px-8 py-6 text-base" asChild>
            <Link href="/login">
              <Radio className="mr-2 h-4 w-4" />
              Connect to Signal Stream
            </Link>
          </Button>
          <Button size="lg" variant="outline" className="border-border text-foreground hover:bg-secondary px-8 py-6 text-base" asChild>
            <Link href="#architecture">
              View Architecture
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>
        </div>
        
        {/* Minimal stats - operational metrics only */}
        <div className="mt-24 grid grid-cols-3 gap-8 max-w-2xl mx-auto">
          {[
            { value: "24/7", label: "Signal Coverage" },
            { value: "<2s", label: "Delivery Latency" },
            { value: "Live", label: "State Updates" },
          ].map((stat) => (
            <div key={stat.label} className="text-center">
              <div className="text-2xl md:text-3xl font-bold text-foreground">{stat.value}</div>
              <div className="text-xs text-muted-foreground mt-1 uppercase tracking-wider">{stat.label}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
