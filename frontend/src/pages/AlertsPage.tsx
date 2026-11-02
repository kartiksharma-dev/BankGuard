import React, { useEffect, useState, useCallback } from 'react';
import {
  AlertOctagon,
  Search,
  Filter,
  FileSearch,
  Calendar,
  CheckCircle2,
  Clock,
} from 'lucide-react';
import { api } from '../services/apiClient';
import { AlertItem } from '../types/api';
import { Badge } from '../components/common/Badge';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorMessage } from '../components/common/ErrorMessage';
import { EmptyState } from '../components/common/EmptyState';

export const AlertsPage: React.FC = () => {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [transactionIdSearch, setTransactionIdSearch] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Investigation creation modal
  const [selectedAlert, setSelectedAlert] = useState<AlertItem | null>(null);
  const [assignedToInput, setAssignedToInput] = useState<string>('analyst_1');
  const [submittingInv, setSubmittingInv] = useState<boolean>(false);
  const [invFeedback, setInvFeedback] = useState<string | null>(null);

  const fetchAlerts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const statusParam = statusFilter !== 'all' ? statusFilter : undefined;
      const res = await api.getAlerts({
        status: statusParam,
        transaction_id: transactionIdSearch.trim() || undefined,
        limit: 50,
      });
      setAlerts(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve alerts.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, transactionIdSearch]);

  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  const handleStartInvestigation = async () => {
    if (!selectedAlert) return;
    setSubmittingInv(true);
    setInvFeedback(null);
    try {
      await api.createInvestigation({
        alert_id: selectedAlert.alert_id,
        assigned_to: assignedToInput.trim() || null,
      });
      setInvFeedback(`Investigation successfully initiated for Alert #${selectedAlert.alert_id}!`);
      setTimeout(() => {
        setSelectedAlert(null);
        setInvFeedback(null);
        fetchAlerts();
      }, 1500);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to start investigation.';
      setInvFeedback(`Error: ${msg}`);
    } finally {
      setSubmittingInv(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">Fraud Alerts</h1>
        <p className="text-sm text-slate-400 mt-1">
          Monitor system-generated fraud alerts and triage potential violations for investigation.
        </p>
      </div>

      {/* Filter / Search Bar */}
      <div className="p-4 bg-slate-900/70 border border-slate-800/80 rounded-xl space-y-4">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search by Transaction ID..."
              value={transactionIdSearch}
              onChange={(e) => setTransactionIdSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-slate-950/80 border border-slate-800 rounded-lg text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-500"
            />
          </div>

          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-slate-400" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 bg-slate-950/80 border border-slate-800 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-emerald-500"
            >
              <option value="all">All Statuses</option>
              <option value="OPEN">Open</option>
              <option value="RESOLVED">Resolved</option>
              <option value="DISMISSED">Dismissed</option>
            </select>
          </div>
        </div>
      </div>

      {/* Error message */}
      {error && (
        <ErrorMessage
          title="Alerts Fetch Failed"
          message={error}
          onRetry={fetchAlerts}
        />
      )}

      {/* Alerts Table */}
      <div className="bg-slate-900/70 border border-slate-800/80 rounded-xl overflow-hidden">
        {loading ? (
          <LoadingSpinner label="Fetching alerts..." />
        ) : alerts.length === 0 ? (
          <EmptyState
            icon={<AlertOctagon className="w-6 h-6 text-slate-500" />}
            title="No alerts found"
            description={
              statusFilter !== 'all' || transactionIdSearch
                ? 'Try adjusting your status or transaction search filters.'
                : 'No alerts have been recorded yet. Alerts are generated for high-risk transactions.'
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-950/70 text-slate-400 text-xs uppercase tracking-wider border-b border-slate-800">
                <tr>
                  <th scope="col" className="px-4 py-3 font-semibold">Alert ID</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Transaction ID</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Alert Type</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Status</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Created At</th>
                  <th scope="col" className="px-4 py-3 font-semibold text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-sans">
                {alerts.map((alert) => (
                  <tr key={alert.alert_id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="px-4 py-3 font-mono text-xs text-slate-200">
                      #{alert.alert_id}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-emerald-400">
                      {alert.transaction_id}
                    </td>
                    <td className="px-4 py-3 text-xs font-medium text-slate-200">
                      <span className="px-2 py-0.5 rounded bg-slate-800 border border-slate-700">
                        {alert.alert_type}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {alert.status.toUpperCase() === 'OPEN' ? (
                        <Badge variant="warning" size="sm">
                          <Clock className="w-3 h-3" />
                          OPEN
                        </Badge>
                      ) : alert.status.toUpperCase() === 'RESOLVED' ? (
                        <Badge variant="success" size="sm">
                          <CheckCircle2 className="w-3 h-3" />
                          RESOLVED
                        </Badge>
                      ) : (
                        <Badge variant="neutral" size="sm">
                          {alert.status}
                        </Badge>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-400 whitespace-nowrap">
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3 h-3 text-slate-500" />
                        {new Date(alert.created_at).toLocaleString()}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => setSelectedAlert(alert)}
                        type="button"
                        className="px-2.5 py-1 text-xs font-medium text-sky-300 bg-sky-950/40 hover:bg-sky-900/60 border border-sky-800/50 rounded-lg transition-colors inline-flex items-center gap-1"
                        title="Investigate this alert"
                      >
                        <FileSearch className="w-3 h-3" />
                        Investigate
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal: Open Investigation */}
      {selectedAlert && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-semibold text-white flex items-center gap-2">
                <FileSearch className="w-5 h-5 text-sky-400" />
                Initiate Investigation
              </h3>
              <button
                onClick={() => setSelectedAlert(null)}
                className="text-slate-400 hover:text-slate-200 text-sm"
              >
                ✕
              </button>
            </div>

            <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800 text-xs space-y-1.5">
              <p><strong className="text-slate-400">Alert ID:</strong> <span className="font-mono text-slate-200">#{selectedAlert.alert_id}</span></p>
              <p><strong className="text-slate-400">Transaction:</strong> <span className="font-mono text-emerald-400">{selectedAlert.transaction_id}</span></p>
              <p><strong className="text-slate-400">Alert Type:</strong> <span className="text-slate-200">{selectedAlert.alert_type}</span></p>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Assign Analyst
              </label>
              <input
                type="text"
                placeholder="e.g. analyst_1, compliance_desk"
                value={assignedToInput}
                onChange={(e) => setAssignedToInput(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-sky-500"
              />
            </div>

            {invFeedback && (
              <p className={`text-xs ${invFeedback.startsWith('Error') ? 'text-rose-400' : 'text-emerald-400'}`}>
                {invFeedback}
              </p>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setSelectedAlert(null)}
                className="px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleStartInvestigation}
                disabled={submittingInv}
                className="px-4 py-1.5 text-xs font-medium bg-sky-600 hover:bg-sky-500 text-white rounded-lg disabled:opacity-50"
              >
                {submittingInv ? 'Creating...' : 'Open Investigation'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
