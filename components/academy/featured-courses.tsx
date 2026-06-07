import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { PlayCircle, Clock, ArrowRight } from "lucide-react"

const courses = [
  {
    title: "Understanding Market Regimes",
    description: "Learn to identify trending, ranging, and volatile market conditions",
    duration: "25 min",
    category: "Market Structure",
    new: true,
  },
  {
    title: "Liquidity Sweep Detection",
    description: "Identify institutional stop hunts and liquidity grabs in real-time",
    duration: "32 min",
    category: "Liquidity",
    new: true,
  },
  {
    title: "Building Your First Trading Bot",
    description: "Connect to MarketMate API and build an automated trading system",
    duration: "45 min",
    category: "Development",
    new: false,
  },
  {
    title: "Conviction Scoring Explained",
    description: "How MarketMate calculates and uses conviction metrics",
    duration: "18 min",
    category: "Intelligence",
    new: false,
  },
  {
    title: "Risk-Adjusted Position Sizing",
    description: "Calculate optimal position sizes based on market conditions",
    duration: "28 min",
    category: "Risk Management",
    new: false,
  },
  {
    title: "Event-Driven Trading Strategies",
    description: "React to market events using structured intelligence data",
    duration: "35 min",
    category: "Strategy",
    new: true,
  },
]

export function FeaturedCourses() {
  return (
    <section className="py-20">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="flex items-center justify-between mb-12">
          <div>
            <h2 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
              Featured Lessons
            </h2>
            <p className="mt-2 text-lg text-muted-foreground">
              Start with these popular lessons from our community
            </p>
          </div>
          <Button variant="outline" className="hidden sm:flex border-border text-foreground hover:bg-secondary">
            View All Lessons
            <ArrowRight className="ml-2 w-4 h-4" />
          </Button>
        </div>
        
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {courses.map((course) => (
            <Card 
              key={course.title} 
              className="bg-card border-border hover:border-accent/50 transition-all cursor-pointer group"
            >
              <CardContent className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <Badge variant="secondary" className="bg-secondary text-muted-foreground text-xs">
                    {course.category}
                  </Badge>
                  {course.new && (
                    <Badge className="bg-accent/20 text-accent border-0 text-xs">
                      New
                    </Badge>
                  )}
                </div>
                
                <h3 className="text-lg font-semibold text-foreground mb-2 group-hover:text-accent transition-colors">
                  {course.title}
                </h3>
                <p className="text-sm text-muted-foreground mb-4">
                  {course.description}
                </p>
                
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1 text-sm text-muted-foreground">
                    <Clock className="w-4 h-4" />
                    <span>{course.duration}</span>
                  </div>
                  <div className="flex items-center justify-center w-10 h-10 rounded-full bg-accent/10 text-accent group-hover:bg-accent group-hover:text-primary-foreground transition-colors">
                    <PlayCircle className="w-5 h-5" />
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
        
        <div className="mt-8 flex justify-center sm:hidden">
          <Button variant="outline" className="border-border text-foreground hover:bg-secondary">
            View All Lessons
            <ArrowRight className="ml-2 w-4 h-4" />
          </Button>
        </div>
      </div>
    </section>
  )
}
