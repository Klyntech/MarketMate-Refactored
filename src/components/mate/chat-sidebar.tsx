'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Plus,
  X,
  MessageSquare,
  Sparkles,
  ChevronLeft,
} from 'lucide-react';
import type { Chat, MateModel } from './types';
import { MATE_MODELS } from './types';

interface ChatSidebarProps {
  open: boolean;
  onClose: () => void;
  chats: Chat[];
  activeChatId: string | null;
  onSelectChat: (id: string) => void;
  onNewChat: () => void;
  onDeleteChat: (id: string) => void;
}

function groupChatsByDate(chats: Chat[]) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86400000);
  const lastWeek = new Date(today.getTime() - 7 * 86400000);

  const groups: { label: string; chats: Chat[] }[] = [
    { label: 'Today', chats: [] },
    { label: 'Yesterday', chats: [] },
    { label: 'Previous 7 Days', chats: [] },
    { label: 'Older', chats: [] },
  ];

  chats.forEach((chat) => {
    const chatDate = new Date(chat.updatedAt);
    if (chatDate >= today) {
      groups[0].chats.push(chat);
    } else if (chatDate >= yesterday) {
      groups[1].chats.push(chat);
    } else if (chatDate >= lastWeek) {
      groups[2].chats.push(chat);
    } else {
      groups[3].chats.push(chat);
    }
  });

  return groups.filter((g) => g.chats.length > 0);
}

export function ChatSidebar({
  open,
  onClose,
  chats,
  activeChatId,
  onSelectChat,
  onNewChat,
  onDeleteChat,
}: ChatSidebarProps) {
  const [hoveredChatId, setHoveredChatId] = useState<string | null>(null);
  const groups = groupChatsByDate(chats);

  return (
    <>
      {/* Mobile overlay */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/60 md:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r border-sidebar-border bg-sidebar transition-transform duration-300 md:relative md:z-auto',
          open ? 'translate-x-0' : '-translate-x-full md:-translate-x-full md:hidden'
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-sidebar-border px-4 py-3">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 ring-1 ring-primary/20">
              <Sparkles className="h-4 w-4 text-primary" />
            </div>
            <div>
              <h1 className="text-sm font-bold text-sidebar-foreground">MATE</h1>
              <p className="text-[10px] text-sidebar-foreground/50">Market Reasoning Engine</p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onClose}
            className="text-sidebar-foreground/50 hover:text-sidebar-foreground hover:bg-sidebar-accent cursor-pointer"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
        </div>

        {/* New Chat Button */}
        <div className="px-3 py-3">
          <Button
            onClick={onNewChat}
            className="w-full justify-start gap-2 bg-sidebar-accent/50 text-sidebar-foreground hover:bg-sidebar-accent cursor-pointer border border-sidebar-border"
            variant="outline"
          >
            <Plus className="h-4 w-4" />
            New Chat
          </Button>
        </div>

        {/* Chat List */}
        <ScrollArea className="flex-1 px-3">
          {groups.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <MessageSquare className="h-8 w-8 text-sidebar-foreground/20 mb-3" />
              <p className="text-xs text-sidebar-foreground/40">No conversations yet</p>
              <p className="text-[10px] text-sidebar-foreground/30 mt-1">Start a new chat to begin</p>
            </div>
          ) : (
            <div className="space-y-4 pb-4">
              {groups.map((group) => (
                <div key={group.label}>
                  <p className="px-2 py-1 text-[10px] font-medium uppercase tracking-wider text-sidebar-foreground/40">
                    {group.label}
                  </p>
                  <div className="space-y-0.5">
                    {group.chats.map((chat) => {
                      const modelInfo = MATE_MODELS[chat.model as MateModel];
                      const isActive = chat.id === activeChatId;
                      const isHovered = chat.id === hoveredChatId;

                      return (
                        <div
                          key={chat.id}
                          onClick={() => onSelectChat(chat.id)}
                          onMouseEnter={() => setHoveredChatId(chat.id)}
                          onMouseLeave={() => setHoveredChatId(null)}
                          className={cn(
                            'group flex items-center gap-2 rounded-lg px-2.5 py-2 cursor-pointer transition-colors',
                            isActive
                              ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                              : 'text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground'
                          )}
                        >
                          <span className="text-xs shrink-0">{modelInfo?.emoji || '⚡'}</span>
                          <span className="flex-1 truncate text-xs">{chat.title}</span>
                          {(isHovered || isActive) && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                onDeleteChat(chat.id);
                              }}
                              className="shrink-0 rounded p-0.5 text-sidebar-foreground/30 hover:text-destructive transition-colors cursor-pointer"
                            >
                              <X className="h-3 w-3" />
                            </button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </ScrollArea>

        {/* Footer */}
        <div className="border-t border-sidebar-border px-4 py-3">
          <p className="text-[10px] text-sidebar-foreground/30 text-center">
            4 Models · 5 Brains · 8 Gates
          </p>
        </div>
      </aside>
    </>
  );
}
