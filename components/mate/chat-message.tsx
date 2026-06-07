'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';
import { Copy, Check, Sparkles } from 'lucide-react';
import type { Message, MateModel } from './types';
import { MATE_MODELS } from './types';

// ─── Inline Markdown Renderer ────────────────────────────────────────────────────

function FormattedText({ text }: { text: string }) {
  const parts: React.ReactNode[] = [];
  let remaining = text;
  let key = 0;

  while (remaining.length > 0) {
    const boldMatch = remaining.match(/\*\*(.*?)\*\*/);
    const codeMatch = remaining.match(/`(.*?)`/);
    let firstMatch: {
      type: 'bold' | 'code';
      index: number;
      length: number;
      content: string;
    } | null = null;

    if (boldMatch && boldMatch.index !== undefined) {
      firstMatch = {
        type: 'bold',
        index: boldMatch.index,
        length: boldMatch[0].length,
        content: boldMatch[1],
      };
    }
    if (codeMatch && codeMatch.index !== undefined) {
      if (!firstMatch || codeMatch.index < firstMatch.index) {
        firstMatch = {
          type: 'code',
          index: codeMatch.index,
          length: codeMatch[0].length,
          content: codeMatch[1],
        };
      }
    }

    if (firstMatch) {
      if (firstMatch.index > 0) {
        parts.push(
          <span key={key++}>{remaining.slice(0, firstMatch.index)}</span>
        );
      }
      if (firstMatch.type === 'bold') {
        parts.push(
          <span key={key++} className="font-semibold text-foreground">
            {firstMatch.content}
          </span>
        );
      } else {
        parts.push(
          <code
            key={key++}
            className="rounded bg-primary/10 px-1.5 py-0.5 font-mono text-[11px] text-primary"
          >
            {firstMatch.content}
          </code>
        );
      }
      remaining = remaining.slice(firstMatch.index + firstMatch.length);
    } else {
      parts.push(<span key={key++}>{remaining}</span>);
      break;
    }
  }

  return <>{parts}</>;
}

function MateMessageContent({ content }: { content: string }) {
  const lines = content.split('\n');

  return (
    <div className="space-y-1.5">
      {lines.map((line, i) => {
        // Headers (## and ###)
        if (line.startsWith('## ')) {
          return (
            <h3 key={i} className="text-sm font-bold text-foreground mt-3 mb-1">
              <FormattedText text={line.replace(/^##\s+/, '')} />
            </h3>
          );
        }
        if (line.startsWith('### ')) {
          return (
            <h4 key={i} className="text-sm font-semibold text-foreground/90 mt-2 mb-1">
              <FormattedText text={line.replace(/^###\s+/, '')} />
            </h4>
          );
        }

        // Bullet points
        if (
          line.trimStart().startsWith('• ') ||
          line.trimStart().startsWith('- ') ||
          line.trimStart().startsWith('* ')
        ) {
          const bulletContent = line.trimStart().replace(/^[•\-*]\s+/, '');
          return (
            <div key={i} className="flex items-start gap-2 pl-2">
              <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-primary/60" />
              <span className="flex-1 text-sm">
                <FormattedText text={bulletContent} />
              </span>
            </div>
          );
        }

        // Numbered lists
        if (/^\d+\.\s/.test(line.trimStart())) {
          const numMatch = line.trimStart().match(/^(\d+\.)\s+(.*)/);
          if (numMatch) {
            return (
              <div key={i} className="flex items-start gap-2 pl-2">
                <span className="text-xs font-mono text-primary/60 mt-0.5 shrink-0">
                  {numMatch[1]}
                </span>
                <span className="flex-1 text-sm">
                  <FormattedText text={numMatch[2]} />
                </span>
              </div>
            );
          }
        }

        // Empty lines
        if (line.trim() === '') {
          return <div key={i} className="h-2" />;
        }

        // Regular lines
        return (
          <div key={i} className="text-sm">
            <FormattedText text={line} />
          </div>
        );
      })}
    </div>
  );
}

// ─── Message Bubble ──────────────────────────────────────────────────────────────

interface ChatMessageProps {
  message: Message;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';
  const [copied, setCopied] = useState(false);
  const modelInfo = message.model ? MATE_MODELS[message.model as MateModel] : null;

  const time =
    message.timestamp instanceof Date
      ? message.timestamp
      : new Date(message.timestamp);

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      className={`group flex ${isUser ? 'justify-end' : 'justify-start'} animate-in fade-in-0 slide-in-from-bottom-2 duration-300`}
    >
      <div
        className={`flex max-w-[85%] gap-2.5 sm:max-w-[75%] ${
          isUser ? 'flex-row-reverse' : 'flex-row'
        }`}
      >
        {/* Avatar */}
        {!isUser && (
          <div
            className={cn(
              'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border',
              modelInfo
                ? cn(modelInfo.bgClass, modelInfo.borderClass)
                : 'bg-primary/10 border-primary/20'
            )}
          >
            <span className="text-sm">{modelInfo?.emoji || '⚡'}</span>
          </div>
        )}

        {/* Message bubble */}
        <div
          className={cn(
            'relative rounded-2xl px-4 py-3',
            isUser
              ? 'bg-primary text-primary-foreground'
              : 'border border-border bg-card text-card-foreground'
          )}
        >
          {/* Model badge for assistant messages */}
          {!isUser && modelInfo && (
            <div className="flex items-center gap-1.5 mb-2">
              <span
                className={cn(
                  'inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] font-medium',
                  modelInfo.bgClass,
                  modelInfo.borderClass,
                  modelInfo.colorClass
                )}
              >
                <span className="text-[10px]">{modelInfo.emoji}</span>
                {modelInfo.name}
              </span>
            </div>
          )}

          {/* Content */}
          {!isUser ? (
            <MateMessageContent content={message.content} />
          ) : (
            <p className="whitespace-pre-wrap text-sm leading-relaxed">
              {message.content}
            </p>
          )}

          {/* Footer: time + copy */}
          <div
            className={`mt-2 flex items-center gap-2 ${
              isUser ? 'justify-end' : 'justify-between'
            }`}
          >
            <p className="text-[10px] text-muted-foreground/50">
              {time.toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit',
              })}
            </p>
            {!isUser && (
              <button
                onClick={handleCopy}
                className="flex items-center gap-1 text-[10px] text-muted-foreground/40 opacity-0 transition-opacity group-hover:opacity-100 hover:text-muted-foreground cursor-pointer"
              >
                {copied ? (
                  <>
                    <Check className="size-3 text-emerald-400" />
                    <span className="text-emerald-400">Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="size-3" />
                    Copy
                  </>
                )}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Typing Indicator ────────────────────────────────────────────────────────────

interface TypingIndicatorProps {
  model: MateModel;
}

export function TypingIndicator({ model }: TypingIndicatorProps) {
  const modelInfo = MATE_MODELS[model];

  return (
    <div className="flex justify-start animate-in fade-in-0 slide-in-from-bottom-2 duration-300">
      <div className="flex max-w-[75%] gap-2.5">
        <div
          className={cn(
            'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border',
            modelInfo.bgClass,
            modelInfo.borderClass
          )}
        >
          <span className="text-sm">{modelInfo.emoji}</span>
        </div>
        <div className="rounded-2xl border border-border bg-card px-4 py-3">
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1">
              <span
                className={cn(
                  'inline-block h-1.5 w-1.5 rounded-full animate-bounce',
                  modelInfo.colorClass
                )}
                style={{ animationDelay: '0ms', animationDuration: '1s' }}
              />
              <span
                className={cn(
                  'inline-block h-1.5 w-1.5 rounded-full animate-bounce',
                  modelInfo.colorClass
                )}
                style={{ animationDelay: '150ms', animationDuration: '1s' }}
              />
              <span
                className={cn(
                  'inline-block h-1.5 w-1.5 rounded-full animate-bounce',
                  modelInfo.colorClass
                )}
                style={{ animationDelay: '300ms', animationDuration: '1s' }}
              />
            </div>
            <span className="text-[10px] text-muted-foreground">
              {modelInfo.name} is thinking...
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
