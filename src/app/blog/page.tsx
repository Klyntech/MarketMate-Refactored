'use client'

import { motion } from 'framer-motion'
import { Clock, ArrowUpRight, Sparkles } from 'lucide-react'

const fadeInUp = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: 'easeOut' as const } },
}

const staggerContainer = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.1 } },
}

type Category = 'Product' | 'Engineering' | 'Education' | 'Developer'

const categoryColors: Record<Category, string> = {
  Product: 'bg-emerald-400/10 text-emerald-400 border-emerald-400/20',
  Engineering: 'bg-blue-400/10 text-blue-400 border-blue-400/20',
  Education: 'bg-amber-400/10 text-amber-400 border-amber-400/20',
  Developer: 'bg-purple-400/10 text-purple-400 border-purple-400/20',
}

interface BlogPost {
  title: string
  date: string
  category: Category
  description: string
}

const posts: BlogPost[] = [
  {
    title: 'Introducing MATE v2.0: Real-Time Market Interpretation',
    date: 'January 2026',
    category: 'Product',
    description:
      'MATE v2.0 represents a fundamental leap in how market intelligence is delivered. The new real-time interpretation engine processes multi-brain signals simultaneously, generating contextual narratives that explain not just what is happening in the markets, but why it matters. With support for streaming responses via WebSocket and a redesigned confidence calibration system, MATE v2.0 turns raw signal data into the kind of insight that typically requires a team of analysts.',
  },
  {
    title: 'How the 5-Brain Architecture Detects Market Regime Changes',
    date: 'December 2025',
    category: 'Engineering',
    description:
      'Market regime changes — the shift from trending to ranging, from low to high volatility — are among the most critical moments for any trader. Our 5-brain architecture detects these transitions by monitoring convergence patterns across TrendBrain, MomentumBrain, and OrderBrain outputs. When multiple brains simultaneously shift their conviction distributions, the Regime Alignment gate triggers a regime change signal, often before it becomes visible on standard indicators.',
  },
  {
    title: 'Understanding Conviction Scoring: From -1.0 to +1.0',
    date: 'November 2025',
    category: 'Education',
    description:
      'Conviction scoring is the backbone of MarketMate\'s signal architecture. Unlike binary buy/sell signals, our -1.0 to +1.0 scale captures the full spectrum of market certainty. A score of +0.3 indicates mild bullish lean with significant uncertainty, while +0.8 signals strong directional conviction backed by convergent evidence. This post breaks down how each brain produces its score, how the 8-gate pipeline refines them, and how traders can use conviction magnitude to size positions and manage risk.',
  },
  {
    title: 'Building a Trading Bot with the MarketMate Python SDK',
    date: 'October 2025',
    category: 'Developer',
    description:
      'The MarketMate Python SDK provides a clean, typed interface to our entire intelligence pipeline. In this tutorial, we walk through building a fully automated trading bot that subscribes to real-time signal streams, filters by conviction threshold, and executes trades through a configurable broker adapter. We cover authentication, WebSocket connection management, signal interpretation, and best practices for handling rate limits and reconnection logic.',
  },
  {
    title: 'Liquidity Sweep Detection: The Science Behind SweepBrain',
    date: 'September 2025',
    category: 'Engineering',
    description:
      'Liquidity sweeps are among the most informative yet underutilized signals in market microstructure. When price briefly pierces a key level — taking out stop losses — only to reverse, it reveals the hand of institutional accumulation or distribution. SweepBrain combines order flow analysis with volume profile mapping and historical sweep pattern recognition to identify these events in real-time, scoring each sweep by its significance and likely market impact.',
  },
  {
    title: 'Gate Pipeline Deep Dive: 8 Layers of Signal Validation',
    date: 'August 2025',
    category: 'Engineering',
    description:
      'Raw signals are cheap; validated signals are invaluable. Our 8-gate pipeline applies sequential quality filters to every brain output before it reaches the MATE interpreter. This deep dive examines each gate — from Data Freshness, which rejects stale inputs, to Final Consensus, which requires multi-brain agreement — explaining the logic, thresholds, and failure modes that shape our signal quality. Understanding the pipeline is essential for anyone building on the MarketMate API.',
  },
]

export default function BlogPage() {
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
          className="mb-16"
        >
          <motion.p variants={fadeInUp} className="text-emerald-400 text-sm font-semibold tracking-wider uppercase mb-4">
            MarketMate Blog
          </motion.p>
          <motion.h1 variants={fadeInUp} className="text-4xl sm:text-5xl font-bold tracking-tight mb-6">
            Intelligence,{' '}
            <span className="bg-gradient-to-r from-emerald-400 to-emerald-300 bg-clip-text text-transparent">
              Engineered
            </span>
          </motion.h1>
          <motion.p variants={fadeInUp} className="text-lg text-zinc-400 leading-relaxed max-w-2xl">
            Deep dives into market intelligence engineering, product updates, developer tutorials,
            and the thinking behind MarketMate&apos;s architecture. We write about what we build and
            how we build it.
          </motion.p>
        </motion.div>

        {/* Blog Grid */}
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-50px' }}
          variants={staggerContainer}
          className="grid gap-6 sm:grid-cols-2"
        >
          {posts.map((post) => (
            <motion.article
              key={post.title}
              variants={fadeInUp}
              className="group relative rounded-xl border border-white/[0.06] bg-white/[0.02] p-6 hover:border-emerald-400/20 transition-all duration-300 hover:bg-white/[0.04] cursor-pointer"
            >
              {/* Coming Soon Badge */}
              <div className="absolute top-4 right-4 flex items-center gap-1.5 rounded-full bg-emerald-400/10 border border-emerald-400/20 px-2.5 py-1">
                <Sparkles className="w-3 h-3 text-emerald-400" />
                <span className="text-xs font-medium text-emerald-400">Coming Soon</span>
              </div>

              {/* Category Badge */}
              <span
                className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium mb-3 ${categoryColors[post.category]}`}
              >
                {post.category}
              </span>

              {/* Title */}
              <h2 className="text-lg font-semibold mb-2 pr-20 group-hover:text-emerald-400 transition-colors leading-snug">
                {post.title}
              </h2>

              {/* Date */}
              <div className="flex items-center gap-1.5 text-zinc-500 text-sm mb-3">
                <Clock className="w-3.5 h-3.5" />
                <span>{post.date}</span>
              </div>

              {/* Description */}
              <p className="text-zinc-400 text-sm leading-relaxed line-clamp-4">
                {post.description}
              </p>

              {/* Read More */}
              <div className="mt-4 flex items-center gap-1 text-sm text-zinc-500 group-hover:text-emerald-400 transition-colors">
                <span>Read more</span>
                <ArrowUpRight className="w-3.5 h-3.5" />
              </div>
            </motion.article>
          ))}
        </motion.div>

        {/* Bottom note */}
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          variants={fadeInUp}
          className="mt-16 rounded-xl border border-white/[0.06] bg-white/[0.02] p-6 text-center"
        >
          <p className="text-zinc-400 text-sm">
            We&apos;re preparing our first batch of articles. Subscribe to our newsletter to get notified
            when the blog goes live.
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
