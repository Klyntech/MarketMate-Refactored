import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { 
  TrendingUp, 
  Shield, 
  Code, 
  BarChart3,
  ArrowRight,
  Clock,
  BookOpen
} from "lucide-react"

const paths = [
  {
    title: "Market Structure Fundamentals",
    description: "Understand how markets operate at a structural level. Learn about order flow, price discovery, and the mechanics behind market movements.",
    icon: TrendingUp,
    lessons: 12,
    duration: "4 hours",
    level: "Beginner",
    topics: ["Order Flow", "Price Discovery", "Market Microstructure", "Auction Theory"],
  },
  {
    title: "Liquidity & Volume Analysis",
    description: "Master the art of reading liquidity behavior. Detect sweeps, identify absorption zones, and understand volume dynamics.",
    icon: BarChart3,
    lessons: 15,
    duration: "6 hours",
    level: "Intermediate",
    topics: ["Liquidity Sweeps", "Volume Profile", "Absorption Detection", "Delta Analysis"],
  },
  {
    title: "Risk Management Systems",
    description: "Build robust risk frameworks for any market condition. Learn position sizing, portfolio heat management, and drawdown control.",
    icon: Shield,
    lessons: 10,
    duration: "3 hours",
    level: "All Levels",
    topics: ["Position Sizing", "Portfolio Heat", "Drawdown Management", "Risk/Reward"],
  },
  {
    title: "Building with MarketMate API",
    description: "Learn to integrate real-time market intelligence into your applications. Build trading bots, dashboards, and automated systems.",
    icon: Code,
    lessons: 18,
    duration: "8 hours",
    level: "Developer",
    topics: ["API Integration", "WebSocket Streams", "Event Handling", "State Management"],
  },
]

export function LearningPaths() {
  return (
    <section className="py-20 bg-card/50">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center mb-16">
          <h2 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
            Learning Paths
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            Structured curriculum designed to take you from fundamentals to mastery
          </p>
        </div>
        
        <div className="grid gap-6 md:grid-cols-2">
          {paths.map((path) => (
            <Card key={path.title} className="bg-card border-border hover:border-accent/50 transition-colors group">
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="flex items-center justify-center w-12 h-12 rounded-lg bg-accent/10 mb-4">
                    <path.icon className="w-6 h-6 text-accent" />
                  </div>
                  <Badge variant="secondary" className="bg-secondary text-muted-foreground">
                    {path.level}
                  </Badge>
                </div>
                <CardTitle className="text-xl text-foreground">{path.title}</CardTitle>
                <CardDescription className="text-muted-foreground">
                  {path.description}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-4 text-sm text-muted-foreground mb-4">
                  <div className="flex items-center gap-1">
                    <BookOpen className="w-4 h-4" />
                    <span>{path.lessons} lessons</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Clock className="w-4 h-4" />
                    <span>{path.duration}</span>
                  </div>
                </div>
                
                <div className="flex flex-wrap gap-2 mb-6">
                  {path.topics.map((topic) => (
                    <span 
                      key={topic}
                      className="px-2 py-1 text-xs rounded-md bg-secondary text-muted-foreground"
                    >
                      {topic}
                    </span>
                  ))}
                </div>
                
                <Button variant="ghost" className="w-full justify-between text-foreground hover:text-accent hover:bg-accent/10 group-hover:text-accent">
                  Start Learning
                  <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  )
}
