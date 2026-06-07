'use client';

import { useEffect } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { useAppStore, type ViewType } from '@/lib/store';
import { AuthModal } from '@/components/marketmate/auth-modal';
import { AppSidebar, AppHeader } from '@/components/marketmate/app-shell';
import { MarketDashboard } from '@/components/marketmate/market-dashboard';
import { ApiKeysPanel } from '@/components/marketmate/api-keys-panel';
import { MateChat } from '@/components/marketmate/mate-chat';
import Navbar from '@/components/marketmate/navbar';
import Hero from '@/components/marketmate/hero';
import LiveStateFeed from '@/components/marketmate/live-state-feed';
import Mission from '@/components/marketmate/mission';
import { Capabilities } from '@/components/marketmate/capabilities';
import { Pillars } from '@/components/marketmate/pillars';
import MateIntelligence from '@/components/marketmate/mate-intelligence';
import Academy from '@/components/marketmate/academy';
import DeveloperHub from '@/components/marketmate/developer-hub';
import { Desk } from '@/components/marketmate/desk';
import Architecture from '@/components/marketmate/architecture';
import Footer from '@/components/marketmate/footer';
import { BookOpen, FileText, GraduationCap } from 'lucide-react';

function DocsView() {
  return (
    <div className="p-4 sm:p-6">
      <div className="mx-auto max-w-4xl">
        <h2 className="flex items-center gap-2.5 text-2xl font-bold text-white">
          <FileText className="h-6 w-6 text-emerald-400" />
          Documentation
        </h2>
        <p className="mt-2 text-sm text-zinc-400">
          Complete API reference and integration guides
        </p>

        <div className="mt-8 grid gap-4 sm:grid-cols-2">
          {[
            {
              title: 'Getting Started',
              desc: 'Quick start guide for the MarketMate API',
              badge: 'Guide',
            },
            {
              title: 'Authentication',
              desc: 'API key management and authentication flows',
              badge: 'Auth',
            },
            {
              title: 'Market State Endpoint',
              desc: 'GET /api/v1/market-state — Real-time market intelligence',
              badge: 'Endpoint',
            },
            {
              title: 'WebSocket Stream',
              desc: 'Real-time market state updates via WebSocket',
              badge: 'Streaming',
            },
            {
              title: 'MATE Interpreter',
              desc: 'POST /api/v1/mate — AI-powered market interpretation',
              badge: 'AI',
            },
            {
              title: 'Event Schemas',
              desc: 'Structured output schemas for all market events',
              badge: 'Schema',
            },
          ].map((doc) => (
            <div
              key={doc.title}
              className="group rounded-xl border border-white/[0.06] bg-white/[0.02] p-5 transition-all duration-300 hover:border-emerald-500/20 hover:shadow-[0_0_24px_-4px_rgba(16,185,129,0.12)]"
            >
              <span className="inline-block rounded-md bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-emerald-400 ring-1 ring-emerald-500/20">
                {doc.badge}
              </span>
              <h3 className="mt-3 text-sm font-semibold text-white/90">
                {doc.title}
              </h3>
              <p className="mt-1.5 text-xs leading-relaxed text-zinc-500">
                {doc.desc}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function AcademyView() {
  return (
    <div className="p-4 sm:p-6">
      <div className="mx-auto max-w-4xl">
        <h2 className="flex items-center gap-2.5 text-2xl font-bold text-white">
          <GraduationCap className="h-6 w-6 text-emerald-400" />
          MMAcademy
        </h2>
        <p className="mt-2 text-sm text-zinc-400">
          Learn market intelligence, structure analysis, and trading principles
        </p>

        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[
            {
              title: 'SMC Foundations',
              desc: 'Smart Money Concepts — market structure, order blocks, and liquidity zones',
              lessons: 12,
              level: 'Beginner',
            },
            {
              title: 'Regime Analysis',
              desc: 'Identify and trade within different market regimes — trending, ranging, volatile',
              lessons: 8,
              level: 'Intermediate',
            },
            {
              title: 'Conviction Scoring',
              desc: 'Understanding MarketMate\'s 5-brain conviction system and how to apply it',
              lessons: 6,
              level: 'Intermediate',
            },
            {
              title: 'Gate Pipeline',
              desc: 'Deep dive into the 8-gate validation system for signal quality',
              lessons: 10,
              level: 'Advanced',
            },
            {
              title: 'Execution Framework',
              desc: 'From conviction to execution — risk management and position sizing',
              lessons: 8,
              level: 'Advanced',
            },
            {
              title: 'API Integration',
              desc: 'Build automated systems with MarketMate\'s real-time intelligence API',
              lessons: 5,
              level: 'Developer',
            },
          ].map((course) => (
            <div
              key={course.title}
              className="group rounded-xl border border-white/[0.06] bg-white/[0.02] p-5 transition-all duration-300 hover:border-emerald-500/20 hover:shadow-[0_0_24px_-4px_rgba(16,185,129,0.12)]"
            >
              <div className="flex items-center justify-between">
                <span className="inline-block rounded-md bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-emerald-400 ring-1 ring-emerald-500/20">
                  {course.level}
                </span>
                <span className="text-[10px] font-mono text-zinc-600">
                  {course.lessons} lessons
                </span>
              </div>
              <h3 className="mt-3 text-sm font-semibold text-white/90">
                {course.title}
              </h3>
              <p className="mt-1.5 text-xs leading-relaxed text-zinc-500">
                {course.desc}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function LandingView() {
  return (
    <div className="min-h-screen flex flex-col bg-background">
      <Navbar />
      <main className="flex-1">
        <Hero />
        <LiveStateFeed />
        <Mission />
        <Capabilities />
        <Pillars />
        <MateIntelligence />
        <Academy />
        <DeveloperHub />
        <Desk />
        <Architecture />
      </main>
      <Footer />
    </div>
  );
}

function AuthenticatedApp() {
  const { currentView } = useAppStore();

  const renderView = () => {
    switch (currentView) {
      case 'dashboard':
        return <MarketDashboard />;
      case 'api-keys':
        return <ApiKeysPanel />;
      case 'mate-chat':
        return <MateChat />;
      case 'docs':
        return <DocsView />;
      case 'academy':
        return <AcademyView />;
      default:
        return <MarketDashboard />;
    }
  };

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <AppSidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <AppHeader />
        <main className="flex-1 overflow-y-auto">
          <AnimatePresence mode="wait">
            <motion.div
              key={currentView}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.2 }}
              className={currentView === 'mate-chat' ? 'h-full' : ''}
            >
              {renderView()}
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}

export default function Home() {
  const { isAuthenticated, currentView, hydrateAuth } = useAppStore();

  // Hydrate auth state from localStorage on mount
  useEffect(() => {
    hydrateAuth();
  }, [hydrateAuth]);

  // If on landing page, show the marketing site
  if (!isAuthenticated || currentView === 'landing') {
    return (
      <>
        <LandingView />
        <AuthModal />
      </>
    );
  }

  // Authenticated app
  return (
    <>
      <AuthenticatedApp />
      <AuthModal />
    </>
  );
}
