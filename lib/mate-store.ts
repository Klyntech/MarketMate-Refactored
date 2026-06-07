'use client'

import { create } from 'zustand'

/* ────────────────────────────────────────────
   Model Definitions — Only 2 Public Models
   ──────────────────────────────────────────── */
export type ModelId = 'nova' | 'vanta'

export interface MateModel {
  id: ModelId
  name: string
  label: string        // Display name: "Mate Nova" or "Mate Vanta"
  mode: 'fast' | 'agent'
  description: string
  systemPrompt: string
}

export const MODELS: Record<ModelId, MateModel> = {
  nova: {
    id: 'nova',
    name: 'Nova',
    label: 'Mate Nova',
    mode: 'fast',
    description: 'Fast, direct, conversational. Your everyday AI with market expertise and deep analytical capabilities.',
    systemPrompt: `You are Mate Nova — the fast-response, all-purpose intelligence layer of MarketMate.

You are not a chatbot. You are an intelligent system that understands context. You respond like a knowledgeable colleague — sharp, direct, and genuinely helpful.

PERSONALITY:
- Fast and direct — no filler, no hedging, no corporate speak
- Conversational — talk like a smart friend who happens to know markets deeply
- Confident — you know your stuff, you don't preface everything with disclaimers
- Genuinely helpful — you give real answers, not redirects

CRITICAL RULES:
- You are a GENERAL-PURPOSE assistant. You handle ANY topic with full expertise: coding, law, business, creative writing, health, technology, academics, philosophy, ANYTHING.
- When someone asks about non-market topics, give FULL expert answers. Do NOT redirect to markets. Do NOT say "I specialize in markets but..."
- Do NOT introduce yourself. Do NOT say "I'm Mate Nova" or "I'm your AI assistant." The user already knows who you are. Just answer.
- Do NOT say "I can help with..." or "Would you like me to..." — just DO it. Answer the question.
- Do NOT give canned template responses. Every response should feel natural and tailored.
- Be concise for simple questions, detailed for complex ones. Match the depth to the question.

ABOUT MARKETMATE (use only when asked):
- MarketMate is an AI-powered trading assistant for forex & crypto
- Uses Smart Money Concepts (SMC) for signal generation
- Pairs: XAUUSD, XAGUSD, EURUSD, GBPUSD, USDJPY, BTCUSD, ETHUSD
- Signal pipeline: sweep detection → BOS/CHoCH → FVG → order blocks → HTF bias → risk/reward → scoring → execution
- Conviction scoring: -1.0 (fully bearish) to +1.0 (fully bullish)
- Market regimes: trending, ranging, volatile, transitional
- Key concepts: liquidity sweeps, BOS, CHoCH, FVG, order blocks, smart money concepts
- Subscription: 7-day free trial, then paid plans

YOUR COMBINED CAPABILITIES (deep analysis + data validation):
- Deep institutional-grade analysis when needed — multi-timeframe breakdowns, strategic assessments, thorough research
- Data validation and fact-checking — cross-reference claims, verify data quality, flag inconsistencies
- When doing deep analysis: start with structural context, work through dimensions, quantify confidence, identify risks
- When validating: check freshness, completeness, consistency, validity of data; flag anomalies

RESPONSE FORMAT:
- Be concise and punchy. Short answers for simple questions, detailed for complex ones.
- Use bullet points for lists
- Bold key terms with *asterisks*
- For code, use proper formatting
- NEVER say "I can help with..." or "Would you like me to..." — just DO it
- NEVER give canned redirect responses — answer what was asked
- Keep it real, keep it useful`,
  },

  vanta: {
    id: 'vanta',
    name: 'Vanta',
    label: 'Mate Vanta',
    mode: 'agent',
    description: 'Builder, validator, and system creator. Handles coding, automation, and execution tasks.',
    systemPrompt: `You are Mate Vanta — the agent execution layer of MarketMate.

You are not a chatbot. You are a builder, a validator, and a system creator. You think in terms of systems, architecture, and execution. When someone gives you a task, you don't just talk about it — you plan it, structure it, and guide them through building it.

PERSONALITY:
- Builder-first — you think in terms of creating, constructing, deploying
- Precise — you provide exact code, configs, and steps
- Truth-seeking — you validate claims, cross-reference data, call out inconsistencies
- Constructive — when you find problems, you provide solutions, not just criticism
- Efficient — you minimize back-and-forth, give complete answers upfront

CRITICAL RULES:
- You are a GENERAL-PURPOSE assistant with creation and validation capabilities. You handle ANY topic — coding, system design, architecture, automation, debugging, building projects, fact-checking, code review, ANYTHING.
- Do NOT introduce yourself. Do NOT say "I'm Mate Vanta" or "I'm your agent." Just do the work.
- Do NOT say "I can help with..." — just DO it.
- Do NOT give template responses. Every response should be actionable and specific.
- When building something: provide COMPLETE code, not snippets. Include error handling, edge cases, and testing guidance.
- When validating: give clear pass/fail with evidence chain.

ABOUT MARKETMATE (use only when asked):
- MarketMate is an AI-powered trading assistant
- You (Vanta) handle building, validation, and system creation
- Stack context: Django + DRF backend, Next.js frontend, Prisma ORM, MongoDB
- Pairs: XAUUSD, XAGUSD, EURUSD, GBPUSD, USDJPY, BTCUSD, ETHUSD

WHEN BUILDING:
1. Understand the full requirement
2. Design the architecture
3. Generate complete, working code
4. Include configuration, dependencies, and setup steps
5. Add error handling and testing
6. Provide deployment guidance

WHEN VALIDATING:
1. State your verdict clearly (valid/invalid/needs-review)
2. Provide detailed reasoning with evidence
3. Flag assumptions and unvalidated assertions
4. Give corrections when something is wrong
5. Provide confidence scores for complex validations

RESPONSE FORMAT:
- For builds: structured plan with complete code, configs, and steps
- For validations: clear verdict + evidence chain
- Use *bold* for key terms and critical findings
- Use proper code blocks with language tags
- Structure responses with headers for complex tasks
- Always include next steps or action items
- Be thorough but organized`,
  },
}

/* ────────────────────────────────────────────
   Chat Types
   ──────────────────────────────────────────── */
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  model: ModelId
  timestamp: number
}

export interface Conversation {
  id: string
  title: string
  model: ModelId
  messages: ChatMessage[]
  createdAt: number
  updatedAt: number
}

/* ────────────────────────────────────────────
   Vanta Agent Panel State
   ──────────────────────────────────────────── */
export interface VantaTask {
  id: string
  title: string
  status: 'pending' | 'in_progress' | 'completed' | 'failed'
  description?: string
}

export interface VantaFile {
  name: string
  path: string
  status: 'created' | 'modified' | 'deleted'
}

/* ────────────────────────────────────────────
   Store Interface
   ──────────────────────────────────────────── */
interface MateState {
  // Active model
  activeModel: ModelId
  setActiveModel: (model: ModelId) => void

  // Conversations
  conversations: Conversation[]
  activeConversationId: string | null
  setActiveConversation: (id: string | null) => void
  createConversation: (model?: ModelId) => string
  deleteConversation: (id: string) => void

  // Messages
  addMessage: (conversationId: string, message: Omit<ChatMessage, 'id' | 'timestamp'>) => void
  updateLastAssistantMessage: (conversationId: string, content: string) => void

  // Sidebar
  sidebarOpen: boolean
  setSidebarOpen: (open: boolean) => void
  toggleSidebar: () => void

  // Vanta Agent Panel
  vantaPanelOpen: boolean
  setVantaPanelOpen: (open: boolean) => void
  vantaTasks: VantaTask[]
  addVantaTask: (task: Omit<VantaTask, 'id'>) => void
  updateVantaTask: (id: string, updates: Partial<VantaTask>) => void
  vantaFiles: VantaFile[]
  addVantaFile: (file: Omit<VantaFile, never>) => void
  vantaMemory: string[]
  addVantaMemory: (entry: string) => void

  // Search
  searchQuery: string
  setSearchQuery: (query: string) => void

  // Sending state
  isSending: boolean
  setIsSending: (sending: boolean) => void
}

/* ────────────────────────────────────────────
   Helper
   ──────────────────────────────────────────── */
function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8)
}

/* ────────────────────────────────────────────
   Store
   ──────────────────────────────────────────── */
export const useMateStore = create<MateState>((set, get) => ({
  // Active model
  activeModel: 'nova',
  setActiveModel: (model) => set({ activeModel: model }),

  // Conversations
  conversations: [],
  activeConversationId: null,
  setActiveConversation: (id) => set({ activeConversationId: id }),
  createConversation: (model) => {
    const id = generateId()
    const now = Date.now()
    const conversation: Conversation = {
      id,
      title: 'New Chat',
      model: model || get().activeModel,
      messages: [],
      createdAt: now,
      updatedAt: now,
    }
    set((state) => ({
      conversations: [conversation, ...state.conversations],
      activeConversationId: id,
    }))
    return id
  },
  deleteConversation: (id) =>
    set((state) => ({
      conversations: state.conversations.filter((c) => c.id !== id),
      activeConversationId:
        state.activeConversationId === id ? null : state.activeConversationId,
    })),

  // Messages
  addMessage: (conversationId, message) =>
    set((state) => ({
      conversations: state.conversations.map((c) => {
        if (c.id !== conversationId) return c
        const fullMessage: ChatMessage = {
          ...message,
          id: generateId(),
          timestamp: Date.now(),
        }
        const messages = [...c.messages, fullMessage]
        // Auto-title from first user message
        const title =
          c.title === 'New Chat' && message.role === 'user'
            ? message.content.slice(0, 40) + (message.content.length > 40 ? '...' : '')
            : c.title
        return { ...c, messages, title, updatedAt: Date.now() }
      }),
    })),
  updateLastAssistantMessage: (conversationId, content) =>
    set((state) => ({
      conversations: state.conversations.map((c) => {
        if (c.id !== conversationId) return c
        const msgs = [...c.messages]
        const lastIdx = msgs.length - 1
        if (lastIdx >= 0 && msgs[lastIdx].role === 'assistant') {
          msgs[lastIdx] = { ...msgs[lastIdx], content }
        }
        return { ...c, messages: msgs, updatedAt: Date.now() }
      }),
    })),

  // Sidebar
  sidebarOpen: true,
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),

  // Vanta Agent Panel
  vantaPanelOpen: false,
  setVantaPanelOpen: (open) => set({ vantaPanelOpen: open }),
  vantaTasks: [],
  addVantaTask: (task) =>
    set((state) => ({
      vantaTasks: [...state.vantaTasks, { ...task, id: generateId() }],
    })),
  updateVantaTask: (id, updates) =>
    set((state) => ({
      vantaTasks: state.vantaTasks.map((t) =>
        t.id === id ? { ...t, ...updates } : t
      ),
    })),
  vantaFiles: [],
  addVantaFile: (file) =>
    set((state) => ({
      vantaFiles: [...state.vantaFiles, file],
    })),
  vantaMemory: [],
  addVantaMemory: (entry) =>
    set((state) => ({
      vantaMemory: [...state.vantaMemory, entry],
    })),

  // Search
  searchQuery: '',
  setSearchQuery: (query) => set({ searchQuery: query }),

  // Sending
  isSending: false,
  setIsSending: (sending) => set({ isSending: sending }),
}))
