/**
 * WebSocket client singleton with reconnect and exponential backoff.
 *
 * Manages a single persistent connection per client.
 * Uses an event emitter pattern for type-safe event handling.
 */

import { getAccessToken } from '@/lib/api/client';

export type WSEventType =
  | 'message.new'
  | 'message.ack'
  | 'typing.update'
  | 'presence.update'
  | 'read.receipt'
  | 'error'
  | 'pong';

export interface WSMessage {
  type: string;
  payload: Record<string, unknown>;
  request_id?: string;
}

type EventHandler = (payload: Record<string, unknown>) => void;

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';

class WebSocketClient {
  private ws: WebSocket | null = null;
  private handlers: Map<string, Set<EventHandler>> = new Map();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private requestIdCounter = 0;

  /** Connect to the WebSocket server with JWT auth. */
  connect(): void {
    const token = getAccessToken();
    if (!token) {
      console.warn('[WS] No access token — cannot connect');
      return;
    }

    if (this.ws?.readyState === WebSocket.OPEN) {
      return; // Already connected
    }

    try {
      this.ws = new WebSocket(`${WS_BASE}/ws?token=${token}`);

      this.ws.onopen = () => {
        console.log('[WS] Connected');
        this.reconnectAttempts = 0;
        this.startHeartbeat();
      };

      this.ws.onmessage = (event: MessageEvent) => {
        try {
          const msg: WSMessage = JSON.parse(event.data);
          this.emit(msg.type, msg.payload);
        } catch (e) {
          console.error('[WS] Failed to parse message:', e);
        }
      };

      this.ws.onclose = (event: CloseEvent) => {
        console.log('[WS] Disconnected:', event.code, event.reason);
        this.stopHeartbeat();

        // Don't reconnect on auth failure
        if (event.code === 4001) {
          console.error('[WS] Auth rejected — not reconnecting');
          return;
        }

        this.scheduleReconnect();
      };

      this.ws.onerror = (error: Event) => {
        console.error('[WS] Error:', error);
      };
    } catch (e) {
      console.error('[WS] Connection failed:', e);
      this.scheduleReconnect();
    }
  }

  /** Disconnect and stop reconnecting. */
  disconnect(): void {
    this.stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.reconnectAttempts = this.maxReconnectAttempts; // Prevent reconnect
    this.ws?.close();
    this.ws = null;
  }

  /** Send a message through the WebSocket. */
  send(type: string, payload: Record<string, unknown>): string {
    const requestId = `req_${++this.requestIdCounter}_${Date.now()}`;
    const message: WSMessage = { type, payload, request_id: requestId };

    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.warn('[WS] Not connected — message queued');
    }

    return requestId;
  }

  /** Register an event handler. */
  on(eventType: string, handler: EventHandler): () => void {
    if (!this.handlers.has(eventType)) {
      this.handlers.set(eventType, new Set());
    }
    this.handlers.get(eventType)!.add(handler);

    // Return unsubscribe function
    return () => {
      this.handlers.get(eventType)?.delete(handler);
    };
  }

  /** Remove all handlers for an event type. */
  off(eventType: string): void {
    this.handlers.delete(eventType);
  }

  /** Emit an event to all registered handlers. */
  private emit(eventType: string, payload: Record<string, unknown>): void {
    this.handlers.get(eventType)?.forEach((handler) => {
      try {
        handler(payload);
      } catch (e) {
        console.error(`[WS] Handler error for ${eventType}:`, e);
      }
    });
  }

  /** Exponential backoff reconnect. */
  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[WS] Max reconnect attempts reached');
      return;
    }

    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
    console.log(`[WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts + 1})`);

    this.reconnectTimer = setTimeout(() => {
      this.reconnectAttempts++;
      this.connect();
    }, delay);
  }

  /** Send periodic pings to keep the connection alive. */
  private startHeartbeat(): void {
    this.heartbeatTimer = setInterval(() => {
      this.send('ping', {});
    }, 25000); // Every 25 seconds (within the 30s presence TTL)
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }
}

// Singleton export
export const wsClient = new WebSocketClient();
