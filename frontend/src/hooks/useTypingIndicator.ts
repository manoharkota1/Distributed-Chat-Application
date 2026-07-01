/**
 * Typing indicator hook.
 *
 * Sends debounced typing events over WebSocket.
 * Automatically stops after 3 seconds of inactivity.
 */

'use client';

import { useCallback, useRef } from 'react';
import { wsClient } from '@/lib/ws/socket';

export function useTypingIndicator(conversationId: string) {
  const typingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isTypingRef = useRef(false);

  /** Call this on every keystroke in the message input. */
  const handleTyping = useCallback(() => {
    if (!isTypingRef.current) {
      isTypingRef.current = true;
      wsClient.send('typing.start', { conversation_id: conversationId });
    }

    // Reset the stop timer
    if (typingTimerRef.current) {
      clearTimeout(typingTimerRef.current);
    }

    // Auto-stop after 3 seconds of no typing
    typingTimerRef.current = setTimeout(() => {
      isTypingRef.current = false;
      wsClient.send('typing.stop', { conversation_id: conversationId });
    }, 3000);
  }, [conversationId]);

  /** Explicitly stop typing (e.g., on message send). */
  const stopTyping = useCallback(() => {
    if (typingTimerRef.current) {
      clearTimeout(typingTimerRef.current);
    }
    if (isTypingRef.current) {
      isTypingRef.current = false;
      wsClient.send('typing.stop', { conversation_id: conversationId });
    }
  }, [conversationId]);

  return { handleTyping, stopTyping };
}
