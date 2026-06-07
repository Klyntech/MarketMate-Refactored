import { Header } from "@/components/header"
import { Footer } from "@/components/footer"
import { DeskHero } from "@/components/desk/desk-hero"
import { DeskIdentity } from "@/components/desk/desk-identity"
import { LiveSignalsDashboard } from "@/components/desk/live-signals"
import { SignalLifecycle } from "@/components/desk/signal-lifecycle"
import { TelegramArchitecture } from "@/components/desk/telegram-architecture"
import { DeskCTA } from "@/components/desk/desk-cta"

export const metadata = {
  title: "MarketMate Desk | Real-Time Signal Distribution",
  description: "The execution stream for MarketMate intelligence. Real-time signal delivery, lifecycle management, and tactical Telegram operations.",
}

export default function DeskPage() {
  return (
    <main className="min-h-screen bg-background">
      <Header />
      <DeskHero />
      <LiveSignalsDashboard />
      <DeskIdentity />
      <SignalLifecycle />
      <TelegramArchitecture />
      <DeskCTA />
      <Footer />
    </main>
  )
}
