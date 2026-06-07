'use client';

import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Menu,
  Plus,
  ChevronDown,
  Sparkles,
} from 'lucide-react';
import type { MateModel } from './types';
import { MATE_MODELS, MODEL_LIST } from './types';

interface ChatHeaderProps {
  model: MateModel;
  onModelChange: (model: MateModel) => void;
  onToggleSidebar: () => void;
  onNewChat: () => void;
  hasMessages: boolean;
}

export function ChatHeader({
  model,
  onModelChange,
  onToggleSidebar,
  onNewChat,
  hasMessages,
}: ChatHeaderProps) {
  const modelInfo = MATE_MODELS[model];

  return (
    <header className="flex items-center justify-between border-b border-border bg-background/80 backdrop-blur-md px-4 py-2.5">
      <div className="flex items-center gap-2">
        {/* Sidebar toggle */}
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={onToggleSidebar}
          className="text-muted-foreground hover:text-foreground cursor-pointer"
        >
          <Menu className="h-4 w-4" />
        </Button>

        {/* Model selector dropdown */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              className="gap-2 px-2.5 cursor-pointer hover:bg-accent/50"
            >
              <div
                className={cn(
                  'flex h-6 w-6 items-center justify-center rounded-md text-xs',
                  modelInfo.bgClass,
                  modelInfo.borderClass,
                  'border'
                )}
              >
                <span className="text-sm">{modelInfo.emoji}</span>
              </div>
              <span className="text-sm font-semibold text-foreground">
                {modelInfo.name}
              </span>
              <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-72">
            <DropdownMenuLabel className="text-xs text-muted-foreground">
              Select MATE Model
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            {MODEL_LIST.map((m) => {
              const info = MATE_MODELS[m];
              const isActive = m === model;
              return (
                <DropdownMenuItem
                  key={m}
                  onClick={() => onModelChange(m)}
                  className={cn(
                    'flex items-start gap-3 py-2.5 px-3 cursor-pointer',
                    isActive && 'bg-accent/50'
                  )}
                >
                  <div
                    className={cn(
                      'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border text-base',
                      info.bgClass,
                      info.borderClass
                    )}
                  >
                    {info.emoji}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-foreground">
                        {info.name}
                      </span>
                      <span className="text-[10px] font-mono text-muted-foreground">
                        {info.layer}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {info.role}
                    </p>
                  </div>
                  {isActive && (
                    <div className={cn('h-2 w-2 rounded-full mt-2', info.bgClass, 'ring-2', info.borderClass)} />
                  )}
                </DropdownMenuItem>
              );
            })}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <div className="flex items-center gap-1.5">
        {/* Active model indicator */}
        <div className="hidden sm:flex items-center gap-1.5 text-[10px] text-muted-foreground mr-2">
          <span className={cn('h-1.5 w-1.5 rounded-full animate-pulse', modelInfo.bgClass)} />
          <span>{modelInfo.role}</span>
        </div>

        {/* New chat */}
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={onNewChat}
          className="text-muted-foreground hover:text-foreground cursor-pointer"
          title="New chat"
        >
          <Plus className="h-4 w-4" />
        </Button>
      </div>
    </header>
  );
}
