import { Button } from "@/components/ui/button"
import { ArrowRight, Sparkles } from "lucide-react"
import Link from "next/link"

export function AcademyCta() {
  return (
    <section className="py-20">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-accent/20 via-card to-card border border-border">
          <div className="absolute inset-0 bg-grid-white/5 [mask-image:radial-gradient(white,transparent_70%)]" />
          
          <div className="relative px-8 py-16 sm:px-16 sm:py-20 text-center">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-accent/10 border border-accent/20 mb-6">
              <Sparkles className="w-4 h-4 text-accent" />
              <span className="text-sm text-accent">Part of the MarketMate Ecosystem</span>
            </div>
            
            <h2 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl text-balance">
              Education that strengthens the ecosystem
            </h2>
            
            <p className="mt-6 text-lg text-muted-foreground max-w-2xl mx-auto text-pretty">
              We believe knowledge should be accessible. MMAcademy exists to build trust, 
              support the next generation of traders and developers, and strengthen the 
              entire MarketMate community.
            </p>
            
            <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
              <Button size="lg" className="bg-primary text-primary-foreground hover:bg-primary/90" asChild>
                <Link href="/academy#featured-courses">
                  Start Learning Free
                  <ArrowRight className="ml-2 w-4 h-4" />
                </Link>
              </Button>
              <Button size="lg" variant="outline" className="border-border text-foreground hover:bg-secondary" asChild>
                <Link href="/developers">Explore MarketMate API</Link>
              </Button>
            </div>
            
            <p className="mt-8 text-sm text-muted-foreground">
              No credit card required. No subscriptions. Just learn.
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}
