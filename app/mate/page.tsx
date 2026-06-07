'use client'

import { useEffect, useState, useRef, useCallback, useMemo } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import ReactMarkdown from 'react-markdown'
import {
  Plus,
  Send,
  Loader2,
  ChevronDown,
  PanelRightOpen,
  PanelRightClose,
  Search,
  X,
  MessageSquare,
  Trash2,
  Zap,
  Shield,
  FileCode2,
  Brain,
  Menu,
  FolderOpen,
  ClipboardList,
  Database,
  Play,
  CheckCircle2,
  AlertCircle,
  Clock,
  Sparkles,
} from 'lucide-react'
import {
  useMateStore,
  MODELS,
  type ModelId,
  type ChatMessage,
  type Conversation,
} from '@/lib/mate-store'

/* ────────────────────────────────────────────
   Constants
   ──────────────────────────────────────────── */
const MATE_COLORS = {
  bg: '#09090b',
  panel: '#111317',
  border: '#1f242b',
  text: '#ffffff',
  secondary: '#9ca3af',
  accent: '#22d3ee',
  accentDim: 'rgba(34,211,238,0.12)',
  surface: '#0d0f12',
  surfaceHover: '#161a20',
  userBubble: 'rgba(34,211,238,0.08)',
  userBorder: 'rgba(34,211,238,0.15)',
}

/* ────────────────────────────────────────────
   Welcome Screen — Empty Chat State
   ──────────────────────────────────────────── */
function WelcomeScreen({ onPromptClick }: { onPromptClick: (prompt: string) => void }) {
  const { activeModel } = useMateStore()
  const model = MODELS[activeModel]

  const novaPrompts = [
    { icon: Zap, label: 'Market Analysis', prompt: 'Give me a breakdown of the current XAUUSD market structure' },
    { icon: Shield, label: 'Risk Assessment', prompt: 'What are the key risk factors in the forex market right now?' },
    { icon: Brain, label: 'SMC Concepts', prompt: 'Explain how Smart Money Concepts apply to liquidity sweeps' },
    { icon: MessageSquare, label: 'General Question', prompt: 'What are the differences between trending and ranging market regimes?' },
  ]

  const vantaPrompts = [
    { icon: FileCode2, label: 'Build a Script', prompt: 'Build me a Python script that calculates RSI and MACD for forex pairs using the ccxt library' },
    { icon: ClipboardList, label: 'System Design', prompt: 'Design a real-time signal notification system with WebSocket support' },
    { icon: Database, label: 'API Integration', prompt: 'Create a Django REST API endpoint for managing trading signals with proper authentication' },
    { icon: Play, label: 'Automation', prompt: 'Write an automated trading bot that places orders based on SMC signals' },
  ]

  const prompts = activeModel === 'vanta' ? vantaPrompts : novaPrompts

  return (
    <div className="flex flex-col items-center justify-center flex-1 px-4 py-12">
      {/* Logo */}
      <div className="flex items-center justify-center w-16 h-16 rounded-2xl mb-6"
        style={{ background: MATE_COLORS.accentDim, border: `1px solid ${MATE_COLORS.accent}30` }}>
        <Sparkles className="w-8 h-8" style={{ color: MATE_COLORS.accent }} />
      </div>

      <h2 className="text-2xl font-bold mb-1" style={{ color: MATE_COLORS.text }}>
        {model.label}
      </h2>
      <p className="text-sm mb-1" style={{ color: MATE_COLORS.secondary }}>
        {model.mode === 'fast' ? 'Fast Response & Market Intelligence' : 'Agent Execution & Building'}
      </p>
      <p className="text-xs mb-8 text-center max-w-md" style={{ color: `${MATE_COLORS.secondary}99` }}>
        {model.description}
      </p>

      {/* Suggested prompts */}
      <div className="w-full max-w-lg">
        <p className="text-[10px] uppercase tracking-widest mb-3 text-center" style={{ color: `${MATE_COLORS.secondary}80` }}>
          Try asking
        </p>
        <div className="grid grid-cols-2 gap-2">
          {prompts.map((p) => {
            const Icon = p.icon
            return (
              <button
                key={p.label}
                onClick={() => onPromptClick(p.prompt)}
                className="flex items-center gap-2.5 rounded-xl px-3.5 py-3 text-left transition-all cursor-pointer hover:scale-[1.02]"
                style={{
                  background: MATE_COLORS.surface,
                  border: `1px solid ${MATE_COLORS.border}`,
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = `${MATE_COLORS.accent}40`
                  e.currentTarget.style.background = MATE_COLORS.surfaceHover
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = MATE_COLORS.border
                  e.currentTarget.style.background = MATE_COLORS.surface
                }}
              >
                <Icon className="w-4 h-4 shrink-0" style={{ color: MATE_COLORS.accent }} />
                <div>
                  <span className="text-xs font-medium block" style={{ color: MATE_COLORS.text }}>
                    {p.label}
                  </span>
                  <span className="text-[10px] line-clamp-1" style={{ color: MATE_COLORS.secondary }}>
                    {p.prompt}
                  </span>
                </div>
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}

/* ────────────────────────────────────────────
   Model Selector Dropdown
   ──────────────────────────────────────────── */
function ModelSelector() {
  const { activeModel, setActiveModel } = useMateStore()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const current = MODELS[activeModel]

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors cursor-pointer"
        style={{
          background: MATE_COLORS.surface,
          border: `1px solid ${MATE_COLORS.border}`,
          color: MATE_COLORS.text,
        }}
      >
        <Sparkles className="w-3.5 h-3.5" style={{ color: MATE_COLORS.accent }} />
        {current.label}
        <ChevronDown className="w-3.5 h-3.5 transition-transform" style={{
          transform: open ? 'rotate(180deg)' : 'rotate(0)',
          color: MATE_COLORS.secondary,
        }} />
      </button>

      {open && (
        <div
          className="absolute top-full left-0 mt-1 w-64 rounded-xl overflow-hidden z-50 shadow-2xl"
          style={{
            background: MATE_COLORS.panel,
            border: `1px solid ${MATE_COLORS.border}`,
          }}
        >
          {(Object.keys(MODELS) as ModelId[]).map((id) => {
            const m = MODELS[id]
            const isActive = id === activeModel
            return (
              <button
                key={id}
                onClick={() => { setActiveModel(id); setOpen(false) }}
                className="w-full flex items-start gap-3 px-4 py-3 text-left transition-colors cursor-pointer"
                style={{
                  background: isActive ? MATE_COLORS.surfaceHover : 'transparent',
                }}
                onMouseEnter={(e) => {
                  if (!isActive) e.currentTarget.style.background = MATE_COLORS.surfaceHover
                }}
                onMouseLeave={(e) => {
                  if (!isActive) e.currentTarget.style.background = 'transparent'
                }}
              >
                <Sparkles className="w-4 h-4 mt-0.5 shrink-0" style={{ color: MATE_COLORS.accent }} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium" style={{ color: MATE_COLORS.text }}>{m.label}</span>
                    <span className="text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded-full"
                      style={{ background: MATE_COLORS.accentDim, color: MATE_COLORS.accent }}>
                      {m.mode}
                    </span>
                  </div>
                  <p className="text-[11px] mt-0.5 line-clamp-2" style={{ color: MATE_COLORS.secondary }}>
                    {m.description}
                  </p>
                </div>
                {isActive && <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" style={{ color: MATE_COLORS.accent }} />}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

/* ────────────────────────────────────────────
   Message Bubble
   ──────────────────────────────────────────── */
function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const time = new Date(message.timestamp).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  })

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} group`}>
      <div className={`flex max-w-[85%] sm:max-w-[75%] ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
        {!isUser && (
          <div
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg mt-1"
            style={{ background: MATE_COLORS.accentDim, border: `1px solid ${MATE_COLORS.accent}25` }}
          >
            <Sparkles className="w-3.5 h-3.5" style={{ color: MATE_COLORS.accent }} />
          </div>
        )}
        <div
          className="relative rounded-2xl px-4 py-3 ml-2 mr-2"
          style={{
            background: isUser ? MATE_COLORS.userBubble : MATE_COLORS.surface,
            border: `1px solid ${isUser ? MATE_COLORS.userBorder : MATE_COLORS.border}`,
          }}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap text-sm leading-relaxed" style={{ color: MATE_COLORS.text }}>
              {message.content}
            </p>
          ) : (
            <div className="prose prose-invert prose-sm max-w-none mate-markdown">
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </div>
          )}
          <div className={`flex items-center gap-2 mt-2 ${isUser ? 'justify-end' : 'justify-between'}`}>
            <span className="text-[10px]" style={{ color: `${MATE_COLORS.secondary}60` }}>{time}</span>
            {!isUser && (
              <button
                onClick={handleCopy}
                className="flex items-center gap-1 text-[10px] opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
                style={{ color: MATE_COLORS.secondary }}
              >
                {copied ? (
                  <><CheckCircle2 className="w-3 h-3" style={{ color: MATE_COLORS.accent }} />
                  <span style={{ color: MATE_COLORS.accent }}>Copied</span></>
                ) : (
                  <><ClipboardList className="w-3 h-3" /> Copy</>
                )}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

/* ────────────────────────────────────────────
   Typing Indicator
   ──────────────────────────────────────────── */
function TypingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="flex items-start gap-2">
        <div
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg mt-1"
          style={{ background: MATE_COLORS.accentDim, border: `1px solid ${MATE_COLORS.accent}25` }}
        >
          <Sparkles className="w-3.5 h-3.5" style={{ color: MATE_COLORS.accent }} />
        </div>
        <div
          className="rounded-2xl px-4 py-3"
          style={{ background: MATE_COLORS.surface, border: `1px solid ${MATE_COLORS.border}` }}
        >
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1">
              {[0, 1, 2].map((i) => (
                <span
                  key={i}
                  className="inline-block w-1.5 h-1.5 rounded-full animate-bounce"
                  style={{
                    backgroundColor: MATE_COLORS.accent,
                    animationDelay: `${i * 0.15}s`,
                    animationDuration: '1s',
                  }}
                />
              ))}
            </div>
            <span className="text-[10px]" style={{ color: `${MATE_COLORS.secondary}80` }}>
              Thinking...
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

/* ────────────────────────────────────────────
   Sidebar — Conversation History
   ──────────────────────────────────────────── */
function Sidebar() {
  const {
    conversations,
    activeConversationId,
    setActiveConversation,
    createConversation,
    deleteConversation,
    activeModel,
    setActiveModel,
    searchQuery,
    setSearchQuery,
    sidebarOpen,
  } = useMateStore()

  const filtered = useMemo(() => {
    if (!searchQuery.trim()) return conversations
    const q = searchQuery.toLowerCase()
    return conversations.filter(
      (c) =>
        c.title.toLowerCase().includes(q) ||
        c.messages.some((m) => m.content.toLowerCase().includes(q))
    )
  }, [conversations, searchQuery])

  // Group by date
  const grouped = useMemo(() => {
    const now = Date.now()
    const day = 86400000
    const today: Conversation[] = []
    const yesterday: Conversation[] = []
    const older: Conversation[] = []

    filtered.forEach((c) => {
      const age = now - c.updatedAt
      if (age < day) today.push(c)
      else if (age < 2 * day) yesterday.push(c)
      else older.push(c)
    })

    return { today, yesterday, older }
  }, [filtered])

  const handleNewChat = () => {
    createConversation(activeModel)
  }

  if (!sidebarOpen) return null

  return (
    <div
      className="flex flex-col h-full w-[280px] shrink-0"
      style={{ background: MATE_COLORS.panel, borderRight: `1px solid ${MATE_COLORS.border}` }}
    >
      {/* New Chat Button */}
      <div className="p-3">
        <button
          onClick={handleNewChat}
          className="flex items-center gap-2 w-full rounded-lg px-3 py-2.5 text-sm font-medium transition-colors cursor-pointer"
          style={{
            background: MATE_COLORS.accentDim,
            border: `1px solid ${MATE_COLORS.accent}30`,
            color: MATE_COLORS.accent,
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = `${MATE_COLORS.accent}25`
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = MATE_COLORS.accentDim
          }}
        >
          <Plus className="w-4 h-4" />
          New Chat
        </button>
      </div>

      {/* Search */}
      <div className="px-3 pb-2">
        <div
          className="flex items-center gap-2 rounded-lg px-3 py-2"
          style={{ background: MATE_COLORS.surface, border: `1px solid ${MATE_COLORS.border}` }}
        >
          <Search className="w-3.5 h-3.5" style={{ color: MATE_COLORS.secondary }} />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search conversations..."
            className="flex-1 bg-transparent text-xs outline-none placeholder:text-zinc-600"
            style={{ color: MATE_COLORS.text }}
          />
          {searchQuery && (
            <button onClick={() => setSearchQuery('')} className="cursor-pointer">
              <X className="w-3 h-3" style={{ color: MATE_COLORS.secondary }} />
            </button>
          )}
        </div>
      </div>

      {/* Conversation List */}
      <div className="flex-1 overflow-y-auto px-2 py-1 space-y-1">
        {grouped.today.length > 0 && (
          <ConversationGroup label="Today" conversations={grouped.today} activeId={activeConversationId} onSelect={setActiveConversation} onDelete={deleteConversation} />
        )}
        {grouped.yesterday.length > 0 && (
          <ConversationGroup label="Yesterday" conversations={grouped.yesterday} activeId={activeConversationId} onSelect={setActiveConversation} onDelete={deleteConversation} />
        )}
        {grouped.older.length > 0 && (
          <ConversationGroup label="Earlier" conversations={grouped.older} activeId={activeConversationId} onSelect={setActiveConversation} onDelete={deleteConversation} />
        )}
        {conversations.length === 0 && (
          <div className="flex flex-col items-center justify-center py-12 px-4">
            <MessageSquare className="w-8 h-8 mb-2" style={{ color: `${MATE_COLORS.secondary}40` }} />
            <p className="text-xs text-center" style={{ color: `${MATE_COLORS.secondary}60` }}>
              No conversations yet. Start a new chat!
            </p>
          </div>
        )}
      </div>

      {/* Model Quick Switch */}
      <div className="p-3" style={{ borderTop: `1px solid ${MATE_COLORS.border}` }}>
        <div className="flex gap-1">
          {(Object.keys(MODELS) as ModelId[]).map((id) => {
            const m = MODELS[id]
            const isActive = id === activeModel
            return (
              <button
                key={id}
                onClick={() => setActiveModel(id)}
                className="flex-1 flex items-center justify-center gap-1.5 rounded-lg py-2 text-[11px] font-medium transition-colors cursor-pointer"
                style={{
                  background: isActive ? MATE_COLORS.accentDim : 'transparent',
                  border: `1px solid ${isActive ? `${MATE_COLORS.accent}40` : MATE_COLORS.border}`,
                  color: isActive ? MATE_COLORS.accent : MATE_COLORS.secondary,
                }}
              >
                {m.mode === 'fast' ? <Zap className="w-3 h-3" /> : <Shield className="w-3 h-3" />}
                {m.name}
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function ConversationGroup({
  label,
  conversations,
  activeId,
  onSelect,
  onDelete,
}: {
  label: string
  conversations: Conversation[]
  activeId: string | null
  onSelect: (id: string) => void
  onDelete: (id: string) => void
}) {
  return (
    <div className="mb-2">
      <p className="px-2 py-1 text-[10px] uppercase tracking-wider font-medium" style={{ color: `${MATE_COLORS.secondary}70` }}>
        {label}
      </p>
      {conversations.map((c) => (
        <div
          key={c.id}
          className="group flex items-center gap-2 rounded-lg px-2 py-2 cursor-pointer transition-colors"
          style={{
            background: c.id === activeId ? MATE_COLORS.surfaceHover : 'transparent',
          }}
          onClick={() => onSelect(c.id)}
          onMouseEnter={(e) => {
            if (c.id !== activeId) e.currentTarget.style.background = MATE_COLORS.surface
          }}
          onMouseLeave={(e) => {
            if (c.id !== activeId) e.currentTarget.style.background = 'transparent'
          }}
        >
          <MessageSquare className="w-3.5 h-3.5 shrink-0" style={{ color: MATE_COLORS.secondary }} />
          <span className="flex-1 text-xs truncate" style={{ color: c.id === activeId ? MATE_COLORS.text : MATE_COLORS.secondary }}>
            {c.title}
          </span>
          <button
            onClick={(e) => { e.stopPropagation(); onDelete(c.id) }}
            className="opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
          >
            <Trash2 className="w-3 h-3" style={{ color: MATE_COLORS.secondary }} />
          </button>
        </div>
      ))}
    </div>
  )
}

/* ────────────────────────────────────────────
   Vanta Agent Panel
   ──────────────────────────────────────────── */
function VantaPanel() {
  const { vantaPanelOpen, setVantaPanelOpen, vantaTasks, vantaFiles, vantaMemory } = useMateStore()
  const [activeTab, setActiveTab] = useState<'tasks' | 'files' | 'memory'>('tasks')

  if (!vantaPanelOpen) return null

  const tabs = [
    { id: 'tasks' as const, label: 'Tasks', icon: ClipboardList, count: vantaTasks.length },
    { id: 'files' as const, label: 'Files', icon: FolderOpen, count: vantaFiles.length },
    { id: 'memory' as const, label: 'Memory', icon: Database, count: vantaMemory.length },
  ]

  return (
    <div
      className="flex flex-col h-full w-[300px] shrink-0"
      style={{ background: MATE_COLORS.panel, borderLeft: `1px solid ${MATE_COLORS.border}` }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: `1px solid ${MATE_COLORS.border}` }}>
        <div className="flex items-center gap-2">
          <Shield className="w-4 h-4" style={{ color: MATE_COLORS.accent }} />
          <span className="text-sm font-medium" style={{ color: MATE_COLORS.text }}>Agent Panel</span>
        </div>
        <button onClick={() => setVantaPanelOpen(false)} className="cursor-pointer">
          <PanelRightClose className="w-4 h-4" style={{ color: MATE_COLORS.secondary }} />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex px-3 pt-2" style={{ borderBottom: `1px solid ${MATE_COLORS.border}` }}>
        {tabs.map((tab) => {
          const Icon = tab.icon
          const isActive = tab.id === activeTab
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium transition-colors cursor-pointer"
              style={{
                color: isActive ? MATE_COLORS.accent : MATE_COLORS.secondary,
                borderBottom: isActive ? `2px solid ${MATE_COLORS.accent}` : '2px solid transparent',
              }}
            >
              <Icon className="w-3.5 h-3.5" />
              {tab.label}
              {tab.count > 0 && (
                <span className="px-1.5 py-0.5 rounded-full text-[9px]"
                  style={{ background: MATE_COLORS.accentDim, color: MATE_COLORS.accent }}>
                  {tab.count}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-3">
        {activeTab === 'tasks' && (
          <div className="space-y-2">
            {vantaTasks.length === 0 ? (
              <EmptyPanel message="No tasks yet. Ask Vanta to build something!" />
            ) : (
              vantaTasks.map((task) => (
                <div key={task.id}
                  className="flex items-start gap-2 rounded-lg p-3"
                  style={{ background: MATE_COLORS.surface, border: `1px solid ${MATE_COLORS.border}` }}>
                  {task.status === 'completed' ? <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" style={{ color: MATE_COLORS.accent }} /> :
                   task.status === 'in_progress' ? <Clock className="w-4 h-4 mt-0.5 shrink-0 animate-spin" style={{ color: MATE_COLORS.accent }} /> :
                   task.status === 'failed' ? <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" style={{ color: '#ef4444' }} /> :
                   <Clock className="w-4 h-4 mt-0.5 shrink-0" style={{ color: MATE_COLORS.secondary }} />}
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium" style={{ color: MATE_COLORS.text }}>{task.title}</p>
                    {task.description && (
                      <p className="text-[10px] mt-0.5" style={{ color: MATE_COLORS.secondary }}>{task.description}</p>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        )}
        {activeTab === 'files' && (
          <div className="space-y-1">
            {vantaFiles.length === 0 ? (
              <EmptyPanel message="No files yet. Vanta will track files it creates." />
            ) : (
              vantaFiles.map((file, i) => (
                <div key={i}
                  className="flex items-center gap-2 rounded-lg px-3 py-2"
                  style={{ background: MATE_COLORS.surface, border: `1px solid ${MATE_COLORS.border}` }}>
                  <FileCode2 className="w-3.5 h-3.5 shrink-0" style={{ color: MATE_COLORS.accent }} />
                  <span className="text-xs truncate" style={{ color: MATE_COLORS.text }}>{file.name}</span>
                  <span className="text-[9px] ml-auto px-1.5 py-0.5 rounded-full"
                    style={{ background: MATE_COLORS.accentDim, color: MATE_COLORS.accent }}>
                    {file.status}
                  </span>
                </div>
              ))
            )}
          </div>
        )}
        {activeTab === 'memory' && (
          <div className="space-y-1">
            {vantaMemory.length === 0 ? (
              <EmptyPanel message="No memory entries yet. Vanta will store key context here." />
            ) : (
              vantaMemory.map((entry, i) => (
                <div key={i}
                  className="rounded-lg px-3 py-2"
                  style={{ background: MATE_COLORS.surface, border: `1px solid ${MATE_COLORS.border}` }}>
                  <p className="text-xs" style={{ color: MATE_COLORS.secondary }}>{entry}</p>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function EmptyPanel({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-8 px-4">
      <p className="text-[11px] text-center" style={{ color: `${MATE_COLORS.secondary}60` }}>{message}</p>
    </div>
  )
}

/* ────────────────────────────────────────────
   Mobile Drawer
   ──────────────────────────────────────────── */
function MobileDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { conversations, activeConversationId, setActiveConversation, createConversation, activeModel } = useMateStore()

  if (!open) return null

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 z-40 bg-black/60" onClick={onClose} />

      {/* Drawer */}
      <div
        className="fixed left-0 top-0 bottom-0 z-50 w-[280px] flex flex-col"
        style={{ background: MATE_COLORS.panel, animation: 'slideInLeft 0.2s ease-out' }}
      >
        <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: `1px solid ${MATE_COLORS.border}` }}>
          <span className="text-sm font-medium" style={{ color: MATE_COLORS.text }}>History</span>
          <button onClick={onClose} className="cursor-pointer">
            <X className="w-5 h-5" style={{ color: MATE_COLORS.secondary }} />
          </button>
        </div>

        <div className="p-3">
          <button
            onClick={() => { createConversation(activeModel); onClose() }}
            className="flex items-center gap-2 w-full rounded-lg px-3 py-2.5 text-sm font-medium cursor-pointer"
            style={{ background: MATE_COLORS.accentDim, border: `1px solid ${MATE_COLORS.accent}30`, color: MATE_COLORS.accent }}
          >
            <Plus className="w-4 h-4" />
            New Chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-2 py-1">
          {conversations.length === 0 ? (
            <div className="flex flex-col items-center py-12 px-4">
              <MessageSquare className="w-8 h-8 mb-2" style={{ color: `${MATE_COLORS.secondary}40` }} />
              <p className="text-xs" style={{ color: `${MATE_COLORS.secondary}60` }}>No conversations yet</p>
            </div>
          ) : (
            conversations.map((c) => (
              <div
                key={c.id}
                className="flex items-center gap-2 rounded-lg px-2 py-2.5 cursor-pointer mb-1"
                style={{ background: c.id === activeConversationId ? MATE_COLORS.surfaceHover : 'transparent' }}
                onClick={() => { setActiveConversation(c.id); onClose() }}
              >
                <MessageSquare className="w-3.5 h-3.5 shrink-0" style={{ color: MATE_COLORS.secondary }} />
                <span className="text-xs truncate" style={{ color: c.id === activeConversationId ? MATE_COLORS.text : MATE_COLORS.secondary }}>
                  {c.title}
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </>
  )
}

/* ────────────────────────────────────────────
   Main MATE Page
   ──────────────────────────────────────────── */
export default function MatePage() {
  const {
    activeModel,
    activeConversationId,
    conversations,
    createConversation,
    addMessage,
    updateLastAssistantMessage,
    sidebarOpen,
    toggleSidebar,
    setSidebarOpen,
    vantaPanelOpen,
    setVantaPanelOpen,
    isSending,
    setIsSending,
  } = useMateStore()

  const [input, setInput] = useState('')
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Get active conversation
  const activeConversation = useMemo(
    () => conversations.find((c) => c.id === activeConversationId) || null,
    [conversations, activeConversationId]
  )

  const messages = activeConversation?.messages || []
  const hasMessages = messages.length > 0

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isSending])

  // Close sidebar on mobile by default
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 768) {
        setSidebarOpen(false)
      }
    }
    handleResize()
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [setSidebarOpen])

  // Send message
  const handleSend = useCallback(async (messageText?: string) => {
    const trimmed = (messageText || input).trim()
    if (!trimmed || isSending) return

    let convId = activeConversationId
    if (!convId) {
      convId = createConversation(activeModel)
    }

    // Add user message
    addMessage(convId, { role: 'user', content: trimmed, model: activeModel })
    setInput('')
    setIsSending(true)

    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }

    try {
      // Get conversation history for context
      const conv = useMateStore.getState().conversations.find((c) => c.id === convId)
      const history = conv
        ? conv.messages.slice(-10).map((m) => ({ role: m.role, content: m.content }))
        : []

      const res = await fetch('/api/mate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: trimmed,
          model: activeModel,
          history,
        }),
      })

      const data = await res.json()

      addMessage(convId, {
        role: 'assistant',
        content: data.response || data.error || 'Something went wrong. Please try again.',
        model: activeModel,
      })
    } catch {
      addMessage(convId, {
        role: 'assistant',
        content: 'Network error. Please check your connection and try again.',
        model: activeModel,
      })
    } finally {
      setIsSending(false)
    }
  }, [input, isSending, activeConversationId, activeModel, createConversation, addMessage, setIsSending])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value)
    const el = e.target
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 150)}px`
  }

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: MATE_COLORS.bg, fontFamily: "'Inter', 'Geist', sans-serif" }}>
      {/* Desktop Sidebar */}
      <div className="hidden md:block">
        <Sidebar />
      </div>

      {/* Mobile Drawer */}
      <MobileDrawer open={mobileDrawerOpen} onClose={() => setMobileDrawerOpen(false)} />

      {/* Main Area */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Top Bar */}
        <div
          className="flex items-center justify-between px-4 py-2.5 shrink-0"
          style={{ borderBottom: `1px solid ${MATE_COLORS.border}`, background: MATE_COLORS.bg }}
        >
          <div className="flex items-center gap-3">
            {/* Mobile menu button */}
            <button
              className="md:hidden cursor-pointer"
              onClick={() => setMobileDrawerOpen(true)}
            >
              <Menu className="w-5 h-5" style={{ color: MATE_COLORS.secondary }} />
            </button>

            {/* Sidebar toggle (desktop) */}
            <button className="hidden md:block cursor-pointer" onClick={toggleSidebar}>
              <PanelRightOpen className="w-4 h-4" style={{ color: MATE_COLORS.secondary }} />
            </button>

            {/* Logo / Back link */}
            <Link href="/" className="flex items-center gap-2 group">
              <Image src="/logo.svg" alt="MarketMate" width={22} height={18} className="h-[18px] w-auto" />
              <span className="text-sm font-bold hidden sm:inline" style={{ color: MATE_COLORS.text }}>
                MarketMate
              </span>
            </Link>

            {/* Model Selector */}
            <ModelSelector />
          </div>

          <div className="flex items-center gap-2">
            {/* Vanta Agent Panel toggle — only when Vanta is active */}
            {activeModel === 'vanta' && (
              <button
                onClick={() => setVantaPanelOpen(!vantaPanelOpen)}
                className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium cursor-pointer transition-colors"
                style={{
                  background: vantaPanelOpen ? MATE_COLORS.accentDim : 'transparent',
                  border: `1px solid ${vantaPanelOpen ? `${MATE_COLORS.accent}40` : MATE_COLORS.border}`,
                  color: vantaPanelOpen ? MATE_COLORS.accent : MATE_COLORS.secondary,
                }}
              >
                <Shield className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Agent</span>
              </button>
            )}

            {/* Status dot */}
            <div className="flex items-center gap-1.5">
              <span className="relative flex h-2 w-2">
                <span
                  className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75"
                  style={{ backgroundColor: MATE_COLORS.accent }}
                />
                <span
                  className="relative inline-flex rounded-full h-2 w-2"
                  style={{ backgroundColor: MATE_COLORS.accent }}
                />
              </span>
              <span className="text-[10px] hidden sm:inline" style={{ color: MATE_COLORS.secondary }}>
                Online
              </span>
            </div>
          </div>
        </div>

        {/* Chat Area */}
        <div className="flex-1 overflow-y-auto">
          {!hasMessages ? (
            <WelcomeScreen onPromptClick={(prompt) => handleSend(prompt)} />
          ) : (
            <div className="p-4 sm:p-6 max-w-4xl mx-auto space-y-4">
              {messages.map((msg) => (
                <MessageBubble key={msg.id} message={msg} />
              ))}
              {isSending && <TypingIndicator />}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input Bar */}
        <div
          className="shrink-0 p-3 sm:px-6"
          style={{ background: MATE_COLORS.bg, borderTop: `1px solid ${MATE_COLORS.border}` }}
        >
          <div className="max-w-4xl mx-auto">
            <div
              className="flex items-end gap-2 rounded-xl px-3 py-2 transition-all"
              style={{
                background: MATE_COLORS.surface,
                border: `1px solid ${MATE_COLORS.border}`,
              }}
              onFocus={(e) => {
                e.currentTarget.style.borderColor = `${MATE_COLORS.accent}40`
              }}
              onBlur={(e) => {
                e.currentTarget.style.borderColor = MATE_COLORS.border
              }}
            >
              <textarea
                ref={textareaRef}
                value={input}
                onChange={handleTextareaChange}
                onKeyDown={handleKeyDown}
                placeholder={activeModel === 'vanta' ? 'Ask Vanta to build, validate, or automate...' : 'Ask Nova anything...'}
                disabled={isSending}
                rows={1}
                className="flex-1 resize-none bg-transparent text-sm outline-none min-h-[36px] max-h-[150px] py-1.5 placeholder:text-zinc-600"
                style={{ color: MATE_COLORS.text }}
              />
              <button
                onClick={() => handleSend()}
                disabled={isSending || !input.trim()}
                className="flex items-center justify-center w-8 h-8 rounded-lg shrink-0 transition-colors cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
                style={{
                  background: input.trim() ? MATE_COLORS.accent : MATE_COLORS.surface,
                  color: input.trim() ? MATE_COLORS.bg : MATE_COLORS.secondary,
                }}
              >
                {isSending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
              </button>
            </div>
            <p className="mt-1.5 text-center text-[10px]" style={{ color: `${MATE_COLORS.secondary}50` }}>
              MATE provides intelligence interpretations. Not financial advice.
            </p>
          </div>
        </div>
      </div>

      {/* Vanta Agent Panel (desktop) */}
      {activeModel === 'vanta' && (
        <div className="hidden md:block">
          <VantaPanel />
        </div>
      )}

      {/* Slide-in animation style */}
      <style jsx global>{`
        @keyframes slideInLeft {
          from { transform: translateX(-100%); }
          to { transform: translateX(0); }
        }
        .mate-markdown p { margin-bottom: 0.5rem; }
        .mate-markdown p:last-child { margin-bottom: 0; }
        .mate-markdown ul, .mate-markdown ol { padding-left: 1.25rem; margin-bottom: 0.5rem; }
        .mate-markdown li { margin-bottom: 0.25rem; }
        .mate-markdown code {
          background: rgba(34,211,238,0.1);
          padding: 0.125rem 0.375rem;
          border-radius: 0.25rem;
          font-size: 0.75rem;
          color: #22d3ee;
        }
        .mate-markdown pre {
          background: #0d0f12;
          border: 1px solid #1f242b;
          border-radius: 0.5rem;
          padding: 0.75rem 1rem;
          overflow-x: auto;
          margin-bottom: 0.5rem;
        }
        .mate-markdown pre code {
          background: transparent;
          padding: 0;
          color: #9ca3af;
        }
        .mate-markdown strong { color: #ffffff; font-weight: 600; }
        .mate-markdown h1, .mate-markdown h2, .mate-markdown h3 {
          color: #ffffff;
          font-weight: 600;
          margin-top: 0.75rem;
          margin-bottom: 0.5rem;
        }
        .mate-markdown h1 { font-size: 1.125rem; }
        .mate-markdown h2 { font-size: 1rem; }
        .mate-markdown h3 { font-size: 0.875rem; }
        .mate-markdown blockquote {
          border-left: 2px solid #22d3ee;
          padding-left: 0.75rem;
          color: #9ca3af;
          margin-bottom: 0.5rem;
        }
        .mate-markdown a { color: #22d3ee; text-decoration: underline; }
        .mate-markdown hr { border-color: #1f242b; margin: 0.75rem 0; }
      `}</style>
    </div>
  )
}
