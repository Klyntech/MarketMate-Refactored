"use client"

import { useState } from "react"
import Link from "next/link"
import { useSession } from "next-auth/react"
import useSWR from "swr"
import { formatDistanceToNow } from "date-fns"
import { Header } from "@/components/header"
import { Footer } from "@/components/footer"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Key,
  Plus,
  Copy,
  Check,
  AlertTriangle,
  Loader2,
  ShieldOff,
} from "lucide-react"

const fetcher = (url: string) => fetch(url).then((r) => r.json())

interface ApiKeyData {
  id: string
  name: string
  prefix: string
  environment: string
  lastUsed: string | null
  createdAt: string
  revokedAt: string | null
}

export default function ApiKeysPage() {
  const { data: session } = useSession()
  const { data: keysData, mutate } = useSWR<{ keys: ApiKeyData[] }>("/api/keys", fetcher)

  const apiKeys = keysData?.keys ?? []

  // Create dialog state
  const [createOpen, setCreateOpen] = useState(false)
  const [keyName, setKeyName] = useState("")
  const [keyEnvironment, setKeyEnvironment] = useState("live")
  const [isCreating, setIsCreating] = useState(false)
  const [createError, setCreateError] = useState("")

  // New key display state
  const [newKeyDialogOpen, setNewKeyDialogOpen] = useState(false)
  const [newKeyValue, setNewKeyValue] = useState("")
  const [newKeyName, setNewKeyName] = useState("")
  const [copied, setCopied] = useState(false)

  // Revoke state
  const [revokingKeyId, setRevokingKeyId] = useState<string | null>(null)
  const [isRevoking, setIsRevoking] = useState(false)

  const handleCreate = async () => {
    if (!keyName.trim()) {
      setCreateError("Name is required")
      return
    }

    setIsCreating(true)
    setCreateError("")

    try {
      const res = await fetch("/api/keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: keyName.trim(), environment: keyEnvironment }),
      })

      const data = await res.json()

      if (!res.ok) {
        setCreateError(data.error || "Failed to create API key")
        return
      }

      // Close create dialog and open new key display
      setCreateOpen(false)
      setNewKeyValue(data.apiKey.key)
      setNewKeyName(data.apiKey.name)
      setNewKeyDialogOpen(true)
      setKeyName("")
      setKeyEnvironment("live")
      setCopied(false)
      mutate()
    } catch {
      setCreateError("Failed to create API key. Please try again.")
    } finally {
      setIsCreating(false)
    }
  }

  const handleCopy = async (text: string) => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleRevoke = async (keyId: string) => {
    setIsRevoking(true)
    try {
      const res = await fetch(`/api/keys/${keyId}`, {
        method: "DELETE",
      })

      if (res.ok) {
        mutate()
      }
    } catch {
      // silently fail
    } finally {
      setIsRevoking(false)
      setRevokingKeyId(null)
    }
  }

  const formatLastUsed = (lastUsed: string | null) => {
    if (!lastUsed) return "Never"
    return formatDistanceToNow(new Date(lastUsed), { addSuffix: true })
  }

  const formatCreatedDate = (createdAt: string) => {
    return formatDistanceToNow(new Date(createdAt), { addSuffix: true })
  }

  return (
    <main className="min-h-screen bg-background flex flex-col">
      <Header />

      <div className="flex-1 pt-20">
        <div className="mx-auto max-w-7xl px-6 py-8 lg:px-8">
          {/* Breadcrumb */}
          <Breadcrumb className="mb-6">
            <BreadcrumbList>
              <BreadcrumbItem>
                <BreadcrumbLink asChild>
                  <Link href="/">Home</Link>
                </BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbLink asChild>
                  <Link href="/dashboard">Dashboard</Link>
                </BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbPage>API Keys</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>

          {/* Page Title */}
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
            <div>
              <h1 className="text-3xl font-bold text-foreground mb-2">API Keys</h1>
              <p className="text-muted-foreground">
                Manage your API keys for authenticating requests to the MarketMate API.
              </p>
            </div>

            {/* Create API Key Dialog */}
            <Dialog open={createOpen} onOpenChange={(open) => {
              setCreateOpen(open)
              if (!open) {
                setCreateError("")
                setKeyName("")
                setKeyEnvironment("live")
              }
            }}>
              <DialogTrigger asChild>
                <Button className="bg-primary text-primary-foreground hover:bg-primary/90 shrink-0">
                  <Plus className="w-4 h-4 mr-2" />
                  Create API Key
                </Button>
              </DialogTrigger>
              <DialogContent className="bg-card border-border">
                <DialogHeader>
                  <DialogTitle className="text-foreground">Create New API Key</DialogTitle>
                  <DialogDescription>
                    Generate a new API key to authenticate your requests. You can create up to 5 active keys.
                  </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-2">
                  <div className="space-y-2">
                    <Label htmlFor="key-name" className="text-foreground">Name</Label>
                    <Input
                      id="key-name"
                      placeholder="e.g., Production API, Trading Bot"
                      value={keyName}
                      onChange={(e) => {
                        setKeyName(e.target.value)
                        setCreateError("")
                      }}
                      className="bg-secondary border-border focus:border-primary focus:ring-primary/20"
                      maxLength={50}
                      disabled={isCreating}
                    />
                    <p className="text-xs text-muted-foreground">{keyName.length}/50 characters</p>
                  </div>

                  <div className="space-y-2">
                    <Label className="text-foreground">Environment</Label>
                    <Select value={keyEnvironment} onValueChange={setKeyEnvironment} disabled={isCreating}>
                      <SelectTrigger className="w-full bg-secondary border-border">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-popover border-border">
                        <SelectItem value="live">
                          <span className="flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-green-500" />
                            Live
                          </span>
                        </SelectItem>
                        <SelectItem value="test">
                          <span className="flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-blue-500" />
                            Test
                          </span>
                        </SelectItem>
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground">
                      {keyEnvironment === "live"
                        ? "Live keys process real requests and count toward your usage."
                        : "Test keys return mock data and don't affect your usage."}
                    </p>
                  </div>

                  {createError && (
                    <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-sm text-red-400">
                      {createError}
                    </div>
                  )}
                </div>

                <DialogFooter>
                  <Button
                    variant="outline"
                    onClick={() => setCreateOpen(false)}
                    disabled={isCreating}
                    className="border-border"
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={handleCreate}
                    disabled={isCreating || !keyName.trim()}
                    className="bg-primary text-primary-foreground hover:bg-primary/90"
                  >
                    {isCreating ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Creating...
                      </>
                    ) : (
                      "Create Key"
                    )}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>

          {/* New Key Display Dialog */}
          <Dialog open={newKeyDialogOpen} onOpenChange={setNewKeyDialogOpen}>
            <DialogContent className="bg-card border-border" showCloseButton={false}>
              <DialogHeader>
                <DialogTitle className="text-foreground flex items-center gap-2">
                  <Check className="w-5 h-5 text-green-500" />
                  API Key Created
                </DialogTitle>
                <DialogDescription>
                  Your API key <span className="text-foreground font-medium">{newKeyName}</span> has been created successfully.
                </DialogDescription>
              </DialogHeader>

              <div className="py-4 space-y-4">
                <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/30">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="w-5 h-5 text-red-400 mt-0.5 shrink-0" />
                    <p className="text-sm text-red-300">
                      Make sure to copy your API key now. You won&apos;t be able to see it again!
                    </p>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label className="text-foreground">Your API Key</Label>
                  <div className="flex items-center gap-2">
                    <code className="flex-1 p-3 rounded-lg bg-secondary border border-border font-mono text-sm text-accent break-all select-all">
                      {newKeyValue}
                    </code>
                    <Button
                      variant="outline"
                      size="icon"
                      className="shrink-0 border-border hover:border-accent/50"
                      onClick={() => handleCopy(newKeyValue)}
                    >
                      {copied ? (
                        <Check className="w-4 h-4 text-green-500" />
                      ) : (
                        <Copy className="w-4 h-4" />
                      )}
                    </Button>
                  </div>
                  {copied && (
                    <p className="text-xs text-green-500 flex items-center gap-1">
                      <Check className="w-3 h-3" />
                      Copied to clipboard
                    </p>
                  )}
                </div>
              </div>

              <DialogFooter>
                <Button
                  onClick={() => setNewKeyDialogOpen(false)}
                  className="bg-primary text-primary-foreground hover:bg-primary/90"
                >
                  I&apos;ve Saved My Key
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          {/* API Keys List */}
          {apiKeys.length === 0 ? (
            <div className="p-12 rounded-xl bg-card border border-border text-center">
              <Key className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-foreground mb-2">No API Keys Yet</h3>
              <p className="text-muted-foreground mb-6 max-w-md mx-auto">
                Create your first API key to start integrating with the MarketMate API. You can use it to authenticate requests and access real-time market data.
              </p>
              <Button
                onClick={() => setCreateOpen(true)}
                className="bg-primary text-primary-foreground hover:bg-primary/90"
              >
                <Plus className="w-4 h-4 mr-2" />
                Create API Key
              </Button>
            </div>
          ) : (
            <div className="rounded-xl bg-card border border-border overflow-hidden">
              {/* Table Header */}
              <div className="hidden md:grid md:grid-cols-[1fr_140px_100px_120px_120px_80px] gap-4 px-6 py-3 border-b border-border bg-secondary/50">
                <span className="text-sm font-medium text-muted-foreground">Name</span>
                <span className="text-sm font-medium text-muted-foreground">Key</span>
                <span className="text-sm font-medium text-muted-foreground">Environment</span>
                <span className="text-sm font-medium text-muted-foreground">Last Used</span>
                <span className="text-sm font-medium text-muted-foreground">Created</span>
                <span className="text-sm font-medium text-muted-foreground">Status</span>
              </div>

              {/* Rows */}
              <div className="divide-y divide-border">
                {apiKeys.map((key) => (
                  <div
                    key={key.id}
                    className="grid grid-cols-1 md:grid-cols-[1fr_140px_100px_120px_120px_80px] gap-2 md:gap-4 px-6 py-4 hover:bg-secondary/30 transition-colors items-center"
                  >
                    {/* Name */}
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="p-2 rounded-lg bg-secondary shrink-0">
                        <Key className="w-4 h-4 text-accent" />
                      </div>
                      <span className="font-medium text-foreground truncate">{key.name}</span>
                    </div>

                    {/* Key prefix */}
                    <code className="text-sm text-muted-foreground font-mono truncate">{key.prefix}****</code>

                    {/* Environment */}
                    <div>
                      {key.environment === "live" ? (
                        <Badge className="bg-accent/20 text-accent border-accent/30 hover:bg-accent/30">
                          Live
                        </Badge>
                      ) : (
                        <Badge variant="secondary" className="bg-blue-500/20 text-blue-400 border-blue-500/30 hover:bg-blue-500/30">
                          Test
                        </Badge>
                      )}
                    </div>

                    {/* Last Used */}
                    <span className="text-sm text-muted-foreground">{formatLastUsed(key.lastUsed)}</span>

                    {/* Created */}
                    <span className="text-sm text-muted-foreground">{formatCreatedDate(key.createdAt)}</span>

                    {/* Status + Actions */}
                    <div className="flex items-center gap-3">
                      <span className="flex items-center gap-1.5">
                        <span
                          className={`w-2 h-2 rounded-full ${key.revokedAt ? "bg-red-500" : "bg-green-500"}`}
                        />
                        <span className="text-xs text-muted-foreground hidden sm:inline">
                          {key.revokedAt ? "Revoked" : "Active"}
                        </span>
                      </span>

                      {!key.revokedAt && (
                        <AlertDialog
                          open={revokingKeyId === key.id}
                          onOpenChange={(open) => {
                            if (!open) setRevokingKeyId(null)
                          }}
                        >
                          <AlertDialogTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              className="text-muted-foreground hover:text-red-400 hover:bg-red-500/10"
                              onClick={() => setRevokingKeyId(key.id)}
                            >
                              <ShieldOff className="w-4 h-4" />
                            </Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent className="bg-card border-border">
                            <AlertDialogHeader>
                              <AlertDialogTitle className="text-foreground flex items-center gap-2">
                                <AlertTriangle className="w-5 h-5 text-red-400" />
                                Revoke API Key
                              </AlertDialogTitle>
                              <AlertDialogDescription>
                                Are you sure you want to revoke the API key <span className="text-foreground font-medium">{key.name}</span>? Any integrations using this key will immediately lose access. This action cannot be undone.
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel className="border-border">Cancel</AlertDialogCancel>
                              <AlertDialogAction
                                onClick={() => handleRevoke(key.id)}
                                disabled={isRevoking}
                                className="bg-red-600 text-white hover:bg-red-700 focus:ring-red-600"
                              >
                                {isRevoking ? (
                                  <>
                                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                    Revoking...
                                  </>
                                ) : (
                                  "Revoke Key"
                                )}
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {/* Footer */}
              <div className="px-6 py-3 border-t border-border bg-secondary/30 flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  {apiKeys.filter((k) => !k.revokedAt).length} active key{apiKeys.filter((k) => !k.revokedAt).length !== 1 ? "s" : ""} of 5 allowed
                </p>
                <p className="text-sm text-muted-foreground">
                  {apiKeys.length} total key{apiKeys.length !== 1 ? "s" : ""}
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      <Footer />
    </main>
  )
}
