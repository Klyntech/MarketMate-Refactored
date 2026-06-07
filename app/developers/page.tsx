import { Header } from "@/components/header"
import { Footer } from "@/components/footer"
import { DevHero } from "@/components/developers/dev-hero"
import { Documentation } from "@/components/developers/documentation"
import { SDKs } from "@/components/developers/sdks"
import { CodeExamples } from "@/components/developers/code-examples"
import { DevResources } from "@/components/developers/dev-resources"
import { DevCTA } from "@/components/developers/dev-cta"

export const metadata = {
  title: "Developer Resources Hub | MarketMate",
  description: "API documentation, SDKs, integration guides, and tools for building with MarketMate market intelligence infrastructure.",
}

export default function DevelopersPage() {
  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main>
        <DevHero />
        <Documentation />
        <SDKs />
        <CodeExamples />
        <DevResources />
        <DevCTA />
      </main>
      <Footer />
    </div>
  )
}
