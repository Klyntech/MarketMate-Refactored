"use client"

import { useState, useEffect } from "react"

type SignalState = "open" | "update" | "tp1" | "closed"

const signalStates: { state: SignalState; content: React.ReactNode }[] = [
  {
    state: "open",
    content: (
      <div className="font-mono text-sm leading-relaxed">
        <div className="text-emerald-400 font-semibold mb-3">OPEN SIGNAL</div>
        <div className="text-primary font-semibold mb-4">MARKETMATE DESK SIGNAL</div>
        <div className="space-y-1 text-muted-foreground">
          <div><span className="text-foreground">PAIR:</span> XAUUSD</div>
          <div><span className="text-foreground">TYPE:</span> SELL</div>
          <div><span className="text-foreground">ENTRY:</span> 2558.20</div>
          <div><span className="text-foreground">SL:</span> 2565.00</div>
        </div>
        <div className="my-4 border-t border-border/50" />
        <div className="space-y-1 text-muted-foreground">
          <div><span className="text-foreground">TP1:</span> 2552.00</div>
          <div><span className="text-foreground">TP2:</span> 2546.00</div>
          <div><span className="text-foreground">TP3:</span> 2538.00</div>
        </div>
        <div className="my-4 border-t border-border/50" />
        <div className="space-y-1 text-muted-foreground text-xs">
          <div><span className="text-foreground">RISK:</span> 1%</div>
          <div><span className="text-foreground">BIAS:</span> BEARISH</div>
          <div><span className="text-foreground">CONFIDENCE:</span> HIGH</div>
        </div>
        <div className="mt-4 pt-3 border-t border-border/50">
          <span className="text-emerald-400">STATUS: ACTIVE</span>
        </div>
      </div>
    ),
  },
  {
    state: "update",
    content: (
      <div className="font-mono text-sm leading-relaxed">
        <div className="text-amber-400 font-semibold mb-3">UPDATE</div>
        <div className="text-muted-foreground">
          <p>Price entering execution zone.</p>
          <p className="mt-2">Liquidity sweep confirmed.</p>
        </div>
        <div className="mt-4 text-xs text-muted-foreground/60">
          Reply to: XAUUSD SELL @ 2558.20
        </div>
      </div>
    ),
  },
  {
    state: "tp1",
    content: (
      <div className="font-mono text-sm leading-relaxed">
        <div className="text-emerald-400 font-semibold mb-3">TP1 HIT</div>
        <div className="text-muted-foreground">
          <p className="text-foreground">+1R secured.</p>
          <p className="mt-2">SL moved to breakeven.</p>
        </div>
        <div className="mt-4 text-xs text-muted-foreground/60">
          Reply to: XAUUSD SELL @ 2558.20
        </div>
      </div>
    ),
  },
  {
    state: "closed",
    content: (
      <div className="font-mono text-sm leading-relaxed">
        <div className="text-red-400 font-semibold mb-3">SIGNAL CLOSED</div>
        <div className="space-y-2 text-muted-foreground">
          <div><span className="text-foreground">TP2 HIT</span></div>
          <div>Final Result: <span className="text-emerald-400">+2R</span></div>
          <div>Duration: 3H 12M</div>
        </div>
        <div className="mt-4 text-xs text-muted-foreground/60">
          Reply to: XAUUSD SELL @ 2558.20
        </div>
      </div>
    ),
  },
]

export function SignalLifecycle() {
  const [activeState, setActiveState] = useState<SignalState>("open")
  const [isAutoPlaying, setIsAutoPlaying] = useState(true)

  useEffect(() => {
    if (!isAutoPlaying) return

    const states: SignalState[] = ["open", "update", "tp1", "closed"]
    const currentIndex = states.indexOf(activeState)
    
    const timer = setTimeout(() => {
      const nextIndex = (currentIndex + 1) % states.length
      setActiveState(states[nextIndex])
    }, 3000)

    return () => clearTimeout(timer)
  }, [activeState, isAutoPlaying])

  const stateLabels: { state: SignalState; label: string; color: string }[] = [
    { state: "open", label: "Open", color: "bg-emerald-500" },
    { state: "update", label: "Update", color: "bg-amber-500" },
    { state: "tp1", label: "TP1 Hit", color: "bg-emerald-500" },
    { state: "closed", label: "Closed", color: "bg-red-500" },
  ]

  return (
    <section className="py-24 border-t border-border bg-card/50">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        {/* Section header */}
        <div className="text-center mb-16">
          <p className="text-sm font-medium text-primary uppercase tracking-wider mb-3">Signal Format</p>
          <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4 text-balance">
            Live State Updates. Not Noise.
          </h2>
          <p className="text-muted-foreground max-w-xl mx-auto text-pretty">
            Every signal has a lifecycle. Desk tracks it from open to close with threaded updates.
          </p>
        </div>

        <div className="grid lg:grid-cols-2 gap-12 items-start max-w-5xl mx-auto">
          {/* Signal preview */}
          <div 
            className="relative"
            onMouseEnter={() => setIsAutoPlaying(false)}
            onMouseLeave={() => setIsAutoPlaying(true)}
          >
            {/* Telegram-style message container */}
            <div className="bg-[#0e1621] rounded-xl p-6 border border-border/50 shadow-2xl">
              {/* Channel header */}
              <div className="flex items-center gap-3 mb-6 pb-4 border-b border-border/30">
                <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center">
                  <span className="text-primary font-bold text-sm">MD</span>
                </div>
                <div>
                  <div className="text-foreground font-medium text-sm">MarketMate Desk</div>
                  <div className="text-muted-foreground text-xs">Signal Channel</div>
                </div>
              </div>

              {/* Signal content */}
              <div className="min-h-[280px]">
                {signalStates.find(s => s.state === activeState)?.content}
              </div>

              {/* Timestamp */}
              <div className="mt-4 text-right text-xs text-muted-foreground/50">
                {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </div>
            </div>

            {/* State indicator pills */}
            <div className="flex items-center justify-center gap-2 mt-6">
              {stateLabels.map((item) => (
                <button
                  key={item.state}
                  onClick={() => {
                    setActiveState(item.state)
                    setIsAutoPlaying(false)
                  }}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                    activeState === item.state
                      ? "bg-secondary border border-border text-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  <span className={`w-1.5 h-1.5 rounded-full ${item.color}`} />
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          {/* Explanation */}
          <div className="space-y-8">
            <div>
              <h3 className="text-lg font-semibold text-foreground mb-3">Why This Matters</h3>
              <p className="text-muted-foreground text-sm leading-relaxed">
                Most signal channels feel dead. Random messages. No lifecycle. No state continuity. 
                Desk should feel like a live tactical operation room.
              </p>
            </div>

            <div className="space-y-4">
              <h4 className="text-sm font-medium text-foreground uppercase tracking-wider">Signal Lifecycle</h4>
              
              <div className="space-y-3">
                {[
                  { step: "1", title: "Signal Opens", desc: "Complete trade parameters published" },
                  { step: "2", title: "State Updates", desc: "Threaded replies track price action" },
                  { step: "3", title: "Targets Hit", desc: "Each TP confirmed with new status" },
                  { step: "4", title: "Signal Closes", desc: "Final result and duration logged" },
                ].map((item) => (
                  <div key={item.step} className="flex gap-4">
                    <div className="w-6 h-6 rounded-full bg-secondary border border-border flex items-center justify-center shrink-0">
                      <span className="text-xs font-medium text-muted-foreground">{item.step}</span>
                    </div>
                    <div>
                      <div className="text-sm font-medium text-foreground">{item.title}</div>
                      <div className="text-xs text-muted-foreground">{item.desc}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="p-4 rounded-lg bg-secondary/50 border border-border">
              <p className="text-xs text-muted-foreground leading-relaxed">
                <span className="text-foreground font-medium">Threading creates continuity.</span>{" "}
                Every update replies to the original signal, creating a clear trade history 
                that builds emotional trust and operational clarity.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
