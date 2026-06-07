'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { ScrollArea } from '@/components/ui/scroll-area';
import { ChatSidebar } from '@/components/mate/chat-sidebar';
import { ChatHeader } from '@/components/mate/chat-header';
import { WelcomeScreen } from '@/components/mate/welcome-screen';
import { ChatMessage, TypingIndicator } from '@/components/mate/chat-message';
import { ChatInput } from '@/components/mate/chat-input';
import type { Chat, Message, MateModel } from '@/components/mate/types';
import { MATE_MODELS } from '@/components/mate/types';

// ─── Helpers ──────────────────────────────────────────────────────────────────────

function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

function generateTitle(message: string): string {
  const trimmed = message.trim();
  if (trimmed.length <= 40) return trimmed;
  return trimmed.slice(0, 40).trim() + '…';
}

// ─── Main Page ────────────────────────────────────────────────────────────────────

export default function MatePage() {
  // ── State ─────────────────────────────────────────────────────────────────────
  const [chats, setChats] = useState<Chat[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [model, setModel] = useState<MateModel>('nova');
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // ── Derived ───────────────────────────────────────────────────────────────────
  const activeChat = chats.find((c) => c.id === activeChatId) || null;
  const messages = activeChat?.messages || [];
  const hasMessages = messages.length > 0;

  // ── Auto-scroll ───────────────────────────────────────────────────────────────
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, sending]);

  // ── Chat management ───────────────────────────────────────────────────────────
  const createNewChat = useCallback(() => {
    const newChat: Chat = {
      id: generateId(),
      title: 'New Chat',
      model,
      messages: [],
      createdAt: new Date(),
      updatedAt: new Date(),
    };
    setChats((prev) => [newChat, ...prev]);
    setActiveChatId(newChat.id);
    setInput('');
    return newChat.id;
  }, [model]);

  const handleNewChat = useCallback(() => {
    createNewChat();
    setSidebarOpen(false);
  }, [createNewChat]);

  const handleSelectChat = useCallback((id: string) => {
    setActiveChatId(id);
    setSidebarOpen(false);
    const chat = chats.find((c) => c.id === id);
    if (chat) {
      setModel(chat.model);
    }
  }, [chats]);

  const handleDeleteChat = useCallback((id: string) => {
    setChats((prev) => prev.filter((c) => c.id !== id));
    if (activeChatId === id) {
      setActiveChatId(null);
    }
  }, [activeChatId]);

  const addMessageToChat = useCallback((chatId: string, message: Message) => {
    setChats((prev) =>
      prev.map((c) => {
        if (c.id !== chatId) return c;
        const isFirstUserMessage =
          message.role === 'user' && c.messages.length === 0;
        return {
          ...c,
          messages: [...c.messages, message],
          title: isFirstUserMessage ? generateTitle(message.content) : c.title,
          updatedAt: new Date(),
        };
      })
    );
  }, []);

  // ── Send message ──────────────────────────────────────────────────────────────
  const handleSend = useCallback(
    async (messageText?: string) => {
      const trimmed = (messageText || input).trim();
      if (!trimmed || sending) return;

      // Create a chat if none is active
      let chatId = activeChatId;
      if (!chatId) {
        const newChat: Chat = {
          id: generateId(),
          title: generateTitle(trimmed),
          model,
          messages: [],
          createdAt: new Date(),
          updatedAt: new Date(),
        };
        setChats((prev) => [newChat, ...prev]);
        setActiveChatId(newChat.id);
        chatId = newChat.id;
      }

      // Add user message
      const userMessage: Message = {
        id: generateId(),
        role: 'user',
        content: trimmed,
        timestamp: new Date(),
      };
      addMessageToChat(chatId, userMessage);
      setInput('');
      setSending(true);

      try {
        const res = await fetch('/api/mate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: trimmed, model }),
        });

        const data = await res.json();

        const assistantMessage: Message = {
          id: generateId(),
          role: 'assistant',
          content: data.response || data.error || 'No response received.',
          model: data.model || model,
          timestamp: new Date(data.timestamp || new Date()),
        };
        addMessageToChat(chatId, assistantMessage);
      } catch {
        const errorMessage: Message = {
          id: generateId(),
          role: 'assistant',
          content: 'Network error. Please check your connection and try again.',
          model,
          timestamp: new Date(),
        };
        addMessageToChat(chatId, errorMessage);
      } finally {
        setSending(false);
      }
    },
    [activeChatId, input, sending, model, addMessageToChat]
  );

  const handleSuggestionClick = useCallback(
    (prompt: string) => {
      handleSend(prompt);
    },
    [handleSend]
  );

  // ── Render ────────────────────────────────────────────────────────────────────
  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Sidebar */}
      <ChatSidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        chats={chats}
        activeChatId={activeChatId}
        onSelectChat={handleSelectChat}
        onNewChat={handleNewChat}
        onDeleteChat={handleDeleteChat}
      />

      {/* Main content */}
      <div className="flex flex-1 flex-col min-w-0">
        {/* Header */}
        <ChatHeader
          model={model}
          onModelChange={setModel}
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
          onNewChat={handleNewChat}
          hasMessages={hasMessages}
        />

        {/* Messages area */}
        <div className="flex-1 overflow-y-auto">
          {!hasMessages ? (
            <WelcomeScreen model={model} onPromptClick={handleSuggestionClick} />
          ) : (
            <div className="p-4 sm:p-6">
              <div className="mx-auto max-w-3xl space-y-4">
                {messages.map((message) => (
                  <ChatMessage key={message.id} message={message} />
                ))}
                {sending && <TypingIndicator model={model} />}
                <div ref={messagesEndRef} />
              </div>
            </div>
          )}
        </div>

        {/* Input */}
        <ChatInput
          value={input}
          onChange={setInput}
          onSend={handleSend}
          disabled={sending}
          model={model}
          hasMessages={hasMessages}
          onSuggestionClick={handleSuggestionClick}
        />
      </div>
    </div>
  );
}
