import { Button } from "@/components/ui/button"
import Link from "next/link"
import { ArrowRight, MessageSquare, Github } from "lucide-react"

export function DevCTA() {
  return (
    <section className="py-24 bg-card/50">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="relative p-8 md:p-12 rounded-2xl bg-background border border-border overflow-hidden">
          <div className="absolute inset-0 -z-10">
            <div className="absolute top-0 right-0 w-64 h-64 bg-accent/5 rounded-full blur-3xl" />
          </div>
          
          <div className="max-w-2xl">
            <h2 className="text-2xl md:text-3xl font-bold text-foreground mb-4 text-balance">
              Ready to build with market intelligence?
            </h2>
            <p className="text-muted-foreground mb-8 text-pretty">
              Get your API key and start integrating real-time market state, conviction 
              signals, and liquidity analysis into your trading systems today.
            </p>
            
            <div className="flex flex-wrap gap-4">
              <Button size="lg" className="bg-primary text-primary-foreground hover:bg-primary/90 gap-2" asChild>
                <Link href="/dashboard/api-keys">
                  Get Free API Key
                  <ArrowRight className="w-4 h-4" />
                </Link>
              </Button>
              <Button size="lg" variant="outline" asChild>
                <Link href="#documentation">
                  Read the Docs
                </Link>
              </Button>
            </div>
          </div>
          
          <div className="mt-12 pt-8 border-t border-border">
            <h3 className="text-sm font-medium text-foreground mb-4">Need help?</h3>
            <div className="flex flex-wrap gap-6">
              <a 
                href="#"
                className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                <MessageSquare className="w-4 h-4" />
                Developer Discord
              </a>
              <a 
                href="https://github.com/Klynttech/MarketMate"
                className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                <Github className="w-4 h-4" />
                GitHub Discussions
              </a>
              <a 
                href="#"
                className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                <MessageSquare className="w-4 h-4" />
                Contact Support
              </a>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
