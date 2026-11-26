import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import {
  WebSocketTransactionEvent,
  WebSocketTransactionPayload,
  SimulationStatusResponse,
} from '../types/api';
import { api } from '../services/apiClient';
import { useWebSocket, ConnectionStatus } from '../hooks/useWebSocket';

interface RealtimeContextValue {
  wsStatus: ConnectionStatus;
  lastEvent: WebSocketTransactionEvent | null;
  liveTransactions: WebSocketTransactionPayload[];
  isSimulating: boolean;
  simStatus: SimulationStatusResponse | null;
  simLoading: boolean;
  startSimulation: (ratePerSecond?: number, scenario?: string) => Promise<void>;
  stopSimulation: () => Promise<void>;
  clearTransactions: () => void;
  reconnectWs: () => void;
}

const RealtimeContext = createContext<RealtimeContextValue | null>(null);

const MAX_BUFFER_SIZE = 50;

export const RealtimeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [liveTransactions, setLiveTransactions] = useState<WebSocketTransactionPayload[]>([]);
  const [isSimulating, setIsSimulating] = useState<boolean>(false);
  const [simStatus, setSimStatus] = useState<SimulationStatusResponse | null>(null);
  const [simLoading, setSimLoading] = useState<boolean>(false);

  // Incoming transaction handler from WebSocket
  const handleTransaction = useCallback((event: WebSocketTransactionEvent) => {
    if (event.type === 'TRANSACTION_PROCESSED' && event.data) {
      const data = event.data as WebSocketTransactionPayload;
      setLiveTransactions((prev) => [data, ...prev.slice(0, MAX_BUFFER_SIZE - 1)]);
    }
  }, []);

  const { status: wsStatus, lastEvent, reconnect: reconnectWs } = useWebSocket({
    onTransaction: handleTransaction,
    enabled: true,
  });

  // Fetch simulation streamer status on mount and sync
  const checkSimStatus = useCallback(async () => {
    try {
      const res = await api.getSimulationStatus();
      setSimStatus(res);
      setIsSimulating(res.is_running);
    } catch {
      // Backend may be starting or offline
    }
  }, []);

  useEffect(() => {
    checkSimStatus();
    const interval = setInterval(checkSimStatus, 4000);
    return () => clearInterval(interval);
  }, [checkSimStatus]);

  const startSimulation = useCallback(
    async (ratePerSecond: number = 1.0, scenario: string = 'MIXED') => {
      setSimLoading(true);
      try {
        const res = await api.startSimulationStream({
          rate_per_second: ratePerSecond,
          scenario,
        });
        setSimStatus(res);
        setIsSimulating(res.is_running);
      } catch (err) {
        console.error('Failed to start simulation stream:', err);
      } finally {
        setSimLoading(false);
      }
    },
    []
  );

  const stopSimulation = useCallback(async () => {
    setSimLoading(true);
    try {
      const res = await api.stopSimulationStream();
      setSimStatus(res);
      setIsSimulating(res.is_running);
    } catch (err) {
      console.error('Failed to stop simulation stream:', err);
    } finally {
      setSimLoading(false);
    }
  }, []);

  const clearTransactions = useCallback(() => {
    setLiveTransactions([]);
  }, []);

  return (
    <RealtimeContext.Provider
      value={{
        wsStatus,
        lastEvent,
        liveTransactions,
        isSimulating,
        simStatus,
        simLoading,
        startSimulation,
        stopSimulation,
        clearTransactions,
        reconnectWs,
      }}
    >
      {children}
    </RealtimeContext.Provider>
  );
};

export const useRealtime = (): RealtimeContextValue => {
  const ctx = useContext(RealtimeContext);
  if (!ctx) {
    throw new Error('useRealtime must be used within a RealtimeProvider');
  }
  return ctx;
};
