'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import { Mail, Github, Twitter, Send, CheckCircle } from 'lucide-react'

const fadeInUp = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: 'easeOut' as const } },
}

const staggerContainer = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.1 } },
}

const contactMethods = [
  {
    icon: Mail,
    label: 'Email',
    value: 'hello@marketmate.io',
    href: 'mailto:hello@marketmate.io',
    description: 'For general inquiries, partnerships, and enterprise discussions',
  },
  {
    icon: Github,
    label: 'GitHub',
    value: 'github.com/Klynttech/MarketMate',
    href: 'https://github.com/Klynttech/MarketMate',
    description: 'Open-source codebase, issues, and feature requests',
  },
  {
    icon: Twitter,
    label: 'Twitter',
    value: '@MarketMate_io',
    href: 'https://twitter.com/MarketMate_io',
    description: 'Product updates, market insights, and community',
  },
]

const subjectOptions = ['General Inquiry', 'Technical Support', 'Partnership', 'Enterprise']

export default function ContactPage() {
  const [formState, setFormState] = useState({
    name: '',
    email: '',
    subject: '',
    message: '',
  })
  const [submitted, setSubmitted] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)

    // Simulate submission
    setTimeout(() => {
      setSubmitting(false)
      setSubmitted(true)
      setFormState({ name: '', email: '', subject: '', message: '' })

      // Reset success message after a few seconds
      setTimeout(() => setSubmitted(false), 5000)
    }, 800)
  }

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => {
    setFormState((prev) => ({ ...prev, [e.target.name]: e.target.value }))
  }

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
          className="mb-16"
        >
          <motion.p variants={fadeInUp} className="text-emerald-400 text-sm font-semibold tracking-wider uppercase mb-4">
            Contact Us
          </motion.p>
          <motion.h1 variants={fadeInUp} className="text-4xl sm:text-5xl font-bold tracking-tight mb-6">
            Get in{' '}
            <span className="bg-gradient-to-r from-emerald-400 to-emerald-300 bg-clip-text text-transparent">
              Touch
            </span>
          </motion.h1>
          <motion.p variants={fadeInUp} className="text-lg text-zinc-400 leading-relaxed max-w-2xl">
            Have a question about MarketMate, need technical support, or interested in a
            partnership? We&apos;d love to hear from you. Our team reviews every message and responds
            within 24–48 hours.
          </motion.p>
        </motion.div>

        <div className="grid gap-12 lg:grid-cols-5">
          {/* Contact Form */}
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: '-50px' }}
            variants={staggerContainer}
            className="lg:col-span-3"
          >
            <motion.form
              variants={fadeInUp}
              onSubmit={handleSubmit}
              className="space-y-5 rounded-xl border border-white/[0.06] bg-white/[0.02] p-6 sm:p-8"
            >
              <h2 className="text-xl font-bold mb-2">Send Us a Message</h2>

              {submitted && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex items-center gap-2 rounded-lg bg-emerald-400/10 border border-emerald-400/20 px-4 py-3 text-sm text-emerald-400"
                >
                  <CheckCircle className="w-4 h-4 flex-shrink-0" />
                  <span>Message received! We&apos;ll get back to you within 24–48 hours.</span>
                </motion.div>
              )}

              <div>
                <label htmlFor="name" className="block text-sm font-medium text-zinc-300 mb-1.5">
                  Name
                </label>
                <input
                  type="text"
                  id="name"
                  name="name"
                  required
                  value={formState.name}
                  onChange={handleChange}
                  placeholder="Your full name"
                  className="w-full rounded-lg border border-white/[0.08] bg-white/[0.03] px-4 py-2.5 text-sm text-white placeholder:text-zinc-600 focus:border-emerald-400/40 focus:outline-none focus:ring-1 focus:ring-emerald-400/20 transition-colors"
                />
              </div>

              <div>
                <label htmlFor="email" className="block text-sm font-medium text-zinc-300 mb-1.5">
                  Email
                </label>
                <input
                  type="email"
                  id="email"
                  name="email"
                  required
                  value={formState.email}
                  onChange={handleChange}
                  placeholder="you@example.com"
                  className="w-full rounded-lg border border-white/[0.08] bg-white/[0.03] px-4 py-2.5 text-sm text-white placeholder:text-zinc-600 focus:border-emerald-400/40 focus:outline-none focus:ring-1 focus:ring-emerald-400/20 transition-colors"
                />
              </div>

              <div>
                <label htmlFor="subject" className="block text-sm font-medium text-zinc-300 mb-1.5">
                  Subject
                </label>
                <select
                  id="subject"
                  name="subject"
                  required
                  value={formState.subject}
                  onChange={handleChange}
                  className="w-full rounded-lg border border-white/[0.08] bg-white/[0.03] px-4 py-2.5 text-sm text-white focus:border-emerald-400/40 focus:outline-none focus:ring-1 focus:ring-emerald-400/20 transition-colors appearance-none"
                >
                  <option value="" disabled className="bg-zinc-900">
                    Select a subject
                  </option>
                  {subjectOptions.map((opt) => (
                    <option key={opt} value={opt} className="bg-zinc-900">
                      {opt}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="message" className="block text-sm font-medium text-zinc-300 mb-1.5">
                  Message
                </label>
                <textarea
                  id="message"
                  name="message"
                  required
                  rows={5}
                  value={formState.message}
                  onChange={handleChange}
                  placeholder="Tell us how we can help..."
                  className="w-full rounded-lg border border-white/[0.08] bg-white/[0.03] px-4 py-2.5 text-sm text-white placeholder:text-zinc-600 focus:border-emerald-400/40 focus:outline-none focus:ring-1 focus:ring-emerald-400/20 transition-colors resize-none"
                />
              </div>

              <button
                type="submit"
                disabled={submitting}
                className="inline-flex items-center gap-2 rounded-lg bg-emerald-400 px-6 py-2.5 text-sm font-semibold text-zinc-950 hover:bg-emerald-300 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {submitting ? (
                  <>
                    <div className="w-4 h-4 border-2 border-zinc-950/30 border-t-zinc-950 rounded-full animate-spin" />
                    Sending...
                  </>
                ) : (
                  <>
                    <Send className="w-4 h-4" />
                    Send Message
                  </>
                )}
              </button>
            </motion.form>
          </motion.div>

          {/* Contact Methods */}
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: '-50px' }}
            variants={staggerContainer}
            className="lg:col-span-2 space-y-4"
          >
            <motion.h2 variants={fadeInUp} className="text-xl font-bold mb-4">
              Other Ways to Reach Us
            </motion.h2>

            {contactMethods.map((method) => (
              <motion.a
                key={method.label}
                variants={fadeInUp}
                href={method.href}
                target={method.href.startsWith('http') ? '_blank' : undefined}
                rel={method.href.startsWith('http') ? 'noopener noreferrer' : undefined}
                className="block rounded-xl border border-white/[0.06] bg-white/[0.02] p-5 hover:border-emerald-400/20 transition-all duration-300 hover:bg-white/[0.04]"
              >
                <div className="flex items-center gap-3 mb-2">
                  <div className="w-9 h-9 rounded-lg bg-emerald-400/10 flex items-center justify-center">
                    <method.icon className="w-4 h-4 text-emerald-400" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold">{method.label}</p>
                    <p className="text-xs text-emerald-400">{method.value}</p>
                  </div>
                </div>
                <p className="text-zinc-500 text-xs leading-relaxed">{method.description}</p>
              </motion.a>
            ))}

            <motion.div
              variants={fadeInUp}
              className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-5"
            >
              <p className="text-sm font-semibold mb-1">Response Time</p>
              <p className="text-zinc-400 text-sm leading-relaxed">
                We typically respond within 24–48 hours. For urgent technical issues, please include
                &quot;URGENT&quot; in your subject line and we&apos;ll prioritize your request.
              </p>
            </motion.div>

            <motion.div
              variants={fadeInUp}
              className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-5"
            >
              <p className="text-sm font-semibold mb-1">Security Vulnerabilities</p>
              <p className="text-zinc-400 text-sm leading-relaxed">
                If you&apos;ve discovered a security issue, please report it responsibly to{' '}
                <a
                  href="mailto:security@marketmate.io"
                  className="text-emerald-400 hover:text-emerald-300 transition-colors"
                >
                  security@marketmate.io
                </a>{' '}
                instead of using this form.
              </p>
            </motion.div>
          </motion.div>
        </div>
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
