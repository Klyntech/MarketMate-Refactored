import { Metadata } from "next"
import { Header } from "@/components/header"
import { Footer } from "@/components/footer"
import { AcademyHero } from "@/components/academy/academy-hero"
import { LearningPaths } from "@/components/academy/learning-paths"
import { FeaturedCourses } from "@/components/academy/featured-courses"
import { Resources } from "@/components/academy/resources"
import { AcademyCta } from "@/components/academy/academy-cta"

export const metadata: Metadata = {
  title: "MMAcademy | Free Market Education | MarketMate",
  description: "High-quality market education, openly accessible. Master market structure, liquidity behavior, risk management, and financial intelligence systems without paywalls.",
}

export default function AcademyPage() {
  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main>
        <AcademyHero />
        <LearningPaths />
        <FeaturedCourses />
        <Resources />
        <AcademyCta />
      </main>
      <Footer />
    </div>
  )
}
