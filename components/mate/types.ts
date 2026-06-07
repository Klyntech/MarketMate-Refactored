// ─── MATE Model Definitions ──────────────────────────────────────────────────────

export type MateModel = 'nova' | 'atlas' | 'vanta' | 'prism';

export interface ModelInfo {
  id: MateModel;
  name: string;
  layer: string;
  color: string;
  colorClass: string;
  bgClass: string;
  borderClass: string;
  emoji: string;
  role: string;
  description: string;
}

export const MATE_MODELS: Record<MateModel, ModelInfo> = {
  nova: {
    id: 'nova',
    name: 'NOVA',
    layer: 'L1',
    color: '#3B82F6',
    colorClass: 'text-blue-400',
    bgClass: 'bg-blue-500/10',
    borderClass: 'border-blue-500/30',
    emoji: '⚡',
    role: 'Fast Response & Public Interface',
    description: 'Quick, clear, and conversational',
  },
  atlas: {
    id: 'atlas',
    name: 'ATLAS',
    layer: 'L3',
    color: '#8B5CF6',
    colorClass: 'text-purple-400',
    bgClass: 'bg-purple-500/10',
    borderClass: 'border-purple-500/30',
    emoji: '🗺',
    role: 'Deep Market Analysis',
    description: 'Institutional-grade, thorough analysis',
  },
  vanta: {
    id: 'vanta',
    name: 'VANTA',
    layer: 'L4',
    color: '#EF4444',
    colorClass: 'text-red-400',
    bgClass: 'bg-red-500/10',
    borderClass: 'border-red-500/30',
    emoji: '🛡',
    role: 'Truth Validator & System Builder',
    description: 'Validates correctness, calls out inconsistencies',
  },
  prism: {
    id: 'prism',
    name: 'PRISM',
    layer: 'L5',
    color: '#06B6D4',
    colorClass: 'text-cyan-400',
    bgClass: 'bg-cyan-500/10',
    borderClass: 'border-cyan-500/30',
    emoji: '🔍',
    role: 'Data Quality & Validation',
    description: 'Quality gate — nothing passes without validation',
  },
};

export const MODEL_LIST: MateModel[] = ['nova', 'atlas', 'vanta', 'prism'];

// ─── Chat Types ──────────────────────────────────────────────────────────────────

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  model?: MateModel;
  timestamp: Date;
}

export interface Chat {
  id: string;
  title: string;
  model: MateModel;
  messages: Message[];
  createdAt: Date;
  updatedAt: Date;
}

// ─── Suggestion Cards ────────────────────────────────────────────────────────────

export interface SuggestionCard {
  icon: string;
  label: string;
  prompt: string;
  colorClass: string;
  bgClass: string;
  borderClass: string;
}

export const SUGGESTION_CARDS: SuggestionCard[] = [
  {
    icon: '📈',
    label: 'Market State',
    prompt: 'What is the current market state and regime across all pairs?',
    colorClass: 'text-emerald-400',
    bgClass: 'bg-emerald-500/10',
    borderClass: 'border-emerald-500/20',
  },
  {
    icon: '🛡',
    label: 'Conviction Analysis',
    prompt: 'Explain how the 5-brain conviction scoring works',
    colorClass: 'text-blue-400',
    bgClass: 'bg-blue-500/10',
    borderClass: 'border-blue-500/20',
  },
  {
    icon: '🔍',
    label: 'Sweep Detection',
    prompt: 'How does MATE detect liquidity sweeps?',
    colorClass: 'text-rose-400',
    bgClass: 'bg-rose-500/10',
    borderClass: 'border-rose-500/20',
  },
  {
    icon: '⚡',
    label: 'Gate Pipeline',
    prompt: 'Walk me through the G1-G8 validation gates',
    colorClass: 'text-amber-400',
    bgClass: 'bg-amber-500/10',
    borderClass: 'border-amber-500/20',
  },
];
