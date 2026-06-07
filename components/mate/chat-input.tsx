'use client';

import { useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Send, Loader2, Paperclip } from 'lucide-react';
import type { MateModel } from './types';
import { MATE_MODELS, SUGGESTION_CARDS } from './types';

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  disabled: boolean;
  model: MateModel;
  hasMessages: boolean;
  onSuggestionClick: (prompt: string) => void;
}

export function ChatInput({
  value,
  onChange,
  onSend,
  disabled,
  model,
  hasMessages,
  onSuggestionClick,
}: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const modelInfo = MATE_MODELS[model];

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    onChange(e.target.value);
    const el = e.target;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  };

  // Reset height when value is cleared
  useEffect(() => {
    if (value === '' && textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [value]);

  return (
    <div className="border-t border-border bg-background/80 backdrop-blur-md p-3 sm:px-4">
      <div className="mx-auto max-w-3xl">
        {/* Input bar */}
        <div
          className={cn(
            'relative flex items-end gap-2 rounded-xl border bg-card px-3 py-2 transition-all',
            'focus-within:ring-1',
            value
              ? cn('border-' + modelInfo.colorClass.replace('text-', ''), modelInfo.borderClass, 'focus-within:ring-' + modelInfo.colorClass.replace('text-', '') + '/30')
              : 'border-border focus-within:border-primary/30 focus-within:ring-primary/10'
          )}
        >
          {/* Attachment button placeholder */}
          <Button
            variant="ghost"
            size="icon-sm"
            className="shrink-0 text-muted-foreground/50 hover:text-muted-foreground cursor-pointer"
            disabled={disabled}
            title="Attach file"
          >
            <Paperclip className="h-4 w-4" />
          </Button>

          {/* Textarea */}
          <textarea
            ref={textareaRef}
            value={value}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder={`Ask ${modelInfo.name} anything...`}
            disabled={disabled}
            rows={1}
            className="min-h-[36px] max-h-[160px] flex-1 resize-none border-0 bg-transparent p-0 text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none disabled:opacity-50"
          />

          {/* Send button */}
          <Button
            onClick={onSend}
            disabled={disabled || !value.trim()}
            size="icon-sm"
            className={cn(
              'shrink-0 cursor-pointer text-white disabled:opacity-30 rounded-lg',
              disabled ? 'bg-muted' : 'bg-primary hover:bg-primary/90'
            )}
          >
            {disabled ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-3.5 w-3.5" />
            )}
          </Button>
        </div>

        {/* Quick prompt pills when in conversation */}
        {hasMessages && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {SUGGESTION_CARDS.slice(0, 3).map((card) => (
              <button
                key={card.label}
                onClick={() => onSuggestionClick(card.prompt)}
                className="inline-flex items-center gap-1 rounded-full bg-card border border-border px-2.5 py-1 text-[10px] text-muted-foreground transition-colors hover:text-primary hover:border-primary/20 cursor-pointer"
              >
                <span className="text-[10px]">{card.icon}</span>
                {card.label}
              </button>
            ))}
          </div>
        )}

        <p className="mt-2 text-center text-[10px] text-muted-foreground/40">
          MATE provides market intelligence interpretations. Not financial advice.
        </p>
      </div>
    </div>
  );
}
