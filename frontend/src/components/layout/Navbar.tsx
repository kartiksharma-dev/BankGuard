import React, { useEffect, useState } from 'react';
import {
  ShieldCheck,
  Activity,
  RefreshCw,
  Menu,
  X,
  WifiOff,
  Radio,
  Play,
  Pause,
  Loader2,
} from 'lucide-react';
import { api } from '../../services/apiClient';
import { useRealtime } from '../../context/RealtimeContext';

interface NavbarProps {
  onRefresh?: () => void;
  isRefreshing?: boolean;
  mobileMenuOpen: boolean;
  setMobileMenuOpen: (open: boolean) => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  onRefresh,
  isRefreshing = false,
  mobileMenuOpen,
  setMobileMenuOpen,
}) => {
  const [backendHealth, setBackendHealth] = useState<'checking' | 'healthy' | 'unhealthy'>('checking');
  const {
    wsStatus,
    isSimulating,
    simLoading,
    simStatus,
    startSimulation,
    stopSimulation,
  } = useRealtime();

  const checkHealth = async () => {
    try {
      const res = await api.getHealth();
      if (res.status === 'healthy') {
        setBackendHealth('healthy');
      } else {
        setBackendHealth('unhealthy');
      }
    } catch {
      setBackendHealth('unhealthy');
    }
  };

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleToggleSimulation = async () => {
    if (isSimulating) {
      await stopSimulation();
    } else {
      await startSimulation(1.0, 'MIXED');
    }
  };

  return (
    <header className="sticky top-0 z-30 flex items-center justify-between px-4 sm:px-6 h-16 bg-slate-900/90 border-b border-slate-800/80 backdrop-blur-md">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="p-2 -ml-2 text-slate-400 hover:text-slate-200 lg:hidden rounded-lg hover:bg-slate-800"
          aria-label={mobileMenuOpen ? 'Close navigation' : 'Open navigation'}
        >
          {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>

        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold tracking-tight text-white text-base">BANKGUARD</span>
              <span className="text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded bg-cyan-950/80 text-cyan-400 border border-cyan-800/60 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
                Phase 8 • Real-Time
              </span>
            </div>
            <p className="text-[11px] text-slate-400 hidden sm:block">AI Fraud Detection & Live Risk Stream</p>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2 sm:gap-3">
        {/* Simulation Stream Toggle Button */}
        <button
          type="button"
          onClick={handleToggleSimulation}
          disabled={simLoading}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
            isSimulating
              ? 'bg-rose-950/70 text-rose-300 border-rose-700/80 hover:bg-rose-900/70 shadow-sm shadow-rose-900/30'
              : 'bg-emerald-600 hover:bg-emerald-500 text-white border-emerald-500 shadow-sm shadow-emerald-900/30'
          } disabled:opacity-50`}
          title={
            isSimulating
              ? 'Pause the real-time background simulation generator'
              : 'Start streaming simulated banking transactions through the risk engine'
          }
        >
          {simLoading ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : isSimulating ? (
            <>
              <Pause className="w-3.5 h-3.5" />
              <span>Pause Stream</span>
              {simStatus?.total_generated !== undefined && simStatus.total_generated > 0 && (
                <span className="ml-1 px-1.5 py-0.2 rounded bg-rose-900/80 text-[10px] font-mono text-rose-200">
                  {simStatus.total_generated}
                </span>
              )}
            </>
          ) : (
            <>
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>Start Stream</span>
            </>
          )}
        </button>

        {/* WebSocket Real-time Connectivity Badge */}
        <div
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${
            wsStatus === 'connected'
              ? 'bg-cyan-950/50 text-cyan-300 border-cyan-800/60'
              : wsStatus === 'connecting' || wsStatus === 'reconnecting'
              ? 'bg-amber-950/50 text-amber-300 border-amber-800/60'
              : 'bg-slate-800/60 text-slate-400 border-slate-700/60'
          }`}
          title={
            wsStatus === 'connected'
              ? 'WebSocket Stream Active (/api/v1/ws/transactions)'
              : wsStatus === 'connecting' || wsStatus === 'reconnecting'
              ? 'WebSocket Reconnecting...'
              : 'WebSocket Disconnected'
          }
        >
          {wsStatus === 'connected' ? (
            <>
              <Radio className="w-3.5 h-3.5 text-cyan-400 animate-pulse" />
              <span className="hidden md:inline">WS Live</span>
            </>
          ) : wsStatus === 'connecting' || wsStatus === 'reconnecting' ? (
            <>
              <Activity className="w-3.5 h-3.5 text-amber-400 animate-spin" />
              <span className="hidden md:inline">Connecting</span>
            </>
          ) : (
            <>
              <WifiOff className="w-3.5 h-3.5 text-slate-500" />
              <span className="hidden md:inline">WS Offline</span>
            </>
          )}
        </div>

        {/* Backend Connectivity Status */}
        <div
          className={`hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${
            backendHealth === 'healthy'
              ? 'bg-emerald-950/50 text-emerald-300 border-emerald-800/60'
              : backendHealth === 'checking'
              ? 'bg-slate-800/60 text-slate-400 border-slate-700/60'
              : 'bg-rose-950/50 text-rose-300 border-rose-800/60'
          }`}
          title={
            backendHealth === 'healthy'
              ? 'FastAPI Backend Connected'
              : backendHealth === 'checking'
              ? 'Checking Backend Connectivity...'
              : 'Backend Unreachable'
          }
        >
          {backendHealth === 'healthy' ? (
            <>
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>API Live</span>
            </>
          ) : backendHealth === 'checking' ? (
            <>
              <Activity className="w-3.5 h-3.5 animate-spin" />
              <span>Checking...</span>
            </>
          ) : (
            <>
              <WifiOff className="w-3.5 h-3.5 text-rose-400" />
              <span>API Offline</span>
            </>
          )}
        </div>

        {/* Global Refresh Button */}
        {onRefresh && (
          <button
            type="button"
            onClick={onRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg transition-colors disabled:opacity-50"
            title="Refresh dashboard data"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-emerald-400' : ''}`} />
            <span className="hidden sm:inline">Refresh</span>
          </button>
        )}
      </div>
    </header>
  );
};
