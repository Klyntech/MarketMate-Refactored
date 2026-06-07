'use client';

import { cn } from '@/lib/utils';
import { Sparkles } from 'lucide-react';
import type { MateModel, SuggestionCard } from './types';
import { MATE_MODELS, SUGGESTION_CARDS, MODEL_LIST } from './types';

interface WelcomeScreenProps {
  model: MateModel;
  onPromptClick: (prompt: string) => void;
}

export function WelcomeScreen({ model, onPromptClick }: WelcomeScreenProps) {
  const modelInfo = MATE_MODELS[model];

  return (
    <div className="flex flex-1 flex-col items-center justify-center px-4 py-12 animate-in fade-in-0 duration-500">
      {/* MATE Logo */}
      <div
        className={cn(
          'flex h-20 w-20 items-center justify-center rounded-2xl border mb-6 transition-colors duration-300',
          modelInfo.bgClass,
          modelInfo.borderClass
        )}
      >
        <Sparkles className={cn('h-10 w-10', modelInfo.colorClass)} />
      </div>

      <h2 className="text-3xl font-bold text-foreground mb-2">MATE</h2>
      <p className="text-sm text-muted-foreground mb-1">
        Market Reasoning Engine
      </p>
      <p className="text-xs text-muted-foreground/60 mb-8 text-center max-w-md">
        A state-aware financial reasoning system built on compiled market intelligence.
        Ask about conviction, regime, structure, or anything MarketMate.
      </p>

      {/* Active model badge */}
      <div
        className={cn(
          'inline-flex items-center gap-2 rounded-full border px-4 py-1.5 mb-8',
          modelInfo.bgClass,
          modelInfo.borderClass
        )}
      >
        <span className="text-sm">{modelInfo.emoji}</span>
        <span className={cn('text-xs font-medium', modelInfo.colorClass)}>
          {modelInfo.name}
        </span>
        <span className="text-[10px] text-muted-foreground">· {modelInfo.role}</span>
      </div>

      {/* Model quick select */}
      <div className="flex items-center gap-2 mb-8">
        {MODEL_LIST.map((m) => {
          const info = MATE_MODELS[m];
          const isActive = m === model;
          return (
            <div
              key={m}
              className={cn(
                'flex items-center gap-1 rounded-full px-2.5 py-1 border transition-all',
                isActive
                  ? cn(info.bgClass, info.borderClass)
                  : 'border-border bg-card'
              )}
            >
              <span className="text-xs">{info.emoji}</span>
              <span
                className={cn(
                  'text-[10px] font-medium',
                  isActive ? info.colorClass : 'text-muted-foreground'
                )}
              >
                {info.name}
              </span>
            </div>
          );
        })}
      </div>

      {/* Suggestion Cards */}
      <div className="w-full max-w-lg">
        <p className="text-[10px] uppercase tracking-wider text-muted-foreground/50 mb-3 text-center">
          Try asking
        </p>
        <div className="grid grid-cols-2 gap-2">
          {SUGGESTION_CARDS.map((card: SuggestionCard) => (
            <button
              key={card.label}
              onClick={() => onPromptClick(card.prompt)}
              className={cn(
                'flex items-center gap-2.5 rounded-xl border px-3.5 py-3 text-left transition-all cursor-pointer',
                'hover:scale-[1.02] hover:-translate-y-0.5 active:scale-[0.98]',
                card.bgClass,
                card.borderClass,
                'hover:shadow-[0_0_20px_-4px_rgba(16,185,129,0.12)]'
              )}
            >
              <span className="text-base shrink-0">{card.icon}</span>
              <div className="min-w-0">
                <span className="text-xs font-medium text-foreground/80 block">
                  {card.label}
                </span>
                <span className="text-[10px] text-muted-foreground line-clamp-1">
                  {card.prompt}
                </span>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
