import Link from "next/link"
import Image from "next/image"
import { ArrowLeft } from "lucide-react"

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-background/80 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <Image
              src="/logo.svg"
              alt="MarketMate Logo"
              width={32}
              height={27}
              className="h-7 w-auto"
            />
            <span className="text-xl font-bold text-foreground">MarketMate</span>
          </Link>
          <Link 
            href="/" 
            className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Home
          </Link>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-4xl mx-auto px-6 py-12">
        <div className="mb-12">
          <h1 className="text-4xl font-bold text-foreground mb-4">Privacy Policy</h1>
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <span>Effective Date: January 1, 2025</span>
            <span className="w-1 h-1 rounded-full bg-muted-foreground" />
            <span>Version 1.0</span>
          </div>
        </div>

        <div className="prose prose-invert prose-lg max-w-none">
          <p className="text-muted-foreground text-lg leading-relaxed mb-8">
            This Privacy Policy explains how MarketMate collects, uses, and protects your information
            when you use our services, APIs, and platforms.
          </p>

          {/* Section 1 */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
              <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/20 text-primary text-sm font-bold">1</span>
              Information We Collect
            </h2>
            <p className="text-muted-foreground mb-6">We may collect the following types of data:</p>
            
            <div className="space-y-6">
              <div className="bg-card border border-border rounded-lg p-6">
                <h3 className="text-foreground font-semibold mb-3">1.1 User Data</h3>
                <ul className="space-y-2 text-muted-foreground">
                  <li className="flex gap-3"><span className="text-primary">&bull;</span> Account identifiers</li>
                  <li className="flex gap-3"><span className="text-primary">&bull;</span> Email address (if provided)</li>
                  <li className="flex gap-3"><span className="text-primary">&bull;</span> Authentication credentials (hashed)</li>
                </ul>
              </div>

              <div className="bg-card border border-border rounded-lg p-6">
                <h3 className="text-foreground font-semibold mb-3">1.2 Usage Data</h3>
                <ul className="space-y-2 text-muted-foreground">
                  <li className="flex gap-3"><span className="text-primary">&bull;</span> API requests</li>
                  <li className="flex gap-3"><span className="text-primary">&bull;</span> Feature usage patterns</li>
                  <li className="flex gap-3"><span className="text-primary">&bull;</span> System interaction logs</li>
                  <li className="flex gap-3"><span className="text-primary">&bull;</span> Error reports</li>
                </ul>
              </div>

              <div className="bg-card border border-border rounded-lg p-6">
                <h3 className="text-foreground font-semibold mb-3">1.3 Technical Data</h3>
                <ul className="space-y-2 text-muted-foreground">
                  <li className="flex gap-3"><span className="text-primary">&bull;</span> IP address</li>
                  <li className="flex gap-3"><span className="text-primary">&bull;</span> Device type</li>
                  <li className="flex gap-3"><span className="text-primary">&bull;</span> Browser information</li>
                  <li className="flex gap-3"><span className="text-primary">&bull;</span> Session timestamps</li>
                </ul>
              </div>

              <div className="bg-card border border-border rounded-lg p-6">
                <h3 className="text-foreground font-semibold mb-3">1.4 Market Interaction Data</h3>
                <ul className="space-y-2 text-muted-foreground">
                  <li className="flex gap-3"><span className="text-primary">&bull;</span> Signals viewed</li>
                  <li className="flex gap-3"><span className="text-primary">&bull;</span> API endpoints accessed</li>
                  <li className="flex gap-3"><span className="text-primary">&bull;</span> Strategy interactions</li>
                </ul>
              </div>
            </div>
          </section>

          {/* Section 2 */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
              <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/20 text-primary text-sm font-bold">2</span>
              How We Use Data
            </h2>
            <p className="text-muted-foreground mb-4">We use collected data to:</p>
            <ul className="space-y-3 text-muted-foreground">
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Operate and maintain services</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Improve AI models and analytics</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Enhance system performance</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Detect abuse or unauthorized access</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Generate aggregated insights</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Ensure system security</li>
            </ul>
          </section>

          {/* Section 3 */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
              <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/20 text-primary text-sm font-bold">3</span>
              Data Sharing
            </h2>
            <div className="bg-primary/10 border border-primary/30 rounded-lg p-6 mb-6">
              <p className="text-foreground font-semibold">We do NOT sell personal data.</p>
            </div>
            <p className="text-muted-foreground mb-4">We may share data only:</p>
            <ul className="space-y-3 text-muted-foreground">
              <li className="flex gap-3"><span className="text-primary">&bull;</span> With infrastructure providers (hosting, database services)</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> For legal compliance</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> For security investigations</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> For system integrity enforcement</li>
            </ul>
            <p className="text-muted-foreground mt-4">
              All third parties are bound by confidentiality obligations.
            </p>
          </section>

          {/* Section 4 */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
              <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/20 text-primary text-sm font-bold">4</span>
              Data Storage
            </h2>
            <ul className="space-y-3 text-muted-foreground">
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Data may be stored in secure cloud infrastructure</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Logs may be retained for system improvement</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Historical market data may be archived indefinitely</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> User data is stored securely with encryption where applicable</li>
            </ul>
          </section>

          {/* Section 5 */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
              <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/20 text-primary text-sm font-bold">5</span>
              Data Security
            </h2>
            <p className="text-muted-foreground mb-4">We implement:</p>
            <div className="grid md:grid-cols-2 gap-4">
              <div className="bg-card border border-border rounded-lg p-4">
                <p className="text-foreground font-medium mb-2">Encryption in transit (TLS)</p>
                <p className="text-muted-foreground text-sm">All data transmitted is encrypted</p>
              </div>
              <div className="bg-card border border-border rounded-lg p-4">
                <p className="text-foreground font-medium mb-2">Access control policies</p>
                <p className="text-muted-foreground text-sm">Strict internal access management</p>
              </div>
              <div className="bg-card border border-border rounded-lg p-4">
                <p className="text-foreground font-medium mb-2">API key authentication</p>
                <p className="text-muted-foreground text-sm">Secure programmatic access</p>
              </div>
              <div className="bg-card border border-border rounded-lg p-4">
                <p className="text-foreground font-medium mb-2">Monitoring &amp; detection</p>
                <p className="text-muted-foreground text-sm">Real-time anomaly monitoring</p>
              </div>
            </div>
            <p className="text-muted-foreground mt-6">
              No system is 100% secure, but we apply industry-standard safeguards.
            </p>
          </section>

          {/* Section 6 */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
              <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/20 text-primary text-sm font-bold">6</span>
              User Rights
            </h2>
            <p className="text-muted-foreground mb-4">Depending on jurisdiction, users may:</p>
            <ul className="space-y-3 text-muted-foreground">
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Request access to their data</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Request correction of inaccurate data</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Request deletion of personal data (subject to legal retention requirements)</li>
            </ul>
          </section>

          {/* Section 7 */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
              <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/20 text-primary text-sm font-bold">7</span>
              Cookies &amp; Tracking
            </h2>
            <p className="text-muted-foreground mb-4">MarketMate may use:</p>
            <ul className="space-y-3 text-muted-foreground">
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Session cookies</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Analytics tracking</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Performance monitoring tools</li>
            </ul>
            <p className="text-muted-foreground mt-4">
              These improve system functionality and reliability.
            </p>
          </section>

          {/* Section 8 */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
              <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/20 text-primary text-sm font-bold">8</span>
              Third-Party Services
            </h2>
            <p className="text-muted-foreground mb-4">We may integrate with:</p>
            <ul className="space-y-3 text-muted-foreground">
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Cloud hosting providers</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> AI model providers</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Database services</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Analytics platforms</li>
            </ul>
            <p className="text-muted-foreground mt-4">
              Each has its own privacy policy.
            </p>
          </section>

          {/* Section 9 */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
              <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/20 text-primary text-sm font-bold">9</span>
              Data Retention
            </h2>
            <p className="text-muted-foreground mb-4">We retain data:</p>
            <ul className="space-y-3 text-muted-foreground">
              <li className="flex gap-3"><span className="text-primary">&bull;</span> As long as necessary for service operation</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> For legal compliance</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> For system analytics and improvement</li>
            </ul>
          </section>

          {/* Section 10 */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
              <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/20 text-primary text-sm font-bold">10</span>
              Children&apos;s Privacy
            </h2>
            <p className="text-muted-foreground">
              MarketMate is not intended for users under 18. We do not knowingly collect data from minors.
            </p>
          </section>

          {/* Section 11 */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
              <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/20 text-primary text-sm font-bold">11</span>
              International Users
            </h2>
            <p className="text-muted-foreground">
              Data may be processed across different jurisdictions depending on infrastructure location.
            </p>
          </section>

          {/* Section 12 */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
              <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/20 text-primary text-sm font-bold">12</span>
              Changes to Privacy Policy
            </h2>
            <p className="text-muted-foreground">
              We may update this policy periodically. Continued use constitutes acceptance.
            </p>
          </section>

          {/* Section 13 */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
              <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/20 text-primary text-sm font-bold">13</span>
              Contact
            </h2>
            <p className="text-muted-foreground mb-4">For privacy inquiries, contact:</p>
            <div className="bg-card border border-border rounded-lg p-6">
              <p className="text-foreground font-medium">support@marketmate.io</p>
            </div>
          </section>
        </div>

        {/* Footer Links */}
        <div className="mt-16 pt-8 border-t border-border">
          <div className="flex flex-wrap gap-6 text-sm text-muted-foreground">
            <Link href="/terms" className="hover:text-primary transition-colors">
              Terms &amp; Conditions
            </Link>
            <Link href="/privacy" className="hover:text-primary transition-colors">
              Privacy Policy
            </Link>
            <Link href="/" className="hover:text-primary transition-colors">
              Back to Home
            </Link>
          </div>
        </div>
      </main>
    </div>
  )
}
