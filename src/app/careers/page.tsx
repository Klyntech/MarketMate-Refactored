'use client'

import { motion } from 'framer-motion'
import {
  Globe,
  Clock,
  GraduationCap,
  Laptop,
  DollarSign,
  Wrench,
  MapPin,
  Briefcase,
  Sparkles,
} from 'lucide-react'

const fadeInUp = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: 'easeOut' as const } },
}

const staggerContainer = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.1 } },
}

const benefits = [
  {
    icon: DollarSign,
    title: 'Competitive Equity',
    description:
      'Early team members receive meaningful equity grants. We believe the people building the product should share in its success, and our equity packages reflect that conviction.',
  },
  {
    icon: Globe,
    title: 'Remote Flexibility',
    description:
      'Work from wherever you do your best work. We\'re a distributed team spanning multiple time zones, and we\'ve built our workflows around async-first communication that respects your schedule.',
  },
  {
    icon: GraduationCap,
    title: 'Learning Budget',
    description:
      'Every team member receives an annual learning budget for courses, books, certifications, and workshops. Whether you want to deep-dive into machine learning or explore a new programming paradigm, we fund your growth.',
  },
  {
    icon: Laptop,
    title: 'Conference Attendance',
    description:
      'We sponsor attendance at two industry conferences per year — covering travel, tickets, and expenses. Present your work, learn from peers, and bring insights back to the team.',
  },
  {
    icon: Wrench,
    title: 'Top-Tier Tools',
    description:
      'From high-performance hardware to premium development tools and SaaS subscriptions, we make sure you have everything you need to work effectively. No friction from subpar tooling.',
  },
  {
    icon: Clock,
    title: 'Deep Work Focus',
    description:
      'We protect focused work time with designated meeting-free blocks and async-by-default communication. Your calendar belongs to you — we optimize for output, not hours logged.',
  },
]

interface Position {
  title: string
  department: string
  type: string
  description: string
}

const positions: Position[] = [
  {
    title: 'Senior Backend Engineer (Python/FastAPI)',
    department: 'Engineering',
    type: 'Full-time · Remote',
    description:
      'Design and build the core market intelligence pipeline. You\'ll work on our real-time data ingestion layer, signal processing architecture, and API infrastructure that serves thousands of requests per second. Experience with async Python, WebSocket protocols, and high-throughput data systems is essential.',
  },
  {
    title: 'ML/AI Engineer (Market Intelligence)',
    department: 'AI & Research',
    type: 'Full-time · Remote',
    description:
      'Develop and deploy the models powering our 5-brain architecture. You\'ll research and implement market regime detection, sentiment analysis, and signal synthesis algorithms. Strong background in time-series analysis, NLP, and production ML systems required. Domain knowledge in financial markets is a significant plus.',
  },
  {
    title: 'Full-Stack Developer (Next.js/TypeScript)',
    department: 'Product',
    type: 'Full-time · Remote',
    description:
      'Build the developer dashboard, documentation platform, and client-facing tools that make MarketMate accessible. You\'ll work across the entire stack — from designing responsive UIs with Next.js and Tailwind to building API routes and integrating WebSocket streams for real-time data visualization.',
  },
  {
    title: 'DevOps/SRE Engineer',
    department: 'Infrastructure',
    type: 'Full-time · Remote',
    description:
      'Own the reliability, scalability, and security of MarketMate\'s infrastructure. You\'ll design CI/CD pipelines, manage container orchestration, implement monitoring and alerting systems, and ensure our 99.9% uptime SLA. Experience with Kubernetes, Terraform, and observability stacks is required.',
  },
]

export default function CareersPage() {
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
        {/* Hero */}
        <motion.div
          initial="hidden"
          animate="visible"
          variants={staggerContainer}
          className="mb-20"
        >
          <motion.p variants={fadeInUp} className="text-emerald-400 text-sm font-semibold tracking-wider uppercase mb-4">
            Careers at MarketMate
          </motion.p>
          <motion.h1 variants={fadeInUp} className="text-4xl sm:text-5xl font-bold tracking-tight mb-6">
            Build the Future of{' '}
            <span className="bg-gradient-to-r from-emerald-400 to-emerald-300 bg-clip-text text-transparent">
              Market Intelligence
            </span>
          </motion.h1>
          <motion.p variants={fadeInUp} className="text-lg text-zinc-400 leading-relaxed max-w-2xl">
            We&apos;re assembling a team of engineers, researchers, and builders who believe that
            market intelligence should be structured, transparent, and accessible. If you want to
            work on infrastructure that processes real-time financial data at scale and translates it
            into actionable intelligence, we want to hear from you.
          </motion.p>
        </motion.div>

        {/* Culture */}
        <motion.section
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-100px' }}
          variants={staggerContainer}
          className="mb-20"
        >
          <motion.h2 variants={fadeInUp} className="text-2xl font-bold mb-6">
            How We Work
          </motion.h2>
          <motion.div variants={fadeInUp} className="grid gap-6 sm:grid-cols-3">
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-6">
              <div className="w-10 h-10 rounded-lg bg-emerald-400/10 flex items-center justify-center mb-4">
                <Globe className="w-5 h-5 text-emerald-400" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Remote-First</h3>
              <p className="text-zinc-400 text-sm leading-relaxed">
                Our team is distributed globally. We don&apos;t have an office you need to commute to —
                we have infrastructure that lets you contribute from anywhere with a reliable
                internet connection and a quiet space to think.
              </p>
            </div>
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-6">
              <div className="w-10 h-10 rounded-lg bg-emerald-400/10 flex items-center justify-center mb-4">
                <Clock className="w-5 h-5 text-emerald-400" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Async Communication</h3>
              <p className="text-zinc-400 text-sm leading-relaxed">
                We default to written communication. Decisions are documented in threads, not
                meeting rooms. When we do meet, it&apos;s purposeful and time-boxed. We trust you to
                manage your own schedule and respond within reasonable windows.
              </p>
            </div>
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-6">
              <div className="w-10 h-10 rounded-lg bg-emerald-400/10 flex items-center justify-center mb-4">
                <Laptop className="w-5 h-5 text-emerald-400" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Deep Work Focus</h3>
              <p className="text-zinc-400 text-sm leading-relaxed">
                Building market intelligence infrastructure requires sustained concentration. We
                protect deep work with meeting-free blocks, minimal Slack interruptions, and a
                culture that measures output, not online presence.
              </p>
            </div>
          </motion.div>
        </motion.section>

        {/* Benefits */}
        <motion.section
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-100px' }}
          variants={staggerContainer}
          className="mb-20"
        >
          <motion.h2 variants={fadeInUp} className="text-2xl font-bold mb-6">
            Benefits &amp; Perks
          </motion.h2>
          <motion.div variants={fadeInUp} className="grid gap-4 sm:grid-cols-2">
            {benefits.map((benefit) => (
              <div
                key={benefit.title}
                className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-5 hover:border-emerald-400/20 transition-colors"
              >
                <div className="flex items-center gap-3 mb-2">
                  <benefit.icon className="w-5 h-5 text-emerald-400 flex-shrink-0" />
                  <h3 className="font-semibold">{benefit.title}</h3>
                </div>
                <p className="text-zinc-400 text-sm leading-relaxed">{benefit.description}</p>
              </div>
            ))}
          </motion.div>
        </motion.section>

        {/* Open Positions */}
        <motion.section
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-100px' }}
          variants={staggerContainer}
        >
          <motion.h2 variants={fadeInUp} className="text-2xl font-bold mb-6">
            Open Positions
          </motion.h2>
          <div className="space-y-4">
            {positions.map((position) => (
              <motion.div
                key={position.title}
                variants={fadeInUp}
                className="group relative rounded-xl border border-white/[0.06] bg-white/[0.02] p-6 hover:border-emerald-400/20 transition-all duration-300 hover:bg-white/[0.04]"
              >
                {/* Coming Soon Badge */}
                <div className="absolute top-4 right-4 flex items-center gap-1.5 rounded-full bg-emerald-400/10 border border-emerald-400/20 px-2.5 py-1">
                  <Sparkles className="w-3 h-3 text-emerald-400" />
                  <span className="text-xs font-medium text-emerald-400">Coming Soon</span>
                </div>

                <div className="flex flex-wrap items-center gap-3 mb-3">
                  <h3 className="text-lg font-semibold group-hover:text-emerald-400 transition-colors">
                    {position.title}
                  </h3>
                </div>

                <div className="flex flex-wrap items-center gap-3 mb-3 text-sm text-zinc-500">
                  <span className="flex items-center gap-1.5">
                    <Briefcase className="w-3.5 h-3.5" />
                    {position.department}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <MapPin className="w-3.5 h-3.5" />
                    {position.type}
                  </span>
                </div>

                <p className="text-zinc-400 text-sm leading-relaxed">{position.description}</p>
              </motion.div>
            ))}
          </div>

          <motion.div
            variants={fadeInUp}
            className="mt-8 rounded-xl border border-white/[0.06] bg-white/[0.02] p-6 text-center"
          >
            <p className="text-zinc-400 text-sm">
              Don&apos;t see a role that fits? We&apos;re always interested in hearing from exceptional
              people. Send us a note at{' '}
              <a
                href="mailto:careers@marketmate.io"
                className="text-emerald-400 hover:text-emerald-300 transition-colors"
              >
                careers@marketmate.io
              </a>{' '}
              and tell us how you&apos;d contribute to the mission.
            </p>
          </motion.div>
        </motion.section>
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
