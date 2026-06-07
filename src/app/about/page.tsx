'use client'

import { motion } from 'framer-motion'
import { Target, Cpu, Zap, Shield, Eye, Lightbulb, Users, ArrowRight } from 'lucide-react'

const fadeInUp = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: 'easeOut' as const } },
}

const staggerContainer = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.1 } },
}

const values = [
  {
    icon: Target,
    title: 'Precision',
    description:
      'Every signal we produce is measured, validated, and scored. We reject ambiguity in favor of quantifiable conviction. Our systems don\'t guess — they calculate, and every calculation carries a confidence interval.',
  },
  {
    icon: Eye,
    title: 'Transparency',
    description:
      'Black-box intelligence is an oxymoron. Every MarketMate signal is traceable to its source data, processing logic, and scoring methodology. If our AI reaches a conclusion, you can see exactly how it got there.',
  },
  {
    icon: Shield,
    title: 'Reliability',
    description:
      'Markets don\'t sleep, and neither does our infrastructure. Built for 99.9% uptime with redundant data pipelines and graceful degradation. When volatility spikes, our systems perform at their peak — not their breaking point.',
  },
  {
    icon: Lightbulb,
    title: 'Innovation',
    description:
      'The market evolves continuously, and our technology must evolve faster. We invest in research across natural language processing, regime detection, and real-time inference to stay ahead of the curve — not chasing it.',
  },
]

const architectureSteps = [
  {
    icon: Cpu,
    title: '5-Brain Architecture',
    description:
      'Five specialized analytical engines — TrendBrain, MomentumBrain, SentimentBrain, OrderBrain, and SweepBrain — each process market data through their own domain-specific lens. Rather than one monolithic model trying to understand everything, each brain develops deep expertise in a single dimension of market behavior, producing independent conviction scores that form the foundation of our signal pipeline.',
  },
  {
    icon: Zap,
    title: '8-Gate Pipeline',
    description:
      'Raw brain outputs pass through eight sequential validation gates: Data Freshness, Noise Filtering, Regime Alignment, Convergence Check, Divergence Screening, Confidence Calibration, Risk Overlay, and Final Consensus. Each gate acts as a quality filter, ensuring that only signals which survive the full gauntlet reach the output layer. A signal rejected at any gate is logged, analyzed, and used to improve future filtering.',
  },
  {
    icon: Users,
    title: 'MATE AI Interpreter',
    description:
      'The MATE (Market Analysis & Trading Engine) AI interpreter synthesizes validated pipeline outputs into human-readable market narratives and actionable intelligence. MATE doesn\'t just aggregate — it interprets, contextualizes, and explains. It identifies the "why" behind market movements, connects disparate signals into coherent themes, and delivers intelligence in the format that matches how traders actually think: with conviction, clarity, and context.',
  },
]

export default function AboutPage() {
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
            About MarketMate
          </motion.p>
          <motion.h1 variants={fadeInUp} className="text-4xl sm:text-5xl font-bold tracking-tight mb-6">
            Financial Intelligence{' '}
            <span className="bg-gradient-to-r from-emerald-400 to-emerald-300 bg-clip-text text-transparent">
              Infrastructure
            </span>
          </motion.h1>
          <motion.p variants={fadeInUp} className="text-lg text-zinc-400 leading-relaxed max-w-2xl">
            MarketMate is building the infrastructure layer for market intelligence. Our real-time
            market state engine transforms raw market data into structured, scored, and interpretable
            signals — enabling traders and developers to make decisions based on conviction, not
            guesswork.
          </motion.p>
        </motion.div>

        {/* Mission */}
        <motion.section
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-100px' }}
          variants={staggerContainer}
          className="mb-20"
        >
          <motion.div variants={fadeInUp} className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-6 sm:p-8">
            <h2 className="text-2xl font-bold mb-4">Our Mission</h2>
            <p className="text-zinc-400 leading-relaxed mb-4">
              Founded in 2024, MarketMate emerged from a straightforward observation: the gap between
              institutional-grade market intelligence and what individual traders can access is
              artificially wide. Not because the technology doesn&apos;t exist — but because it&apos;s locked
              behind proprietary systems, six-figure subscriptions, and closed ecosystems.
            </p>
            <p className="text-zinc-400 leading-relaxed mb-4">
              We&apos;re building the infrastructure to close that gap. Our real-time market state engine
              processes thousands of data points per second across price action, order flow,
              liquidity dynamics, sentiment, and macro signals — transforming them into a structured,
              queryable intelligence layer that any developer or trader can integrate into their
              workflow.
            </p>
            <p className="text-zinc-400 leading-relaxed">
              This isn&apos;t about replacing human judgment. It&apos;s about giving that judgment the
              information architecture it deserves — real-time, validated, and interpretable.
            </p>
          </motion.div>
        </motion.section>

        {/* Philosophy */}
        <motion.section
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-100px' }}
          variants={staggerContainer}
          className="mb-20"
        >
          <motion.h2 variants={fadeInUp} className="text-2xl font-bold mb-6">
            Our Philosophy
          </motion.h2>
          <motion.div variants={fadeInUp} className="grid gap-6 sm:grid-cols-2">
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-6">
              <h3 className="text-lg font-semibold text-emerald-400 mb-3">Structure Over Noise</h3>
              <p className="text-zinc-400 text-sm leading-relaxed">
                Markets produce an infinite stream of noise. The edge isn&apos;t in processing more
                data — it&apos;s in applying the right structure to filter signal from noise at every
                layer. Our 8-gate pipeline exists precisely for this reason: to systematically
                eliminate noise before it reaches the output, ensuring that every signal that passes
                through carries genuine informational weight.
              </p>
            </div>
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-6">
              <h3 className="text-lg font-semibold text-emerald-400 mb-3">Conviction Over Emotion</h3>
              <p className="text-zinc-400 text-sm leading-relaxed">
                The difference between a guess and a decision is conviction. Our scoring system
                ranges from -1.0 to +1.0 for a reason — it forces nuance. A conviction of +0.3 is
                fundamentally different from +0.8, and understanding that difference is what
                separates disciplined trading from emotional reaction. We build tools that quantify
                certainty, not manufacture it.
              </p>
            </div>
          </motion.div>
        </motion.section>

        {/* Architecture */}
        <motion.section
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-100px' }}
          variants={staggerContainer}
          className="mb-20"
        >
          <motion.h2 variants={fadeInUp} className="text-2xl font-bold mb-6">
            How It Works
          </motion.h2>
          <motion.p variants={fadeInUp} className="text-zinc-400 leading-relaxed mb-8">
            MarketMate&apos;s intelligence pipeline is built on three interconnected layers, each
            responsible for a distinct phase of signal processing. Together, they transform raw
            market data into actionable, interpretable intelligence.
          </motion.p>
          <div className="space-y-6">
            {architectureSteps.map((step, i) => (
              <motion.div
                key={step.title}
                variants={fadeInUp}
                className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-6 sm:p-8 flex gap-5"
              >
                <div className="flex-shrink-0 w-12 h-12 rounded-lg bg-emerald-400/10 flex items-center justify-center">
                  <step.icon className="w-6 h-6 text-emerald-400" />
                </div>
                <div>
                  <div className="flex items-center gap-3 mb-3">
                    <span className="text-xs font-semibold text-emerald-400/70 uppercase tracking-wider">
                      Layer {i + 1}
                    </span>
                    <h3 className="text-lg font-semibold">{step.title}</h3>
                  </div>
                  <p className="text-zinc-400 text-sm leading-relaxed">{step.description}</p>
                </div>
              </motion.div>
            ))}
          </div>
          <motion.div
            variants={fadeInUp}
            className="mt-8 flex items-center gap-3 text-zinc-500 text-sm"
          >
            <ArrowRight className="w-4 h-4 text-emerald-400" />
            <span>
              Data flows: Raw Market Data &rarr; 5 Brains &rarr; 8 Gates &rarr; MATE Interpreter
              &rarr; Structured Intelligence
            </span>
          </motion.div>
        </motion.section>

        {/* Values */}
        <motion.section
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-100px' }}
          variants={staggerContainer}
          className="mb-20"
        >
          <motion.h2 variants={fadeInUp} className="text-2xl font-bold mb-6">
            Our Values
          </motion.h2>
          <div className="grid gap-6 sm:grid-cols-2">
            {values.map((value) => (
              <motion.div
                key={value.title}
                variants={fadeInUp}
                className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-6 hover:border-emerald-400/20 transition-colors"
              >
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-10 h-10 rounded-lg bg-emerald-400/10 flex items-center justify-center">
                    <value.icon className="w-5 h-5 text-emerald-400" />
                  </div>
                  <h3 className="text-lg font-semibold">{value.title}</h3>
                </div>
                <p className="text-zinc-400 text-sm leading-relaxed">{value.description}</p>
              </motion.div>
            ))}
          </div>
        </motion.section>

        {/* Vision */}
        <motion.section
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-100px' }}
          variants={staggerContainer}
        >
          <motion.div variants={fadeInUp} className="rounded-xl border border-emerald-400/20 bg-emerald-400/[0.03] p-6 sm:p-8">
            <h2 className="text-2xl font-bold mb-4">Our Vision</h2>
            <p className="text-zinc-400 leading-relaxed mb-4">
              Making institutional-grade market intelligence accessible to every trader and
              developer. We believe the next generation of trading tools won&apos;t be built by
              institutions — they&apos;ll be built by developers who have access to the same quality
              of intelligence infrastructure, at a fraction of the cost.
            </p>
            <p className="text-zinc-400 leading-relaxed">
              Our API-first approach means that MarketMate isn&apos;t just a product — it&apos;s a platform.
              Whether you&apos;re building a personal trading bot, powering a fintech application, or
              running a quantitative desk, the intelligence layer should be consistent, reliable,
              and transparent. That&apos;s the infrastructure we&apos;re building, and we&apos;re just getting
              started.
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
