import Link from "next/link"
import Image from "next/image"
import { Github, Twitter } from "lucide-react"

const footerLinks = {
  Products: [
    { name: "MarketMate API", href: "#" },
    { name: "MATE AI", href: "#" },
    { name: "MMAcademy", href: "/academy" },
    { name: "MarketMate Desk", href: "/desk" },
  ],
  Developers: [
    { name: "Documentation", href: "#" },
    { name: "API Reference", href: "#" },
    { name: "SDKs", href: "#" },
    { name: "Status", href: "#" },
  ],
  Company: [
    { name: "About", href: "#" },
    { name: "Blog", href: "#" },
    { name: "Careers", href: "#" },
    { name: "Contact", href: "#" },
  ],
  Legal: [
    { name: "Privacy", href: "#" },
    { name: "Terms", href: "#" },
    { name: "Security", href: "#" },
  ],
}

export function Footer() {
  return (
    <footer className="border-t border-border bg-card">
      <div className="mx-auto max-w-7xl px-6 py-12 lg:px-8">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-8">
          {/* Logo and description */}
          <div className="col-span-2 md:col-span-1">
            <Link href="/" className="flex items-center gap-2 mb-4">
              <Image
                src="/logo.svg"
                alt="MarketMate Logo"
                width={32}
                height={27}
                className="h-7 w-auto"
              />
              <span className="text-lg font-bold text-foreground">MarketMate</span>
            </Link>
            <p className="text-sm text-muted-foreground mb-4">
              Real-time market intelligence infrastructure for the modern trader.
            </p>
            <div className="flex gap-4">
              <Link href="#" className="text-muted-foreground hover:text-foreground transition-colors">
                <Twitter className="h-5 w-5" />
              </Link>
              <Link href="#" className="text-muted-foreground hover:text-foreground transition-colors">
                <Github className="h-5 w-5" />
              </Link>
            </div>
          </div>
          
          {/* Links */}
          {Object.entries(footerLinks).map(([category, links]) => (
            <div key={category}>
              <h3 className="text-sm font-semibold text-foreground mb-4">{category}</h3>
              <ul className="space-y-3">
                {links.map((link) => (
                  <li key={link.name}>
                    <Link 
                      href={link.href}
                      className="text-sm text-muted-foreground hover:text-foreground transition-colors"
                    >
                      {link.name}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        
        <div className="mt-12 pt-8 border-t border-border">
          <p className="text-sm text-muted-foreground text-center">
            &copy; {new Date().getFullYear()} MarketMate. All rights reserved.
          </p>
        </div>
      </div>
    </footer>
  )
}
