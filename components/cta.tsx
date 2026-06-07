"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ArrowRight, Check } from "lucide-react"

export function CTA() {
  const [email, setEmail] = useState("")
  const [submitted, setSubmitted] = useState(false)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitted(true)
    setEmail("")
  }

  return (
    <section className="py-24 relative overflow-hidden">
      {/* Background gradient */}
      <div className="absolute inset-0">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-accent/20 rounded-full blur-[120px] opacity-50" />
      </div>
      
      <div className="relative z-10 mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4 text-balance">
            Ready to Transform Your Trading Intelligence?
          </h2>
          <p className="text-muted-foreground text-lg mb-8 text-pretty">
            Join thousands of traders and developers building with structured market context. 
            Get early access to new features and priority support.
          </p>
          
          {submitted ? (
            <div className="flex items-center justify-center gap-2 text-accent">
              <Check className="h-5 w-5" />
              <span className="font-medium">Thanks! We&apos;ll be in touch soon.</span>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-3 max-w-md mx-auto">
              <Input
                type="email"
                placeholder="Enter your email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="bg-secondary border-border text-foreground placeholder:text-muted-foreground flex-1"
              />
              <Button 
                type="submit"
                className="bg-primary text-primary-foreground hover:bg-primary/90"
              >
                Get Early Access
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </form>
          )}
          
          <p className="text-xs text-muted-foreground mt-4">
            Free tier available. No credit card required.
          </p>
        </div>
      </div>
    </section>
  )
}
