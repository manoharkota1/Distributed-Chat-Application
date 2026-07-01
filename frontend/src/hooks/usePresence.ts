/**
 * Presence hook for tracking online/offline users.
 *
 * Listens to WebSocket presence.update events.
 */

'use client';

import { useEffect } from 'react';
import { wsClient } from '@/lib/ws/socket';
import { useAppStore } from '@/lib/store';

export function usePresence() {
  const { onlineUsers, setUserOnline } = useAppStore();

  useEffect(() => {
    const unsub = wsClient.on('presence.update', (payload) => {
      const userId = payload.user_id as string;
      const status = payload.status as string;
      setUserOnline(userId, status === 'online');
    });

    return unsub;
  }, [setUserOnline]);

  return {
    isOnline: (userId: string) => onlineUsers.has(userId),
    onlineUsers,
  };
}
