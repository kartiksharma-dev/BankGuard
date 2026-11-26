import React, { useState } from 'react';
import {
  Activity,
  Pause,
  Play,
  Trash2,
  ShieldAlert,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Radio,
} from 'lucide-react';
import { WebSocketTransactionPayload } from '../../types/api';
import { Badge } from '../common/Badge';
import { formatCurrencyINR } from '../../utils/formatters';

interface LiveTransactionFeedProps {
  transactions: WebSocketTransactionPayload[];
  isWsConnected: boolean;
  onClear?: () => void;
}

export const LiveTransactionFeed: React.FC<LiveTransactionFeedProps> = ({
  transactions,
  isWsConnected,
  onClear,
}) => {
  const [isPaused, setIsPaused] = useState<boolean>(false);
  const [displayedTransactions, setDisplayedTransactions] = useState<WebSocketTransactionPayload[]>([]);

  // Update displayed transactions unless user paused the view
  React.useEffect(() => {
    if (!isPaused) {
      setDisplayedTransactions(transactions);
    }
  }, [transactions, isPaused]);

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-xl overflow-hidden shadow-lg backdrop-blur-sm">
      {/* Feed Header */}
      <div className="px-5 py-4 border-b border-slate-800 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <Radio className={`w-4 h-4 ${isWsConnected ? 'animate-pulse text-emerald-400' : 'text-slate-500'}`} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-semibold text-white">Live Transaction Stream</h2>
              {isWsConnected ? (
                <span className="flex items-center gap-1.5 text-[11px] font-medium text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded-full border border-emerald-800/60">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
                  Streaming Live
                </span>
              ) : (
                <span className="text-[11px] font-medium text-slate-400 bg-slate-800 px-2 py-0.5 rounded-full">
                  Connecting...
                </span>
              )}
              {isPaused && (
                <span className="text-[11px] font-medium text-amber-400 bg-amber-950/60 px-2 py-0.5 rounded-full border border-amber-800/60">
                  Feed Paused
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Real-time ingestion, continuous XGBoost inference, and automated fraud triage.
            </p>
          </div>
        </div>

        {/* Feed Actions */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setIsPaused(!isPaused)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
              isPaused
                ? 'bg-emerald-950/60 text-emerald-300 border-emerald-800 hover:bg-emerald-900/60'
                : 'bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-700'
            }`}
            title={isPaused ? 'Resume live feed updates' : 'Pause view to inspect incoming items'}
          >
            {isPaused ? <Play className="w-3.5 h-3.5" /> : <Pause className="w-3.5 h-3.5" />}
            <span>{isPaused ? 'Resume Feed' : 'Pause Feed'}</span>
          </button>

          {onClear && (
            <button
              type="button"
              onClick={onClear}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-700 transition-colors"
              title="Clear live feed buffer"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Feed Table / List */}
      <div className="overflow-x-auto max-h-[420px] overflow-y-auto divide-y divide-slate-800/60 scrollbar-thin scrollbar-thumb-slate-700">
        {displayedTransactions.length === 0 ? (
          <div className="p-8 text-center text-slate-400">
            <Activity className="w-8 h-8 text-slate-600 mx-auto mb-2 animate-pulse" />
            <p className="text-sm font-medium text-slate-300">Awaiting real-time transactions...</p>
            <p className="text-xs text-slate-500 mt-1">
              Start the simulation in the top bar to stream simulated transactions live.
            </p>
          </div>
        ) : (
          <table className="w-full text-left text-xs border-collapse">
            <thead className="bg-slate-950/60 text-slate-400 uppercase font-semibold text-[10px] tracking-wider sticky top-0 z-10 backdrop-blur-sm">
              <tr>
                <th className="py-2.5 px-4">Transaction ID</th>
                <th className="py-2.5 px-4">Customer</th>
                <th className="py-2.5 px-4">Amount</th>
                <th className="py-2.5 px-4">Category & Location</th>
                <th className="py-2.5 px-4">XGBoost ML</th>
                <th className="py-2.5 px-4">Risk Level</th>
                <th className="py-2.5 px-4">Auto-Alert</th>
                <th className="py-2.5 px-4 text-right">Time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50 text-slate-200">
              {displayedTransactions.map((item, index) => {
                const tx = item.transaction;
                const risk = item.risk_assessment;
                const alert = item.alert;
                const isFraud = tx.fraud_prediction === 1;
                const isHighRisk = risk?.risk_level === 'HIGH';

                return (
                  <tr
                    key={`${tx.transaction_id}-${index}`}
                    className={`transition-colors hover:bg-slate-800/40 ${
                      isFraud || isHighRisk
                        ? 'bg-rose-950/20'
                        : index === 0
                        ? 'bg-emerald-500/5'
                        : ''
                    }`}
                  >
                    <td className="py-2.5 px-4 font-mono font-medium text-white">
                      {tx.transaction_id}
                    </td>
                    <td className="py-2.5 px-4 text-slate-300 font-mono">
                      {tx.customer_id}
                    </td>
                    <td className="py-2.5 px-4 font-semibold text-white">
                      {formatCurrencyINR(tx.amount)}
                    </td>
                    <td className="py-2.5 px-4 text-slate-300">
                      <span className="font-medium text-slate-200">{tx.merchant_category}</span>
                      <span className="text-slate-500 mx-1.5">•</span>
                      <span className="text-slate-400">{tx.location}</span>
                    </td>
                    <td className="py-2.5 px-4">
                      {isFraud ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-rose-950/80 text-rose-300 border border-rose-800/70">
                          <AlertTriangle className="w-3 h-3 text-rose-400" />
                          FRAUD
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-950/60 text-emerald-300 border border-emerald-800/50">
                          <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                          LEGITIMATE
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 px-4">
                      <Badge
                        variant={
                          risk?.risk_level === 'HIGH'
                            ? 'danger'
                            : risk?.risk_level === 'MEDIUM'
                            ? 'warning'
                            : 'success'
                        }
                      >
                        {risk?.risk_level || (isFraud ? 'HIGH' : 'LOW')}
                      </Badge>
                    </td>
                    <td className="py-2.5 px-4">
                      {alert ? (
                        <span
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-950/70 text-amber-300 border border-amber-800/70 animate-pulse"
                          title={`Auto alert triggered: ${alert.alert_type}`}
                        >
                          <ShieldAlert className="w-3 h-3 text-amber-400" />
                          ALERT #{alert.alert_id}
                        </span>
                      ) : (
                        <span className="text-slate-500 text-[11px]">—</span>
                      )}
                    </td>
                    <td className="py-2.5 px-4 text-right text-slate-400 font-mono text-[11px]">
                      {tx.timestamp ? new Date(tx.timestamp).toLocaleTimeString() : 'Just now'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Feed Footer */}
      <div className="px-5 py-2.5 bg-slate-950/40 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
        <div className="flex items-center gap-2">
          <Clock className="w-3.5 h-3.5 text-slate-500" />
          <span>Showing latest {displayedTransactions.length} ingested transactions</span>
        </div>
        <span className="text-[11px] text-slate-500 font-mono">
          Sliding buffer capped at 50 records
        </span>
      </div>
    </div>
  );
};
