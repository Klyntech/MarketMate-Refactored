import Link from "next/link"
import Image from "next/image"
import { ArrowLeft } from "lucide-react"

export default function TermsPage() {
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
          <h1 className="text-4xl font-bold text-foreground mb-4">Terms and Conditions</h1>
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <span>Effective Date: January 1, 2025</span>
            <span className="w-1 h-1 rounded-full bg-muted-foreground" />
            <span>Version 1.0</span>
          </div>
        </div>

        <div className="prose prose-invert prose-lg max-w-none">
          <p className="text-muted-foreground text-lg leading-relaxed mb-8">
            These Terms and Conditions (&quot;Terms&quot;) govern access to and use of MarketMate services, 
            platforms, APIs, tools, websites, applications, and associated infrastructure (&quot;Services&quot;). 
            By accessing or using MarketMate, you agree to be legally bound by these Terms.
          </p>
          
          <p className="text-primary font-medium mb-12">
            If you do not agree, you must discontinue use immediately.
          </p>

          {/* Section 1 */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
              <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/20 text-primary text-sm font-bold">1</span>
              Definitions
            </h2>
            <p className="text-muted-foreground mb-4">For clarity within these Terms:</p>
            <ul className="space-y-3 text-muted-foreground">
              <li className="flex gap-3">
                <span className="text-primary">&bull;</span>
                <span><strong className="text-foreground">&quot;MarketMate&quot;</strong> refers to the trading intelligence infrastructure, including all APIs, models, systems, dashboards, academy tools, bots, and services.</span>
              </li>
              <li className="flex gap-3">
                <span className="text-primary">&bull;</span>
                <span><strong className="text-foreground">&quot;User&quot;</strong> means any individual, organization, or entity accessing MarketMate.</span>
              </li>
              <li className="flex gap-3">
                <span className="text-primary">&bull;</span>
                <span><strong className="text-foreground">&quot;API Services&quot;</strong> refers to all programmatic access endpoints provided by MarketMate.</span>
              </li>
              <li className="flex gap-3">
                <span className="text-primary">&bull;</span>
                <span><strong className="text-foreground">&quot;Intelligence Layer&quot;</strong> refers to MarketMate&apos;s analytical systems, including signal generation, state engine, and event processing systems.</span>
              </li>
              <li className="flex gap-3">
                <span className="text-primary">&bull;</span>
                <span><strong className="text-foreground">&quot;Academy&quot;</strong> (MMAcademy) refers to educational and training materials provided by MarketMate.</span>
              </li>
              <li className="flex gap-3">
                <span className="text-primary">&bull;</span>
                <span><strong className="text-foreground">&quot;Signals&quot;</strong> refers to algorithmically generated market insights or trade suggestions.</span>
              </li>
              <li className="flex gap-3">
                <span className="text-primary">&bull;</span>
                <span><strong className="text-foreground">&quot;Virtual Account&quot;</strong> refers to simulated trading environments provided within MarketMate.</span>
              </li>
            </ul>
          </section>

          {/* Section 2 */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
              <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/20 text-primary text-sm font-bold">2</span>
              Acceptance of Terms
            </h2>
            <p className="text-muted-foreground mb-4">By accessing MarketMate, the User confirms:</p>
            <ul className="space-y-3 text-muted-foreground">
              <li className="flex gap-3">
                <span className="text-primary">&bull;</span>
                <span>They are at least 18 years old or the legal age in their jurisdiction.</span>
              </li>
              <li className="flex gap-3">
                <span className="text-primary">&bull;</span>
                <span>They have full authority to enter into these Terms.</span>
              </li>
              <li className="flex gap-3">
                <span className="text-primary">&bull;</span>
                <span>They understand that MarketMate provides informational and analytical services only.</span>
              </li>
            </ul>
          </section>

          {/* Section 3 */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
              <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/20 text-primary text-sm font-bold">3</span>
              Nature of Services
            </h2>
            <p className="text-muted-foreground mb-4">
              MarketMate is a financial intelligence infrastructure system, not a brokerage, exchange, or financial advisor.
            </p>
            <div className="bg-card border border-border rounded-lg p-6 mt-4">
              <p className="text-foreground font-semibold mb-4">MarketMate:</p>
              <ul className="space-y-2 text-muted-foreground">
                <li className="flex gap-3"><span className="text-destructive">&#10005;</span> Does NOT execute trades on behalf of users</li>
                <li className="flex gap-3"><span className="text-destructive">&#10005;</span> Does NOT hold user funds</li>
                <li className="flex gap-3"><span className="text-destructive">&#10005;</span> Does NOT guarantee profitability</li>
                <li className="flex gap-3"><span className="text-destructive">&#10005;</span> Does NOT provide personalized financial advice</li>
                <li className="flex gap-3"><span className="text-destructive">&#10005;</span> Does NOT act as a fiduciary</li>
              </ul>
            </div>
            <p className="text-primary font-medium mt-4">
              All outputs are for informational, analytical, and educational purposes only.
            </p>
          </section>

          {/* Section 4 */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
              <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/20 text-primary text-sm font-bold">4</span>
              Risk Disclosure
            </h2>
            <div className="bg-destructive/10 border border-destructive/30 rounded-lg p-6 mb-6">
              <p className="text-foreground font-semibold">Trading financial instruments involves significant risk.</p>
            </div>
            <p className="text-muted-foreground mb-4">Users acknowledge:</p>
            <ul className="space-y-3 text-muted-foreground">
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Markets are volatile and unpredictable</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Loss of capital is possible and likely in some cases</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Past performance does not guarantee future results</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> AI-generated signals may be incorrect or incomplete</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> MarketMate systems may experience delays, errors, or data inconsistencies</li>
            </ul>
            <p className="text-foreground font-medium mt-4">
              Users accept full responsibility for all trading decisions.
            </p>
          </section>

          {/* Section 5 */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
              <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/20 text-primary text-sm font-bold">5</span>
              Intellectual Property Rights
            </h2>
            <p className="text-muted-foreground mb-4">
              All MarketMate systems, including but not limited to source code, APIs, models, algorithms, 
              signal logic, state engine architecture, UI/UX designs, and Academy content are the exclusive 
              intellectual property of MarketMate.
            </p>
            <p className="text-muted-foreground mb-4">Users are strictly prohibited from:</p>
            <ul className="space-y-3 text-muted-foreground">
              <li className="flex gap-3"><span className="text-destructive">&bull;</span> Copying or reverse engineering systems</li>
              <li className="flex gap-3"><span className="text-destructive">&bull;</span> Redistributing API outputs at scale without authorization</li>
              <li className="flex gap-3"><span className="text-destructive">&bull;</span> Replicating MarketMate infrastructure</li>
              <li className="flex gap-3"><span className="text-destructive">&bull;</span> Selling derived systems based on MarketMate logic</li>
            </ul>
            <p className="text-destructive font-medium mt-4">
              Violation results in immediate termination and possible legal action.
            </p>
          </section>

          {/* Section 6 */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
              <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/20 text-primary text-sm font-bold">6</span>
              API Usage Terms
            </h2>
            <p className="text-muted-foreground mb-4">Access to MarketMate API is subject to strict controls:</p>
            
            <div className="grid md:grid-cols-2 gap-6 mt-6">
              <div className="bg-card border border-border rounded-lg p-6">
                <p className="text-foreground font-semibold mb-4">Users must NOT:</p>
                <ul className="space-y-2 text-muted-foreground text-sm">
                  <li className="flex gap-2"><span className="text-destructive">&#10005;</span> Abuse rate limits</li>
                  <li className="flex gap-2"><span className="text-destructive">&#10005;</span> Scrape or mirror data</li>
                  <li className="flex gap-2"><span className="text-destructive">&#10005;</span> Attempt unauthorized system access</li>
                  <li className="flex gap-2"><span className="text-destructive">&#10005;</span> Reconstruct internal logic or state engine behavior</li>
                  <li className="flex gap-2"><span className="text-destructive">&#10005;</span> Use API outputs to train competing AI systems</li>
                </ul>
              </div>
              <div className="bg-card border border-border rounded-lg p-6">
                <p className="text-foreground font-semibold mb-4">MarketMate reserves the right to:</p>
                <ul className="space-y-2 text-muted-foreground text-sm">
                  <li className="flex gap-2"><span className="text-primary">&#10003;</span> Rate limit or suspend access at any time</li>
                  <li className="flex gap-2"><span className="text-primary">&#10003;</span> Monitor API usage for abuse patterns</li>
                  <li className="flex gap-2"><span className="text-primary">&#10003;</span> Modify or deprecate endpoints without notice</li>
                </ul>
              </div>
            </div>
          </section>

          {/* Section 7 */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
              <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/20 text-primary text-sm font-bold">7</span>
              Signals &amp; Intelligence Disclaimer
            </h2>
            <p className="text-muted-foreground mb-4">MarketMate signals are:</p>
            <ul className="space-y-3 text-muted-foreground mb-6">
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Probabilistic outputs based on model conditions</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Not guaranteed trade outcomes</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Subject to market conditions and latency effects</li>
            </ul>
            <p className="text-muted-foreground mb-4">No signal should be treated as:</p>
            <ul className="space-y-3 text-muted-foreground">
              <li className="flex gap-3"><span className="text-destructive">&bull;</span> Financial advice</li>
              <li className="flex gap-3"><span className="text-destructive">&bull;</span> Investment instruction</li>
              <li className="flex gap-3"><span className="text-destructive">&bull;</span> Guaranteed trade opportunity</li>
            </ul>
            <p className="text-foreground font-medium mt-4">
              Users must perform independent analysis before acting.
            </p>
          </section>

          {/* Section 8 */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
              <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/20 text-primary text-sm font-bold">8</span>
              MATE AI System
            </h2>
            <p className="text-muted-foreground mb-4">MATE is an AI-driven market intelligence interface. Users acknowledge:</p>
            <ul className="space-y-3 text-muted-foreground">
              <li className="flex gap-3"><span className="text-primary">&bull;</span> MATE is not human</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> MATE may produce incomplete or delayed interpretations</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> MATE relies on system state, which may be partially unavailable</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> MATE responses may change with updated market data</li>
            </ul>
            <p className="text-primary font-medium mt-4">
              MATE outputs are informational only and not advisory.
            </p>
          </section>

          {/* Section 9 */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
              <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/20 text-primary text-sm font-bold">9</span>
              Virtual Accounts
            </h2>
            <p className="text-muted-foreground mb-4">Virtual trading environments:</p>
            <ul className="space-y-3 text-muted-foreground">
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Do NOT reflect real market execution conditions exactly</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> May differ in latency, liquidity modeling, or price feeds</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Are intended for simulation and training purposes only</li>
            </ul>
            <p className="text-foreground font-medium mt-4">
              Performance in virtual accounts does not guarantee real-world results.
            </p>
          </section>

          {/* Section 10 */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
              <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/20 text-primary text-sm font-bold">10</span>
              User Obligations
            </h2>
            <p className="text-muted-foreground mb-4">Users agree to:</p>
            <ul className="space-y-3 text-muted-foreground">
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Use MarketMate ethically and legally</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Not exploit system vulnerabilities</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Not attempt unauthorized data extraction</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Not misrepresent MarketMate outputs as guaranteed financial advice</li>
            </ul>
            <p className="text-foreground font-medium mt-4">
              Users are responsible for compliance with local financial laws.
            </p>
          </section>

          {/* Section 11 */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
              <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/20 text-primary text-sm font-bold">11</span>
              Prohibited Uses
            </h2>
            <p className="text-muted-foreground mb-4">Users may NOT use MarketMate for:</p>
            <div className="bg-destructive/10 border border-destructive/30 rounded-lg p-6">
              <ul className="space-y-2 text-muted-foreground">
                <li className="flex gap-3"><span className="text-destructive">&#10005;</span> Illegal financial activities</li>
                <li className="flex gap-3"><span className="text-destructive">&#10005;</span> Market manipulation</li>
                <li className="flex gap-3"><span className="text-destructive">&#10005;</span> Fraudulent trading schemes</li>
                <li className="flex gap-3"><span className="text-destructive">&#10005;</span> Automated high-frequency abuse of APIs</li>
                <li className="flex gap-3"><span className="text-destructive">&#10005;</span> Redistribution of proprietary datasets</li>
                <li className="flex gap-3"><span className="text-destructive">&#10005;</span> Building competing intelligence systems without authorization</li>
              </ul>
            </div>
          </section>

          {/* Section 12 */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
              <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/20 text-primary text-sm font-bold">12</span>
              Data &amp; Privacy
            </h2>
            <div className="grid md:grid-cols-2 gap-6">
              <div className="bg-card border border-border rounded-lg p-6">
                <p className="text-foreground font-semibold mb-4">MarketMate may collect:</p>
                <ul className="space-y-2 text-muted-foreground text-sm">
                  <li className="flex gap-2"><span className="text-primary">&bull;</span> Usage analytics</li>
                  <li className="flex gap-2"><span className="text-primary">&bull;</span> API request logs</li>
                  <li className="flex gap-2"><span className="text-primary">&bull;</span> System interaction data</li>
                  <li className="flex gap-2"><span className="text-primary">&bull;</span> Performance metrics</li>
                </ul>
              </div>
              <div className="bg-card border border-border rounded-lg p-6">
                <p className="text-foreground font-semibold mb-4">This data is used for:</p>
                <ul className="space-y-2 text-muted-foreground text-sm">
                  <li className="flex gap-2"><span className="text-primary">&bull;</span> System improvement</li>
                  <li className="flex gap-2"><span className="text-primary">&bull;</span> Security monitoring</li>
                  <li className="flex gap-2"><span className="text-primary">&bull;</span> Model enhancement</li>
                  <li className="flex gap-2"><span className="text-primary">&bull;</span> Infrastructure scaling</li>
                </ul>
              </div>
            </div>
            <p className="text-primary font-medium mt-6">
              MarketMate does NOT sell personal user data.
            </p>
          </section>

          {/* Section 13 */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
              <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/20 text-primary text-sm font-bold">13</span>
              System Availability
            </h2>
            <p className="text-muted-foreground mb-4">MarketMate does not guarantee:</p>
            <ul className="space-y-3 text-muted-foreground">
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Continuous uptime</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Error-free operation</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Real-time accuracy under all conditions</li>
            </ul>
            <p className="text-muted-foreground mt-4">
              Maintenance, outages, or upgrades may occur without notice.
            </p>
          </section>

          {/* Section 14 */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
              <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/20 text-primary text-sm font-bold">14</span>
              Limitation of Liability
            </h2>
            <p className="text-muted-foreground mb-4">To the maximum extent permitted by law, MarketMate is not liable for:</p>
            <div className="bg-card border border-border rounded-lg p-6">
              <ul className="space-y-2 text-muted-foreground">
                <li className="flex gap-3"><span className="text-muted-foreground">&bull;</span> Trading losses</li>
                <li className="flex gap-3"><span className="text-muted-foreground">&bull;</span> Missed opportunities</li>
                <li className="flex gap-3"><span className="text-muted-foreground">&bull;</span> System delays</li>
                <li className="flex gap-3"><span className="text-muted-foreground">&bull;</span> Incorrect signals</li>
                <li className="flex gap-3"><span className="text-muted-foreground">&bull;</span> API downtime</li>
                <li className="flex gap-3"><span className="text-muted-foreground">&bull;</span> Financial decisions made based on outputs</li>
              </ul>
            </div>
            <p className="text-foreground font-medium mt-4">
              Users assume full responsibility for all actions taken.
            </p>
          </section>

          {/* Section 15 */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
              <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/20 text-primary text-sm font-bold">15</span>
              Termination
            </h2>
            <p className="text-muted-foreground mb-4">MarketMate reserves the right to:</p>
            <ul className="space-y-3 text-muted-foreground">
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Suspend access without notice</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Terminate accounts violating Terms</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Restrict API usage permanently</li>
              <li className="flex gap-3"><span className="text-primary">&bull;</span> Disable services in specific regions</li>
            </ul>
          </section>

          {/* Section 16 */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
              <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/20 text-primary text-sm font-bold">16</span>
              Modifications to Terms
            </h2>
            <p className="text-muted-foreground">
              MarketMate may update these Terms at any time. Continued use constitutes acceptance of updated Terms.
            </p>
          </section>

          {/* Section 17 */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
              <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/20 text-primary text-sm font-bold">17</span>
              Governing Law
            </h2>
            <p className="text-muted-foreground">
              These Terms are governed by applicable international commercial and digital service laws depending on jurisdiction of operation.
            </p>
          </section>

          {/* Section 18 */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
              <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/20 text-primary text-sm font-bold">18</span>
              Final Acknowledgement
            </h2>
            <div className="bg-primary/10 border border-primary/30 rounded-lg p-6">
              <p className="text-foreground font-semibold mb-4">By using MarketMate, Users acknowledge:</p>
              <ul className="space-y-3 text-muted-foreground">
                <li className="flex gap-3"><span className="text-primary">&#10003;</span> They understand the risks involved</li>
                <li className="flex gap-3"><span className="text-primary">&#10003;</span> They are not relying on MarketMate for guaranteed financial outcomes</li>
                <li className="flex gap-3"><span className="text-primary">&#10003;</span> They accept full responsibility for all decisions made using MarketMate systems</li>
              </ul>
            </div>
          </section>
        </div>

        {/* Footer navigation */}
        <div className="border-t border-border pt-8 mt-12 flex flex-col sm:flex-row justify-between items-center gap-4">
          <p className="text-sm text-muted-foreground">
            Last updated: January 1, 2025
          </p>
          <div className="flex gap-6">
            <Link href="/privacy" className="text-sm text-primary hover:underline">
              Privacy Policy
            </Link>
            <Link href="/" className="text-sm text-primary hover:underline">
              Back to Home
            </Link>
          </div>
        </div>
      </main>
    </div>
  )
}
