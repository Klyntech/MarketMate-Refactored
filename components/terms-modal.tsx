"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { CheckCircle2, AlertTriangle, Shield, Code2, Bot, FileText } from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"

const TERMS_STORAGE_KEY = "mate-api-terms-accepted"
const TERMS_VERSION = "1.0"

interface TermSection {
  icon: React.ElementType
  title: string
  items: string[]
  variant: "info" | "warning" | "danger"
}

const termsSections: TermSection[] = [
  {
    icon: Shield,
    title: "Nature of Services",
    variant: "info",
    items: [
      "MarketMate is a financial intelligence platform, not a broker or advisor",
      "We do NOT execute trades, hold funds, or guarantee profits",
      "All outputs are for informational and analytical purposes only",
    ],
  },
  {
    icon: AlertTriangle,
    title: "Risk Disclosure",
    variant: "warning",
    items: [
      "Trading financial instruments involves significant risk",
      "Loss of capital is possible — past performance does not guarantee results",
      "AI-generated signals may be incorrect or incomplete",
      "You accept full responsibility for all trading decisions",
    ],
  },
  {
    icon: Code2,
    title: "API Usage Terms",
    variant: "info",
    items: [
      "Do not abuse rate limits, scrape data, or attempt unauthorized access",
      "Do not use API outputs to train competing AI systems",
      "MarketMate may rate limit, suspend, or modify endpoints without notice",
    ],
  },
  {
    icon: Bot,
    title: "MATE AI System",
    variant: "info",
    items: [
      "MATE is an AI interface — not human, not a financial advisor",
      "Responses may be incomplete, delayed, or change with updated data",
      "MATE outputs are informational only — always perform independent analysis",
    ],
  },
  {
    icon: FileText,
    title: "Data & Liability",
    variant: "danger",
    items: [
      "We collect usage analytics and API logs for system improvement",
      "We do NOT sell personal user data",
      "MarketMate is not liable for trading losses, missed opportunities, or system delays",
      "Violation of terms results in immediate termination",
    ],
  },
]

export function TermsModal() {
  const [isOpen, setIsOpen] = useState(false)
  const [accepted, setAccepted] = useState(false)
  const [hasScrolled, setHasScrolled] = useState(false)

  useEffect(() => {
    // Check if terms have been accepted
    const storedAcceptance = localStorage.getItem(TERMS_STORAGE_KEY)
    if (storedAcceptance) {
      const { version, timestamp } = JSON.parse(storedAcceptance)
      // If version matches and was accepted, don't show modal
      if (version === TERMS_VERSION) {
        return
      }
    }
    // Show modal after a brief delay to let the page load
    const timer = setTimeout(() => setIsOpen(true), 500)
    return () => clearTimeout(timer)
  }, [])

  const handleAccept = () => {
    localStorage.setItem(
      TERMS_STORAGE_KEY,
      JSON.stringify({
        version: TERMS_VERSION,
        timestamp: new Date().toISOString(),
      })
    )
    setIsOpen(false)
  }

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const target = e.target as HTMLDivElement
    const scrollPercentage = (target.scrollTop / (target.scrollHeight - target.clientHeight)) * 100
    if (scrollPercentage > 80) {
      setHasScrolled(true)
    }
  }

  const variantStyles = {
    info: "border-border bg-secondary/30",
    warning: "border-amber-500/30 bg-amber-500/5",
    danger: "border-destructive/30 bg-destructive/5",
  }

  const iconStyles = {
    info: "text-primary",
    warning: "text-amber-500",
    danger: "text-destructive",
  }

  return (
    <Dialog open={isOpen} onOpenChange={() => {}}>
      <DialogContent
        showCloseButton={false}
        className="max-w-2xl gap-0 overflow-hidden p-0"
        onPointerDownOutside={(e) => e.preventDefault()}
        onEscapeKeyDown={(e) => e.preventDefault()}
      >
        {/* Header */}
        <DialogHeader className="border-b border-border bg-secondary/30 px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/20">
              <Shield className="h-5 w-5 text-primary" />
            </div>
            <div>
              <DialogTitle className="text-lg font-bold text-foreground">
                MATE API Terms of Service
              </DialogTitle>
              <DialogDescription className="text-sm text-muted-foreground">
                Please review and accept to continue
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        {/* Content */}
        <ScrollArea className="h-[400px]" onScrollCapture={handleScroll}>
          <div className="space-y-4 p-6">
            {/* Intro */}
            <p className="text-sm text-muted-foreground">
              By using the MarketMate MATE API, you agree to be bound by these terms.
              Please read carefully before proceeding.
            </p>

            {/* Sections */}
            {termsSections.map((section, index) => (
              <div
                key={index}
                className={cn(
                  "rounded-lg border p-4",
                  variantStyles[section.variant]
                )}
              >
                <div className="mb-3 flex items-center gap-2">
                  <section.icon
                    className={cn("h-4 w-4", iconStyles[section.variant])}
                  />
                  <h3 className="font-mono text-sm font-semibold uppercase tracking-wider text-foreground">
                    {section.title}
                  </h3>
                </div>
                <ul className="space-y-2">
                  {section.items.map((item, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-muted-foreground">
                      <span className={cn("mt-1.5 h-1 w-1 flex-shrink-0 rounded-full", 
                        section.variant === "warning" ? "bg-amber-500" : 
                        section.variant === "danger" ? "bg-destructive" : "bg-primary"
                      )} />
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            ))}

            {/* Full Terms Link */}
            <div className="rounded-lg border border-border bg-card p-4 text-center">
              <p className="text-sm text-muted-foreground">
                This is a summary of key terms.{" "}
                <Link
                  href="/terms"
                  target="_blank"
                  className="font-medium text-primary hover:underline"
                >
                  Read the full Terms and Conditions
                </Link>
              </p>
            </div>
          </div>
        </ScrollArea>

        {/* Footer */}
        <DialogFooter className="flex-col gap-4 border-t border-border bg-secondary/30 px-6 py-4 sm:flex-col">
          {/* Checkbox */}
          <div className="flex items-start gap-3">
            <Checkbox
              id="accept-terms"
              checked={accepted}
              onCheckedChange={(checked) => setAccepted(checked === true)}
              disabled={!hasScrolled}
              className="mt-0.5"
            />
            <label
              htmlFor="accept-terms"
              className={cn(
                "text-sm leading-relaxed",
                hasScrolled ? "text-foreground" : "text-muted-foreground"
              )}
            >
              I have read and agree to the Terms of Service. I understand that MarketMate
              provides informational services only and I accept full responsibility for
              my trading decisions.
            </label>
          </div>

          {/* Scroll hint */}
          {!hasScrolled && (
            <p className="text-center text-xs text-muted-foreground">
              Please scroll through the terms to enable acceptance
            </p>
          )}

          {/* Accept Button */}
          <Button
            onClick={handleAccept}
            disabled={!accepted}
            className="w-full gap-2"
          >
            <CheckCircle2 className="h-4 w-4" />
            Accept and Continue
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
