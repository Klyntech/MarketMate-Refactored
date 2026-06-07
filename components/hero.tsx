"use client"

import { Button } from "@/components/ui/button"
import { ArrowRight, Zap } from "lucide-react"
import Link from "next/link"

export function Hero() {
  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden pt-20">
      {/* Gradient orb background */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[800px] h-[800px] bg-accent/30 rounded-full blur-[120px] opacity-50" />
        <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-accent/20 rounded-full blur-[100px] opacity-30" />
      </div>
      
      <div className="relative z-10 mx-auto max-w-7xl px-6 lg:px-8 text-center">
        {/* Badge */}
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-secondary border border-border mb-8">
          <Zap className="w-4 h-4 text-accent" />
          <span className="text-sm font-medium text-muted-foreground">
            Now in Public Beta
          </span>
        </div>
        
        {/* Main headline */}
        <h1 className="text-5xl md:text-7xl lg:text-8xl font-bold tracking-tight text-foreground mb-6">
          <span className="block text-balance">Real-Time Market</span>
          <span className="block text-accent text-balance">Intelligence.</span>
        </h1>
        
        {/* Subtitle */}
        <p className="mx-auto max-w-2xl text-lg md:text-xl text-muted-foreground mb-10 text-pretty">
          The API-first platform converting live market structure, liquidity behavior, 
          and regime transitions into structured machine-readable intelligence.
        </p>
        
        {/* CTAs */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <Button size="lg" className="bg-primary text-primary-foreground hover:bg-primary/90 px-8 py-6 text-base" asChild>
            <Link href="/developers">
              Get API Access
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>
          <Button size="lg" variant="outline" className="border-border text-foreground hover:bg-secondary px-8 py-6 text-base" asChild>
            <Link href="/developers#quickstart">View Documentation</Link>
          </Button>
        </div>
        
        {/* Stats */}
        <div className="mt-20 grid grid-cols-2 md:grid-cols-4 gap-8 max-w-4xl mx-auto">
          {[
            { value: "<10ms", label: "Latency" },
            { value: "99.9%", label: "Uptime" },
            { value: "1M+", label: "API Calls/Day" },
            { value: "50+", label: "Market Signals" },
          ].map((stat) => (
            <div key={stat.label} className="text-center">
              <div className="text-3xl md:text-4xl font-bold text-foreground">{stat.value}</div>
              <div className="text-sm text-muted-foreground mt-1">{stat.label}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
