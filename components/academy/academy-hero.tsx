import { Button } from "@/components/ui/button"
import { BookOpen, Users, Zap } from "lucide-react"
import Link from "next/link"

export function AcademyHero() {
  return (
    <section className="relative pt-32 pb-20 overflow-hidden">
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[800px] h-[800px] rounded-full bg-accent/5 blur-3xl" />
      </div>
      
      <div className="relative mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-secondary border border-border mb-8">
            <BookOpen className="w-4 h-4 text-accent" />
            <span className="text-sm text-muted-foreground">Free & Open Access Education</span>
          </div>
          
          <h1 className="text-4xl font-bold tracking-tight text-foreground sm:text-6xl text-balance">
            MMAcademy
          </h1>
          <p className="mt-4 text-xl text-accent font-medium">
            Learn Market Intelligence
          </p>
          <p className="mt-6 text-lg text-muted-foreground leading-relaxed max-w-2xl mx-auto text-pretty">
            High-quality market education, openly accessible. Master market structure, liquidity behavior, 
            risk management, and financial intelligence systems without paywalls.
          </p>
          
          <div className="mt-10 flex items-center justify-center gap-4">
            <Button size="lg" className="bg-primary text-primary-foreground hover:bg-primary/90" asChild>
              <Link href="#featured-courses">Start Learning</Link>
            </Button>
            <Button size="lg" variant="outline" className="border-border text-foreground hover:bg-secondary" asChild>
              <Link href="#learning-paths">Browse Courses</Link>
            </Button>
          </div>
        </div>
        
        <div className="mt-16 grid grid-cols-1 gap-6 sm:grid-cols-3">
          <div className="flex items-center gap-4 p-6 rounded-xl bg-card border border-border">
            <div className="flex items-center justify-center w-12 h-12 rounded-lg bg-accent/10">
              <BookOpen className="w-6 h-6 text-accent" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">50+</p>
              <p className="text-sm text-muted-foreground">Free Lessons</p>
            </div>
          </div>
          
          <div className="flex items-center gap-4 p-6 rounded-xl bg-card border border-border">
            <div className="flex items-center justify-center w-12 h-12 rounded-lg bg-accent/10">
              <Users className="w-6 h-6 text-accent" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">10K+</p>
              <p className="text-sm text-muted-foreground">Active Learners</p>
            </div>
          </div>
          
          <div className="flex items-center gap-4 p-6 rounded-xl bg-card border border-border">
            <div className="flex items-center justify-center w-12 h-12 rounded-lg bg-accent/10">
              <Zap className="w-6 h-6 text-accent" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">100%</p>
              <p className="text-sm text-muted-foreground">Free Forever</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
