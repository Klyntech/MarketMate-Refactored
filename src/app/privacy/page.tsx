'use client'

import { motion } from 'framer-motion'

const fadeInUp = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: 'easeOut' as const } },
}

const staggerContainer = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.08 } },
}

const sections = [
  {
    title: '1. Information We Collect',
    content: [
      {
        subtitle: 'Account Information',
        text: 'When you create a MarketMate account, we collect your email address, display name, and account credentials. If you subscribe to a paid plan, we also collect billing information through our payment processor. We do not store full credit card numbers on our servers.',
      },
      {
        subtitle: 'API Usage Data',
        text: 'When you interact with the MarketMate API, we log request metadata including API key identifiers (not the full key), endpoints accessed, request timestamps, and response status codes. This data is essential for rate limiting, abuse prevention, and service quality monitoring. We do not log the full content of your API requests or responses beyond what is necessary for debugging and security purposes.',
      },
      {
        subtitle: 'Market Intelligence Queries',
        text: 'Queries submitted to our market intelligence endpoints — such as symbol lookups, conviction score requests, and MATE AI prompts — are processed in real-time and may be temporarily cached for performance optimization. These queries are not permanently stored in a way that associates them with your identity, except as required for usage analytics and billing.',
      },
      {
        subtitle: 'Automatically Collected Data',
        text: 'We collect standard technical information when you visit our website or use our services, including IP addresses, browser type, operating system, referring URLs, and device identifiers. This information helps us maintain service security, optimize performance, and understand aggregate usage patterns.',
      },
    ],
  },
  {
    title: '2. How We Use Information',
    content: [
      {
        text: 'We use collected information for the following purposes:',
      },
      {
        subtitle: 'Service Delivery',
        text: 'To provide, maintain, and improve the MarketMate platform, including processing API requests, delivering market intelligence signals, and operating the MATE AI interpreter.',
      },
      {
        subtitle: 'Communication',
        text: 'To send service-related notifications, security alerts, and responses to your inquiries. We will not send marketing communications without your explicit opt-in consent.',
      },
      {
        subtitle: 'Security & Abuse Prevention',
        text: 'To detect, prevent, and mitigate fraud, abuse, unauthorized access, and other illegal activities. API usage patterns are analyzed to identify anomalous behavior that may indicate compromised credentials or service abuse.',
      },
      {
        subtitle: 'Analytics & Improvement',
        text: 'To analyze aggregate usage patterns, identify performance bottlenecks, and guide product development decisions. Analytics are performed on anonymized or pseudonymized data whenever possible.',
      },
    ],
  },
  {
    title: '3. Data Storage & Security',
    content: [
      {
        text: 'MarketMate data is stored on secured infrastructure with encryption at rest (AES-256) and in transit (TLS 1.3). API keys are hashed using industry-standard cryptographic algorithms and are never stored in plaintext. Access to production systems is restricted through multi-factor authentication, role-based access controls, and regular access audits.',
      },
      {
        text: 'We retain personal data only for as long as necessary to fulfill the purposes outlined in this policy. API usage logs are retained for 90 days for security and debugging purposes, after which they are automatically purged. Account data is retained for the duration of your account and deleted within 30 days of account termination, unless retention is required by law.',
      },
    ],
  },
  {
    title: '4. API Usage Data',
    content: [
      {
        text: 'The MarketMate API is designed with privacy in mind. Specific details about our API data practices:',
      },
      {
        subtitle: 'API Key Handling',
        text: 'API keys are generated using cryptographically secure random generators and are transmitted only over encrypted connections. Keys are stored as salted hashes in our database. If you believe your API key has been compromised, you can rotate it immediately through the dashboard without contacting support.',
      },
      {
        subtitle: 'Query Privacy',
        text: 'Your market intelligence queries — including symbols analyzed, conviction thresholds set, and MATE AI prompts submitted — are not shared with other users or third parties. Aggregate, anonymized query statistics may be used for market data licensing compliance and product improvement.',
      },
      {
        subtitle: 'WebSocket Stream Data',
        text: 'Real-time signal streams delivered via WebSocket are transmitted over encrypted connections. We do not record or store the content of streamed signals on a per-user basis beyond what is required for delivery confirmation and billing.',
      },
    ],
  },
  {
    title: '5. Cookies & Tracking',
    content: [
      {
        text: 'Our website uses essential cookies to maintain session state, authentication tokens, and user preferences. We do not use third-party advertising trackers or sell data to advertising networks.',
      },
      {
        text: 'Specific cookies we use include: session authentication cookies (essential), theme preference cookies (essential), and analytics cookies (optional, requires consent). You can manage cookie preferences at any time through your browser settings or our cookie consent interface.',
      },
      {
        text: 'We use privacy-respecting analytics that do not track individual users across sessions or websites. Analytics data is aggregated and cannot be used to identify or profile individual visitors.',
      },
    ],
  },
  {
    title: '6. Third-Party Services',
    content: [
      {
        text: 'MarketMate integrates with the following categories of third-party services, each subject to their own privacy policies:',
      },
      {
        subtitle: 'Market Data Providers',
        text: 'We receive real-time and historical market data from licensed exchanges and data aggregators. These providers may log API requests from our infrastructure as part of their standard operations.',
      },
      {
        subtitle: 'Cloud Infrastructure',
        text: 'Our services run on cloud infrastructure providers that comply with industry-standard security certifications (SOC 2, ISO 27001). These providers may process data on our behalf but are contractually prohibited from accessing or using your data for their own purposes.',
      },
      {
        subtitle: 'Payment Processing',
        text: 'Payment transactions are processed by certified PCI-DSS compliant payment processors. MarketMate does not receive or store full credit card numbers.',
      },
      {
        text: 'We do not sell, rent, or trade your personal data to any third party under any circumstances.',
      },
    ],
  },
  {
    title: '7. Your Rights',
    content: [
      {
        text: 'You have the following rights regarding your personal data:',
      },
      {
        subtitle: 'Access & Portability',
        text: 'You can request a copy of all personal data we hold about you. We provide this in a machine-readable format within 30 days of receiving a verified request.',
      },
      {
        subtitle: 'Correction & Deletion',
        text: 'You can update your account information at any time through the dashboard. You can request deletion of your account and associated data, which will be processed within 30 days subject to legal retention requirements.',
      },
      {
        subtitle: 'Objection & Restriction',
        text: 'You can object to the processing of your data for specific purposes, such as analytics, and request that we restrict processing while your objection is being reviewed.',
      },
      {
        subtitle: 'Data Processing Agreements',
        text: 'Enterprise customers can request a Data Processing Agreement (DPA) that outlines specific data handling commitments, sub-processor lists, and breach notification procedures.',
      },
    ],
  },
  {
    title: '8. Contact Us',
    content: [
      {
        text: 'If you have questions about this Privacy Policy or wish to exercise your data rights, please contact us at:',
      },
      {
        text: 'Email: privacy@marketmate.io',
      },
      {
        text: 'We will respond to all privacy-related inquiries within 30 days. For urgent data protection matters, include "PRIVACY URGENT" in your subject line.',
      },
    ],
  },
]

export default function PrivacyPage() {
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
            Legal
          </motion.p>
          <motion.h1 variants={fadeInUp} className="text-4xl sm:text-5xl font-bold tracking-tight mb-4">
            Privacy Policy
          </motion.h1>
          <motion.p variants={fadeInUp} className="text-zinc-500 text-sm">
            Last updated: March 1, 2026
          </motion.p>
        </motion.div>

        {/* Intro */}
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-50px' }}
          variants={fadeInUp}
          className="mb-12 rounded-xl border border-white/[0.06] bg-white/[0.02] p-6 sm:p-8"
        >
          <p className="text-zinc-400 leading-relaxed">
            MarketMate (&quot;we,&quot; &quot;our,&quot; or &quot;us&quot;) is committed to protecting your privacy and
            ensuring transparency about how we collect, use, and safeguard your data. This Privacy
            Policy describes our practices regarding personal information collected through our
            website, API services, and related products (collectively, the &quot;Services&quot;). By using
            our Services, you agree to the data practices described herein.
          </p>
        </motion.div>

        {/* Sections */}
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-50px' }}
          variants={staggerContainer}
          className="space-y-10"
        >
          {sections.map((section) => (
            <motion.section key={section.title} variants={fadeInUp}>
              <h2 className="text-xl font-bold mb-4 text-white">{section.title}</h2>
              <div className="space-y-4">
                {section.content.map((item, i) => (
                  <div key={i}>
                    {item.subtitle && (
                      <h3 className="text-sm font-semibold text-emerald-400 mb-1.5">
                        {item.subtitle}
                      </h3>
                    )}
                    <p className="text-zinc-400 text-sm leading-relaxed">{item.text}</p>
                  </div>
                ))}
              </div>
            </motion.section>
          ))}
        </motion.div>

        {/* No selling data callout */}
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          variants={fadeInUp}
          className="mt-12 rounded-xl border border-emerald-400/20 bg-emerald-400/[0.03] p-6"
        >
          <p className="text-sm font-semibold text-emerald-400 mb-1">Our Commitment</p>
          <p className="text-zinc-400 text-sm leading-relaxed">
            MarketMate will never sell your personal data. Period. Your trading queries, API usage
            patterns, and account information are yours. We use data only to deliver and improve our
            services, protect against abuse, and comply with legal obligations.
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
