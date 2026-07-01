/**
 * Cursor-based infinite scroll hook for message history.
 *
 * Fetches messages in pages using opaque cursors and supports
 * loading more messages when the user scrolls to the top.
 */

'use client';

import { useCallback, useRef, useState } from 'react';
import { api } from '@/lib/api/client';
import { useAppStore, Message } from '@/lib/store';

interface MessagesResponse {
  messages: Message[];
  next_cursor: string | null;
  has_more: boolean;
}

export function useInfiniteMessages(conversationId: string) {
  const { messages, setMessages, prependMessages } = useAppStore();
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const cursorRef = useRef<string | null>(null);
  const isInitialLoad = useRef(true);

  const conversationMessages = messages[conversationId] || [];

  /** Load the initial page of messages. */
  const loadInitial = useCallback(async () => {
    if (loading) return;
    setLoading(true);
    isInitialLoad.current = true;
    cursorRef.current = null;

    const res = await api.get<MessagesResponse>(
      `/conversations/${conversationId}/messages?limit=50`
    );

    if (res.data) {
      // Messages come in DESC order — reverse for display
      setMessages(conversationId, [...res.data.messages].reverse());
      cursorRef.current = res.data.next_cursor;
      setHasMore(res.data.has_more);
    }

    setLoading(false);
    isInitialLoad.current = false;
  }, [conversationId, loading, setMessages]);

  /** Load more (older) messages using the cursor. */
  const loadMore = useCallback(async () => {
    if (loading || !hasMore || !cursorRef.current) return;
    setLoading(true);

    const res = await api.get<MessagesResponse>(
      `/conversations/${conversationId}/messages?cursor=${cursorRef.current}&limit=50`
    );

    if (res.data) {
      prependMessages(conversationId, [...res.data.messages].reverse());
      cursorRef.current = res.data.next_cursor;
      setHasMore(res.data.has_more);
    }

    setLoading(false);
  }, [conversationId, loading, hasMore, prependMessages]);

  return {
    messages: conversationMessages,
    loading,
    hasMore,
    loadInitial,
    loadMore,
  };
}
