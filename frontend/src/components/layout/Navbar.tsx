import React, { useEffect, useState } from 'react';
import { ShieldCheck, Activity, RefreshCw, Menu, X, WifiOff } from 'lucide-react';
import { api } from '../../services/apiClient';

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
              <span className="text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded bg-emerald-950/80 text-emerald-400 border border-emerald-800/60">
                Phase 7
              </span>
            </div>
            <p className="text-[11px] text-slate-400 hidden sm:block">Fraud Detection & Risk Management</p>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {/* Backend Connectivity Status */}
        <div
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${
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
              <span className="hidden sm:inline">Backend API Live</span>
            </>
          ) : backendHealth === 'checking' ? (
            <>
              <Activity className="w-3.5 h-3.5 animate-spin" />
              <span className="hidden sm:inline">Connecting...</span>
            </>
          ) : (
            <>
              <WifiOff className="w-3.5 h-3.5 text-rose-400" />
              <span className="hidden sm:inline">Backend Offline</span>
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
