/**
 * Zustand store for global application state.
 *
 * Manages auth, conversations, messages, and presence state.
 */

import { create } from 'zustand';

export interface User {
  id: string;
  email: string;
  display_name: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  sender_id: string;
  sender_display_name?: string;
  content: string;
  created_at: string;
  // Optimistic UI fields
  client_temp_id?: string;
  pending?: boolean;
}

export interface ConversationMember {
  user_id: string;
  display_name: string;
  is_online: boolean;
}

export interface Conversation {
  id: string;
  type: 'direct' | 'group';
  name: string | null;
  created_at: string;
  members: ConversationMember[];
  last_message: {
    id: string;
    content: string;
    sender_id: string;
    created_at: string;
  } | null;
  unread_count: number;
}

interface AppState {
  // Auth
  user: User | null;
  isAuthenticated: boolean;
  setUser: (user: User | null) => void;

  // Conversations
  conversations: Conversation[];
  activeConversationId: string | null;
  setConversations: (convos: Conversation[]) => void;
  setActiveConversation: (id: string | null) => void;
  updateConversation: (id: string, updates: Partial<Conversation>) => void;

  // Messages
  messages: Record<string, Message[]>;
  addMessage: (conversationId: string, message: Message) => void;
  setMessages: (conversationId: string, messages: Message[]) => void;
  prependMessages: (conversationId: string, messages: Message[]) => void;
  reconcileMessage: (conversationId: string, tempId: string, message: Message) => void;

  // Typing
  typingUsers: Record<string, string[]>; // conversationId → list of userIds typing
  setTypingUser: (conversationId: string, userId: string, isTyping: boolean) => void;

  // Presence
  onlineUsers: Set<string>;
  setUserOnline: (userId: string, online: boolean) => void;
}

export const useAppStore = create<AppState>((set, get) => ({
  // ── Auth ────────────────────────────────────────────────────
  user: null,
  isAuthenticated: false,
  setUser: (user) => set({ user, isAuthenticated: !!user }),

  // ── Conversations ──────────────────────────────────────────
  conversations: [],
  activeConversationId: null,
  setConversations: (conversations) => set({ conversations }),
  setActiveConversation: (id) => set({ activeConversationId: id }),
  updateConversation: (id, updates) =>
    set((state) => ({
      conversations: state.conversations.map((c) =>
        c.id === id ? { ...c, ...updates } : c
      ),
    })),

  // ── Messages ───────────────────────────────────────────────
  messages: {},
  addMessage: (conversationId, message) =>
    set((state) => ({
      messages: {
        ...state.messages,
        [conversationId]: [
          ...(state.messages[conversationId] || []),
          message,
        ],
      },
    })),
  setMessages: (conversationId, messages) =>
    set((state) => ({
      messages: { ...state.messages, [conversationId]: messages },
    })),
  prependMessages: (conversationId, messages) =>
    set((state) => ({
      messages: {
        ...state.messages,
        [conversationId]: [
          ...messages,
          ...(state.messages[conversationId] || []),
        ],
      },
    })),
  reconcileMessage: (conversationId, tempId, message) =>
    set((state) => ({
      messages: {
        ...state.messages,
        [conversationId]: (state.messages[conversationId] || []).map((m) =>
          m.client_temp_id === tempId
            ? { ...message, pending: false }
            : m
        ),
      },
    })),

  // ── Typing ─────────────────────────────────────────────────
  typingUsers: {},
  setTypingUser: (conversationId, userId, isTyping) =>
    set((state) => {
      const current = state.typingUsers[conversationId] || [];
      const updated = isTyping
        ? Array.from(new Set([...current, userId]))
        : current.filter((id) => id !== userId);
      return {
        typingUsers: { ...state.typingUsers, [conversationId]: updated },
      };
    }),

  // ── Presence ───────────────────────────────────────────────
  onlineUsers: new Set(),
  setUserOnline: (userId, online) =>
    set((state) => {
      const next = new Set(state.onlineUsers);
      if (online) next.add(userId);
      else next.delete(userId);
      return { onlineUsers: next };
    }),
}));
