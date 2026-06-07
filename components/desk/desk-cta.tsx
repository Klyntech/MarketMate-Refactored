import { Button } from "@/components/ui/button"
import { Send, ArrowRight } from "lucide-react"
import Link from "next/link"

export function DeskCTA() {
  return (
    <section className="py-24 border-t border-border">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="relative overflow-hidden rounded-2xl bg-card border border-border p-12 md:p-16">
          {/* Subtle background accent */}
          <div className="absolute top-0 right-0 w-64 h-64 bg-primary/5 rounded-full blur-3xl" />
          
          <div className="relative max-w-2xl">
            <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4 text-balance">
              Connect to the Signal Stream
            </h2>
            <p className="text-muted-foreground mb-8 text-pretty">
              Not another signal group. A live institutional intelligence stream 
              with lifecycle tracking and tactical delivery.
            </p>
            
            <div className="flex flex-col sm:flex-row gap-4">
              <Button size="lg" className="bg-primary text-primary-foreground hover:bg-primary/90" asChild>
                <a href="https://t.me/MarketMateBot" target="_blank" rel="noopener noreferrer">
                  <Send className="mr-2 h-4 w-4" />
                  Join Telegram Channel
                </a>
              </Button>
              <Button size="lg" variant="outline" className="border-border text-foreground hover:bg-secondary" asChild>
                <Link href="/#pricing">
                  View Pricing
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
            </div>

            {/* Trust indicators */}
            <div className="mt-10 pt-8 border-t border-border">
              <div className="flex flex-wrap gap-x-8 gap-y-4 text-sm text-muted-foreground">
                <div className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                  Live signal stream
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                  State lifecycle tracking
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                  MATE AI assistant access
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
