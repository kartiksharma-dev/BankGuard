import { useEffect, useRef, useState, useCallback } from 'react';
import { WebSocketTransactionEvent } from '../types/api';
import { API_BASE_URL } from '../services/apiClient';

export type ConnectionStatus = 'connected' | 'connecting' | 'reconnecting' | 'disconnected';

interface UseWebSocketOptions {
  onTransaction?: (event: WebSocketTransactionEvent) => void;
  enabled?: boolean;
}

export function useWebSocket({ onTransaction, enabled = true }: UseWebSocketOptions = {}) {
  const [status, setStatus] = useState<ConnectionStatus>('connecting');
  const [lastEvent, setLastEvent] = useState<WebSocketTransactionEvent | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef<number>(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const onTransactionRef = useRef(onTransaction);

  // Keep callback reference updated without triggering reconnects
  useEffect(() => {
    onTransactionRef.current = onTransaction;
  }, [onTransaction]);

  const getWebSocketUrl = useCallback(() => {
    const endpoint = '/api/v1/ws/transactions';
    if (API_BASE_URL) {
      const wsBase = API_BASE_URL.replace(/^http/, 'ws');
      return `${wsBase}${endpoint}`;
    }
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}${endpoint}`;
  }, []);

  const connect = useCallback(() => {
    if (!enabled) return;

    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const url = getWebSocketUrl();
    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setStatus('connected');
        reconnectAttemptsRef.current = 0;

        // Start ping/pong heartbeat
        if (heartbeatTimerRef.current) clearInterval(heartbeatTimerRef.current);
        heartbeatTimerRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'PING' }));
          }
        }, 25000);
      };

      ws.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data) as WebSocketTransactionEvent;
          setLastEvent(parsed);

          if (parsed.type === 'TRANSACTION_PROCESSED' && onTransactionRef.current) {
            onTransactionRef.current(parsed);
          }
        } catch {
          // Ignore non-JSON messages
        }
      };

      ws.onclose = () => {
        if (heartbeatTimerRef.current) {
          clearInterval(heartbeatTimerRef.current);
          heartbeatTimerRef.current = null;
        }

        if (enabled) {
          setStatus('reconnecting');
          const backoff = Math.min(1000 * Math.pow(1.5, reconnectAttemptsRef.current), 10000);
          reconnectAttemptsRef.current += 1;

          if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
          reconnectTimerRef.current = setTimeout(() => {
            connect();
          }, backoff);
        } else {
          setStatus('disconnected');
        }
      };

      ws.onerror = () => {
        // Socket close event will handle reconnect
      };
    } catch {
      setStatus('reconnecting');
    }
  }, [enabled, getWebSocketUrl]);

  useEffect(() => {
    if (enabled) {
      connect();
    } else {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      setStatus('disconnected');
    }

    return () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (heartbeatTimerRef.current) clearInterval(heartbeatTimerRef.current);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [enabled, connect]);

  const send = useCallback((data: unknown) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(typeof data === 'string' ? data : JSON.stringify(data));
    }
  }, []);

  const manualReconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
    }
    reconnectAttemptsRef.current = 0;
    connect();
  }, [connect]);

  return {
    status,
    lastEvent,
    send,
    reconnect: manualReconnect,
  };
}
