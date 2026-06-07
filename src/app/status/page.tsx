'use client'

import { motion } from 'framer-motion'
import { CheckCircle2, Clock, Activity, Sparkles } from 'lucide-react'

const fadeInUp = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: 'easeOut' as const } },
}

const staggerContainer = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.08 } },
}

type Status = 'Operational' | 'Degraded' | 'Outage'

interface Component {
  name: string
  status: Status
  description: string
}

const components: Component[] = [
  {
    name: 'MarketMate API',
    status: 'Operational',
    description: 'REST and WebSocket API endpoints for market intelligence data delivery',
  },
  {
    name: 'MATE AI Engine',
    status: 'Operational',
    description: 'Real-time market interpretation and narrative generation engine',
  },
  {
    name: 'WebSocket Streams',
    status: 'Operational',
    description: 'Live signal streaming and real-time market state updates',
  },
  {
    name: 'Data Ingestion',
    status: 'Operational',
    description: 'Market data feed processing, normalization, and pipeline input layer',
  },
  {
    name: 'Authentication Service',
    status: 'Operational',
    description: 'User authentication, API key validation, and session management',
  },
  {
    name: 'Dashboard',
    status: 'Operational',
    description: 'Web-based account management, monitoring, and developer tools',
  },
]

const statusColors: Record<Status, { dot: string; bg: string; text: string }> = {
  Operational: {
    dot: 'bg-emerald-400',
    bg: 'bg-emerald-400/10',
    text: 'text-emerald-400',
  },
  Degraded: {
    dot: 'bg-amber-400',
    bg: 'bg-amber-400/10',
    text: 'text-amber-400',
  },
  Outage: {
    dot: 'bg-red-400',
    bg: 'bg-red-400/10',
    text: 'text-red-400',
  },
}

const uptimeBars = Array.from({ length: 90 }, (_, i) => ({
  day: i + 1,
  status: 'operational' as const,
}))

export default function StatusPage() {
  const now = new Date()
  const formattedDate = now.toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZoneName: 'short',
  })

  return (
    <div className="min-h-screen bg-background text-white">
      {/* Nav */}
      <nav className="border-b border-white/[0.06] bg-zinc-950/80 backdrop-blur-md">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 flex h-16 items-center justify-between">
          <a href="/" className="flex items-center gap-2.5">
            <img src="/logo.png" alt="MarketMate" width={28} height={28} className="rounded-md" />
            <span className="text-lg font-bold text-white">
              Market<span className="text-emerald-400">Mate</span>
            </span>
          </a>
          <a href="/" className="text-sm text-zinc-400 hover:text-emerald-400 transition-colors">
            &larr; Back to Home
          </a>
        </div>
      </nav>

      {/* Content */}
      <main className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 py-16">
        {/* Header */}
        <motion.div
          initial="hidden"
          animate="visible"
          variants={staggerContainer}
          className="mb-12"
        >
          <motion.p variants={fadeInUp} className="text-emerald-400 text-sm font-semibold tracking-wider uppercase mb-4">
            System Status
          </motion.p>
          <motion.h1 variants={fadeInUp} className="text-4xl sm:text-5xl font-bold tracking-tight mb-4">
            Service Status
          </motion.h1>
          <motion.p variants={fadeInUp} className="text-zinc-500 text-sm">
            Real-time operational status for all MarketMate services
          </motion.p>
        </motion.div>

        {/* Overall Status */}
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          variants={fadeInUp}
          className="mb-10 rounded-xl border border-emerald-400/20 bg-emerald-400/[0.03] p-6 sm:p-8 flex items-center gap-4"
        >
          <CheckCircle2 className="w-8 h-8 text-emerald-400 flex-shrink-0" />
          <div>
            <p className="text-xl font-bold text-emerald-400">All Systems Operational</p>
            <p className="text-zinc-500 text-sm mt-1">
              All MarketMate services are running normally with no detected issues.
            </p>
          </div>
        </motion.div>

        {/* Component Statuses */}
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-50px' }}
          variants={staggerContainer}
          className="mb-10"
        >
          <motion.h2 variants={fadeInUp} className="text-lg font-bold mb-4">
            Component Status
          </motion.h2>
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] divide-y divide-white/[0.06]">
            {components.map((component) => {
              const colors = statusColors[component.status]
              return (
                <motion.div
                  key={component.name}
                  variants={fadeInUp}
                  className="flex items-center justify-between p-4 sm:p-5"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <span
                      className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${colors.dot}`}
                      title={component.status}
                    />
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">{component.name}</p>
                      <p className="text-xs text-zinc-500 truncate">{component.description}</p>
                    </div>
                  </div>
                  <span
                    className={`text-xs font-medium px-2.5 py-1 rounded-full flex-shrink-0 ${colors.bg} ${colors.text}`}
                  >
                    {component.status}
                  </span>
                </motion.div>
              )
            })}
          </div>
        </motion.div>

        {/* Uptime */}
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-50px' }}
          variants={staggerContainer}
          className="mb-10"
        >
          <motion.h2 variants={fadeInUp} className="text-lg font-bold mb-4">
            Uptime
          </motion.h2>
          <motion.div variants={fadeInUp} className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <p className="text-3xl font-bold text-emerald-400">Beta</p>
                <p className="text-zinc-500 text-sm">infrastructure status — building toward production SLA</p>
              </div>
              <Activity className="w-8 h-8 text-zinc-700" />
            </div>

            {/* Uptime bar chart */}
            <div className="flex gap-[2px] h-8 items-end mb-3">
              {uptimeBars.map((bar) => (
                <div
                  key={bar.day}
                  className="flex-1 rounded-sm bg-emerald-400/60 min-h-[4px] h-full"
                  title={`Day ${bar.day}: Operational`}
                />
              ))}
            </div>

            <div className="flex justify-between text-xs text-zinc-600">
              <span>90 days ago</span>
              <span>Today</span>
            </div>
          </motion.div>
        </motion.div>

        {/* Incident History */}
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-50px' }}
          variants={staggerContainer}
          className="mb-10"
        >
          <motion.h2 variants={fadeInUp} className="text-lg font-bold mb-4">
            Recent Incident History
          </motion.h2>
          <motion.div
            variants={fadeInUp}
            className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-6 text-center"
          >
            <CheckCircle2 className="w-8 h-8 text-zinc-700 mx-auto mb-2" />
            <p className="text-zinc-500 text-sm">No incidents in the last 90 days</p>
            <p className="text-zinc-600 text-xs mt-1">
              All services have been operating normally with no recorded disruptions.
            </p>
          </motion.div>
        </motion.div>

        {/* Last Checked */}
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          variants={fadeInUp}
          className="mb-6 flex items-center gap-2 text-zinc-600 text-xs"
        >
          <Clock className="w-3.5 h-3.5" />
          <span>Last checked: {formattedDate}</span>
        </motion.div>

        {/* Preview note */}
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          variants={fadeInUp}
          className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-5 flex items-center gap-4"
        >
          <div className="w-10 h-10 rounded-lg bg-emerald-400/10 flex items-center justify-center flex-shrink-0">
            <Sparkles className="w-5 h-5 text-emerald-400" />
          </div>
          <p className="text-zinc-400 text-sm">
            This is a status page preview. Real-time monitoring with live incident tracking,
            automated alerts, and historical reporting is coming soon.
          </p>
        </motion.div>
      </main>

      {/* Footer */}
      <footer className="border-t border-white/[0.06] py-8 text-center">
        <a href="/" className="text-sm text-zinc-400 hover:text-emerald-400 transition-colors">
          &larr; Back to MarketMate
        </a>
        <p className="text-xs text-zinc-600 mt-2">&copy; 2026 MarketMate. All rights reserved.</p>
      </footer>
    </div>
  )
}
