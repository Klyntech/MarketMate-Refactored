"use client"

import { useState } from "react"
import Link from "next/link"
import Image from "next/image"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ArrowLeft, ArrowRight, Check, Mail, Shield } from "lucide-react"

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [isSubmitted, setIsSubmitted] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    // Simulate sending reset email
    await new Promise((resolve) => setTimeout(resolve, 1500))
    setIsLoading(false)
    setIsSubmitted(true)
  }

  return (
    <div className="min-h-screen bg-background flex">
      {/* Left Panel - Branding (matches signup/login) */}
      <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden">
        {/* Background gradient */}
        <div className="absolute inset-0 bg-gradient-to-br from-primary/20 via-background to-accent/10" />
        
        {/* Grid pattern overlay */}
        <div 
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage: `linear-gradient(rgba(212, 165, 42, 0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(212, 165, 42, 0.3) 1px, transparent 1px)`,
            backgroundSize: '60px 60px'
          }}
        />
        
        {/* Glowing orbs */}
        <div className="absolute top-1/3 left-1/3 w-96 h-96 bg-primary/30 rounded-full blur-[120px]" />
        <div className="absolute bottom-1/4 right-1/4 w-64 h-64 bg-accent/20 rounded-full blur-[100px]" />
        
        {/* Content */}
        <div className="relative z-10 flex flex-col justify-between p-12 w-full">
          <Link href="/" className="flex items-center gap-3">
            <Image
              src="/logo.svg"
              alt="MarketMate Logo"
              width={40}
              height={34}
              className="h-9 w-auto"
            />
            <span className="text-2xl font-bold text-foreground">MarketMate</span>
          </Link>
          
          <div className="max-w-md">
            <h1 className="text-4xl font-bold text-foreground mb-6 leading-tight text-balance">
              Recover Your Account
            </h1>
            <p className="text-lg text-muted-foreground mb-8">
              Secure account recovery powered by MarketMate infrastructure. Your data and access are protected at every step.
            </p>
            
            {/* Security highlights */}
            <div className="space-y-4">
              {[
                "Encrypted password reset link",
                "Link expires after 24 hours",
                "No password is ever sent in plain text",
              ].map((feature, index) => (
                <div key={index} className="flex items-center gap-3">
                  <div className="flex items-center justify-center w-6 h-6 rounded-full bg-primary/20 border border-primary/30">
                    <Shield className="w-3 h-3 text-primary" />
                  </div>
                  <span className="text-muted-foreground">{feature}</span>
                </div>
              ))}
            </div>
          </div>
          
          {/* Trust stats */}
          <div className="flex gap-12">
            <div>
              <div className="text-3xl font-bold text-primary">256-bit</div>
              <div className="text-sm text-muted-foreground">Encryption</div>
            </div>
            <div>
              <div className="text-3xl font-bold text-primary">24h</div>
              <div className="text-sm text-muted-foreground">Link Expiry</div>
            </div>
            <div>
              <div className="text-3xl font-bold text-primary">0</div>
              <div className="text-sm text-muted-foreground">Data Leaks</div>
            </div>
          </div>
        </div>
      </div>

      {/* Right Panel - Reset Form */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center justify-center gap-3 mb-8">
            <Image
              src="/logo.svg"
              alt="MarketMate Logo"
              width={40}
              height={34}
              className="h-9 w-auto"
            />
            <span className="text-2xl font-bold text-foreground">MarketMate</span>
          </div>

          {isSubmitted ? (
            <div className="text-center space-y-6">
              {/* Success icon */}
              <div className="flex items-center justify-center w-16 h-16 rounded-full bg-emerald-500/10 border border-emerald-500/20 mx-auto">
                <Check className="w-8 h-8 text-emerald-500" />
              </div>
              
              <div>
                <h2 className="text-2xl font-bold text-foreground mb-2">Check your email</h2>
                <p className="text-muted-foreground">
                  If an account exists for <span className="text-foreground font-medium">{email}</span>, 
                  you will receive a password reset link shortly.
                </p>
              </div>

              {/* Security note */}
              <div className="flex items-start gap-3 p-4 rounded-lg bg-secondary/50 border border-border text-left">
                <Shield className="w-5 h-5 text-primary shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm text-foreground font-medium">Security note</p>
                  <p className="text-xs text-muted-foreground">
                    The reset link will expire in 24 hours. If you did not request this, you can safely ignore this email.
                  </p>
                </div>
              </div>
              
              <div className="pt-4 space-y-3">
                <Button 
                  type="button"
                  variant="outline" 
                  className="w-full h-12 border-border hover:bg-secondary hover:border-primary/50"
                  onClick={() => { setIsSubmitted(false); setEmail(""); }}
                >
                  <Mail className="w-4 h-4 mr-2" />
                  Try a different email
                </Button>
                
                <Button asChild className="w-full h-12 bg-primary text-primary-foreground hover:bg-primary/90">
                  <Link href="/login">
                    <ArrowLeft className="w-4 h-4 mr-2" />
                    Back to Sign In
                  </Link>
                </Button>
              </div>
            </div>
          ) : (
            <>
              <div className="text-center mb-8">
                <h2 className="text-2xl font-bold text-foreground mb-2">Forgot your password?</h2>
                <p className="text-muted-foreground">
                  No worries. Enter your email address and we&apos;ll send you a link to reset your password.
                </p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-5">
                <div className="space-y-2">
                  <Label htmlFor="email" className="text-foreground">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="you@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="h-12 bg-secondary border-border focus:border-primary focus:ring-primary/20"
                    required
                    disabled={isLoading}
                  />
                </div>
                
                <Button 
                  type="submit" 
                  className="w-full h-12 bg-primary text-primary-foreground hover:bg-primary/90 transition-all group"
                  disabled={isLoading}
                >
                  {isLoading ? (
                    <div className="flex items-center gap-2">
                      <div className="w-5 h-5 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full animate-spin" />
                      Sending reset link...
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      Send Reset Link
                      <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                    </div>
                  )}
                </Button>
              </form>
              
              <div className="text-center mt-8">
                <Link 
                  href="/login" 
                  className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  <ArrowLeft className="w-4 h-4" />
                  Back to Sign In
                </Link>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
