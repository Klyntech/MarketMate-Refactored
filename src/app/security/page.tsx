'use client'

import { motion } from 'framer-motion'
import {
  Shield,
  Lock,
  Key,
  Server,
  Scan,
  FileCheck,
  Bug,
  Mail,
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

const securityAreas = [
  {
    icon: Server,
    title: 'Infrastructure Security',
    items: [
      'All services run on hardened cloud infrastructure with encrypted networking and isolated compute environments',
      'Network segmentation isolates production systems from development and staging environments',
      'All internal service communication is encrypted via mTLS (mutual TLS) with automatic certificate rotation',
      'Infrastructure is managed as code using version-controlled configuration with mandatory peer review',
      'Regular penetration testing by independent security firms, with results reviewed and remediated within defined SLAs',
      'Automated vulnerability scanning of all container images before deployment to production',
    ],
  },
  {
    icon: Key,
    title: 'API Security',
    items: [
      'API keys are generated using cryptographically secure random generators (256-bit entropy)',
      'Keys are stored exclusively as salted hashes using bcrypt — we cannot retrieve your original key if lost',
      'Key rotation can be performed instantly through the dashboard without service interruption',
      'All API endpoints enforce TLS 1.3 with strong cipher suites; plaintext connections are rejected',
      'Rate limiting is enforced at the API gateway layer to prevent abuse, brute-force attacks, and denial-of-service attempts',
      'Input validation and sanitization are applied at every entry point to prevent injection attacks, malformed payloads, and buffer overflow attempts',
      'CORS policies are strictly configured — only authorized origins can make browser-based API requests',
    ],
  },
  {
    icon: Lock,
    title: 'Data Protection',
    items: [
      'All data is encrypted at rest using AES-256 encryption',
      'All data in transit is protected by TLS 1.3 with forward secrecy',
      'Market intelligence queries are processed in isolated execution environments',
      'Personal data is logically separated from analytical and market data storage',
      'Data retention policies are enforced automatically — expired data is purged within 24 hours of its retention deadline',
      'Backup data is encrypted with separate keys stored in hardware security modules (HSMs)',
      'Database access requires multi-factor authentication and is logged with immutable audit trails',
    ],
  },
  {
    icon: Shield,
    title: 'Authentication',
    items: [
      'Multi-factor authentication (MFA) is required for all team member accounts with production access',
      'User accounts support optional MFA via TOTP authenticator apps',
      'Session tokens use short-lived JWTs with automatic refresh; sessions expire after configurable idle timeouts',
      'Failed authentication attempts trigger progressive rate limiting and optional account lockout',
      'OAuth 2.0 and API key authentication are the only supported methods — password authentication is not used for API access',
    ],
  },
  {
    icon: Scan,
    title: 'Vulnerability Reporting',
    items: [
      'We maintain a responsible disclosure program and welcome reports from security researchers',
      'Vulnerabilities can be reported to security@marketmate.io with PGP encryption (our public key is available on our website)',
      'We commit to acknowledging receipt of vulnerability reports within 24 hours',
      'Initial assessment and triage are completed within 72 hours of acknowledgment',
      'Critical vulnerabilities are patched within 7 days; medium and low severity within 30 days',
      'We ask that researchers avoid accessing, modifying, or deleting user data, and that they report findings before public disclosure',
    ],
  },
  {
    icon: FileCheck,
    title: 'Compliance',
    items: [
      'SOC 2 Type II compliance in progress — currently building controls and documentation toward audit readiness',
      'GDPR compliance for all EU users, including data processing agreements for enterprise customers',
      'API data handling practices align with financial data security standards',
      'Regular internal security audits conducted quarterly with findings tracked to resolution',
      'Incident response plan is documented, tested, and updated semi-annually',
      'All team members complete annual security awareness training',
    ],
  },
]

export default function SecurityPage() {
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
            Security
          </motion.p>
          <motion.h1 variants={fadeInUp} className="text-4xl sm:text-5xl font-bold tracking-tight mb-6">
            Security is{' '}
            <span className="bg-gradient-to-r from-emerald-400 to-emerald-300 bg-clip-text text-transparent">
              Foundational
            </span>
          </motion.h1>
          <motion.p variants={fadeInUp} className="text-lg text-zinc-400 leading-relaxed max-w-2xl">
            Security isn&apos;t an afterthought at MarketMate — it&apos;s a foundational design principle.
            Our market intelligence infrastructure handles sensitive data streams and powers
            real-time trading decisions. That responsibility demands a security-first approach
            embedded in every layer of our architecture, from infrastructure provisioning to API
            key management.
          </motion.p>
        </motion.div>

        {/* Security Areas */}
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-50px' }}
          variants={staggerContainer}
          className="space-y-8"
        >
          {securityAreas.map((area) => (
            <motion.section
              key={area.title}
              variants={fadeInUp}
              className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-6 sm:p-8"
            >
              <div className="flex items-center gap-3 mb-5">
                <div className="w-10 h-10 rounded-lg bg-emerald-400/10 flex items-center justify-center">
                  <area.icon className="w-5 h-5 text-emerald-400" />
                </div>
                <h2 className="text-xl font-bold">{area.title}</h2>
              </div>
              <ul className="space-y-3">
                {area.items.map((item, i) => (
                  <li key={i} className="flex gap-3 text-sm text-zinc-400 leading-relaxed">
                    <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-emerald-400/60 flex-shrink-0" />
                    {item}
                  </li>
                ))}
              </ul>
            </motion.section>
          ))}
        </motion.div>

        {/* Vulnerability Disclosure */}
        <motion.section
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-50px' }}
          variants={staggerContainer}
          className="mt-12"
        >
          <motion.div variants={fadeInUp} className="rounded-xl border border-emerald-400/20 bg-emerald-400/[0.03] p-6 sm:p-8">
            <div className="flex items-center gap-3 mb-4">
              <Bug className="w-6 h-6 text-emerald-400" />
              <h2 className="text-xl font-bold">Vulnerability Disclosure Policy</h2>
            </div>
            <p className="text-zinc-400 text-sm leading-relaxed mb-4">
              We take security vulnerabilities seriously and are committed to working with the
              security community to verify and address potential issues. If you believe you&apos;ve
              discovered a vulnerability in MarketMate&apos;s systems or services, we encourage you to
              report it responsibly.
            </p>
            <div className="space-y-2 mb-4">
              <div className="flex items-center gap-2 text-sm text-zinc-400">
                <Mail className="w-4 h-4 text-emerald-400" />
                <span>Report vulnerabilities to: </span>
                <a
                  href="mailto:security@marketmate.io"
                  className="text-emerald-400 hover:text-emerald-300 transition-colors"
                >
                  security@marketmate.io
                </a>
              </div>
            </div>
            <p className="text-zinc-500 text-xs leading-relaxed">
              We request that you: (1) avoid accessing or modifying user data, (2) do not degrade
              service availability, (3) provide sufficient detail to reproduce the issue, and (4)
              allow reasonable time for remediation before public disclosure.
            </p>
          </motion.div>
        </motion.section>

        {/* Bug Bounty */}
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          variants={fadeInUp}
          className="mt-6 rounded-xl border border-white/[0.06] bg-white/[0.02] p-6 flex items-center gap-4"
        >
          <div className="w-10 h-10 rounded-lg bg-emerald-400/10 flex items-center justify-center flex-shrink-0">
            <Sparkles className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <p className="text-sm font-semibold">Bug Bounty Program</p>
            <p className="text-zinc-500 text-sm">
              We&apos;re preparing a formal bug bounty program with monetary rewards for valid
              vulnerability reports. Stay tuned for details.
            </p>
          </div>
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
