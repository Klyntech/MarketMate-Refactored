"use client"

import { useSession } from "next-auth/react"
import Link from "next/link"
import useSWR from "swr"
import { Header } from "@/components/header"
import { Footer } from "@/components/footer"
import { Button } from "@/components/ui/button"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import {
  Key,
  Activity,
  Signal,
  Clock,
  Plus,
  BookOpen,
  BarChart3,
  Settings,
  ArrowRight,
} from "lucide-react"

const fetcher = (url: string) => fetch(url).then((r) => r.json())

export default function DashboardPage() {
  const { data: session } = useSession()
  const { data: keysData } = useSWR("/api/keys", fetcher)

  const apiKeys = keysData?.keys ?? []
  const activeKeyCount = apiKeys.filter((k: { revokedAt: string | null }) => !k.revokedAt).length

  const stats = [
    {
      label: "API Keys",
      value: activeKeyCount,
      icon: Key,
    },
    {
      label: "Total Requests",
      value: "1,284",
      icon: Activity,
    },
    {
      label: "Active Signals",
      value: "7",
      icon: Signal,
    },
    {
      label: "Uptime",
      value: "99.9%",
      icon: Clock,
    },
  ]

  const quickActions = [
    {
      label: "Create API Key",
      description: "Generate a new API key for your integrations",
      icon: Plus,
      href: "/dashboard/api-keys",
      primary: true,
    },
    {
      label: "View Documentation",
      description: "Explore API references and guides",
      icon: BookOpen,
      href: "/developers",
      primary: false,
    },
    {
      label: "Go to Desk",
      description: "Access real-time signal distribution",
      icon: BarChart3,
      href: "/desk",
      primary: false,
    },
    {
      label: "Account Settings",
      description: "Manage your account preferences",
      icon: Settings,
      href: "#",
      primary: false,
      disabled: true,
    },
  ]

  return (
    <main className="min-h-screen bg-background flex flex-col">
      <Header />

      <div className="flex-1 pt-20">
        <div className="mx-auto max-w-7xl px-6 py-8 lg:px-8">
          {/* Breadcrumb */}
          <Breadcrumb className="mb-6">
            <BreadcrumbList>
              <BreadcrumbItem>
                <BreadcrumbLink asChild>
                  <Link href="/">Home</Link>
                </BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbPage>Dashboard</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>

          {/* Page Title & Welcome */}
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-foreground mb-2">Dashboard</h1>
            <p className="text-muted-foreground">
              Welcome back, {session?.user?.name || session?.user?.email || "trader"}. Here&apos;s an overview of your account.
            </p>
          </div>

          {/* Stats Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            {stats.map((stat) => (
              <div
                key={stat.label}
                className="p-6 rounded-xl bg-card border border-border"
              >
                <div className="flex items-center gap-3 mb-4">
                  <div className="p-2 rounded-lg bg-secondary">
                    <stat.icon className="w-5 h-5 text-accent" />
                  </div>
                  <span className="text-sm text-muted-foreground">{stat.label}</span>
                </div>
                <div className="text-2xl font-bold text-foreground">{stat.value}</div>
              </div>
            ))}
          </div>

          {/* Quick Actions */}
          <div className="mb-8">
            <h2 className="text-xl font-semibold text-foreground mb-4">Quick Actions</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {quickActions.map((action) => (
                <div
                  key={action.label}
                  className="p-6 rounded-xl bg-card border border-border hover:border-accent/50 transition-colors group"
                >
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 rounded-lg bg-secondary">
                      <action.icon className="w-5 h-5 text-accent" />
                    </div>
                    <h3 className="font-medium text-foreground">{action.label}</h3>
                  </div>
                  <p className="text-sm text-muted-foreground mb-4">{action.description}</p>
                  {action.disabled ? (
                    <Button
                      variant="outline"
                      size="sm"
                      className="w-full opacity-50 cursor-not-allowed"
                      disabled
                    >
                      Coming Soon
                    </Button>
                  ) : action.primary ? (
                    <Button
                      size="sm"
                      className="w-full bg-primary text-primary-foreground hover:bg-primary/90 group-hover:shadow-lg group-hover:shadow-primary/20 transition-all"
                      asChild
                    >
                      <Link href={action.href}>
                        Get Started
                        <ArrowRight className="w-4 h-4 ml-1 group-hover:translate-x-1 transition-transform" />
                      </Link>
                    </Button>
                  ) : (
                    <Button
                      variant="outline"
                      size="sm"
                      className="w-full border-border hover:border-accent/50"
                      asChild
                    >
                      <Link href={action.href}>
                        Open
                        <ArrowRight className="w-4 h-4 ml-1" />
                      </Link>
                    </Button>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Recent API Keys */}
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold text-foreground">Recent API Keys</h2>
              <Button variant="outline" size="sm" className="border-border hover:border-accent/50" asChild>
                <Link href="/dashboard/api-keys">
                  View All
                  <ArrowRight className="w-4 h-4 ml-1" />
                </Link>
              </Button>
            </div>

            {apiKeys.length === 0 ? (
              <div className="p-8 rounded-xl bg-card border border-border text-center">
                <Key className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
                <p className="text-muted-foreground mb-4">No API keys yet</p>
                <Button className="bg-primary text-primary-foreground hover:bg-primary/90" asChild>
                  <Link href="/dashboard/api-keys">
                    <Plus className="w-4 h-4 mr-1" />
                    Create Your First API Key
                  </Link>
                </Button>
              </div>
            ) : (
              <div className="rounded-xl bg-card border border-border overflow-hidden">
                <div className="divide-y divide-border">
                  {apiKeys.slice(0, 5).map((key: {
                    id: string
                    name: string
                    prefix: string
                    environment: string
                    revokedAt: string | null
                    createdAt: string
                  }) => (
                    <div
                      key={key.id}
                      className="flex items-center justify-between p-4 hover:bg-secondary/50 transition-colors"
                    >
                      <div className="flex items-center gap-4 min-w-0">
                        <div className="p-2 rounded-lg bg-secondary shrink-0">
                          <Key className="w-4 h-4 text-accent" />
                        </div>
                        <div className="min-w-0">
                          <p className="font-medium text-foreground truncate">{key.name}</p>
                          <p className="text-sm text-muted-foreground font-mono">{key.prefix}****</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <span
                          className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-medium ${
                            key.environment === "live"
                              ? "bg-accent/20 text-accent"
                              : "bg-secondary text-secondary-foreground"
                          }`}
                        >
                          {key.environment === "live" ? "Live" : "Test"}
                        </span>
                        <span className="flex items-center gap-1.5 text-xs">
                          <span
                            className={`w-2 h-2 rounded-full ${
                              key.revokedAt ? "bg-red-500" : "bg-green-500"
                            }`}
                          />
                          <span className="text-muted-foreground">
                            {key.revokedAt ? "Revoked" : "Active"}
                          </span>
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      <Footer />
    </main>
  )
}
